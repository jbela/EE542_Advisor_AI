import json
from pathlib import Path



def format_course_requirements(requirements):
    """Format simple requirements while preserving uncertainty."""

    if requirements is None:
        return None

    if not requirements:
        return []

    groups = []

    for requirement in requirements:
        options = requirement.get("courseOptions") or []
        required_count = requirement.get("requiredCourses")

        codes = []

        for option in options:
            code = option.get("courseSpace")

            if not code:
                prefix = option.get("prefix")
                number = option.get("number")
                if prefix and number:
                    code = f"{prefix} {number}"

            if code:
                codes.append(code)

        # Only interpret unambiguous single-course groups
        if len(codes) == 1 and required_count == 1:
            groups.append({
                "operator": "SINGLE",
                "courses": codes
            })
        else:
            groups.append({
                "operator": "UNVERIFIED",
                "courses": codes,
                "required_courses": required_count
            })

    if len(groups) == 1:
        return groups[0]

    return {
        "operator": "UNVERIFIED",
        "groups": groups
    }



def normalize_course(course, term_code):
    """Convert a USC course into a standard record."""

    sections = []

    for section in course.get("sections") or []:
        sections.append({
            "section_id": section.get("sisSectionId"),
            "type": section.get("rnrMode"),
            "units": section.get("units"),
            "instructors": section.get("instructors") or [],
            "schedule": section.get("schedule") or [],
            "registered_seats": section.get("registeredSeats"),
            "total_seats": section.get("totalSeats"),
            "d_clearance": section.get("hasDClearance")
        })

    return {
        "course_id": course.get("courseId"),
        "course_code": course.get("fullCourseName"),
        "title": course.get("name"),
        "description": course.get("description"),
        "units": course.get("courseUnits"),
        "prerequisites": course.get("prerequisiteCourseCodes"),
        "prerequisites_display": format_course_requirements(
            course.get("prerequisiteCourseCodes")
        ),
        "corequisites": course.get("corequisiteCourseCodes"),
        "corequisites_display": format_course_requirements(
            course.get("corequisiteCourseCodes")
        ),
        "recommended_preparation": course.get("recommendedPrep"),
        "restrictions": course.get("courseRestrictions"),
        "term_code": str(term_code),
        "sections": sections
    }


def normalize_response(data):
    """Normalize a USC CoursesByTermSchoolProgram response."""

    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")

    if "courses" not in data:
        raise ValueError("Missing courses field")

    term_code = data.get("termCode")

    if term_code is None:
        raise ValueError("Missing termCode")

    courses = data["courses"]

    if not isinstance(courses, list):
        raise ValueError("courses must be a list")

    return [
        normalize_course(course, term_code)
        for course in courses
    ]


if __name__ == "__main__":
    print("USC course normalization module ready.")