# Legal Document Comparison: LG-RAG-029

## Goal

Compare two legal documents (or versions) to identify **meaningful changes** in structure, clauses, obligations, and terms.

Move beyond "diff" (character-level) to **semantic comparison** (clause-level understanding).

## The Problem

**Without LG-RAG-029:**
```
User: "What changed between v1 and v2?"
System: Shows character-level diff
  "Old: liability is unlimited
   New: liability capped at $100,000"
  
But also shows:
  - Whitespace changes
  - Line break changes
  - Moved sections (flagged as added + removed)
  - Punctuation changes
  
User: Must manually parse what actually matters
Result: Slow, error-prone, easy to miss critical changes
```

**With LG-RAG-029:**
```
User: "What changed between v1 and v2?"
System: Returns structured comparison:

MODIFIED OBLIGATIONS:
  ✓ Payment Terms
    - Deadline: 30 days → 45 days (+15 days favorable)
    - Late penalty: 5% monthly → 2% monthly (-3% favorable)
    - Total impact: +$15,000 cash flow improvement

MODIFIED RIGHTS:
  ✗ Termination Right
    - Changed from: "at-will" termination
    - Changed to: "for cause only" (-freedom favorable)
    - Penalty for wrongful termination: NEW $500K clause

REMOVED CLAUSES:
  - Section 3.2: Confidentiality (3-year duration)
  - Section 5.1: IP Assignment (why removed? Flag for review)

RISKS INTRODUCED:
  ⚠️ CRITICAL: Liability cap reduced 50%
  ⚠️ HIGH: Indemnification expanded to cover "any claims"

Result: User gets actionable summary in seconds
```

## Architecture

```
Document A (v1)          Document B (v2)
      ↓                         ↓
[Normalize & Parse]
      ↓                         ↓
Structure Extraction
  - Extract sections
  - Extract obligations
  - Extract rights
  - Extract conditions
      ↓                         ↓
Semantic Chunking
  - Group by meaning
  - Preserve context
  - Track relationships
      ↓                         ↓
Alignment & Matching
  - Map equivalent clauses
  - Detect moved sections
  - Handle rephrasing
      ↓
Comparison Engine
  - Calculate similarity
  - Classify changes
  - Extract impact
      ↓
Structured Output
{
  "added": [...],           // New clauses in B
  "removed": [...],         // Removed from B
  "modified": [...],        // Changed in B
  "moved": [...],           // Relocated in B
  "unchanged": [...]        // Same in both
}
      ↓
Analysis Layer
  - Impact scoring
  - Risk assessment
  - Highlight critical changes
  - Generate summary
      ↓
Output Formats
  - JSON (programmatic)
  - Markdown (readable)
  - HTML/PDF (shareable)
  - Side-by-side (interactive)
```

## Core Concepts

### 1. Change Types

#### A. Added Clause
**Definition:** Clause exists in Document B but not in Document A

**Example:**
```
v1: (no indemnification clause)
v2: "7.1 Indemnification
     Company shall indemnify and hold harmless all third-party claims
     arising from Company's use of the Software..."

Change: ADDED
Impact: HIGH (new obligation)
Risk: CRITICAL (unlimited indemnification)
```

**Detection:**
- Not present in v1
- Present in v2
- No counterpart in v1 (semantic matching)

#### B. Removed Clause
**Definition:** Clause exists in Document A but removed from Document B

**Example:**
```
v1: "5.2 License Grant
     Licensor grants non-exclusive license..."
v2: (section removed)

Change: REMOVED
Impact: HIGH (lost right)
Risk: MEDIUM (loss of access)
```

**Detection:**
- Present in v1
- Not present in v2
- No obvious relocation

#### C. Modified Clause
**Definition:** Clause exists in both documents but with meaningful changes

**Example:**
```
v1: "4.2 Payment
     Buyer shall pay within 30 days
     Late penalty: 5% per month"

v2: "4.2 Payment
     Buyer shall pay within 45 days
     Late penalty: 2% per month"

Changes:
  - Deadline: 30 → 45 days (FAVORABLE: +15 days)
  - Penalty: 5% → 2% (FAVORABLE: -3%)
  - Overall: FAVORABLE
```

**Modification Types:**
- **Numeric Change:** 30 → 45 (deadline, amount, percentage)
- **Conditional Addition:** "unless" clause added
- **Scope Expansion/Reduction:** "all claims" → "direct claims only"
- **Definition Change:** Term redefined
- **Structure Change:** Split into subsections or consolidated

#### D. Moved Clause
**Definition:** Clause exists in both documents but at different location

**Example:**
```
v1: "Section 5: Intellectual Property"
v2: "Section 7: Intellectual Property"
    (Content identical, but moved)

Change: MOVED
Impact: LOW (no substantive change)
```

**Detection:**
- High semantic similarity (>0.95)
- Different section numbers
- Same content (word-for-word or minor formatting)

#### E. Rephrased Clause
**Definition:** Same obligation but expressed differently

**Example:**
```
v1: "Seller shall deliver goods within 10 business days"
v2: "Delivery must occur no later than two calendar weeks"

Semantic: Same obligation (but different duration math)
Change: REPHRASED + MODIFIED
Impact: MEDIUM (subtle deadline change)
```

**Detection:**
- Similar semantic meaning
- Different wording/structure
- Subtle parameter changes

### 2. Impact Scoring

**Dimensions:**

#### Favorability (for party receiving comparison)
- **FAVORABLE:** Reduces obligations, increases rights, reduces penalties
- **NEUTRAL:** No material change
- **UNFAVORABLE:** Increases obligations, reduces rights, increases penalties
- **CRITICAL:** Major shift in legal exposure

#### Magnitude
- **MAJOR:** Affects financial terms, termination rights, or core obligations
- **MODERATE:** Affects secondary obligations, clarifications
- **MINOR:** Formatting, grammar, non-substantive clarifications

#### Risk Level
- **CRITICAL:** Legal exposure, liability, termination triggers
- **HIGH:** Financial impact, operational impact
- **MEDIUM:** Administrative burden, monitoring requirements
- **LOW:** Informational, courtesy, non-binding

**Impact Score Formula:**
```
Impact Score = (Magnitude × Favorability Multiplier × Risk Weight) / 3

Magnitude: MAJOR=3, MODERATE=2, MINOR=1
Favorability: UNFAVORABLE=1.5, NEUTRAL=1.0, FAVORABLE=0.5
Risk: CRITICAL=1.5, HIGH=1.2, MEDIUM=0.8, LOW=0.5

Example:
  Unfavorable MAJOR change with CRITICAL risk:
  (3 × 1.5 × 1.5) / 3 = 2.25 → HIGHEST PRIORITY
```

### 3. Comparison Strategies

#### Strategy 1: Section-Level Comparison
**Approach:** Compare document sections one-by-one

**Pros:**
- ✅ Preserves document structure
- ✅ Clear before/after for each section
- ✅ Good for identifying section movement

**Cons:**
- ❌ Misses cross-section impacts
- ❌ May miss clause relocation

#### Strategy 2: Clause-Level Comparison
**Approach:** Extract clauses, match semantically, compare independently

**Pros:**
- ✅ Semantic matching handles rephrasing
- ✅ Detects clause movement across sections
- ✅ More granular changes

**Cons:**
- ❌ Loses document structure
- ❌ More computation

#### Strategy 3: Obligation-Level Comparison (Recommended)
**Approach:** Extract obligations (LG-RAG-028), compare structured data

**Pros:**
- ✅ Understands meaning, not just text
- ✅ Can identify rephrased obligations
- ✅ Shows impact on business terms
- ✅ Can detect conditional changes

**Cons:**
- ❌ Depends on extraction quality
- ❌ May miss non-obligation content

### 4. Similarity Scoring

**Semantic Similarity:**
```
similarity = cosine_similarity(embedding_v1, embedding_v2)

Thresholds:
- > 0.95: Likely same clause (moved/reformatted)
- 0.85-0.95: Likely same clause with minor changes (rephrased)
- 0.70-0.85: Related clause (similar topic, possibly modified)
- 0.50-0.70: Possibly related (needs human review)
- < 0.50: Different clause
```

**Lexical Similarity (Fallback):**
```
Jaccard similarity: intersection(tokens_v1, tokens_v2) / union(...)
Levenshtein distance: character-level edit distance

Used when semantic similarity unavailable or for verification.
```

**Structural Similarity:**
```
If section headers match and position similar → high probability same section
If headers changed but content > 0.85 similarity → possibly moved
```

## Data Models

```python
@dataclass(frozen=True)
class ClauseLocation:
    """Where a clause exists in document."""
    document_id: str
    section: str              # "4.2"
    section_name: str         # "Payment Terms"
    page_number: int
    line_numbers: str         # "12-15"
    subsection_path: list[str]  # ["4", "2", "a"]

@dataclass(frozen=True)
class TextChange:
    """Specific text change within a clause."""
    change_type: str          # "NUMERIC", "CONDITIONAL", "SCOPE", "DEFINITION"
    location: str             # "deadline", "penalty_rate", "scope"
    old_value: str | None
    new_value: str | None
    magnitude: str            # "MAJOR", "MODERATE", "MINOR"
    impact: str               # "FAVORABLE", "NEUTRAL", "UNFAVORABLE"

@dataclass(frozen=True)
class Clause:
    """Extracted clause from document."""
    clause_id: str
    title: str                # "Payment Terms"
    text: str
    obligations: list[str]    # IDs of obligations in this clause
    location: ClauseLocation
    embedding: list[float] | None  # Vector representation

@dataclass(frozen=True)
class ClauseComparison:
    """Comparison of two versions of a clause."""
    clause_id: str
    change_type: str          # "ADDED", "REMOVED", "MODIFIED", "MOVED", "UNCHANGED"
    
    # For ADDED/REMOVED
    clause_v1: Clause | None  # None if ADDED
    clause_v2: Clause | None  # None if REMOVED
    
    # For MODIFIED
    text_changes: list[TextChange]
    similarity_score: float   # 0.0-1.0
    
    # Impact assessment
    favorability: str         # "FAVORABLE", "NEUTRAL", "UNFAVORABLE"
    magnitude: str            # "MAJOR", "MODERATE", "MINOR"
    risk_level: str           # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    
    # For MOVED
    old_location: ClauseLocation | None
    new_location: ClauseLocation | None
    
    # Overall assessment
    impact_score: float       # 0.0-1.0 (higher = more impactful)
    summary: str              # Human-readable summary
    recommendation: str       # Action recommended (negotiate, accept, flag)

@dataclass(frozen=True)
class DocumentComparison:
    """Complete comparison between two documents."""
    document_v1_id: str
    document_v2_id: str
    
    comparisons: list[ClauseComparison]
    
    # Aggregates
    added_count: int
    removed_count: int
    modified_count: int
    moved_count: int
    unchanged_count: int
    
    # Summary statistics
    total_changes: int
    favorable_changes: int
    unfavorable_changes: int
    critical_risks_introduced: int
    
    # Recommendations
    critical_items: list[ClauseComparison]  # Flagged for review
    favorable_items: list[ClauseComparison]  # Wins for this party
    
    comparison_time_ms: float
    confidence_score: float   # 0.0-1.0 overall confidence
```

---

## Comparison Methods

### Method 1: Semantic Matching (LLM-based)

**Approach:** Use embeddings and LLM to understand clause similarity

```python
class SemanticComparator:
    def __init__(self, embedding_model):
        self.embeddings = embedding_model
    
    def compare(self, clause_v1: Clause, clause_v2: Clause):
        # Embed both clauses
        emb_v1 = self.embeddings.embed(clause_v1.text)
        emb_v2 = self.embeddings.embed(clause_v2.text)
        
        # Calculate similarity
        similarity = cosine_similarity(emb_v1, emb_v2)
        
        # If similar enough, analyze changes
        if similarity > 0.85:
            changes = self.extract_text_changes(clause_v1, clause_v2)
            return ClauseComparison(
                change_type="MODIFIED",
                text_changes=changes,
                similarity_score=similarity
            )
        else:
            return None  # Different clauses
```

**Pros:**
- ✅ Understands rephrasing
- ✅ Handles moved clauses
- ✅ Semantic matching

**Cons:**
- ❌ Expensive (embedding cost)
- ❌ Variable quality by model

### Method 2: Structure-Aware Diff

**Approach:** Leverage document structure (sections, subsections) + fuzzy matching

```python
class StructureAwareDiffer:
    def compare(self, doc_v1: Document, doc_v2: Document):
        comparisons = []
        
        # Map sections by number/name
        sections_v1 = {s.number: s for s in doc_v1.sections}
        sections_v2 = {s.number: s for s in doc_v2.sections}
        
        # Compare matching sections
        for section_num in sections_v1:
            if section_num in sections_v2:
                # Sections with same number: compare content
                diff = self.diff_sections(
                    sections_v1[section_num],
                    sections_v2[section_num]
                )
                comparisons.extend(diff)
            else:
                # Section removed
                comparisons.append(ClauseComparison(
                    change_type="REMOVED",
                    clause_v1=sections_v1[section_num]
                ))
        
        # Added sections
        for section_num in sections_v2:
            if section_num not in sections_v1:
                comparisons.append(ClauseComparison(
                    change_type="ADDED",
                    clause_v2=sections_v2[section_num]
                ))
        
        return DocumentComparison(comparisons=comparisons)
```

**Pros:**
- ✅ Fast (no embedding cost)
- ✅ Preserves structure
- ✅ Good baseline

**Cons:**
- ❌ Misses rephrasing
- ❌ Misses moved sections

### Method 3: Obligation-Level Comparison (Recommended)

**Approach:** Extract obligations (LG-RAG-028), compare structured data

```python
class ObligationComparator:
    def __init__(self, obligation_extractor):
        self.extractor = obligation_extractor
    
    def compare(self, doc_v1: Document, doc_v2: Document):
        # Extract obligations from both
        obligations_v1 = self.extractor.extract_all(doc_v1.text)
        obligations_v2 = self.extractor.extract_all(doc_v2.text)
        
        # Match obligations
        matches = self.match_obligations(obligations_v1, obligations_v2)
        
        comparisons = []
        for match in matches:
            if match.type == "ADDED":
                comparisons.append(ClauseComparison(
                    change_type="ADDED",
                    summary=f"New obligation: {match.obligation_v2.action}"
                ))
            elif match.type == "REMOVED":
                comparisons.append(ClauseComparison(
                    change_type="REMOVED",
                    summary=f"Removed obligation: {match.obligation_v1.action}"
                ))
            elif match.type == "MODIFIED":
                changes = self.extract_changes(
                    match.obligation_v1,
                    match.obligation_v2
                )
                comparisons.append(ClauseComparison(
                    change_type="MODIFIED",
                    text_changes=changes
                ))
        
        return DocumentComparison(comparisons=comparisons)
    
    def match_obligations(self, obs_v1, obs_v2):
        """Match obligations between versions."""
        matches = []
        used_v2 = set()
        
        for ob1 in obs_v1:
            # Find best match in v2
            best_match = None
            best_similarity = 0.0
            
            for ob2 in obs_v2:
                if ob2.obligation_id in used_v2:
                    continue
                
                # Similarity based on actor + action
                similarity = self.obligation_similarity(ob1, ob2)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = ob2
            
            if best_similarity > 0.7:
                # Found match
                matches.append(Match(
                    type="MODIFIED" if best_similarity < 0.95 else "UNCHANGED",
                    obligation_v1=ob1,
                    obligation_v2=best_match
                ))
                used_v2.add(best_match.obligation_id)
            else:
                # No match: obligation removed
                matches.append(Match(
                    type="REMOVED",
                    obligation_v1=ob1
                ))
        
        # Remaining in v2 are added
        for ob2 in obs_v2:
            if ob2.obligation_id not in used_v2:
                matches.append(Match(
                    type="ADDED",
                    obligation_v2=ob2
                ))
        
        return matches
```

**Pros:**
- ✅ Semantic understanding
- ✅ Handles rephrasing
- ✅ Shows business impact
- ✅ Can extract specific changes

**Cons:**
- ❌ Depends on extraction quality
- ❌ May miss non-obligation content

---

## Acceptance Criteria

✅ **Section-aware comparison**
- Identify sections in both documents
- Compare matching sections
- Flag moved sections
- Detect new/removed sections

✅ **Added/removed/modified clause detection**
- Classify changes correctly
- Distinguish from moving clauses
- Handle rephrased clauses (semantic matching)

✅ **Changed obligations identified**
- Track obligation changes (added, removed, modified)
- Extract specific parameter changes (deadline, amount, penalty)
- Link to source clauses

✅ **Changed conditions extracted**
- Identify new/removed conditions
- Track condition modifications
- Show impact on obligation triggers

✅ **Structured comparison output**
- JSON format for programmatic use
- Side-by-side view for manual review
- Summary report highlighting critical changes
- CSV export for spreadsheet analysis

✅ **Impact scoring and prioritization**
- Favorable/unfavorable assessment
- Risk level classification
- Priority ranking for review

✅ **Quality and confidence metrics**
- Confidence score for each comparison
- Precision/recall on test set
- Latency <5 seconds for typical contract

---

## Testing Strategy

### Unit Tests

```python
def test_added_clause_detection():
    """Detect newly added clause."""
    v1 = "Section 4: Payment\nBuyer shall pay by June 1"
    v2 = """Section 4: Payment
             Buyer shall pay by June 1
             
             Section 5: Indemnification
             Company shall indemnify all claims"""
    
    comparison = comparator.compare(v1, v2)
    
    added = [c for c in comparison.comparisons if c.change_type == "ADDED"]
    assert len(added) == 1
    assert "Indemnification" in added[0].clause_v2.text

def test_removed_clause_detection():
    """Detect removed clause."""
    v1 = """Section 4: Warranty
            Seller warrants goods are fit
            
            Section 5: Payment
            Buyer shall pay"""
    v2 = "Section 5: Payment\nBuyer shall pay"
    
    comparison = comparator.compare(v1, v2)
    
    removed = [c for c in comparison.comparisons if c.change_type == "REMOVED"]
    assert len(removed) == 1
    assert "Warranty" in removed[0].clause_v1.text

def test_modified_deadline_detection():
    """Extract changed deadline."""
    v1 = "Payment due within 30 days"
    v2 = "Payment due within 45 days"
    
    comparison = comparator.compare(v1, v2)
    
    modified = [c for c in comparison.comparisons if c.change_type == "MODIFIED"][0]
    assert len(modified.text_changes) == 1
    
    change = modified.text_changes[0]
    assert change.location == "deadline"
    assert change.old_value == "30 days"
    assert change.new_value == "45 days"
    assert change.impact == "FAVORABLE"

def test_moved_clause_detection():
    """Detect clause moved to different section."""
    v1 = """Section 3: IP Rights
            Licensor owns all IP
            
            Section 4: Payment
            Buyer pays $100"""
    v2 = """Section 4: Payment
            Buyer pays $100
            
            Section 5: IP Rights
            Licensor owns all IP"""
    
    comparison = comparator.compare(v1, v2)
    
    moved = [c for c in comparison.comparisons if c.change_type == "MOVED"]
    assert len(moved) == 1

def test_rephrased_obligation_detection():
    """Handle obligation rephrased differently."""
    v1 = "Seller shall deliver goods by June 1"
    v2 = "Delivery must occur no later than June 1"
    
    comparison = comparator.compare(v1, v2)
    
    # Should recognize as same obligation (not new/removed)
    comparisons = [c for c in comparison.comparisons if c.change_type != "UNCHANGED"]
    assert len(comparisons) == 0 or all(
        c.change_type in ["MODIFIED", "REPHRASED"] for c in comparisons
    )

def test_impact_scoring():
    """Calculate impact scores correctly."""
    unfavorable_major = ClauseComparison(
        change_type="MODIFIED",
        favorability="UNFAVORABLE",
        magnitude="MAJOR",
        risk_level="CRITICAL"
    )
    
    score = impact_scorer.score(unfavorable_major)
    assert score > 2.0  # HIGH priority

def test_similarity_scoring():
    """Semantic similarity scores in valid range."""
    v1_text = "Seller shall deliver goods by June 1"
    v2_text = "Delivery must occur no later than June 1"
    
    similarity = semantic_scorer.score(v1_text, v2_text)
    assert 0.85 <= similarity <= 1.0  # High similarity (same meaning)

def test_conflicting_clauses():
    """Detect contradictory changes."""
    v1 = """Section 4: Liability
            Liability unlimited
            
            Section 5: Cap
            No liability cap"""
    v2 = """Section 4: Liability
            Liability capped at $100K
            
            Section 5: Cap
            Liability cap of $100K"""
    
    comparison = comparator.compare(v1, v2)
    
    # Should flag as related changes with same impact
    liability_changes = [
        c for c in comparison.comparisons 
        if "liab" in c.clause_v1.text.lower() or 
           "liab" in c.clause_v2.text.lower()
    ]
    assert len(liability_changes) >= 2
```

### Integration Tests

```python
def test_real_contract_comparison():
    """Compare realistic contract versions."""
    v1 = load_contract("employment_agreement_v1.docx")
    v2 = load_contract("employment_agreement_v2.docx")
    
    comparison = comparator.compare(v1, v2)
    
    # Validate structure
    assert comparison.total_changes == comparison.added_count + \
           comparison.removed_count + comparison.modified_count + \
           comparison.moved_count
    
    # Should identify material changes
    critical = comparison.critical_items
    assert len(critical) > 0
    
    # Should show favorability breakdown
    assert comparison.favorable_changes >= 0
    assert comparison.unfavorable_changes >= 0

def test_multi_section_changes():
    """Handle complex multi-section changes."""
    v1 = load_contract("complex_contract_v1.pdf")
    v2 = load_contract("complex_contract_v2.pdf")
    
    comparison = comparator.compare(v1, v2)
    
    # Verify all changes captured
    total_in_v2 = count_unique_clauses(v2)
    total_in_v1 = count_unique_clauses(v1)
    
    # All clauses should be accounted for
    assert comparison.total_changes >= abs(total_in_v2 - total_in_v1)

def test_cross_version_obligation_tracking():
    """Track obligation changes across versions."""
    v1 = load_contract("service_agreement_v1.txt")
    v2 = load_contract("service_agreement_v2.txt")
    
    comparison = comparator.compare(v1, v2)
    
    # Extract obligation comparisons
    obligation_changes = [
        c for c in comparison.comparisons 
        if c.change_type != "UNCHANGED"
    ]
    
    # Verify specific changes
    assert any(
        "payment" in c.summary.lower() 
        for c in obligation_changes
    )
```

### Evaluation Tests

```python
def test_comparison_precision_recall():
    """Measure precision/recall on annotated dataset."""
    eval_set = load_evaluation_set("contracts_with_change_annotations.json")
    
    tp, fp, fn = 0, 0, 0
    for v1, v2, annotations in eval_set:
        comparison = comparator.compare(v1, v2)
        
        detected_changes = {c.clause_id: c.change_type for c in comparison.comparisons}
        annotated_changes = {a.clause_id: a.change_type for a in annotations}
        
        for clause_id in annotated_changes:
            if clause_id in detected_changes:
                if detected_changes[clause_id] == annotated_changes[clause_id]:
                    tp += 1
                else:
                    fp += 1  # Wrong change type
            else:
                fn += 1  # Missed change
        
        # False positives
        fp += len(detected_changes) - len(detected_changes & annotated_changes)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    # Target: precision > 0.90, recall > 0.85, F1 > 0.87
    assert precision > 0.90
    assert recall > 0.85
    assert f1 > 0.87
```

---

## Usage Examples

### Example 1: Basic Comparison

```python
from src.comparison.document_comparator import DocumentComparator

# Initialize comparator
comparator = DocumentComparator(
    method="semantic",  # or "structure", "obligation"
    embedding_model="all-MiniLM-L6-v2"
)

# Load documents
v1 = Document.load("contract_v1.pdf")
v2 = Document.load("contract_v2.pdf")

# Compare
comparison = comparator.compare(v1, v2)

# Display summary
print(f"Changes detected: {comparison.total_changes}")
print(f"  Added: {comparison.added_count}")
print(f"  Removed: {comparison.removed_count}")
print(f"  Modified: {comparison.modified_count}")
print(f"  Moved: {comparison.moved_count}")
print(f"\nCritical items requiring review: {len(comparison.critical_items)}")
```

### Example 2: Detailed Change Analysis

```python
# Focus on unfavorable changes
unfavorable = [c for c in comparison.comparisons 
               if c.favorability == "UNFAVORABLE"]

print("Unfavorable changes (against us):")
for change in sorted(unfavorable, key=lambda c: c.impact_score, reverse=True):
    print(f"\n⚠️ {change.summary}")
    print(f"   Section: {change.clause_v2.location.section}")
    print(f"   Impact: {change.magnitude} ({change.risk_level} risk)")
    print(f"   Recommendation: {change.recommendation}")
    
    if change.text_changes:
        for tc in change.text_changes:
            print(f"   - {tc.location}: {tc.old_value} → {tc.new_value}")
```

### Example 3: Obligation Impact Report

```python
# Get obligation-level changes
obligation_comps = [c for c in comparison.comparisons 
                    if c.change_type in ["ADDED", "REMOVED", "MODIFIED"]]

print("Obligation Changes:")
for oc in obligation_comps:
    if oc.change_type == "ADDED":
        print(f"\n+ NEW: {oc.clause_v2.title}")
        print(f"  {oc.clause_v2.text[:100]}...")
    elif oc.change_type == "REMOVED":
        print(f"\n- REMOVED: {oc.clause_v1.title}")
        print(f"  {oc.clause_v1.text[:100]}...")
    elif oc.change_type == "MODIFIED":
        print(f"\n~ MODIFIED: {oc.clause_v1.title}")
        for change in oc.text_changes:
            print(f"  {change.location}: {change.old_value} → {change.new_value}")
```

### Example 4: Export Formatted Report

```python
# Generate HTML report
html_report = comparison.to_html()
with open("comparison_report.html", "w") as f:
    f.write(html_report)

# Generate CSV for spreadsheet
csv_report = comparison.to_csv()
with open("comparison_analysis.csv", "w") as f:
    f.write(csv_report)

# Generate Markdown for sharing
md_report = comparison.to_markdown()
print(md_report)
```

### Example 5: Side-by-Side Interactive Comparison

```python
# Generate interactive comparison view
interactive = comparison.to_interactive_html()
with open("comparison_interactive.html", "w") as f:
    f.write(interactive)

# Open in browser
import webbrowser
webbrowser.open("comparison_interactive.html")

# Result: 
# - Left side: v1 text
# - Right side: v2 text
# - Color-coded changes
# - Hover tooltips with analysis
# - Click to expand/collapse sections
```

---

## Implementation Roadmap

### Phase 1: Structure-Aware Baseline (MVP)
**Effort:** 3-5 days
- Section-level comparison
- Added/removed/moved detection
- Basic similarity scoring
- Simple impact scoring

**Deliverable:** Functional comparison with 85% precision on added/removed

### Phase 2: Semantic Matching
**Effort:** 2-3 days
- Integrate embedding similarity
- Rephrased clause detection
- Better moved section handling

**Deliverable:** Handle rephrased clauses, improve to 88% precision

### Phase 3: Obligation-Level Comparison
**Effort:** 3-5 days
- Integrate LG-RAG-028 (obligation extraction)
- Extract and compare obligations
- Show business impact

**Deliverable:** Compare obligations semantically, show impact scores

### Phase 4: Interactive UI & Export
**Effort:** 2-3 days
- HTML/interactive comparison view
- CSV/JSON export
- PDF report generation
- Side-by-side display

**Deliverable:** Multiple export formats, interactive viewer

---

## Success Metrics

### Accuracy
- **Precision:** >90% (avoid false positives confusing users)
- **Recall:** >85% (catch most changes)
- **F1 Score:** >0.87

### Usability
- **Comparison Latency:** <5 seconds for typical 10-page contract
- **Critical Changes Identified:** >95% of high-risk items flagged
- **User Satisfaction:** Extracted changes useful without manual verification

### Coverage
- **Change Type Coverage:** >95% of changes classified correctly
- **Obligation Change Coverage:** >90% of obligation modifications captured

---

## Files to Create

### Implementation
- `src/comparison/models.py` — Data structures
- `src/comparison/document_comparator.py` — Main comparison logic
- `src/comparison/similarity_scorer.py` — Semantic/lexical similarity
- `src/comparison/impact_analyzer.py` — Impact scoring
- `src/comparison/report_generator.py` — Export formats

### Tests
- `tests/test_document_comparison.py` — Unit tests
- `tests/test_comparison_evaluation.py` — Precision/recall tests

### Documentation
- `LEGAL_DOCUMENT_COMPARISON_SPECIFICATION.md` — This file
- `LG-RAG-029-SUMMARY.md` — Feature summary

---

## Next Steps

**LG-RAG-030: Change Negotiation Advisor**
- Identify problematic changes
- Suggest counter-proposals
- Rank negotiation priorities
- Generate response language

**LG-RAG-031: Compliance Change Tracking**
- Track changes over time
- Alert on compliance-related changes
- Generate audit trail
- Link to regulatory requirements

---

## Summary

**LG-RAG-029 delivers:**
- ✅ Section-aware document comparison
- ✅ Clause-level change detection (added, removed, modified, moved)
- ✅ Semantic understanding of clause changes
- ✅ Obligation-level comparison (integrates LG-RAG-028)
- ✅ Impact scoring and prioritization
- ✅ Structured output (JSON, CSV, HTML, interactive)
- ✅ Quality metrics (precision, recall, confidence)

**Ready for:** Contract negotiation, version control, compliance review, change tracking.

**Impact:** Move from "character-level diff" to "semantic comparison" → Users get actionable insights in seconds, not hours.
