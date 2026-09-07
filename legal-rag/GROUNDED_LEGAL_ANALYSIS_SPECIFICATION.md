# Grounded Legal Analysis & Citations: LG-RAG-030

## Goal

Ensure all legal analysis is **evidence-backed with precise citations**, preventing unsupported conclusions and enabling verification.

Every claim must link to source documents. No hallucinations. No assumptions. Only provable statements.

## The Problem

**Without LG-RAG-030:**
```
User: "What are our payment obligations?"
System: "You must pay $10,000 within 30 days or face 5% penalties.
         You also need to provide a deposit and sign a guarantee."

User: "Where does it say that about the deposit?"
System: (silence) Can't find it.
User: Not checking that claim. Lost credibility.
```

**With LG-RAG-030:**
```
User: "What are our payment obligations?"
System: "You must pay $10,000 within 30 days [Section 4.2, p3] 
         or face 5% monthly penalties [Section 4.2, p3].
         
         NOTE: No mention of deposit or guarantee requirements 
         found in provided documents [searched Sections 4, 5, 7]"

User: Can verify each claim. Trusts system.
```

## Core Concept: The Citation Chain

```
Claim → Supporting Evidence → Source Citation
  ↓
User can click/navigate to verify
  ↓
Full traceability
```

### Citation Precision Levels

**Level 1: Section & Page**
```
"Payment due within 30 days" [Section 4.2, page 3]
```

**Level 2: Specific Lines**
```
"Payment due within 30 days" [Section 4.2, page 3, lines 12-15]
```

**Level 3: Full Quote**
```
"Payment due within 30 days" [Section 4.2, page 3, lines 12-15:
 "Buyer shall pay Invoice Amount within thirty (30) days 
  of receipt of invoice."]
```

**Level 4: Multiple Sources**
```
"Payment obligations include invoice payment [Section 4.2, page 3] 
 and deposit [Section 5.1, page 4]"
```

## Architecture

```
User Query
    ↓
Retrieve Relevant Chunks (LG-RAG-019 through 027)
    ↓
Extract Obligations/Analysis (LG-RAG-028)
    ↓
[GROUNDING ENGINE]
    ├─ Verify claims against chunks
    ├─ Find exact evidence
    ├─ Determine citation precision
    ├─ Flag unsupported claims
    └─ Build citation chain
    ↓
Generate Analysis with Citations (LG-RAG-031)
    ├─ Claim: "Payment within 30 days"
    ├─ Evidence: Exact matching text
    ├─ Citation: [Section 4.2, page 3]
    └─ Confidence: 95%
    ↓
Validate Grounding
    ├─ Every claim has evidence
    ├─ No unsupported conclusions
    ├─ Confidence > threshold
    └─ All citations traceable
    ↓
Response to User
```

## Data Models

```python
@dataclass(frozen=True)
class Citation:
    """Reference to source material."""
    
    document_id: str
    section: str              # "4.2"
    section_name: str         # "Payment Terms"
    page_number: int
    line_numbers: str | None  # "12-15" or None
    exact_quote: str | None   # For Level 3+
    
    confidence: float         # 0.0-1.0 (match quality)
    
    def to_markdown(self) -> str:
        """Format as markdown citation."""
        if self.line_numbers:
            return f"[{self.section} ({self.page_number}:{self.line_numbers})]"
        else:
            return f"[{self.section} (p{self.page_number})]"
    
    def to_full_citation(self) -> str:
        """Full citation with context."""
        parts = [f"Section {self.section}"]
        if self.section_name:
            parts.append(f"'{self.section_name}'")
        parts.append(f"page {self.page_number}")
        
        if self.line_numbers:
            parts.append(f"lines {self.line_numbers}")
        
        citation = ", ".join(parts)
        
        if self.exact_quote:
            citation += f": \"{self.exact_quote}\""
        
        return citation


@dataclass(frozen=True)
class GroundedClaim:
    """Analysis claim with evidence."""
    
    claim: str                # "Payment due within 30 days"
    claim_type: str           # "OBLIGATION", "RIGHT", "CONDITION", "RISK"
    
    # Evidence
    evidence_chunks: list[str]  # [chunk_id_1, chunk_id_2, ...]
    citations: list[Citation]   # Multiple sources possible
    
    # Quality
    confidence: float         # 0.0-1.0 overall confidence
    supporting_text: list[str]  # Extracted supporting text
    
    # Grounding status
    is_grounded: bool         # All claims supported by evidence
    grounding_quality: str    # "DIRECT", "INFERRED", "WEAK", "UNSUPPORTED"
    
    def to_markdown(self) -> str:
        """Format as markdown with citations."""
        md = f"**{self.claim}**\n\n"
        
        for citation in self.citations:
            md += f"- {citation.to_full_citation()}\n"
        
        if not self.is_grounded:
            md += f"\n⚠️ Confidence: {self.confidence:.1%}\n"
        
        return md


@dataclass(frozen=True)
class GroundingReport:
    """Complete grounding analysis for analysis."""
    
    query: str
    claims: list[GroundedClaim]
    
    # Statistics
    total_claims: int
    grounded_claims: int
    partially_grounded_claims: int
    unsupported_claims: int
    
    # Quality
    overall_groundedness: float  # 0.0-1.0
    min_claim_confidence: float
    avg_claim_confidence: float
    
    # Issues
    unsupported_statements: list[str]
    assumptions_made: list[str]
    
    def grounding_quality(self) -> str:
        """Overall quality assessment."""
        if self.overall_groundedness >= 0.95:
            return "EXCELLENT"
        elif self.overall_groundedness >= 0.85:
            return "GOOD"
        elif self.overall_groundedness >= 0.70:
            return "FAIR"
        else:
            return "POOR"


@dataclass(frozen=True)
class Evidence:
    """Retrieved evidence for a claim."""
    
    chunk_id: str
    document_id: str
    section: str
    page_number: int
    text: str                 # Full chunk text
    
    # Relevance
    relevance_score: float    # How well this supports the claim
    quote_match: bool         # Does it contain exact phrases from claim
    semantic_match: bool      # Does it match semantically
    
    def extract_supporting_quote(self, claim: str, context_chars: int = 100) -> str:
        """Extract quote from text that supports claim.
        
        Args:
            claim: Claim to support
            context_chars: Characters of context to include
        
        Returns:
            Extracted quote
        """
        # Simple implementation: find claim phrases in text
        import re
        
        # Extract key phrases from claim
        phrases = claim.split()
        phrases = [p for p in phrases if len(p) > 3]  # Skip short words
        
        for phrase in phrases:
            if phrase.lower() in self.text.lower():
                match = re.search(
                    rf".{{0,{context_chars}}}{phrase}.{{0,{context_chars}}}}",
                    self.text,
                    re.IGNORECASE
                )
                if match:
                    return match.group().strip()
        
        # Fallback: return beginning of text
        return self.text[:context_chars].strip()
```

## Grounding Strategies

### Strategy 1: Exact Match Grounding
**Approach**: Claim phrases must appear verbatim in source

```python
Claim: "Payment within 30 days"
Source: "Buyer shall pay Invoice Amount within thirty (30) days"

Match: ✓ "within thirty (30) days" ~ "within 30 days"
Grounding: DIRECT (exact meaning match)
Confidence: 95%
```

### Strategy 2: Semantic Match Grounding
**Approach**: Claim meaning matches source, even if phrasing different

```python
Claim: "Payment deadline is 30 days"
Source: "30 days from invoice receipt is when payment is due"

Match: ✓ Same meaning, different words
Grounding: DIRECT (semantic equivalence)
Confidence: 85%
```

### Strategy 3: Inferred Grounding
**Approach**: Claim logically follows from multiple sources

```python
Claim: "Late payments have consequences"
Source 1: "If payment is delayed"
Source 2: "5% penalty per month"

Match: ✓ Inference from combining sources
Grounding: INFERRED (requires combining evidence)
Confidence: 75%
```

### Strategy 4: No Grounding
**Approach**: Claim has no supporting evidence

```python
Claim: "Company must provide deposit"
Source: (searched all sections, not found)

Match: ✗ No evidence
Grounding: UNSUPPORTED
Confidence: 0%
Action: Flag or reject claim
```

## Grounding Quality Levels

### Level 1: Direct & Explicit
- ✅ Claim appears nearly verbatim in source
- ✅ High confidence (0.90+)
- ✅ Single source or consistent across sources
- Example: "Payment due within 30 days" [Section 4.2, page 3]

### Level 2: Direct & Inferred
- ✅ Claim meaning is explicit, phrasing inferred
- ✅ Good confidence (0.80+)
- ✅ May combine multiple sources
- Example: "Late payment incurs penalties" [Sections 4.2 + 4.3]

### Level 3: Partially Supported
- ⚠️ Part of claim explicit, part inferred
- ⚠️ Moderate confidence (0.60-0.80)
- ⚠️ Requires user to verify interpretation
- Example: "Payment alternatives exist" [Section 4.2 mentions bank transfer, Section 4.3 mentions check]

### Level 4: Unsupported
- ❌ No evidence in provided documents
- ❌ Low or zero confidence
- ❌ Should be rejected or flagged
- Example: "Company provides financing" [Not found in any section]

## Implementation Strategy

### Phase 1: Citation Mapping
**Step 1**: For each claim, identify all supporting chunks
```python
claim = "Payment within 30 days"
supporting_chunks = retriever.find_chunks_for_claim(claim)
# Returns: [chunk_id_1 (Section 4.2, p3), chunk_id_2 (Section 4.3, p4)]
```

**Step 2**: For each chunk, find exact quote
```python
for chunk in supporting_chunks:
    quote = extract_supporting_quote(chunk, claim)
    # Returns: "Buyer shall pay Invoice Amount within thirty (30) days"
    
    citation = Citation(
        document_id=chunk.document_id,
        section=chunk.section,
        page_number=chunk.page_number,
        exact_quote=quote,
        confidence=0.95
    )
```

**Step 3**: Create grounded claim
```python
grounded_claim = GroundedClaim(
    claim=claim,
    citations=[citation],
    evidence_chunks=supporting_chunks,
    confidence=0.95,
    is_grounded=True,
    grounding_quality="DIRECT"
)
```

### Phase 2: Confidence Scoring
**Calculate confidence based on:**

```python
confidence = base_confidence * quality_factor * source_factor

base_confidence = {
    "DIRECT": 0.95,        # Exact match
    "SEMANTIC": 0.85,      # Same meaning, different words
    "INFERRED": 0.70,      # Logical inference
    "WEAK": 0.40,          # Loosely related
    "UNSUPPORTED": 0.0     # No evidence
}

quality_factor = {
    "Single source": 0.95,
    "Multiple consistent sources": 1.0,
    "Partial match": 0.80,
    "Requires interpretation": 0.70
}

source_factor = {
    "Primary section": 1.0,
    "Related section": 0.95,
    "Appendix": 0.90,
    "Implied": 0.80
}

# Example:
# Direct match + single source + primary section
confidence = 0.95 * 0.95 * 1.0 = 0.90
```

### Phase 3: Unsupported Claim Detection
**Identify claims lacking evidence:**

```python
for claim in analysis.claims:
    if not find_supporting_chunks(claim, min_similarity=0.7):
        unsupported_claims.append(claim)
        
        # Suggest what might support it
        potential_locations = [
            "Section 4 (Payment Terms)",
            "Section 5 (Obligations)",
            "Section 7 (Conditions)"
        ]
        
        flag = {
            "claim": claim,
            "message": f"No supporting text found. Check: {', '.join(potential_locations)}",
            "action": "REJECT or REQUEST MORE DOCUMENTS"
        }
```

### Phase 4: Report Generation
**Create grounding report:**

```python
report = GroundingReport(
    query=user_query,
    claims=all_claims,
    total_claims=len(all_claims),
    grounded_claims=sum(1 for c in all_claims if c.is_grounded),
    unsupported_claims=unsupported,
    overall_groundedness=calculate_groundedness(all_claims),
    unsupported_statements=unsupported_list,
    assumptions_made=assumptions_list
)

# Report shows:
# - 15 claims extracted
# - 14 grounded (93.3%)
# - 1 unsupported (deposit requirement)
# - Average confidence: 0.87
# - Quality: GOOD
```

## Acceptance Criteria

✅ **Evidence-backed reasoning**
- Every claim links to supporting chunks
- No unsupported conclusions
- Citation chain verifiable

✅ **Claim → Source Mapping**
- Each claim has 1+ supporting chunks
- Chunks ranked by relevance
- Multiple sources identified

✅ **Precise Citations**
- Section and page numbers included
- Line numbers when possible
- Exact quotes at Level 3+

✅ **Insufficient Evidence Handling**
- Unsupported claims flagged
- Suggestions for where to look
- User not misled

✅ **No Unsupported Conclusions**
- Analysis stays within evidence
- Inferences marked as such
- Confidence scores transparent

✅ **Quality Metrics**
- Overall groundedness score (0-1)
- Per-claim confidence
- Grounding quality level assigned

---

## Testing Strategy

### Unit Tests
```python
def test_exact_quote_extraction():
    """Extract exact quote matching claim."""
    chunk_text = "Buyer shall pay $100 within thirty (30) days"
    claim = "Payment within 30 days"
    
    quote = extract_supporting_quote(chunk_text, claim)
    assert "thirty (30) days" in quote or "30 days" in quote

def test_confidence_scoring():
    """Score confidence correctly."""
    # Direct match, single source
    confidence = score_confidence(
        grounding_type="DIRECT",
        source_count=1,
        quality="exact_match"
    )
    assert confidence >= 0.90

def test_unsupported_claim_detection():
    """Detect unsupported claims."""
    claim = "Company must provide financing"
    chunks = [section4, section5, section7]  # No financing mentioned
    
    supported = find_supporting_chunks(claim, chunks, threshold=0.7)
    assert len(supported) == 0  # No match

def test_citation_formatting():
    """Format citations correctly."""
    citation = Citation(
        section="4.2",
        page_number=3,
        line_numbers="12-15",
        exact_quote="Buyer shall pay..."
    )
    
    md = citation.to_markdown()
    assert "[4.2 (3:12-15)]" in md

def test_grounding_report():
    """Generate complete grounding report."""
    claims = [
        GroundedClaim(claim="Payment 30 days", is_grounded=True),
        GroundedClaim(claim="Financing available", is_grounded=False),
    ]
    
    report = GroundingReport(claims=claims, ...)
    assert report.total_claims == 2
    assert report.grounded_claims == 1
    assert report.overall_groundedness == 0.5
```

### Integration Tests
```python
def test_grounding_full_pipeline():
    """Full grounding pipeline."""
    # Query
    query = "What are payment obligations?"
    
    # Retrieve
    chunks = retriever.retrieve(query, top_k=10)
    
    # Extract
    analysis = extractor.extract(chunks[0].text)
    
    # Ground
    grounded = grounder.ground_analysis(analysis, chunks)
    
    # Verify
    assert all(c.is_grounded or c.confidence > 0 for c in grounded.claims)
    assert len(grounded.unsupported_statements) <= 1
    assert grounded.overall_groundedness > 0.8
```

---

## Usage Examples

### Example 1: Grounding User Query

```python
from src.grounding.grounder import Grounder

grounder = Grounder()

# User asks question
query = "What must we pay and when?"

# System retrieves and analyzes
chunks = retriever.retrieve(query, top_k=20)
analysis = extractor.extract(chunks)

# Ground the analysis
grounded = grounder.ground_analysis(analysis, chunks)

# Display with citations
print(grounded.to_markdown())

# Output:
# **What must we pay and when?**
# 
# **Payment obligation**: Buyer must pay $10,000
# - [Section 4.2, page 3, lines 12-15]: "Buyer shall pay Invoice Amount of $10,000"
# - Confidence: 95%
#
# **Payment deadline**: Within 30 days of invoice
# - [Section 4.2, page 3, lines 16-17]: "within thirty (30) days of receipt of invoice"
# - Confidence: 95%
#
# **Late penalties**: 5% monthly interest
# - [Section 4.2, page 3, lines 18-19]: "5% per month on outstanding balance"
# - Confidence: 90%
#
# ✅ Overall: 3/3 claims grounded (100%), avg confidence 93.3%
```

### Example 2: Detecting Unsupported Claims

```python
# User asks about financing
query = "Can we get financing?"

chunks = retriever.retrieve(query)
analysis = extractor.extract(chunks)

grounded = grounder.ground_analysis(analysis, chunks)

# Some claims unsupported
print(grounded.unsupported_statements)
# Output: ["Company offers financing options"]

# Show where to look
print(f"⚠️ Unsupported claim: 'Company offers financing'")
print(f"   Searched: Sections 4, 5, 7 (payment), 8 (terms)")
print(f"   Not found. Check: Appendix A (services) or separate term sheet")

print(f"\nRecommendation: Request documents about financing options")
```

### Example 3: Grounding Report

```python
# Generate full report
report = grounder.generate_report(analysis, chunks, query)

print(f"Grounding Analysis: {report.query}")
print(f"=====================================")
print(f"Total claims: {report.total_claims}")
print(f"  ✅ Grounded: {report.grounded_claims} ({report.grounded_claims/report.total_claims:.1%})")
print(f"  ⚠️  Partial: {report.partially_grounded_claims}")
print(f"  ❌ Unsupported: {report.unsupported_claims}")
print(f"\nQuality: {report.grounding_quality()} ({report.overall_groundedness:.1%})")
print(f"Confidence range: {report.min_claim_confidence:.1%} - {report.avg_claim_confidence:.1%}")

if report.unsupported_statements:
    print(f"\nUnsupported claims:")
    for stmt in report.unsupported_statements:
        print(f"  - {stmt}")

if report.assumptions_made:
    print(f"\nAssumptions:")
    for assumption in report.assumptions_made:
        print(f"  - {assumption}")
```

---

## Success Metrics

### Accuracy
- **Citation Precision**: >95% of citations point to relevant text
- **Unsupported Detection**: >90% of actually-unsupported claims flagged
- **Confidence Calibration**: Predicted confidence matches actual accuracy

### Usability
- **Verification Speed**: User can verify any claim in <30 seconds
- **Citation Completeness**: >95% of claims have citations
- **False Positives**: <5% of flagged unsupported claims actually have evidence

### Quality
- **Groundedness**: >85% of claims well-grounded
- **Avg Confidence**: >0.85 for all grounded claims
- **User Trust**: Users report >80% confidence in analysis

---

## Files to Create

### Implementation
- `src/grounding/models.py` — Citation, GroundedClaim, GroundingReport
- `src/grounding/grounder.py` — Main grounding engine
- `src/grounding/citation_mapper.py` — Map claims to sources
- `src/grounding/confidence_scorer.py` — Score confidence

### Tests
- `tests/test_grounding.py` — Comprehensive grounding tests
- `tests/test_citations.py` — Citation formatting and accuracy

### Documentation
- `GROUNDED_LEGAL_ANALYSIS_SPECIFICATION.md` — This file
- `LG-RAG-030-SUMMARY.md` — Feature summary

---

## Impact

**Before LG-RAG-030:**
- User gets analysis with no way to verify claims
- System confidence unknown
- Hallucinations possible
- Legal advice not trustworthy

**After LG-RAG-030:**
- Every claim has precise citation
- Confidence score for each claim
- Unsupported claims flagged
- Analysis fully verifiable
- **System becomes trustworthy for legal work**

---

## Summary

**LG-RAG-030 delivers:**
- ✅ Evidence-backed reasoning (every claim has source)
- ✅ Precise citations (section, page, line numbers, quotes)
- ✅ Claim → source mapping (traceable chain)
- ✅ Unsupported claim detection (no hallucinations)
- ✅ Confidence scoring (transparent quality)
- ✅ Grounding reports (full transparency)
- ✅ Zero hallucinations (only provable statements)

**Ready for:** Legal analysis at scale, regulatory compliance, high-stakes decision support, audit trails.

**This is the layer that makes legal RAG trustworthy.**
