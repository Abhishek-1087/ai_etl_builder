import json
import os
from datetime import datetime


SNAPSHOT_PATH = "schema_snapshot.json"


def load_snapshot():
    if not os.path.exists(SNAPSHOT_PATH):
        return None
    with open(SNAPSHOT_PATH, "r") as f:
        return json.load(f)


def save_snapshot(schema):
    snapshot = {
        "captured_at": datetime.utcnow().isoformat(),
        "schema": {
            table: [c["column"] for c in cols]
            for table, cols in schema.items()
        }
    }
    with open(SNAPSHOT_PATH, "w") as f:
        json.dump(snapshot, f, indent=2)
    print(f"Schema snapshot saved to {SNAPSHOT_PATH}")


def detect_drift(current_schema):
    """
    Compares current schema against the last saved snapshot.
    Returns a drift report dict and saves new snapshot.
    """

    previous = load_snapshot()

    drift = {
        "has_drift": False,
        "new_tables": [],
        "removed_tables": [],
        "changed_tables": {}
    }

    if previous is None:
        print("No previous snapshot found - this is the first run. Saving baseline.")
        save_snapshot(current_schema)
        return drift

    prev_schema = previous["schema"]
    curr_tables = set(current_schema.keys())
    prev_tables = set(prev_schema.keys())

    # New tables
    drift["new_tables"] = sorted(curr_tables - prev_tables)

    # Removed tables
    drift["removed_tables"] = sorted(prev_tables - curr_tables)

    # Changed tables (columns added or removed)
    for table in curr_tables & prev_tables:
        curr_cols = set(c["column"] for c in current_schema[table])
        prev_cols = set(prev_schema[table])

        added = sorted(curr_cols - prev_cols)
        removed = sorted(prev_cols - curr_cols)

        if added or removed:
            drift["changed_tables"][table] = {
                "columns_added": added,
                "columns_removed": removed
            }

    drift["has_drift"] = bool(
        drift["new_tables"] or
        drift["removed_tables"] or
        drift["changed_tables"]
    )

    # Save updated snapshot
    save_snapshot(current_schema)

    return drift


def print_drift_report(drift):
    if not drift["has_drift"]:
        print("\nSchema drift check: No changes detected.")
        return

    print("\n" + "=" * 50)
    print("SCHEMA DRIFT DETECTED")
    print("=" * 50)

    if drift["new_tables"]:
        print(f"\nNew tables ({len(drift['new_tables'])}):")
        for t in drift["new_tables"]:
            print(f"  + {t}")

    if drift["removed_tables"]:
        print(f"\nRemoved tables ({len(drift['removed_tables'])}):")
        for t in drift["removed_tables"]:
            print(f"  - {t}")

    if drift["changed_tables"]:
        print(f"\nModified tables ({len(drift['changed_tables'])}):")
        for table, changes in drift["changed_tables"].items():
            print(f"\n  {table}")
            for col in changes["columns_added"]:
                print(f"    + {col}")
            for col in changes["columns_removed"]:
                print(f"    - {col}")

    print("=" * 50 + "\n")
