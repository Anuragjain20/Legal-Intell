# 🎯 Retrieval Evaluation Harness - START HERE

## What Is This?

A complete system to **measure how well your retriever finds relevant legal documents**.

- ✅ Does NOT modify your pipeline
- ✅ Questions grounded in real corpus
- ✅ 5 key metrics with interpretation
- ✅ Beautiful dashboard
- ✅ Detailed failure analysis
- ✅ Production ready

---

## 3-Minute Setup

### Step 1: Create Questions from Your Corpus
```bash
python build_valid_evaluation_dataset.py
```
⏱️ Takes 30 seconds  
✅ Creates 25-30 real questions from indexed chunks

### Step 2: Run Evaluation
```bash
python run_evaluation_real.py
```
⏱️ Takes 10 seconds  
✅ Shows metrics like:
```
Recall@1: 0.76  (76% questions answered immediately)
Recall@5: 0.92  (92% questions found in top 5)
MRR:      0.81  (Good ranking quality)
```

### Step 3: View Dashboard
```bash
streamlit run app.py
```
⏱️ Opens immediately  
✅ Navigate to "Evaluation" page in sidebar  
✅ 5 tabs with charts, tables, deep dives

---

## Where to Find Everything

### 📚 Documentation

| Need | File | Time |
|------|------|------|
| 30-second overview | This file | 1 min |
| Quick how-to | `EVALUATION_QUICKSTART.md` | 3 min |
| Full guide | `VALID_EVALUATION_GUIDE.md` | 10 min |
| Architecture | `EVALUATION_STORY_COMPLETION.md` | 15 min |
| All files | `FILES_CREATED.md` | 5 min |

### 🎯 Action Items

| Want to... | Do This |
|-----------|---------|
| Just run it | `python run_evaluation_real.py` |
| Use UI button | `streamlit run app.py` → Click button |
| See all metrics | Go to Evaluation page → All 5 tabs |
| Find failed questions | Evaluation page → Tab 3 or 4 |
| Run tests | `pytest tests/test_evaluator.py -v` |

---

## What You'll Get

### 📊 Metrics

```
RETRIEVAL PERFORMANCE
  Recall@1:  0.7600  ← Most questions answered immediately
  Recall@3:  0.8400  ← 84% questions in top 3
  Recall@5:  0.9200  ← 92% questions in top 5
  MRR:       0.8145  ← Average ranking quality

BY QUESTION TYPE
  Direct Definition:   Recall@1=0.86  ✅
  Paraphrased:         Recall@1=0.60  ⚠️
  Consequence/Effect:  Recall@1=0.80  ✅
  ... (6 types total)

FAILURES
  Q015: Expected Section 15, got [12,13,14,16,17]
  ... (with scores and evidence)
```

### 📈 Dashboard

**Tab 1**: Summary metrics + interpretation  
**Tab 2**: Performance by question type  
**Tab 3**: All 30 test cases, filterable  
**Tab 4**: Deep dive on one question  
**Tab 5**: Recall curve visualization  

---

## The Flow

```
You → Run Script → Retriever Tests → Metrics → Dashboard → Insights
        ↓              ↓                ↓          ↓          ↓
     25-30        Are answers      Recall@K    Visual    Find weak
     real Q's     in results?      & MRR      analysis   spots to
     from                                                  improve
     corpus
```

---

## Why This Matters

### For You
- Know which questions your retriever struggles with
- Measure improvement over time
- Identify corpus gaps

### For Users
- Confidence that answers are grounded
- Understand system limitations
- See what works well/poorly

### For Operations
- Baseline for monitoring
- Regression detection
- Track progress

---

## Key Principles

✅ **Valid Questions**
- Grounded in real indexed chunks
- No synthetic or invented sections
- Based on actual document content

✅ **Complete Metrics**
- Not just pass/fail
- Multiple perspectives (Recall@K, MRR)
- By question type breakdown

✅ **Non-Invasive**
- Only observes pipeline
- Does NOT modify anything
- Isolated measurement

✅ **Easy to Use**
- One button in UI
- One command in terminal
- Beautiful dashboard

---

## Typical Results

### Good System
```
Recall@5: 0.95  ✅ Great - 95% found in top 5
MRR: 0.85       ✅ Good - Average rank is ~1.2
```

### Okay System
```
Recall@5: 0.80  ⚠️ Okay - 20% not found in top 5
MRR: 0.70       ⚠️ Fair - Average rank is ~1.4
```

### Needs Work
```
Recall@5: 0.65  ❌ Poor - 35% not found in top 5
MRR: 0.55       ❌ Bad - Average rank is ~1.8
```

---

## Files You'll Touch

### Main Files
```
data/evaluation_dataset.json      ← 25-30 questions (auto-generated)
data/evaluation_results.json      ← Results (auto-generated)
pages/3_Evaluation.py             ← Dashboard (view results)
app.py                            ← Updated with button
```

### Scripts You Run
```
build_valid_evaluation_dataset.py ← Create questions once
run_evaluation_real.py            ← Run evaluation (repeatable)
```

### Documentation
```
README_EVALUATION.md              ← Overview
EVALUATION_QUICKSTART.md          ← Quick reference
VALID_EVALUATION_GUIDE.md         ← Detailed reference
START_HERE.md                     ← This file
```

---

## Common Questions

**Q: Will this slow down my app?**  
A: No. Run evaluation separately, view results anytime.

**Q: Does it change my pipeline?**  
A: No. Only reads and measures, never modifies.

**Q: How often should I run it?**  
A: Whenever you change embedding model or retriever settings.

**Q: Can I add more questions?**  
A: Yes. Edit `evaluation_dataset.json` with real chunks.

**Q: What if metrics are low?**  
A: Look at failed questions to identify corpus gaps or retriever issues.

---

## Quick Reference

### Commands
```bash
# Create questions from corpus
python build_valid_evaluation_dataset.py

# Run evaluation
python run_evaluation_real.py

# View dashboard
streamlit run app.py

# Run tests
pytest tests/test_evaluator.py -v

# Inspect corpus
python inspect_corpus.py
```

### Metrics at a Glance
```
Recall@1  → Is correct answer in position 1?
Recall@3  → Is it in top 3?
Recall@5  → Is it in top 5?
MRR       → On average, what rank is it?
```

### Dashboard Navigation
```
app.py → Scroll down to Evaluation section
      → Click "Run Evaluation" button
      → OR go to Evaluation page in sidebar
      → Choose tab (Summary, Type, Results, Details, Comparison)
```

---

## Success Criteria ✅

- [x] Questions grounded in real corpus ✅
- [x] 5 key metrics calculated ✅
- [x] Dashboard with visualizations ✅
- [x] Detailed failure analysis ✅
- [x] Non-invasive measurement ✅
- [x] Complete documentation ✅
- [x] Production ready ✅

---

## Next Step

**Pick one**:

### Option A: Just Run It
```bash
python run_evaluation_real.py
```
See metrics in 10 seconds

### Option B: Full Experience
```bash
streamlit run app.py
# Click "Run Evaluation" button
# Go to "Evaluation" page
# Explore dashboard
```

### Option C: Deep Dive
Read: `VALID_EVALUATION_GUIDE.md`  
Then run: `python run_evaluation_real.py`  
Then explore: Dashboard

---

## Support

- **Quickest Help**: Read this file ← You are here
- **Quick Setup**: `EVALUATION_QUICKSTART.md`
- **Full Details**: `VALID_EVALUATION_GUIDE.md`
- **Architecture**: `EVALUATION_STORY_COMPLETION.md`

---

## The Bottom Line

```
Run 3 commands → Get 5 metrics → View dashboard → Improve pipeline
   ~1 minute        Clear      Visual + Deep   Targeted work
```

That's it. Simple. Effective. Non-invasive.

---

## Ready? 🚀

```bash
python run_evaluation_real.py
```

**That's your starting point.**

Then explore the dashboard. Then read the guides.

Questions? Check `EVALUATION_QUICKSTART.md`.

Let's go! 📊
