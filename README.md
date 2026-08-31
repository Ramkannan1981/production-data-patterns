# FDE Interview Prep — Code Samples

Working, tested Python scripts built for Google Data FDE (Forward Deployed
Engineer) interview prep, mapped directly to the JD requirements for
"Staff Forward Deployed Engineer, GenAI, Google Cloud, Data" (Singapore).

Each script is self-contained, runnable, and includes a demo/test at the
bottom (`if __name__ == "__main__":`) so you can run it directly to see
it work.

## How to run any script

```bash
python3 <folder>/<script_name>.py
```

No external dependencies required — everything uses only the Python
standard library, so these will run anywhere without `pip install`.

## Folder structure

### `data-engineering/`
- **`synthetic_data_generator.py`** — Generates customers → accounts →
  transactions with referential integrity (no orphaned foreign keys) and
  realistic weighted distributions (not uniform randomness). Maps to JD:
  *"synthetic data generation at scale while maintaining multi-table
  referential integrity."*
- **`messy_data_cleaner.py`** — Cleans a messy CSV: normalizes
  inconsistent column names (snake_case/camelCase/spaces), handles
  missing-value tokens (NULL/N/A/empty), removes duplicates, coerces
  numeric types. Maps to the common FDE pattern: *"parse a messy CSV
  with inconsistent naming conventions."*
- **`semantic_metadata_layer.py`** — Profiles a raw SQLite schema, then
  attaches human-authored business metadata and entity relationships
  (an ontology) to produce an LLM-consumable semantic layer. Maps to JD:
  *"integrating semantic metadata formats, enterprise taxonomies, or
  ontologies into large-scale data warehouses and lakes."*
- **`sample_input.csv`** — deliberately messy sample file used to test
  `messy_data_cleaner.py`.

### `integration-patterns/`
- **`rate_limiter.py`** — Token bucket rate limiter (allows short bursts,
  enforces a long-run average rate). Common live-coding request when
  integrating with rate-limited client APIs.
- **`retry_with_backoff.py`** — Retries a flaky request with exponential
  backoff + jitter, only retrying on retryable errors (5xx/429), logging
  each attempt. Common FDE robustness pattern.
- **`code_execution_sandbox.py`** — Sandboxes untrusted/LLM-generated
  Python code: static AST analysis rejects dangerous imports before
  execution, restricted builtins, subprocess isolation, hard timeout.
  Maps to JD: *"secure code execution harnesses and interpreter
  sandboxes."*

## Design principles demonstrated across these scripts

1. **Parent-before-child generation** — never create a foreign key
   without sourcing it from an already-generated parent record.
2. **Weighted, not uniform, randomness** — real-world data is skewed;
   `random.choices(weights=...)` over `random.randint()`.
3. **Fail loud, not silent** — data quality issues are logged and
   counted, not silently dropped.
4. **Defense in depth for security** — the sandbox uses multiple
   independent layers (static check + restricted builtins + process
   isolation + timeout), not just one.
5. **CLI-first design** — scripts are runnable as standalone tools with
   `argparse`, not just importable functions — matches the "build a
   small CLI tool" interview pattern.
