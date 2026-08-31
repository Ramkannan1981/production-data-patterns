"""
Secure Code Execution Sandbox (Python/SQL interpreter isolation)
====================================================================

JD requirement: "Practical knowledge of configuring and deploying secure
code execution harnesses and interpreter sandboxes (e.g., Python/SQL
execution environments) for automated data analysis."

THE PROBLEM: when an LLM generates Python or SQL code to analyze data
(e.g., "write a pandas script to compute average transaction value"),
you cannot just exec() that code directly in your main application.
Generated code could be wrong, inefficient, or actively harmful:
  - It might try to read/write arbitrary files
  - It might try to make network calls (exfiltrate data)
  - It might run forever (infinite loop) or consume all memory
  - It might import dangerous modules (os, subprocess, socket)

THE SOLUTION (defense in depth - multiple independent layers):
  1. Restrict available builtins/modules (deny-by-default allowlist)
  2. Enforce a hard execution timeout
  3. Run in a subprocess (isolates memory space, and a crash/hang in
     the subprocess doesn't take down the parent process)
  4. Capture stdout/stderr instead of letting code print freely
  5. (In production: also use OS-level isolation - containers, gVisor,
     or Firecracker microVMs. This script demonstrates the
     application-level layer, which sits IN ADDITION to OS-level
     isolation, not instead of it - worth saying explicitly in an
     interview so you don't imply this is sufficient on its own.)

This script demonstrates layers 1-4, which are the parts you can
reasonably write and explain in a 60-minute coding round.
"""

import ast
import multiprocessing
import queue

# ---------------------------------------------------------------------------
# Layer 1: Static analysis - reject dangerous code BEFORE execution
# ---------------------------------------------------------------------------

DISALLOWED_MODULES = {"os", "sys", "subprocess", "socket", "shutil", "importlib"}
DISALLOWED_BUILTINS = {"eval", "exec", "compile", "__import__", "open"}


class UnsafeCodeError(Exception):
    pass


def static_safety_check(code: str) -> None:
    """Parse the code into an AST and reject anything touching a
    disallowed module or builtin, WITHOUT executing it. Catching this
    at parse-time (not runtime) is important - it means unsafe code
    never even reaches the interpreter."""
    tree = ast.parse(code)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module]
            )
            for name in module_names:
                if name and name.split(".")[0] in DISALLOWED_MODULES:
                    raise UnsafeCodeError(f"Import of disallowed module: {name}")

        if isinstance(node, ast.Name) and node.id in DISALLOWED_BUILTINS:
            raise UnsafeCodeError(f"Use of disallowed builtin: {node.id}")

        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise UnsafeCodeError(f"Access to dunder attribute: {node.attr}")


# ---------------------------------------------------------------------------
# Layer 2 + 3: Restricted execution in an isolated subprocess with a
# hard timeout
# ---------------------------------------------------------------------------

SAFE_BUILTINS = {
    "len": len, "range": range, "sum": sum, "min": min, "max": max,
    "print": print, "abs": abs, "round": round, "sorted": sorted,
    "enumerate": enumerate, "zip": zip, "str": str, "int": int,
    "float": float, "list": list, "dict": dict, "set": set, "bool": bool,
}


def _run_in_subprocess(code: str, result_queue: multiprocessing.Queue) -> None:
    """Runs in a separate process. Even if this hangs or crashes,
    the parent process is unaffected."""
    import io
    import contextlib

    output_buffer = io.StringIO()
    restricted_globals = {"__builtins__": SAFE_BUILTINS}

    try:
        with contextlib.redirect_stdout(output_buffer):
            exec(code, restricted_globals)  # noqa: S102 - this IS the sandbox
        result_queue.put({"success": True, "output": output_buffer.getvalue()})
    except Exception as exc:
        result_queue.put({"success": False, "error": str(exc)})


def run_sandboxed(code: str, timeout_seconds: float = 5.0) -> dict:
    """
    Public entry point. Returns a dict:
        {"success": True, "output": "..."} or
        {"success": False, "error": "..."}

    Raises UnsafeCodeError immediately if static analysis rejects the
    code (never even spawns a process for known-bad code).
    """
    static_safety_check(code)

    result_queue: multiprocessing.Queue = multiprocessing.Queue()
    process = multiprocessing.Process(
        target=_run_in_subprocess, args=(code, result_queue)
    )
    process.start()
    process.join(timeout=timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join()
        return {"success": False, "error": f"Execution exceeded {timeout_seconds}s timeout"}

    try:
        return result_queue.get_nowait()
    except queue.Empty:
        return {"success": False, "error": "Process exited without returning a result"}


# ---------------------------------------------------------------------------
# Demonstration
# ---------------------------------------------------------------------------

def _demo():
    print("=== Case 1: Safe code ===")
    result = run_sandboxed("total = sum([1, 2, 3, 4, 5])\nprint(f'Total: {total}')")
    print(result)

    print("\n=== Case 2: Disallowed import (caught by static analysis) ===")
    try:
        run_sandboxed("import os\nos.system('echo hacked')")
    except UnsafeCodeError as exc:
        print(f"Rejected before execution: {exc}")

    print("\n=== Case 3: Infinite loop (caught by timeout) ===")
    result = run_sandboxed("while True:\n    pass", timeout_seconds=2)
    print(result)


if __name__ == "__main__":
    _demo()
