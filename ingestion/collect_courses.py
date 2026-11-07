import requests
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

from ingestion.connectors.usc_courses import normalize_response

ROOT = Path(__file__).resolve().parents[1]

COURSES_DIR = ROOT / "data" / "courses"
COURSES_DIR.mkdir(parents=True, exist_ok=True)


def calculate_hash(data):
    serialized = json.dumps(
        data,
        sort_keys=True,
        ensure_ascii=False
    )
    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def calculate_academic_hash(courses):
    academic_data = []

    for course in courses:
        academic_data.append({
            "course_id": course.get("course_id"),
            "course_code": course.get("course_code"),
            "title": course.get("title"),
            "description": course.get("description"),
            "units": course.get("units"),
            "prerequisites": course.get("prerequisites"),
            "prerequisites_display": course.get("prerequisites_display"),
            "corequisites": course.get("corequisites"),
            "corequisites_display": course.get("corequisites_display"),
            "recommended_preparation": course.get("recommended_preparation"),
            "restrictions": course.get("restrictions")
        })

    academic_data.sort(
        key=lambda c: str(c["course_id"])
    )

    return calculate_hash(academic_data)


def calculate_operational_hash(courses):
    operational_data = []

    for course in courses:
        operational_data.append({
            "course_id": course.get("course_id"),
            "sections": course.get("sections", [])
        })

    operational_data.sort(
        key=lambda c: str(c["course_id"])
    )

    return calculate_hash(operational_data)

def save_course_data(data):
    """Validate, normalize, and save course information."""

    courses = normalize_response(data)

    if not courses:
        raise ValueError("No courses found in response")

    term_code = str(data["termCode"])

    academic_hash = calculate_academic_hash(courses)
    operational_hash = calculate_operational_hash(courses)

    academic_changed =  True
    operational_changed = True

    output = {
        "term_code": term_code,
        "school": data.get("schoolPrefix"),
        "program": data.get("programPrefix"),
        "collected_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "source_url": (
            f"https://classes.usc.edu/term/{term_code}/"
            "catalogue/school/ENGV/program/EE"
        ),
        "courses": courses,
        "academic_hash": academic_hash,
        "operational_hash": operational_hash
    }

    serialized = json.dumps(
        courses,
        sort_keys=True,
        ensure_ascii=False
    )

    output["content_hash"] = hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()

    file_path = COURSES_DIR / f"ee_{term_code}.json"

    if file_path.exists():
        old = json.loads(
            file_path.read_text(encoding="utf-8")
        )

        if old.get("content_hash") == output["content_hash"]:
            print(f"No changes detected for {term_code}")
            
            return {
                "term_code": term_code,
                "academic_changed": False,
                "operational_changed": False,
                "saved": False
            }

        old_academic_hash = old.get("academic_hash")
        old_operational_hash = old.get("operational_hash")

        if old_academic_hash is None:
            old_academic_hash = calculate_academic_hash(
                old["courses"]
            )

        if old_operational_hash is None:
            old_operational_hash = calculate_operational_hash(
                old["courses"]
            )

        academic_changed = academic_hash != old_academic_hash
        operational_changed = operational_hash != old_operational_hash

        print(f"Academic content changed: {academic_changed}")
        print(f"Operational data changed: {operational_changed}")

        # Preserve the previous version before updating
        versions_dir = ROOT / "data" / "versions" / "courses"
        versions_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(
            timezone.utc
        ).strftime("%Y%m%d_%H%M%S_%f")

        backup_file = versions_dir / (
            f"ee_{term_code}_{timestamp}.json"
        )

        backup_file.write_text(
            json.dumps(old, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        print(f"Previous version saved: {backup_file.name}")

    file_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"Saved {len(courses)} EE courses for {term_code}")

    return {
        "term_code": term_code,
        "academic_changed": academic_changed,
        "operational_changed": operational_changed,
        "saved": True
    }
    

COURSES_API = (
    "https://classes.usc.edu/api/Courses/"
    "CoursesByTermSchoolProgram"
)


def fetch_courses(term_code):
    """Fetch publicly listed EE courses for one semester."""

    response = requests.get(
        COURSES_API,
        params={
            "termCode": str(term_code),
            "school": "ENGV",
            "program": "EE"
        },
        headers={
            "User-Agent": "USCAdvisorAI-StudentResearch/0.1",
            "Accept": "application/json"
        },
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, dict):
        raise ValueError("Unexpected course response format")

    if not isinstance(data.get("courses"), list):
        raise ValueError("Missing or invalid courses list")

    if str(data.get("termCode")) != str(term_code):
        raise ValueError("Returned semester does not match request")

    if data.get("schoolPrefix") != "ENGV":
        raise ValueError("Unexpected school")

    if data.get("programPrefix") != "EE":
        raise ValueError("Unexpected program")

    return data

if __name__ == "__main__":
    term_code = "20263"

    print(f"Fetching EE courses for {term_code}...")

    data = fetch_courses(term_code)

    save_course_data(data)
