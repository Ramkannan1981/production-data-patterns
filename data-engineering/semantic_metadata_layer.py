"""
Semantic Metadata Layer for Raw Schema
=========================================

JD requirement: "Experience integrating semantic metadata formats,
enterprise taxonomies, or ontologies into large-scale data warehouses
and lakes."

THE PROBLEM: raw database schemas are technical and meaningless to an
LLM (or a new team member). Column names like "cust_tier" or "acct_typ"
don't say what values mean or how tables relate to each other. An LLM
generating SQL from a natural-language question needs this context to
produce accurate queries - this is often called "schema linking."

THIS SCRIPT demonstrates building a semantic layer on top of a raw
schema:
  1. Profile the raw schema (inspect actual data to infer types/patterns)
  2. Attach human-authored metadata (descriptions, business meaning)
  3. Define relationships between tables (the "ontology" piece -
     capturing that accounts.customer_id -> customers.customer_id)
  4. Export a clean, LLM-consumable semantic layer (JSON) that could be
     handed to a Text-to-SQL system instead of raw schema

In production this metadata would live in a catalog tool like Google
Cloud's Dataplex, or dbt's schema.yml / column descriptions - this
script shows the underlying logic those tools implement.
"""

import json
import sqlite3
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Step 1: Schema profiling - inspect what's actually in the database
# ---------------------------------------------------------------------------

def profile_schema(db_path: str) -> dict:
    """Connects to a SQLite DB and extracts raw structural info:
    table names, column names, column types, and foreign keys declared
    at the DB level (if any). This is the 'technical' layer - no
    business meaning yet."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    schema = {}
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [
            {"name": row[1], "type": row[2]} for row in cursor.fetchall()
        ]

        cursor.execute(f"PRAGMA foreign_key_list({table})")
        foreign_keys = [
            {"column": row[3], "references_table": row[2], "references_column": row[4]}
            for row in cursor.fetchall()
        ]

        schema[table] = {"columns": columns, "foreign_keys": foreign_keys}

    conn.close()
    return schema


# ---------------------------------------------------------------------------
# Step 2 + 3: Semantic layer - business meaning + relationships
# This is normally authored by a human domain expert working with the
# FDE, not inferred automatically - shown here as a hand-authored dict
# to demonstrate the STRUCTURE an FDE would design and populate.
# ---------------------------------------------------------------------------

@dataclass
class ColumnMetadata:
    business_name: str
    description: str
    value_mapping: dict | None = None  # e.g. {"1": "Enterprise", "2": "SMB"}


@dataclass
class TableMetadata:
    business_name: str
    description: str
    domain: str  # taxonomy grouping, e.g. "Sales", "Finance"
    columns: dict[str, ColumnMetadata] = field(default_factory=dict)


# Example semantic layer for the customers/accounts/transactions schema
# from the synthetic data generator script - this is the kind of
# artifact an FDE builds WITH the client's domain experts.
SEMANTIC_LAYER = {
    "customers": TableMetadata(
        business_name="Customers",
        description="Individuals or organizations holding one or more accounts.",
        domain="Customer Management",
        columns={
            "customer_id": ColumnMetadata(
                business_name="Customer ID",
                description="Unique identifier for a customer.",
            ),
            "region": ColumnMetadata(
                business_name="Region",
                description="Geographic region the customer is based in.",
                value_mapping={"APAC": "Asia-Pacific", "EMEA": "Europe/Middle East/Africa", "AMER": "Americas"},
            ),
        },
    ),
    "accounts": TableMetadata(
        business_name="Accounts",
        description="Financial accounts owned by a customer.",
        domain="Finance",
        columns={
            "account_id": ColumnMetadata(
                business_name="Account ID",
                description="Unique identifier for an account.",
            ),
            "customer_id": ColumnMetadata(
                business_name="Customer ID (FK)",
                description="References the owning customer.",
            ),
            "account_type": ColumnMetadata(
                business_name="Account Type",
                description="The kind of account held.",
                value_mapping={"checking": "Checking Account", "savings": "Savings Account", "credit": "Credit Account"},
            ),
        },
    ),
}

# Ontology: explicit relationships between business entities (this is
# the piece a plain taxonomy does NOT capture - taxonomy = categories,
# ontology = categories + relationships between them)
ENTITY_RELATIONSHIPS = [
    {"from": "customers", "to": "accounts", "relationship": "owns", "via": "customer_id"},
    {"from": "accounts", "to": "transactions", "relationship": "has", "via": "account_id"},
]


# ---------------------------------------------------------------------------
# Step 4: Merge technical profile + semantic layer into an
# LLM-consumable export
# ---------------------------------------------------------------------------

def build_semantic_export(raw_schema: dict, semantic_layer: dict, relationships: list) -> dict:
    """Combines the raw technical schema with human-authored business
    metadata into a single document that could be handed to a
    Text-to-SQL system as context - far more useful than raw DDL."""
    export = {"tables": {}, "relationships": relationships}

    for table_name, table_info in raw_schema.items():
        meta = semantic_layer.get(table_name)
        table_export = {
            "business_name": meta.business_name if meta else table_name,
            "description": meta.description if meta else "(no description available)",
            "domain": meta.domain if meta else "(uncategorized)",
            "columns": [],
        }
        for col in table_info["columns"]:
            col_meta = meta.columns.get(col["name"]) if meta else None
            table_export["columns"].append({
                "technical_name": col["name"],
                "type": col["type"],
                "business_name": col_meta.business_name if col_meta else col["name"],
                "description": col_meta.description if col_meta else "(no description available)",
                "value_mapping": col_meta.value_mapping if col_meta else None,
            })
        export["tables"][table_name] = table_export

    return export


# ---------------------------------------------------------------------------
# Demo: build a small SQLite DB matching the synthetic data generator's
# schema, profile it, and produce the semantic export
# ---------------------------------------------------------------------------

def _build_demo_db(path: str) -> None:
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE customers (
            customer_id TEXT PRIMARY KEY,
            region TEXT
        );
        CREATE TABLE accounts (
            account_id TEXT PRIMARY KEY,
            customer_id TEXT,
            account_type TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );
    """)
    conn.commit()
    conn.close()


def _demo():
    db_path = "/tmp/demo_schema.db"
    _build_demo_db(db_path)

    raw_schema = profile_schema(db_path)
    print("Raw technical schema (what you get by default):")
    print(json.dumps(raw_schema, indent=2))

    semantic_export = build_semantic_export(raw_schema, SEMANTIC_LAYER, ENTITY_RELATIONSHIPS)
    print("\nSemantic export (what you'd hand to a Text-to-SQL system):")
    print(json.dumps(semantic_export, indent=2))


if __name__ == "__main__":
    _demo()
