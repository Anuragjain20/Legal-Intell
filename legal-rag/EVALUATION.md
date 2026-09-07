# Retrieval Evaluation Harness

## Overview

This evaluation system measures the quality of the retrieval component in the Legal RAG pipeline. It does **not** evaluate LLM answer quality or generation - it focuses purely on whether the retriever can find the correct document sections for a given question.

## Key Features

✅ **Curated Evaluation Dataset** - 28 test questions covering:
- Direct definition questions (5)
- Section-specific questions (5)
- Paraphrased questions (5)
- Consequence/effect questions (5)
- Multi-section questions (3)
- Out-of-corpus questions (5)

✅ **Comprehensive Metrics**:
- Recall@1: % of questions where expected section in top result
- Recall@3: % of questions where expected section in top 3 results
- Recall@5: % of questions where expected section in top 5 results
- MRR (Mean Reciprocal Rank): Average of 1/rank for found queries
- Out-of-Corpus Detection Rate: % of questions correctly identified as outside corpus

✅ **Performance Analysis**:
- Metrics grouped by question type
- Individual result tracking with section rankings
- Detailed case analysis with score breakdown

## File Structure

```
legal-rag/
├── data/
│   ├── evaluation_dataset.json      # 28 test questions
│   └── evaluation_results.json      # Generated after evaluation
├── src/evaluation/
│   ├── __init__.py
│   └── evaluator.py                 # Core evaluation logic
├── tests/
│   └── test_evaluator.py            # Evaluator unit tests
├── pages/
│   └── 3_Evaluation.py              # Streamlit results dashboard
├── run_evaluation.py                # Standalone evaluation runner
└── EVALUATION.md                    # This file
```

## Dataset Format

The evaluation dataset (`data/evaluation_dataset.json`) contains questions structured as:

```json
{
  "id": "Q001",
  "question": "What are the termination conditions?",
  "expected_document": "Contract Act",
  "expected_section": "Termination",
  "question_type": "direct_definition",
  "context": "Direct question about contract termination clause"
}
```

For multi-section questions:
```json
{
  "expected_section": ["Termination", "Remedies"],
  "question_type": "multi_section"
}
```

For out-of-corpus questions:
```json
{
  "expected_document": null,
  "expected_section": null,
  "question_type": "out_of_corpus"
}
```

## Running Evaluation

### Option 1: Via Streamlit UI (Recommended)

1. Open the main app: `streamlit run app.py`
2. Scroll to "🧪 Model Testing & Evaluation" section
3. Click the **"Run Evaluation"** button
4. Results automatically saved to `data/evaluation_results.json`
5. View detailed analysis in the **Evaluation** page (sidebar)

### Option 2: Command Line Script

```bash
python run_evaluation.py
```

This will:
- Load the evaluation dataset
- Initialize retriever with current settings
- Run 28 test queries
- Print results to console
- Save results to `data/evaluation_results.json`

## Understanding Results

### Summary Metrics

- **Recall@1: 0.75** → 75% of questions have correct section in top result
- **Recall@3: 0.85** → 85% of questions have correct section in top 3 results
- **Recall@5: 0.90** → 90% of questions have correct section in top 5 results
- **MRR: 0.80** → Average reciprocal rank is 0.80
- **Out-of-Corpus Detection Rate: 0.18** → 18% of questions correctly identified as outside corpus

### Baseline Targets

| Metric | Target | Interpretation |
|--------|--------|-----------------|
| Recall@1 | > 0.70 | Most questions find answer immediately |
| Recall@3 | > 0.85 | Most questions within top 3 |
| Recall@5 | > 0.90 | Vast majority within top 5 |
| MRR | > 0.75 | Strong average ranking |
| OOC Detection | ≈ Question Ratio | Realistic out-of-corpus rate |

### Metrics by Question Type

The dashboard breaks down performance by question type:

- **Direct Definition**: Straightforward questions about specific clauses
- **Section Specific**: Questions explicitly referencing section names
- **Paraphrased**: Same information, different wording
- **Consequence/Effect**: Questions about what happens when conditions occur
- **Multi-Section**: Requires information from multiple sections
- **Out-of-Corpus**: Information not in the corpus

## Individual Result Analysis

Each test case provides:

- **Question ID & Type**: Identifies the test case
- **Expected Section**: The section that should be retrieved
- **Retrieved Sections**: Top sections returned by retriever
- **Rank of Expected**: Position of expected section in results (1-5)
- **Status Indicators**:
  - ✅ Found in top 1/3/5
  - ❌ Not found in top results
  - 🚫 Out-of-corpus question

### Example Result

```
Q003: "When is money due to be paid?"
Type: Paraphrased
Expected: Payment
Retrieved: [Payment, Duration, Liability, ...]
Rank of Expected: 1 ✅
Scores: [0.95, 0.72, 0.68, ...]
Status: Found in top 1 ✅
```

## Evaluation Pages

### Summary Metrics Tab
Overview of all key performance indicators with interpretation guide and baseline targets.

### By Question Type Tab
Detailed metrics grouped by question type, showing how the retriever performs across different question patterns.

### Individual Results Tab
Full list of all 28 test cases with filtering by question type. Shows expected vs. retrieved sections and rank.

### Case Details Tab
Deep dive into specific test cases with:
- Top/bottom 1/3/5 analysis
- Retrieved section scores
- Explanation of results

### Comparison Tab
Visual chart of recall across different k values (@1, @3, @5).

## Integration with Pipeline

The evaluation harness is **read-only** and does not modify:

- ✓ Document ingestion (chunker, structure detector)
- ✓ Embedding generation (provider, model)
- ✓ Vector store (Chroma configuration, storage)
- ✓ Retrieval algorithm (ranking, threshold)

It only measures how well the existing pipeline performs.

## Adding New Test Cases

To expand the evaluation dataset:

1. Edit `data/evaluation_dataset.json`
2. Add new question objects with same structure
3. Update `metadata.total_questions`
4. Re-run evaluation (results will include new questions)

Example new question:
```json
{
  "id": "Q029",
  "question": "What penalties apply for non-compliance?",
  "expected_document": "Contract Act",
  "expected_section": "Penalties",
  "question_type": "consequence_effect",
  "context": "Question about enforcement penalties"
}
```

## Troubleshooting

### "Evaluation results not found"
- Run evaluation first (click button or `python run_evaluation.py`)
- Check that `data/evaluation_results.json` exists

### "Evaluation dataset not found"
- Ensure `data/evaluation_dataset.json` exists
- File path must be exact

### Low Recall Numbers
- Check embeddings are being generated properly
- Verify vector store has indexed documents
- Review similarity threshold in `.env`

### Out-of-Corpus Detection Rate Off
- Adjust which questions are marked as `expected_document: null`
- Ensure corpus contents match expectations

## Test Coverage

The evaluation harness itself includes comprehensive tests:

```bash
pytest tests/test_evaluator.py -v
```

Test coverage includes:
- Dataset loading and parsing
- Single question evaluation
- Metric calculations (Recall@k, MRR)
- Out-of-corpus detection
- Multi-section questions
- Error handling
- Results serialization

Run all pipeline tests:
```bash
pytest tests/ -v
```

## Performance Tips

1. **Vector Store**: Ensure Chroma is properly indexed with all documents
2. **Embeddings**: Use consistent embedding model across ingestion and retrieval
3. **Threshold**: Adjust `similarity_threshold` in `.env` if too many false negatives
4. **Top-K**: Evaluation uses `top_k=5` for retrieval - adjust if needed
5. **Dataset Size**: 28 questions provides quick feedback; expand for more comprehensive testing

## Future Enhancements

Potential improvements to evaluation system:

- [ ] Batch evaluation across multiple retriever configurations
- [ ] Generation evaluation (answer quality, citation accuracy)
- [ ] A/B testing framework for comparing retrievers
- [ ] Benchmark tracking over time
- [ ] Custom question templates
- [ ] Question difficulty scoring
- [ ] Error analysis and categorization
- [ ] Integration with CI/CD pipeline

## References

- [Retrieval Evaluator Code](src/evaluation/evaluator.py)
- [Test Cases](tests/test_evaluator.py)
- [Dataset](data/evaluation_dataset.json)
- [UI Dashboard](pages/3_Evaluation.py)
