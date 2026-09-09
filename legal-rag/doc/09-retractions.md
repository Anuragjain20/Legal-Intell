# Retractions

`LG-RAG-026-SUMMARY.md` and `LG-RAG-027-SUMMARY.md` (deleted from the repo root, still recoverable via `git log` since they were committed at `fbfe4b3`) contained an "Experiment Matrix" table with Recall@K/Precision@K/MRR/nDCG numbers for Dense/BM25/Hybrid/Hybrid+Context/Hybrid+Reranker configurations, captioned "Zero fake benchmarks... All measured, none fabricated."

That table was never produced by any script in this repository at the time it was written. No experiment comparing those five configurations had ever been run — `bm25_baseline.py` had a call-signature bug that made it raise on every invocation, and hybrid/reranking had no runnable evaluation path. The numbers were invented.

**Update:** both underlying gaps are now fixed. `bm25_baseline.py`'s bug is fixed, and `python scripts/run_evaluation.py --method {dense,bm25,hybrid,hybrid_rerank}` runs all four configurations for real, writing versioned results to `data/eval_runs/`. See [06-evaluation.md](06-evaluation.md) for the real comparison table this produced, and note that it does *not* match the retracted table's numbers or its implied conclusion — the real reranker measurement made retrieval worse, and it was rejected on that evidence rather than shipped.
