"""LLM latency benchmark for the /ask generation path.

Run on any machine with Ollama running (e.g. the AWS GPU instance):

    python tests/benchmark_llm_latency.py                      # default model
    python tests/benchmark_llm_latency.py qwen2.5:3b qwen2.5:7b --runs 3

For each question it captures the exact Ollama payload /ask would send
(system prompt, sources, options), then calls Ollama directly with each model
and reports prompt-processing speed, generation speed, and wall time. It also
reports the end-to-end /ask time for the configured model, which includes any
citation retry. Results go to reports/llm_latency.csv. Answers are printed
for manual review; speed numbers say nothing about correctness.
"""
import argparse
import csv
import statistics
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import backend.main as main  # noqa: E402

QUESTIONS = [
    "What does USC OIS say about reduced course load for international students?",
    "Does EE 542 require Python programming?",
    "Does EE 510 require Python?",
    "What is the late submission policy in EE 542?",
]


def capture_payloads(questions):
    """Run /ask with a fake LLM client to record the exact request bodies."""
    captured = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "Placeholder [1]."}}

    class Capture:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json=None):
            captured.append(json)
            return FakeResponse()

    real = main.httpx.AsyncClient
    main.httpx.AsyncClient = Capture
    try:
        client = TestClient(main.app)
        payloads = []
        for question in questions:
            captured.clear()
            client.post("/ask", json={"question": question})
            if captured:
                payloads.append((question, captured[0]))
            else:
                print(f"[skip] answered without the LLM: {question}")
        return payloads
    finally:
        main.httpx.AsyncClient = real


def call(model, payload):
    body = dict(payload, model=model)
    started = time.perf_counter()
    response = httpx.post(main.URL, json=body, timeout=900)
    response.raise_for_status()
    data = response.json()
    wall = time.perf_counter() - started
    pe = data.get("prompt_eval_count") or 0
    pd = (data.get("prompt_eval_duration") or 0) / 1e9
    ec = data.get("eval_count") or 0
    ed = (data.get("eval_duration") or 0) / 1e9
    return {
        "wall_s": round(wall, 2),
        "load_s": round((data.get("load_duration") or 0) / 1e9, 2),
        "prompt_tokens": pe,
        "prompt_tok_per_s": round(pe / pd, 1) if pd else "",
        "gen_tokens": ec,
        "gen_tok_per_s": round(ec / ed, 1) if ed else "",
        "answer": data["message"]["content"],
    }


def main_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("models", nargs="*", default=[main.MODEL])
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--no-e2e", action="store_true",
                        help="skip the end-to-end /ask timing")
    args = parser.parse_args()

    payloads = capture_payloads(QUESTIONS)
    rows = []
    for model in args.models:
        call(model, payloads[0][1])  # load the model; not timed
        for question, payload in payloads:
            results = [call(model, payload) for _ in range(args.runs)]
            median = statistics.median(r["wall_s"] for r in results)
            r = results[-1]
            print(f"\n## {model} | {question}")
            print(f"median wall {median:.1f}s | prompt {r['prompt_tokens']} tok "
                  f"@ {r['prompt_tok_per_s']} tok/s | gen {r['gen_tokens']} tok "
                  f"@ {r['gen_tok_per_s']} tok/s")
            print("ANSWER:", r["answer"].replace("\n", " / "))
            rows.append({"mode": "direct", "model": model, "question": question,
                         "median_wall_s": median, **r})

    if not args.no_e2e:
        client = TestClient(main.app)
        for question, _ in payloads:
            started = time.perf_counter()
            data = client.post("/ask", json={"question": question}).json()
            wall = round(time.perf_counter() - started, 2)
            print(f"\n## /ask end-to-end ({main.MODEL}) {wall}s | {question}")
            print("ANSWER:", data.get("answer", "").replace("\n", " / "))
            rows.append({"mode": "ask_e2e", "model": main.MODEL, "question": question,
                         "median_wall_s": wall, "answer": data.get("answer", "")})

    out = ROOT / "reports" / "llm_latency.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = ["mode", "model", "question", "median_wall_s", "wall_s", "load_s",
              "prompt_tokens", "prompt_tok_per_s", "gen_tokens", "gen_tok_per_s", "answer"]
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main_cli()
