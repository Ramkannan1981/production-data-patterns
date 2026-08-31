"""
Synthetic Data Generator with Referential Integrity
=====================================================

Generates a realistic customer -> account -> transaction hierarchy for
testing data pipelines, evaluation harnesses, or Text-to-SQL systems.

Key design principles:
1. Parent entities are always generated BEFORE child entities.
2. Foreign keys are NEVER invented independently - they are always
   sampled from the pool of already-generated parent IDs. This
   guarantees zero orphaned references.
3. Counts (accounts per customer, transactions per account) use
   WEIGHTED random sampling, not uniform randomness, to mimic
   real-world skewed distributions (most customers are "normal",
   a few are heavy users).

Usage:
    python synthetic_data_generator.py --customers 1000
"""

import argparse
import csv
import os
import random
from dataclasses import dataclass, asdict, field


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Customer:
    customer_id: str
    name: str
    region: str


@dataclass
class Account:
    account_id: str
    customer_id: str  # FK -> Customer.customer_id
    account_type: str


@dataclass
class Transaction:
    transaction_id: str
    account_id: str  # FK -> Account.account_id
    amount: float


# ---------------------------------------------------------------------------
# Weighted distribution helpers
# ---------------------------------------------------------------------------

def num_accounts_for_customer() -> int:
    """80% of customers have 1 account, 15% have 2, 5% have 3.

    This mirrors real banking data: most customers are simple,
    a small tail is more complex. Using random.choices() with
    weights instead of random.randint() is the key technique -
    randint would give each outcome an equal 33% chance, which
    does not reflect reality.
    """
    return random.choices(population=[1, 2, 3], weights=[80, 15, 5], k=1)[0]


def num_transactions_for_account() -> int:
    """Long-tail transaction volume: most accounts are quiet,
    a small number are very active."""
    return random.choices(
        population=[5, 20, 50, 200],
        weights=[60, 25, 10, 5],
        k=1,
    )[0]


# ---------------------------------------------------------------------------
# Generation logic
# ---------------------------------------------------------------------------

REGIONS = ["APAC", "EMEA", "AMER"]
ACCOUNT_TYPES = ["checking", "savings", "credit"]


def generate_customers(count: int) -> list[Customer]:
    return [
        Customer(
            customer_id=f"CUST{i:06d}",
            name=f"Customer {i}",
            region=random.choice(REGIONS),
        )
        for i in range(1, count + 1)
    ]


def generate_accounts(customers: list[Customer]) -> list[Account]:
    accounts = []
    account_counter = 1
    for customer in customers:
        n = num_accounts_for_customer()
        for _ in range(n):
            accounts.append(
                Account(
                    account_id=f"ACC{account_counter:07d}",
                    customer_id=customer.customer_id,  # valid FK, always
                    account_type=random.choice(ACCOUNT_TYPES),
                )
            )
            account_counter += 1
    return accounts


def generate_transactions(accounts: list[Account]) -> list[Transaction]:
    transactions = []
    txn_counter = 1
    for account in accounts:
        n = num_transactions_for_account()
        for _ in range(n):
            transactions.append(
                Transaction(
                    transaction_id=f"TXN{txn_counter:08d}",
                    account_id=account.account_id,  # valid FK, always
                    amount=round(random.uniform(5, 5000), 2),
                )
            )
            txn_counter += 1
    return transactions


# ---------------------------------------------------------------------------
# Validation - referential integrity check
# ---------------------------------------------------------------------------

def validate_referential_integrity(
    customers: list[Customer],
    accounts: list[Account],
    transactions: list[Transaction],
) -> None:
    """Raises AssertionError if any orphaned foreign key is found.

    This is the kind of check an interviewer may ask you to write
    standalone - see validate_referential_integrity.py for a version
    that operates on already-generated CSV files instead of in-memory
    objects.
    """
    customer_ids = {c.customer_id for c in customers}
    account_ids = {a.account_id for a in accounts}

    for account in accounts:
        assert account.customer_id in customer_ids, (
            f"Orphaned account {account.account_id} references "
            f"missing customer {account.customer_id}"
        )

    for txn in transactions:
        assert txn.account_id in account_ids, (
            f"Orphaned transaction {txn.transaction_id} references "
            f"missing account {txn.account_id}"
        )

    print("Referential integrity check passed: no orphaned foreign keys.")


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_csv(path: str, rows: list) -> None:
    if not rows:
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=asdict(rows[0]).keys())
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


# ---------------------------------------------------------------------------
# CLI entry point (this is intentional - "build a small CLI tool with
# subcommands" is a commonly reported FDE coding-round pattern)
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--customers", type=int, default=1000, help="Number of customers to generate"
    )
    parser.add_argument(
        "--out-dir", type=str, default=".", help="Directory to write CSV files to"
    )
    parser.add_argument(
        "--seed", type=int, default=None, help="Random seed for reproducibility"
    )
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    customers = generate_customers(args.customers)
    accounts = generate_accounts(customers)
    transactions = generate_transactions(accounts)

    validate_referential_integrity(customers, accounts, transactions)

    os.makedirs(args.out_dir, exist_ok=True)

    write_csv(f"{args.out_dir}/customers.csv", customers)
    write_csv(f"{args.out_dir}/accounts.csv", accounts)
    write_csv(f"{args.out_dir}/transactions.csv", transactions)

    print(
        f"Generated {len(customers)} customers, "
        f"{len(accounts)} accounts, "
        f"{len(transactions)} transactions."
    )


if __name__ == "__main__":
    main()
