import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

VERSIONS_DIR = ROOT / "data" / "versions" / "courses"
COURSES_DIR = ROOT / "data" / "courses"

TERM_CODE = "20271"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def compare_dicts(old, new, prefix=""):
    """Recursively identify changed fields."""

    changes = []

    if isinstance(old, dict) and isinstance(new, dict):
        keys = set(old) | set(new)

        for key in sorted(keys):
            field = f"{prefix}.{key}" if prefix else key

            if key not in old:
                changes.append((field, "ADDED", new[key]))
            elif key not in new:
                changes.append((field, "REMOVED", old[key]))
            else:
                changes.extend(
                    compare_dicts(old[key], new[key], field)
                )

    elif isinstance(old, list) and isinstance(new, list):
        for i in range(max(len(old), len(new))):
            field = f"{prefix}[{i}]"

            if i >= len(old):
                changes.append((field, "ADDED", new[i]))
            elif i >= len(new):
                changes.append((field, "REMOVED", old[i]))
            else:
                changes.extend(
                    compare_dicts(old[i], new[i], field)
                )

    elif old != new:
        changes.append(
            (prefix, "CHANGED", {"old": old, "new": new})
        )

    return changes


def main():
    backups = sorted(
        VERSIONS_DIR.glob(f"ee_{TERM_CODE}_*.json")
    )

    if not backups:
        print("No previous versions found.")
        return

    old_path = backups[-1]
    new_path = COURSES_DIR / f"ee_{TERM_CODE}.json"

    old_data = load_json(old_path)
    new_data = load_json(new_path)

    changes = compare_dicts(
        old_data["courses"],
        new_data["courses"]
    )

    print(f"Previous: {old_path.name}")
    print(f"Current: {new_path.name}")
    print(f"Total changes: {len(changes)}")

    for field, change_type, value in changes[:30]:
        print(f"\n{change_type}: {field}")
        print(json.dumps(value, indent=2)[:500])

    if len(changes) > 30:
        print(f"\n... {len(changes) - 30} more changes")


if __name__ == "__main__":
    main()
