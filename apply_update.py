"""One-time compatibility updater. Run from repository root: python apply_update.py"""
from pathlib import Path
import shutil

root = Path.cwd()
main = root / 'backend' / 'main.py'
quality = root / 'backend' / 'quality_improvements.py'
if not main.exists():
    raise SystemExit('Run this script from the repository root (backend/main.py missing).')
s = main.read_text(encoding='utf-8')
if 'QUALITY_UPDATE_V1' in s:
    raise SystemExit('Already installed; no changes made.')

# Keep earlier debug and citation-prompt changes, but make the new import robust.
imp = 'from backend.quality_improvements import (\n    course_discovery_answer, catalog_availability_answer,\n    clearance_evidence_answer, cite_safe_policy_excerpts, citation_problems,\n)\n'
anchor = 'from rag.evidence_sufficiency import classify_evidence'
if anchor not in s:
    raise SystemExit('Expected import anchor missing; repository differs from reviewed version.')
s = s.replace(anchor, imp + anchor, 1)

# Insert deterministic branches immediately before building the LLM context.
anchor = '    context = "\\n\\n".join('
if anchor not in s:
    raise SystemExit('Expected context anchor missing; repository differs from reviewed version.')
block = '''    # QUALITY_UPDATE_V1: deterministic answers where evidence is structured.
    structured = clearance_evidence_answer(question, docs)
    if structured is None:
        structured = course_discovery_answer(question, docs)
    if structured is not None:
        return {
            "answer": structured,
            "sources": _response_sources(docs),
            "status": "review_required",
            "decision_status": "evidence_available",
            "invalid_citations": [],
            "citations_required": False,
            "missing_citations": False,
        }

'''
s = s.replace(anchor, block + anchor, 1)

# Place this earlier than the existing single-document no-URL fallback.
availability_anchor = "    if (" + "\n" + "        len(docs) == 1" + "\n" + '        and docs[0].get("retrieval_method") == "syllabus_unavailable"'
if availability_anchor not in s:
    raise SystemExit('Syllabus/availability insertion anchor missing.')
s = s.replace(availability_anchor, '    # QUALITY_UPDATE_V1: availability derives from checked records only.\n    availability_answer = catalog_availability_answer(docs)\n    if availability_answer is not None:\n        return {\n            "answer": availability_answer,\n            "sources": _response_sources(docs),\n            "status": "review_required",\n            "decision_status": "evidence_available" if docs[0].get("availability_status") == "listed" else "evidence_unavailable",\n            "invalid_citations": [],\n            "citations_required": False,\n            "missing_citations": False,\n        }\n\n' + availability_anchor, 1)

# Add a stronger, scoped instruction. Existing prompt remains unmodified.
anchor = '                "You are a USC academic information assistant. Use ONLY the source "'
if anchor not in s:
    raise SystemExit('Expected system-prompt anchor missing.')
s = s.replace(anchor, '''                "Never present a USC policy as university-wide when only an "
                "individual department's evidence is available. For policy claims, "
                "provide the supporting citation on that same sentence. "
                "If the source does not explicitly establish a prerequisite, "
                "placement exam, approval requirement, or deadline, do not claim one. "
''' + anchor, 1)

# Replace the final citation validation region. Older temporary debug logs
# are superseded by the new retry behavior; prior logs remain on disk. We also keep existing course-title citation repair.
start = s.find('    answer, invalid = check_citations(answer, docs)', s.find('    context = "\\n\\n".join('))
if start < 0:
    raise SystemExit('Final citation validation anchor missing.')
end = s.find('    sources = _response_sources(docs)', start)
if end < 0:
    raise SystemExit('Final response-sources anchor missing.')
replacement = '''    # QUALITY_UPDATE_V1: validate, retry once, and validate again.
    required = requires_source_citations(data.question, docs)
    answer, invalid, coverage, course_issues = citation_problems(
        answer, docs, required, check_citations, citation_coverage, course_citation_issues
    )
    if coverage["missing_citations"] or course_issues:
        # Preserve supplied evidence and ask the model to fix only verifiable
        # citation format. The same validation rules still apply on retry.
        retry_messages = messages + [
            {"role": "assistant", "content": answer},
            {"role": "user", "content": (
                "Revise your previous answer using ONLY the supplied source passages. "
                "Every factual sentence about USC policy needs its supporting [number] "
                "citation. Each course recommendation line needs the matching course "
                "citation on that same line. Cite only matching evidence; remove "
                "unsupported statements rather than inventing citations. "
                "Do not add new facts. Return the corrected answer only."
            )},
        ]
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=10.0)) as client:
                retry_response = await client.post(
                    URL, json={"model": MODEL, "messages": retry_messages,
                               "stream": False, "options": {"num_predict": 500}},
                )
                retry_response.raise_for_status()
                retry_answer = retry_response.json()["message"]["content"]
            # Earlier exact-title repair is safe to apply again; it will not
            # invent citations for arbitrary policy or course claims.
            if 'cite_exact_course_listings' in globals():
                retry_answer = cite_exact_course_listings(retry_answer, docs)
            retry_clean, retry_invalid, retry_coverage, retry_course_issues = citation_problems(
                retry_answer, docs, required, check_citations,
                citation_coverage, course_citation_issues
            )
            if not (retry_coverage["missing_citations"] or retry_course_issues or retry_invalid):
                answer = retry_clean
                invalid = []
                coverage = retry_coverage
                course_issues = []
            else:
                answer = None
                invalid = retry_invalid
                coverage = retry_coverage
                course_issues = retry_course_issues
        except (httpx.HTTPError, KeyError, ValueError):
            answer = None
    if answer is None or coverage["missing_citations"] or course_issues:
        # Grounded excerpts are more useful than a fabricated policy answer.
        answer = cite_safe_policy_excerpts(docs) or (
            "I found related USC sources, but couldn't produce an answer "
            "with a verifiable source reference. Please review the sources "
            "below or ask the appropriate USC office."
        )
        # The status reflects a fallback; don't report the rejected model's
        # citation check as success.
        coverage = citation_coverage(answer, docs, required=required)
    if course_issues:
        coverage["course_citation_issues"] = course_issues
'''
s = s[:start] + replacement + s[end:]
# Ensure the original helper remains imported, if user did not apply prior patch.
if 'cite_exact_course_listings' not in s.split('from rag.evidence_sufficiency', 1)[0]:
    # Existing repair optional; users already applied it, but allow pristine source.
    pass

backup = main.with_suffix('.py.before_quality_update')
if backup.exists():
    raise SystemExit(f'Backup {backup} already exists; stop to avoid overwriting it.')
shutil.copy2(main, backup)
shutil.copy2(Path(__file__).with_name('quality_improvements.py'), quality)
main.write_text(s, encoding='utf-8')
print('Updated backend/main.py and added backend/quality_improvements.py')
print('Backup:', backup)
