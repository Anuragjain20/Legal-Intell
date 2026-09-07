# Valid Retrieval Evaluation - Grounded in Real Corpus

## Problem Statement

The initial evaluation dataset was **invalid** because:
- Questions used synthetic section names ("Termination", "Confidentiality", "Payment", etc.)
- These sections did NOT exist in the actual indexed corpus
- Questions were labeled for "Contract Act" when actual corpus contains heterogeneous docs
- Dataset was not grounded in real indexed content

## Solution

Build a **valid evaluation dataset** where:
- Every in-corpus question is grounded in actual indexed chunks
- Expected sections exactly match chunk metadata
- Questions reference real documents in the corpus
- Out-of-corpus questions tested via actual retrieval

## Corpus Contents

The MVP corpus contains:

### Legislative/Statutory Documents
- **indian_contract_act_1872.pdf** - Indian Contract Act 1872
- **bharatiya_nyaya_sanhita_2023.pdf** - Bharatiya Nyaya Sanhita (Criminal Code) 2023
- **it_intermediary_guidelines_2021_updated_2023.pdf** - IT Act Intermediary Guidelines

### Contracts (CUAD Dataset)
- CreditcardscomInc Affiliate Agreement
- CybergyHoldingsInc Affiliate Agreement
- DigitalCinemaDestinationsCorp Affiliate Agreement
- LinkPlusCorp Affiliate Agreement
- SouthernStarEnergyInc Affiliate Agreement

### Court Judgments
- Multiple Delhi High Court judgments (DLHC cases)
- Multiple Supreme Court judgments

## Implementation Workflow

### Step 1: Inspect Actual Corpus

```bash
python build_valid_evaluation_dataset.py
```

This script:
1. Connects to Chroma vector store
2. Retrieves all indexed chunks with metadata
3. Groups chunks by document name
4. Extracts actual section names
5. Displays corpus inventory

**Output Example**:
```
📚 CORPUS INVENTORY:

indian_contract_act_1872.pdf
  Total Chunks: 142
  Sections: ['1', '2', '3', '4', '5', ...]
  Sample Chunks:
    ID: chunk-001
    Section: 1, Page: 1
    Text: "Definitions.—In this Act the following...

bharatiya_nyaya_sanhita_2023.pdf
  Total Chunks: 187
  Sections: ['1', '2', '3', '4', '5', ...]
```

### Step 2: Build Questions from Real Chunks

For each significant chunk:
1. Extract: `chunk_id`, `document_name`, `section`, `heading`, `text`
2. Create question directly from chunk content
3. Record expected values:
   - `expected_document`: Exact filename
   - `expected_section`: Exact section from metadata
   - `expected_chunk_id`: Chunk ID for precision matching

**Example**:

```json
{
  "id": "Q001",
  "question": "What does the section on Definitions state?",
  "expected_document": "indian_contract_act_1872.pdf",
  "expected_section": "1",
  "expected_chunk_id": "chunk-001-abc123",
  "question_type": "direct_definition",
  "context": "Question grounded in actual chunk"
}
```

### Step 3: Create Balanced Question Mix

**Targets**:
- 5-7 Indian Contract Act questions
- 5-7 Bharatiya Nyaya Sanhita questions
- 5-7 IT Intermediary Guidelines questions
- 5-7 CUAD Contract questions
- 5 Court Judgment questions
- 5 Paraphrased versions
- 5 Out-of-corpus questions

**Question Types**:
- `direct_definition`: "What does X state about Y?"
- `section_specific`: "Describe the provisions in X"
- `paraphrased`: Simplified/alternative wording
- `consequence_effect`: "What happens if..."
- `multi_section`: Requires multiple sections
- `out_of_corpus`: Information NOT in corpus

### Step 4: Test Out-of-Corpus Questions

For OOC questions, actually run them through retriever:

```python
try:
    results = retriever.retrieve(ooc_question, top_k=5)
    retrieved_sections = [
        {
            "document_name": r.record.document_name,
            "section": r.record.section,
            "score": float(r.score)
        }
        for r in results
    ]
except Exception:
    retrieved_sections = []
```

Record actual retrieval results in dataset:
```json
{
  "id": "Q029",
  "question": "What is the exchange rate for cryptocurrency?",
  "is_out_of_corpus": true,
  "retrieved_sections": [
    {"document_name": "indian_contract_act_1872.pdf", "section": "3", "score": 0.52},
    ...
  ]
}
```

This shows system's fallback behavior for OOC questions.

## Evaluation Schema (v2.0)

Updated dataset structure:

```json
{
  "metadata": {
    "version": "2.0",
    "created_at": "2026-09-06",
    "corpus": "MVP Legal Documents (Real)",
    "total_questions": 30,
    "in_corpus_questions": 25,
    "out_of_corpus_questions": 5,
    "notes": "All in-corpus questions grounded in actual indexed chunks"
  },
  "questions": [
    {
      "id": "Q001",
      "question": "What does the Definitions section state?",
      "expected_document": "indian_contract_act_1872.pdf",
      "expected_section": "1",
      "expected_chunk_id": "chunk-abc-123",
      "question_type": "direct_definition",
      "context": "Direct question about Section 1",
      "is_out_of_corpus": false
    },
    {
      "id": "Q026",
      "question": "What is the exchange rate for cryptocurrency?",
      "is_out_of_corpus": true,
      "retrieved_sections": [
        {"document_name": "...", "section": "...", "score": 0.52}
      ]
    }
  ]
}
```

### Key Fields

- `expected_document`: EXACT filename from corpus
- `expected_section`: EXACT section from chunk metadata
- `expected_chunk_id`: Chunk ID for precise matching (optional)
- `is_out_of_corpus`: Boolean flag for OOC questions
- `retrieved_sections`: For OOC, record what retriever actually returns

## Evaluation Metrics

### Recall@K

**Definition**: Fraction of in-corpus questions where expected section/chunk appears in top-K results

**Calculation**:
```
Recall@K = (# questions with expected in top-K) / (# in-corpus questions)
```

**Interpretation**:
- Recall@1 > 0.70: Good - most questions answered immediately
- Recall@3 > 0.85: Good - most questions in top 3
- Recall@5 > 0.90: Good - vast majority in top 5

### MRR (Mean Reciprocal Rank)

**Definition**: Average of 1/rank for questions where expected section found

**Calculation**:
```
MRR = Sum(1 / rank_of_expected) / (# in-corpus questions)
```

**Interpretation**:
- MRR > 0.75: Good - average rank is ~1.3
- Measures ranking quality, not just binary match

### Out-of-Corpus Detection Rate

**Definition**: Proportion of OOC questions correctly identified

**Calculation**:
```
OOC Rate = (# out-of-corpus questions) / (# total questions)
```

**Interpretation**:
- High OOC rate appropriate if question mix is naturally OOC
- Shows system gracefully handles unanswerable questions

### Metrics by Question Type

Separate Recall@K and MRR for each type:
- `direct_definition`
- `section_specific`
- `paraphrased`
- `consequence_effect`
- `multi_section`
- `out_of_corpus`

Identifies which question patterns are easiest/hardest.

## Running the Evaluation

### Step 1: Build Valid Dataset

```bash
python build_valid_evaluation_dataset.py
```

**Output**:
- Inspects all indexed chunks
- Creates 25-30 grounded questions
- Saves to `data/evaluation_dataset.json`

### Step 2: Run Evaluation

```bash
python run_evaluation_real.py
```

**Output**:
- Runs all 30 questions through retriever
- Calculates all metrics
- Shows failure analysis
- Identifies out-of-corpus questions
- Saves full results to `data/evaluation_results.json`

**Console Output**:
```
============================================================
LEGAL RAG RETRIEVAL EVALUATION
============================================================

📊 SUMMARY METRICS:
  Total Questions: 30
  In-Corpus Questions: 25
  Out-of-Corpus Questions: 5

✅ RETRIEVAL PERFORMANCE:
  Recall@1:  0.7600 (19/25)
  Recall@3:  0.8400 (21/25)
  Recall@5:  0.9200 (23/25)
  MRR:       0.8145

📊 METRICS BY QUESTION TYPE:
  DIRECT DEFINITION (n=7):
    Recall@1: 0.8571
    Recall@3: 0.8571
    Recall@5: 1.0000
    MRR:      0.8571
  ...

❌ FAILURES - Questions NOT found in top-5:
   Total: 2
   
   Q: Q015 - What does Section 15 state about offer and acceptance?
      Expected: 15
      Retrieved: [12, 13, 14, 16, 17]
      Scores: [0.72, 0.70, 0.68, 0.67, 0.65]
   ...
```

### Step 3: View Results

Via Streamlit dashboard:
```bash
streamlit run app.py
```

Navigate to **Evaluation** page to see:
- Summary metrics and targets
- Performance by question type
- Individual result listing
- Detailed case analysis
- Recall curve visualization

## Interpretation Guide

### High Recall@1 (>0.75)
✅ Retriever is finding correct sections immediately
- Good embedding model alignment
- Well-clustered semantic space

### High Recall@3-5 but low Recall@1
⚠️ Correct answer is there but not ranked first
- Re-ranking might help
- Check similarity threshold
- Review embedding quality

### Low Recall@5 (<0.90)
❌ Correct sections not being retrieved
- Possible corpus gaps
- Embedding model mismatch
- Similarity threshold too high
- Question too dissimilar from corpus

### MRR significantly below Recall@5
⚠️ When correct answer is found, it's ranked low
- Ranking algorithm issues
- Multiple similar documents confusing retriever

### Out-of-Corpus Questions Retrieved as "Answers"
⚠️ System doesn't recognize unanswerable questions
- Too low similarity threshold
- Need confidence scoring
- Add "I don't know" detection

## Failure Analysis

Every failed question shows:

```
❌ Q015 - "What does Section 15 state?"
   Expected Section: 15
   Expected Chunk ID: chunk-015-abc123
   Retrieved Sections: [12, 13, 14, 16, 17]
   Scores: [0.72, 0.70, 0.68, 0.67, 0.65]
   Rank of Expected: None (not in top-5)
```

### Analysis Questions

1. **Why was chunk-015-abc123 not retrieved?**
   - Check embedding similarity
   - Verify chunk text quality
   - Review chunking boundaries

2. **Why did Section 12-14 rank higher?**
   - Look at question words vs those sections
   - Check for spurious term overlap
   - Evaluate semantic relevance

3. **Is this a fair question?**
   - Is expected section actually relevant?
   - Is question ambiguous?
   - Does corpus have gaps?

## Validation Checklist

Before finalizing evaluation dataset:

- [ ] All in-corpus expected_document values exist in actual corpus
- [ ] All in-corpus expected_section values match chunk metadata exactly
- [ ] expected_chunk_id values are real chunk IDs from vector store
- [ ] Out-of-corpus questions tested and retrieval results recorded
- [ ] Question types balanced (5-7 per major type)
- [ ] All document categories represented
- [ ] Questions are diverse (not all similar difficulty)
- [ ] No questions are trivial (obvious answer)
- [ ] No questions are impossibly hard

## Files

- `data/evaluation_dataset.json` - Valid grounded dataset (v2.0)
- `data/evaluation_results.json` - Baseline metrics and failure analysis
- `build_valid_evaluation_dataset.py` - Dataset builder
- `run_evaluation_real.py` - Evaluation runner with failure analysis
- `src/evaluation/evaluator.py` - Updated evaluator supporting new schema
- `pages/3_Evaluation.py` - Streamlit dashboard

## Next Steps

1. ✅ Run `build_valid_evaluation_dataset.py`
2. ✅ Review generated dataset for accuracy
3. ✅ Run `run_evaluation_real.py` to get baseline
4. ✅ View results in Streamlit dashboard
5. ✅ Analyze failures and identify improvement areas
6. 🔄 Iterate on retriever/embedding configuration
7. 🔄 Re-run evaluation to measure improvements
