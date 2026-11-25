USC Trojan Guide quality update — based on user-uploaded (2).zip

Contents:
- apply_update.py: modifies your existing backend/main.py using stable anchors, saves backup.
- quality_improvements.py: new deterministic evidence handling helpers.
- test_quality_improvements.py: new mocked API and helper tests.

Windows PowerShell:
1. Back up or commit your current branch.
2. Extract these files to the repository root, preserving names.
3. python apply_update.py
4. Copy-Item test_quality_improvements.py tests/test_quality_improvements.py
5. python -m py_compile backend/main.py backend/quality_improvements.py
6. python -m unittest tests.test_quality_improvements -v
7. python -m unittest discover -s tests -v
8. Start Ollama and FastAPI; run python tests/benchmark_week3_api.py

Important: Existing citation validation remains on model replies. Source-excerpt
fallback is conservative and NOT a full semantic fact-check. It still requires
human review of important academic-policy advice.

This updater retains your prior prompt and course-citation changes. It replaces
the old final validation block, so any TEMPORARY DEBUG_CITATIONS logging in
that block is superseded. Existing reports/citation_debug.jsonl is untouched.
The updater retains the earlier prompt and course-citation repair if present.
It replaces the temporary DEBUG_CITATIONS logging at the final validation site;
old log files remain untouched. Run the updated tests without a live Ollama
service; then run the project's API benchmark with Ollama/FastAPI running.
