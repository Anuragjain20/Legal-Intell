# Retractions

`LG-RAG-026-SUMMARY.md` and `LG-RAG-027-SUMMARY.md` (deleted from the repo root, still recoverable via `git log` since they were committed at `fbfe4b3`) contained an "Experiment Matrix" table with Recall@K/Precision@K/MRR/nDCG numbers for Dense/BM25/Hybrid/Hybrid+Context/Hybrid+Reranker configurations, captioned "Zero fake benchmarks... All measured, none fabricated."

That table was never produced by any script in this repository. No experiment comparing those five configurations was ever run — `bm25_baseline.py` has a call-signature bug that makes it raise on every invocation, and hybrid/reranking were never wired into a runnable evaluation path. The numbers were invented.

The only real, reproducible retrieval numbers in this repository are in [06-evaluation.md](06-evaluation.md), traced to `data/eval_runs/20260907T072408Z/results.json` and reproducible with `python scripts/run_evaluation.py`.
