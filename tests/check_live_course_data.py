"""Optional environment check: confirms whether local generated course snapshots exist.

This does not collect anything or modify project data. It is NOT a unit test.
Run: python tests/check_live_course_data.py
"""

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
COURSES = ROOT / "data" / "courses"

for term, targets in [("20271", ["EE 562", "EE 597", "EE 450"]), ("20263", ["EE 542"])]:
    path = COURSES / f"ee_{term}.json"
    print(f"\n{term}: {path}")
    if not path.exists():
        print("  MISSING SNAPSHOT: run your ingestion/backfill workflow or obtain the team's data")
        continue
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        codes = {c.get("course_code") for c in data.get("courses", [])}
        print("  course records:", len(codes))
        for code in targets:
            print(f"  {code}: {'FOUND' if code in codes else 'NOT IN THIS SNAPSHOT'}")
    except (ValueError, OSError) as exc:
        print("  INVALID/UNREADABLE:", exc)
