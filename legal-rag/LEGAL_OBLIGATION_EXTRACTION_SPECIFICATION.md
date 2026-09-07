# Legal Obligation & Risk Extraction: LG-RAG-028

## Goal

Extract and classify **obligations, rights, conditions, and risks** from legal documents automatically.

Move from "retrieve relevant chunks" (retrieval layer) to **"understand what chunks mean"** (semantic understanding layer).

## The Problem

**Without LG-RAG-028:**
```
User: "What are our payment obligations?"
System: Returns top 5 chunks containing "payment"
User: Must manually read and understand
  → "Pay $X by date Y"
  → "If late, pay penalty Z"
  → "Unless vendor delays"
→ Manual extraction = slow, error-prone
```

**With LG-RAG-028:**
```
User: "What are our payment obligations?"
System: Returns structured extraction:
{
  "obligation": "Pay $10,000",
  "actor": "Buyer",
  "deadline": "30 days from invoice",
  "conditions": ["Invoice received", "Services delivered"],
  "penalties": "5% late fee per month",
  "evidence": "Section 4.2, lines 12-15",
  "risk_level": "HIGH"
}
→ Ready for analysis = fast, actionable
```

## Architecture

```
Retrieved Chunk
  ↓
Semantic Parser
  ├─ Identify actors/parties
  ├─ Extract obligations
  ├─ Extract rights
  ├─ Identify conditions
  ├─ Extract deadlines
  └─ Classify risks
  ↓
Structured Extraction
{
  "type": "OBLIGATION | RIGHT | CONDITION | RISK",
  "actor": "Party A",
  "action": "Description",
  "deadline": "When",
  "conditions": ["Triggering conditions"],
  "penalties": "Consequences if breached",
  "evidence": "Source reference",
  "risk_level": "LOW | MEDIUM | HIGH | CRITICAL",
  "confidence": 0.95
}
  ↓
Risk Classification
  ├─ Priority scoring
  ├─ Cross-reference conflicts
  └─ Alert on critical items
  ↓
Output
```

## Core Concepts

### 1. Actors/Parties

**Definition:** Who has the obligation?

**Examples:**
```
"The Buyer shall pay..." → Actor: Buyer
"Services Provider must deliver..." → Actor: Services Provider
"Either party may terminate..." → Actors: Both parties
"Licensor grants non-exclusive rights..." → Actor: Licensor
```

**Extraction Method:**
- Identify pronouns: "I", "we", "you", "party"
- Identify explicit party names in agreement
- Resolve "the Buyer" → "Buyer"
- Handle complex: "Buyer and its affiliates" → Actors: Buyer, Buyer's affiliates

### 2. Obligations

**Definition:** What must a party do?

**Patterns:**
- "shall", "must", "will", "agrees to"
- "is required to", "undertakes to"
- "responsible for", "liable for"

**Examples:**
```
✓ "Seller shall deliver goods by June 1"
✓ "Buyer must pay within 30 days"
✓ "Company undertakes to provide support"
✓ "Licensor is responsible for maintenance"
```

**Structure:**
```python
{
  "type": "OBLIGATION",
  "actor": "Party who must act",
  "action": "What they must do",
  "deadline": "When (if any)",
  "conditions": ["Triggering conditions"],
  "evidence": "Source location"
}
```

### 3. Rights

**Definition:** What can/may a party do?

**Patterns:**
- "may", "shall have the right to"
- "is entitled to", "can"
- "has the right to", "may elect"

**Examples:**
```
✓ "Buyer may cancel within 30 days"
✓ "Seller has the right to audit records"
✓ "Company is entitled to injunctive relief"
✓ "Licensor may terminate for cause"
```

**Structure:**
```python
{
  "type": "RIGHT",
  "actor": "Party who has the right",
  "action": "What they can do",
  "conditions": ["When applicable"],
  "limitations": "Restrictions on exercise",
  "evidence": "Source location"
}
```

### 4. Conditions

**Definition:** When do obligations/rights apply?

**Patterns:**
- "if", "unless", "provided that", "except"
- "in the event of", "upon", "subject to"
- "contingent on", "in case of"

**Examples:**
```
✓ "Payment is due IF invoice is received"
✓ "Seller must deliver UNLESS weather prevents"
✓ "Warranty applies ONLY IF defect within 90 days"
✓ "Termination allowed PROVIDED no breach"
```

**Types:**
- **Triggering Condition:** What activates the obligation
  ```
  "Upon delivery of goods, buyer shall pay"
  Trigger: Goods delivered
  Action: Pay
  ```

- **Limiting Condition:** What restricts the obligation
  ```
  "Seller must respond within 48 hours, unless emergency"
  Limit: Unless emergency
  Action: Response time can extend
  ```

- **Concurrent Condition:** Must happen together
  ```
  "Seller delivers AND buyer pays simultaneously"
  Both must happen together
  ```

### 5. Deadlines/Temporal Constraints

**Definition:** When must something happen?

**Patterns:**
- Specific dates: "by June 1, 2025"
- Relative: "within 30 days", "within 2 business days"
- Triggered: "within 30 days of notice"
- Recurring: "quarterly", "annually"

**Extraction:**
```python
{
  "deadline_type": "ABSOLUTE | RELATIVE | TRIGGERED | RECURRING",
  "date": "June 1, 2025",  # ABSOLUTE
  "duration": "30 days",    # RELATIVE
  "trigger": "Notice received",  # TRIGGERED
  "frequency": "Quarterly",  # RECURRING
  "confidence": 0.95
}
```

### 6. Risk Classification

**Dimension 1: Risk Level**
- **CRITICAL:** Breach creates existential threat, massive financial loss, legal liability
  - Examples: Indemnification clauses, IP ownership disputes, unlimited liability
- **HIGH:** Breach creates significant financial impact or legal exposure
  - Examples: Payment obligations, delivery deadlines, confidentiality
- **MEDIUM:** Breach creates material impact but manageable
  - Examples: Reporting requirements, audit rights, record keeping
- **LOW:** Breach has minimal direct impact
  - Examples: Courtesy notices, advisory communications, non-binding recommendations

**Dimension 2: Risk Category**
- **FINANCIAL:** Money at stake
  - "If payment delayed, 5% monthly penalty"
- **OPERATIONAL:** Day-to-day impact
  - "Must respond within 24 hours"
- **LEGAL:** Legal exposure
  - "Liable for all damages including consequential damages"
- **REPUTATIONAL:** Brand/relationship impact
  - "Public disclosure of relationship creates liability"
- **COMPLIANCE:** Regulatory/contractual breach
  - "Must comply with GDPR requirements"
- **TERMINATION:** Triggers contract end
  - "Material breach allows immediate termination"

**Dimension 3: Probability**
- **LIKELY:** Party known to have difficulty, history of breach, common scenario
- **POSSIBLE:** Normal business risk, could happen
- **UNLIKELY:** Rare scenario, well-controlled mitigants
- **UNKNOWN:** Insufficient information

**Risk Score Formula:**
```
Risk Score = (Level × Category Weight × Probability) / 3

Level: CRITICAL=5, HIGH=4, MEDIUM=3, LOW=2
Weight: Financial/Legal=1.0, Termination=1.0, Compliance=0.9, Operational=0.7, Reputational=0.8
Probability: Likely=1.0, Possible=0.6, Unlikely=0.3, Unknown=0.5

Example:
  "CRITICAL" financial risk, "LIKELY" = 5 × 1.0 × 1.0 / 3 = 1.67 (HIGH PRIORITY)
```

### 7. Evidence/Source References

**Definition:** Where in the document is this extracted from?

**Structure:**
```python
{
  "document_id": "contract-001",
  "section": "4.2",
  "section_name": "Payment Terms",
  "page_number": 3,
  "line_numbers": "12-15",
  "quote": "Buyer shall pay $10,000 within 30 days of invoice",
  "confidence": 0.98
}
```

**Why Important:**
- User can verify extraction
- Audit trail for compliance
- Trace back to original text
- Dispute resolution (proves claim)

---

## Data Models

```python
@dataclass(frozen=True)
class Actor:
    """Party/actor in the agreement."""
    name: str              # "Buyer", "Seller", "Licensor"
    aliases: list[str]     # ["Purchaser", "Licensee"]
    entity_type: str       # "INDIVIDUAL", "CORPORATION", "INSTITUTION"
    role: str              # "Buyer", "Seller", "Service Provider"

@dataclass(frozen=True)
class Deadline:
    """Temporal constraint."""
    deadline_type: str     # "ABSOLUTE", "RELATIVE", "TRIGGERED", "RECURRING"
    date: str | None       # "2025-06-01"
    duration: str | None   # "30 days"
    trigger_event: str | None  # "Upon invoice receipt"
    frequency: str | None  # "Quarterly"
    confidence: float      # 0.95

@dataclass(frozen=True)
class Condition:
    """Triggering or limiting condition."""
    condition_type: str    # "TRIGGER", "LIMITATION", "CONCURRENT"
    description: str       # "If weather prevents delivery"
    related_obligation_id: str | None
    confidence: float

@dataclass(frozen=True)
class Obligation:
    """Obligation extracted from text."""
    obligation_id: str
    type: str              # "OBLIGATION"
    actor: Actor
    action: str            # "Deliver goods", "Pay invoice"
    deadline: Deadline | None
    conditions: list[Condition]
    penalties: str | None  # "5% late fee per month"
    evidence: Evidence
    confidence: float      # 0.95
    severity: str          # "MUST", "SHOULD", "MAY"

@dataclass(frozen=True)
class Right:
    """Right/permission extracted from text."""
    right_id: str
    type: str              # "RIGHT"
    actor: Actor
    action: str            # "Terminate contract", "Audit records"
    conditions: list[Condition]
    limitations: str | None  # "Only if written notice provided"
    evidence: Evidence
    confidence: float

@dataclass(frozen=True)
class Risk:
    """Risk classification."""
    risk_id: str
    obligation_id: str      # Which obligation creates this risk
    risk_level: str         # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    risk_categories: list[str]  # ["FINANCIAL", "LEGAL", "TERMINATION"]
    probability: str        # "LIKELY", "POSSIBLE", "UNLIKELY"
    description: str        # "Unlimited liability exposure"
    mitigation: str | None  # "Add liability cap to Section 8"
    priority_score: float   # 0.0-1.0 (higher = more urgent)

@dataclass(frozen=True)
class Evidence:
    """Source reference."""
    document_id: str
    section: str            # "4.2"
    section_name: str       # "Payment Terms"
    page_number: int
    line_numbers: str       # "12-15"
    quote: str              # Exact text from document
    confidence: float

@dataclass(frozen=True)
class ExtractionResult:
    """Complete extraction from a chunk."""
    chunk_id: str
    document_id: str
    
    actors: list[Actor]
    obligations: list[Obligation]
    rights: list[Right]
    conditions: list[Condition]
    
    risks: list[Risk]
    risk_summary: dict      # Count of CRITICAL, HIGH, MEDIUM, LOW
    
    extraction_time_ms: float
    model_used: str
    confidence_overall: float
```

---

## Extraction Methods

### Method 1: Prompt-Based Extraction (LLM)

**Approach:** Use LLM to extract structured data with careful prompting

**Pros:**
- ✅ Handles complex language and context
- ✅ Can understand nuanced conditions
- ✅ Can infer implied obligations
- ✅ Fast (single LLM call per chunk)

**Cons:**
- ❌ Variable quality (depends on model)
- ❌ Hallucination risk
- ❌ Expensive (token cost)
- ❌ Non-deterministic (same input might give slightly different output)

**Prompt Template:**
```
You are a legal contract analyst. Extract all obligations, rights, conditions, 
and risks from the following contract excerpt.

For each obligation, identify:
1. Actor: Who must act?
2. Action: What must they do?
3. Deadline: When (if any)?
4. Conditions: What activates this?
5. Penalties: What if breached?
6. Risk level: CRITICAL/HIGH/MEDIUM/LOW

Format as JSON: {
  "obligations": [...],
  "rights": [...],
  "conditions": [...],
  "risks": [...]
}

Contract text:
[CONTRACT CHUNK]

Confidence levels (0.0-1.0):
- HIGH (0.8-1.0): Clear language, no ambiguity
- MEDIUM (0.5-0.7): Some ambiguity, reasonable interpretation
- LOW (0.0-0.5): Unclear, contradictory, or highly interpretive
```

### Method 2: Pattern-Based Extraction (Rules)

**Approach:** Use regex and linguistic patterns to identify obligations/rights

**Example Patterns:**
```
OBLIGATION:
  - "{Actor} shall {action}"
  - "{Actor} must {action}"
  - "{Actor} agrees to {action}"
  - "{Actor} is responsible for {action}"

RIGHT:
  - "{Actor} may {action}"
  - "{Actor} has the right to {action}"
  - "{Actor} can {action}"
  - "{Actor} is entitled to {action}"

CONDITION:
  - "if {condition}, then {obligation}"
  - "{obligation} unless {exception}"
  - "{obligation} provided that {condition}"
  - "upon {trigger}, {obligation}"

DEADLINE:
  - "within {duration} [of {event}]"
  - "by {date}"
  - "{frequency}" (e.g., "quarterly")
```

**Pros:**
- ✅ Deterministic (same input → same output)
- ✅ Fast
- ✅ No hallucination risk
- ✅ Cheap (no model cost)

**Cons:**
- ❌ Low recall (misses complex cases)
- ❌ Limited to literal patterns
- ❌ Can't handle rephrasing

**Implementation:**
```python
class ObligationExtractor:
    def __init__(self):
        self.patterns = {
            "shall": r"(\w+)\s+shall\s+(.+?)(?:unless|if|provided|or|\.|$)",
            "must": r"(\w+)\s+must\s+(.+?)(?:unless|if|provided|or|\.|$)",
            "agrees": r"(\w+)\s+agrees?\s+to\s+(.+?)(?:unless|if|provided|or|\.|$)",
        }
    
    def extract_obligations(self, text: str) -> list[Obligation]:
        obligations = []
        for pattern_name, pattern in self.patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                actor, action = match.groups()
                obligations.append(Obligation(
                    actor=Actor(name=actor),
                    action=action,
                    evidence=Evidence(quote=match.group())
                ))
        return obligations
```

### Method 3: Hybrid Approach (Recommended)

**Approach:** Combine pattern-based (recall) with LLM verification (precision)

**Pipeline:**
```
1. Pattern-based extraction → Find candidate obligations (high recall)
2. LLM verification → Confirm and enrich with metadata (high precision)
3. Conflict resolution → Merge/deduplicate results
4. Risk classification → Score and prioritize
```

**Pros:**
- ✅ High recall (patterns find most cases)
- ✅ High precision (LLM confirms/filters)
- ✅ Efficient (LLM only validates, doesn't generate from scratch)
- ✅ Deterministic for common cases, flexible for complex

---

## Acceptance Criteria

✅ **Obligations extracted from chunks**
- Identify actor, action, deadline, conditions
- Classify severity (MUST, SHOULD, MAY)
- Preserve evidence (source reference)

✅ **Rights extracted with same detail**
- Who has the right
- What they can do
- When applicable
- Limitations

✅ **Conditions identified and linked**
- Triggering conditions
- Limiting conditions
- Concurrent conditions
- Evidence preserved

✅ **Deadlines parsed and normalized**
- Absolute dates (June 1, 2025)
- Relative durations (30 days)
- Triggered deadlines (30 days from notice)
- Recurring (quarterly)

✅ **Risks classified with scoring**
- Risk level (CRITICAL, HIGH, MEDIUM, LOW)
- Risk categories (FINANCIAL, LEGAL, OPERATIONAL, etc.)
- Probability assessment
- Priority scoring

✅ **Evidence tied to source**
- Document, section, page, line numbers
- Exact quote from text
- Confidence scores

✅ **Actors identified and resolved**
- Primary parties (Buyer, Seller)
- Pronouns resolved (I → Buyer)
- Affiliates and related entities
- Role clarification

✅ **Extraction quality measured**
- Overall confidence score per result
- Per-component confidence (obligation, deadline, condition)
- Precision/recall on test set

---

## Testing Strategy

### Unit Tests
```python
def test_extract_simple_obligation():
    """Extract basic 'shall' obligation."""
    text = "Buyer shall pay $100 within 30 days"
    extractor = ObligationExtractor()
    result = extractor.extract(text)
    
    assert len(result.obligations) == 1
    obligation = result.obligations[0]
    assert obligation.actor.name == "Buyer"
    assert "pay" in obligation.action.lower()
    assert obligation.deadline.duration == "30 days"

def test_extract_conditional_obligation():
    """Extract obligation with condition."""
    text = "If buyer requests, seller shall provide warranty"
    result = extractor.extract(text)
    
    obligation = result.obligations[0]
    assert len(obligation.conditions) > 0
    assert any("buyer request" in c.description.lower() for c in obligation.conditions)

def test_extract_deadline_variations():
    """Parse different deadline formats."""
    cases = [
        ("by June 1, 2025", "2025-06-01"),
        ("within 30 days", "30 days"),
        ("within 30 days of notice", "30 days from notice"),
        ("quarterly", "recurring:quarterly"),
    ]
    
    for text, expected in cases:
        deadline = deadline_parser.parse(text)
        assert deadline.normalize() == expected

def test_risk_scoring():
    """Risk priority scoring is correct."""
    obligation = Obligation(
        action="Unlimited liability",
        risk_level="CRITICAL",
        risk_categories=["LEGAL", "FINANCIAL"],
        probability="LIKELY"
    )
    
    score = risk_scorer.score(obligation)
    assert score > 0.8  # HIGH priority

def test_evidence_preservation():
    """Source references are accurate."""
    text = "Seller shall deliver goods by June 1"
    # Extract with location tracking
    result = extractor.extract(text, track_location=True)
    
    evidence = result.obligations[0].evidence
    assert evidence.quote == "Seller shall deliver goods by June 1"
    assert evidence.section is not None
```

### Integration Tests
```python
def test_extract_from_real_contract_section():
    """Test on realistic contract language."""
    contract_text = """
    4.2 Payment Terms
    Buyer shall pay Seller the Invoice Amount within thirty (30) days
    of receipt of invoice. Payment shall be made via bank transfer to
    Seller's designated account. If payment is not received within the
    required period, Buyer shall pay interest at 1.5% per month on the
    outstanding balance, calculated daily.
    """
    
    result = extractor.extract(contract_text)
    
    # Should find:
    # - Obligation: Buyer pays within 30 days
    # - Payment method: Bank transfer
    # - Penalty: 1.5% monthly interest
    # - Risk: HIGH (payment default has automatic penalty)
    
    assert len(result.obligations) >= 1
    assert any("pay" in o.action.lower() for o in result.obligations)
    assert any(r.risk_level == "HIGH" for r in result.risks)

def test_extract_complex_conditions():
    """Test handling of complex nested conditions."""
    text = """
    Licensor may terminate this Agreement immediately upon written notice
    if (i) Licensee breaches any material term and fails to cure within
    thirty (30) days of notice, or (ii) Licensee becomes insolvent or
    bankrupt, except that the cure period shall not apply in cases of
    breach of confidentiality or IP infringement.
    """
    
    result = extractor.extract(text)
    
    # Should identify:
    # - Right: Licensor can terminate
    # - Conditions: Multiple (3 conditions identified)
    # - Exception: Cure period waived for confidentiality/IP
    # - Risk: CRITICAL (termination right)
    
    assert len(result.rights) >= 1
    assert any("terminate" in r.action.lower() for r in result.rights)
    assert len([c for c in result.conditions if c.condition_type == "EXCEPTION"]) >= 1

def test_conflict_detection():
    """Detect contradictory obligations."""
    text = """
    5.1 Buyer shall provide notice within 10 days of any issues.
    5.2 Buyer may provide notice within 30 days at its discretion.
    """
    
    result = extractor.extract(text)
    
    # Should flag:
    # - Conflicting deadlines (10 vs 30 days)
    # - Mixed obligation/right (shall vs may)
    
    conflicts = result.detect_conflicts()
    assert len(conflicts) > 0
    assert any("deadline" in c.lower() for c in conflicts)
```

### Evaluation Tests
```python
def test_extraction_precision_recall():
    """Measure precision/recall on annotated dataset."""
    # Load evaluation set with manual annotations
    eval_set = load_evaluation_set("contracts_with_annotations.json")
    
    extractor = ObligationExtractor()
    
    tp, fp, fn = 0, 0, 0
    for contract, annotations in eval_set:
        result = extractor.extract(contract)
        extracted_ids = {o.obligation_id for o in result.obligations}
        annotated_ids = {a.obligation_id for a in annotations}
        
        tp += len(extracted_ids & annotated_ids)
        fp += len(extracted_ids - annotated_ids)
        fn += len(annotated_ids - extracted_ids)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    # Target: precision > 0.85, recall > 0.75, F1 > 0.80
    assert precision > 0.85, f"Precision {precision} below target"
    assert recall > 0.75, f"Recall {recall} below target"
    assert f1 > 0.80, f"F1 {f1} below target"
```

---

## Usage Examples

### Example 1: Extract from Retrieved Chunk

```python
from src.extraction.obligation_extractor import ObligationExtractor

# Get chunk from retrieval layer
chunk = retrieval_result.chunks[0]

# Extract obligations
extractor = ObligationExtractor(model="gpt-4")  # or "hybrid"
result = extractor.extract(chunk.text)

# Display results
print(f"Obligations found: {len(result.obligations)}")
for obligation in result.obligations:
    print(f"\n  Actor: {obligation.actor.name}")
    print(f"  Action: {obligation.action}")
    print(f"  Deadline: {obligation.deadline}")
    print(f"  Conditions: {[c.description for c in obligation.conditions]}")
    print(f"  Risk level: {result.risks[0].risk_level if result.risks else 'N/A'}")
    print(f"  Source: {obligation.evidence.section} (p{obligation.evidence.page_number})")

# Risk summary
print(f"\nRisk Summary: {result.risk_summary}")
# Output: {'CRITICAL': 1, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 0}
```

### Example 2: Batch Extraction from Multiple Chunks

```python
chunks = retrieval_result.chunks  # Top-20 from retrieval

extractor = ObligationExtractor(model="hybrid")
results = extractor.batch_extract(chunks)

# Aggregate across all chunks
all_obligations = []
all_risks = []
for result in results:
    all_obligations.extend(result.obligations)
    all_risks.extend(result.risks)

# Sort by risk priority
critical_risks = sorted(
    [r for r in all_risks if r.risk_level == "CRITICAL"],
    key=lambda r: r.priority_score,
    reverse=True
)

print(f"Total obligations: {len(all_obligations)}")
print(f"CRITICAL risks: {len(critical_risks)}")
for risk in critical_risks[:3]:
    print(f"\n⚠️ {risk.description}")
    print(f"   Mitigation: {risk.mitigation}")
```

### Example 3: Deadline Analysis

```python
extractor = ObligationExtractor()
result = extractor.extract(contract_text)

# Filter obligations with deadlines
time_sensitive = [o for o in result.obligations if o.deadline]

# Normalize and sort by urgency
normalized = []
for obligation in time_sensitive:
    deadline = obligation.deadline.normalize_to_days()
    normalized.append((obligation, deadline))

normalized.sort(key=lambda x: x[1])

print("Upcoming obligations (by urgency):")
for obligation, days_until in normalized:
    print(f"  Day {days_until}: {obligation.action}")
```

### Example 4: Risk Report

```python
# Extract from entire contract
all_results = extractor.batch_extract(all_chunks)

# Generate risk report
report = RiskReportGenerator()
risk_report = report.generate(all_results)

print(risk_report.to_html())
# Output: HTML dashboard with
# - Risk heatmap (CRITICAL, HIGH, MEDIUM, LOW)
# - Top risks by priority
# - Obligation timeline
# - Party responsibilities matrix
# - Conflict/ambiguity flags
```

---

## Implementation Roadmap

### Phase 1: Pattern-Based Extraction (MVP)
- Implement regex patterns for common obligations
- Simple deadline parsing
- Basic risk classification
- Evidence tracking
- **Effort:** 3-5 days
- **Recall:** ~70%, Precision: ~80%

### Phase 2: LLM Verification
- Add LLM validation layer
- Enrich with context understanding
- Improve condition handling
- **Effort:** 2-3 days
- **Recall:** ~85%, Precision: ~90%

### Phase 3: Cross-Reference & Conflict Detection
- Link obligations across document (same obligation stated twice?)
- Detect contradictions (conflicting deadlines)
- Identify dependencies (obligation A requires obligation B)
- **Effort:** 2-3 days

### Phase 4: Risk Intelligence
- ML-based risk scoring
- Learn from user feedback (true risks vs false positives)
- Prioritize by business impact
- **Effort:** 3-5 days

---

## Success Metrics

### Accuracy Metrics
- **Precision:** >85% (avoid false positives that confuse users)
- **Recall:** >75% (catch most real obligations)
- **F1 Score:** >0.80

### Coverage Metrics
- **Obligation Coverage:** >90% of obligations in contract identified
- **Risk Coverage:** >95% of high-risk items flagged

### Usability Metrics
- **Extraction Latency:** <2 seconds per chunk
- **Confidence Score:** >0.80 for critical items
- **User Satisfaction:** Extracted results useful without manual review

---

## Files to Create

### Implementation
- `src/extraction/models.py` — Data structures
- `src/extraction/patterns.py` — Regex patterns
- `src/extraction/obligation_extractor.py` — Main extraction logic
- `src/extraction/risk_classifier.py` — Risk scoring
- `src/extraction/evidence_tracker.py` — Source tracking

### Tests
- `tests/test_obligation_extraction.py` — Unit tests
- `tests/test_risk_classification.py` — Risk scoring tests
- `tests/test_extraction_evaluation.py` — Precision/recall tests

### Documentation
- `LEGAL_OBLIGATION_EXTRACTION_SPECIFICATION.md` — This file
- `LG-RAG-028-SUMMARY.md` — Feature summary

---

## Next Steps

After LG-RAG-028:

**LG-RAG-029: Answer Generation**
- Use extracted obligations as context
- Generate natural language answers to legal questions
- Synthesize across multiple obligations

**LG-RAG-030: Compliance Monitoring**
- Track obligations over time
- Alert on approaching deadlines
- Monitor obligation fulfillment

---

## Summary

**LG-RAG-028 delivers:**
- ✅ Obligation extraction with full context
- ✅ Rights extraction with conditions and limitations
- ✅ Deadline parsing and normalization
- ✅ Risk classification and scoring
- ✅ Actor/party identification and resolution
- ✅ Evidence tracking with source references
- ✅ Conflict detection
- ✅ Hybrid extraction (patterns + LLM)

**Ready for:** Contract analysis, compliance monitoring, risk management, obligation tracking.

**Impact:** Move from "retrieve chunks" → "understand meaning" → (future) "generate answers" and "monitor compliance"
