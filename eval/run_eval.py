"""Usage: python eval/run_eval.py  (API must be running on :8000; pip install httpx)"""
import json
import time
from pathlib import Path

import httpx

API = "http://localhost:8000"
data = json.loads((Path(__file__).parent / "dataset.json").read_text())
cite_hits = kw_hits = grounded = 0
latencies = []

for i, row in enumerate(data, 1):
    t = time.time()
    r = httpx.post(f"{API}/ask", json={"question": row["question"]}, timeout=120).json()
    latencies.append(time.time() - t)
    answer = r.get("answer", "").lower()
    cited = {c["source"] for c in r.get("citations", [])}
    ok_cite = (row["expected_source"] in cited) if row["expected_source"] else not cited
    ok_kw = any(k.lower() in answer for k in row["keywords_any"])
    cite_hits += ok_cite; kw_hits += ok_kw; grounded += bool(r.get("grounded"))
    print(f"{i}. cite={'PASS' if ok_cite else 'FAIL'} answer={'PASS' if ok_kw else 'FAIL'} "
          f"verified={r.get('grounded')} {latencies[-1]:.1f}s | {row['question']}")

n = len(data)
print(f"\ncitation accuracy {cite_hits}/{n} | answer accuracy {kw_hits}/{n} | "
      f"verified {grounded}/{n} | avg latency {sum(latencies)/n:.1f}s")
