# LG-RAG-004 — Workload & Capacity Assumptions

## 1. Purpose

This document defines the expected workload and capacity assumptions for the Legal RAG System.

The objective is to establish a quantitative model for:

* Users.
* Queries.
* Concurrent requests.
* Peak traffic.
* Legal documents.
* Document size.
* Document ingestion.
* Document updates.
* Retrieval workload.
* LLM workload.
* Embedding workload.
* Storage.
* Processing capacity.

These assumptions will be used to derive the system architecture and determine the required capacity of individual components.

Where actual business data is not yet available, values in this document are explicitly identified as **working assumptions** and must be validated before production capacity is finalized.

---

# 2. Workload Modeling Principles

The system must be designed for more than average traffic.

Capacity planning shall consider:

```text
Normal Load
     ↓
Peak Load
     ↓
Dependency Capacity
     ↓
Resource Capacity
     ↓
Failure / Recovery Capacity
```

The architecture should not be sized only for the average workload.

Peak traffic, bursts, concurrency, document-processing load, and downstream dependency limits must also be considered.

---

# 3. User Workload

## 3.1 Registered Users

The initial working assumption is:

**Registered users: TBD**

The final value must be determined from the expected organization/team size.

---

## 3.2 Concurrent Users

The initial working assumption is:

**Concurrent active users: TBD**

Concurrent users are more important for capacity planning than total registered users because they determine the number of requests that may exist simultaneously.

---

## 3.3 Active Users

The system should distinguish between:

* Registered users.
* Daily active users.
* Concurrent active users.

These values must not be treated as interchangeable.

---

# 4. Query Workload

## 4.1 Average Daily Queries

The expected number of legal questions submitted per day is:

**TBD queries/day**

This value should be estimated using:

```text
Active users per day
        ×
Queries per user per day
        =
Daily queries
```

---

# 5. Average QPS

Average queries per second can be estimated using:

```text
Average QPS =
Daily queries / 86,400
```

For example, if:

```text
Daily queries = 86,400
```

then:

```text
Average QPS = 86,400 / 86,400
            = 1 QPS
```

The actual daily-query value for this system is currently **TBD**.

---

# 6. Peak Traffic

Average traffic does not represent the maximum workload.

The system shall define a peak traffic multiplier.

Initial working assumption:

**Peak factor: TBD**

The expected peak QPS is:

```text
Peak QPS =
Average QPS × Peak Factor
```

For example:

```text
Average QPS = 5
Peak factor = 5

Peak QPS = 5 × 5
         = 25 QPS
```

The actual peak factor must be established using expected usage patterns.

---

# 7. Burst Traffic

The system should also account for short traffic bursts above the normal peak.

Examples include:

* A large team starting work at the same time.
* A legal deadline.
* An incident requiring immediate document analysis.
* A newly published regulation.
* Organizational events that generate unusually high query volume.

The exact burst factor is:

**TBD**

The architecture should not assume traffic is perfectly uniform.

---

# 8. Query Concurrency

Concurrent requests can be approximated using:

```text
Concurrency ≈ QPS × Average Request Duration
```

For example:

```text
QPS = 20
Average response duration = 5 seconds

Concurrency ≈ 20 × 5
             = 100 concurrent requests
```

This is important because the system may have significantly more concurrent operations than its QPS suggests.

The actual expected latency and concurrency values will be established after the performance targets are finalized.

---

# 9. Query Types

The workload should be categorized by query type because different queries may require different amounts of processing.

Initial query categories:

### Type A — Exact / Lexical Query

Examples:

* Specific clause.
* Section number.
* Regulation identifier.
* Named entity.

Potentially benefits from keyword retrieval.

---

### Type B — Semantic Question

The user describes a concept without using the exact wording in the source.

Potentially requires semantic retrieval.

---

### Type C — Multi-Source Question

The answer requires evidence from multiple documents.

Potentially requires:

* Multiple retrieval results.
* Ranking.
* Context construction across sources.

---

### Type D — Comparison Question

The user asks to compare information from different documents or versions.

Potentially requires:

* Multiple source retrieval.
* Version awareness.
* Evidence separation.

---

### Type E — Historical / Version-Specific Question

The user asks about a particular version or historical state of a legal document.

This requires document-version awareness.

---

# 10. Query Distribution

The percentage distribution across query categories is currently:

| Query Type                    | Expected Percentage |
| ----------------------------- | ------------------: |
| Exact / lexical               |                 TBD |
| Semantic                      |                 TBD |
| Multi-source                  |                 TBD |
| Comparison                    |                 TBD |
| Historical / version-specific |                 TBD |

This distribution will influence the retrieval architecture.

---

# 11. Document Workload

## 11.1 Initial Document Count

Expected initial legal document count:

**TBD documents**

---

## 11.2 Total Corpus Size

Expected total corpus size:

**TBD GB/TB**

The corpus estimate should include:

* Original documents.
* Parsed content.
* Metadata.
* Processing artifacts where retained.
* Search/index data where applicable.

---

# 12. Document Types

The initial system may contain documents such as:

* Policies.
* Regulations.
* Contracts.
* Case material.
* Internal legal guidance.
* Other authoritative legal sources.

The exact distribution is:

**TBD**

Document type distribution matters because different document structures may create different parsing and chunking workloads.

---

# 13. Document Size

## 13.1 Average Document Size

Average document size:

**TBD MB**

---

## 13.2 Maximum Document Size

Maximum supported document size:

**TBD MB/GB**

This requirement must be explicitly defined because very large documents can affect:

* Upload handling.
* Parsing.
* Memory consumption.
* Processing duration.
* Chunking.
* Embedding generation.
* Storage.

---

# 14. Document Ingestion Rate

Expected new documents per day:

**TBD documents/day**

The ingestion workload is separate from the query workload.

The system therefore needs to support two major workload paths:

```text
Online Query Workload
        +
Offline / Asynchronous Knowledge Workload
```

---

# 15. Document Update Rate

Expected document updates per day:

**TBD updates/day**

Updates may include:

* New versions.
* Corrections.
* Revisions.
* Metadata changes.
* Document deactivation.

The update workload is important because changes may trigger reprocessing.

---

# 16. Document Processing Workload

A typical document-processing path is:

```text
Document
   ↓
Validation
   ↓
Parsing
   ↓
Chunking
   ↓
Metadata
   ↓
Embedding
   ↓
Indexing
```

The system must have sufficient capacity to process the expected ingestion and update workload.

---

# 17. Chunking Assumptions

Each document will produce some number of retrievable chunks.

Expected average chunks per document:

**TBD chunks/document**

Expected maximum chunks per document:

**TBD chunks/document**

Therefore:

```text
Total chunks =
Documents × Average chunks/document
```

Example:

```text
100,000 documents
×
200 chunks/document
=
20,000,000 chunks
```

The actual values must be established using representative legal documents.

---

# 18. Embedding Workload

Every eligible chunk may require embedding generation.

Therefore:

```text
Embedding workload =
New chunks
+
Updated chunks
```

If:

```text
10,000 new chunks/day
+
20,000 updated chunks/day
```

then:

```text
30,000 embeddings/day
```

The actual embedding workload is currently **TBD**.

---

# 19. Embedding Processing Requirements

Embedding generation capacity shall be sufficient to process expected:

* Initial corpus ingestion.
* Daily document ingestion.
* Document updates.
* Reprocessing jobs.

Embedding throughput must be measured rather than assumed.

---

# 20. Retrieval Workload

Each user query may result in one or more retrieval operations.

A logical retrieval flow may include:

```text
User Query
    ↓
Keyword Retrieval
    ↓
Vector Retrieval
    ↓
Candidate Combination
    ↓
Ranking
    ↓
Reranking
    ↓
Final Evidence
```

The exact number of retrieval operations per query is:

**TBD**

---

# 21. Retrieval Candidate Volume

The system must define:

* Number of candidates returned from keyword retrieval.
* Number of candidates returned from vector retrieval.
* Number of combined candidates.
* Number of candidates sent to reranking.
* Final number of evidence chunks sent to generation.

Initial values:

| Stage                 | Candidates |
| --------------------- | ---------: |
| Keyword retrieval     |        TBD |
| Vector retrieval      |        TBD |
| Combined candidates   |        TBD |
| Reranking candidates  |        TBD |
| Final evidence chunks |        TBD |

These values directly affect retrieval latency and LLM context size.

---

# 22. Reranking Workload

If reranking is used, the system must account for the number of candidates processed per query.

Expected reranking candidates:

**TBD/query**

Expected peak reranking throughput:

**TBD candidates/sec**

Reranking capacity must be sufficient to avoid becoming a bottleneck in the online query path.

---

# 23. LLM Workload

LLM workload depends primarily on:

* Number of queries.
* Input context size.
* Prompt size.
* Output size.
* Number of LLM calls per request.
* Retry behavior.
* Validation behavior.

The system shall measure:

* Input tokens/request.
* Output tokens/request.
* Total tokens/request.
* LLM calls/request.

---

# 24. Input Token Assumption

Expected average LLM input tokens per request:

**TBD tokens**

Expected maximum LLM input tokens:

**TBD tokens**

The input token budget must account for:

```text
System instructions
+
User query
+
Retrieved evidence
+
Metadata / citation information
```

---

# 25. Output Token Assumption

Expected average response length:

**TBD tokens**

Expected maximum response length:

**TBD tokens**

The output limit should be sufficient for useful legal answers while preventing uncontrolled generation.

---

# 26. LLM Calls Per Query

The system should explicitly track how many model calls are required for a successful request.

Initial assumption:

**TBD LLM calls/query**

Potential stages include:

```text
Query Processing
        ↓
Generation
        ↓
Grounding Validation
```

If multiple LLM calls are introduced, the capacity model must account for each call.

---

# 27. LLM Concurrency

The system must define expected LLM concurrency.

Approximation:

```text
LLM concurrency ≈ Query QPS × LLM processing duration
```

This value must also account for:

* Streaming.
* Long-running generations.
* Retries.
* Validation calls.
* Provider limits.

---

# 28. Storage Requirements

Storage requirements will include multiple categories.

## Original Documents

```text
Number of documents
×
Average document size
```

## Parsed Content

Depends on the parsing representation.

## Metadata

Document and chunk metadata.

## Embeddings

Embedding storage depends on:

* Number of chunks.
* Embedding dimensions.
* Numeric representation.
* Index overhead.

## Search / Vector Index

Additional index storage must be included.

## Logs and Audit Data

Operational and audit data must be included in storage planning.

---

# 29. Approximate Embedding Storage

For an embedding with:

```text
D dimensions
```

and a 32-bit floating-point representation:

```text
Raw embedding size ≈ D × 4 bytes
```

Therefore:

```text
Raw embedding storage ≈
Number of vectors × D × 4 bytes
```

Actual storage will be higher because indexes and metadata introduce overhead.

The final storage calculation requires:

* Number of vectors.
* Embedding dimensions.
* Data representation.
* Index implementation.
* Metadata size.

These values are currently **TBD**.

---

# 30. Storage Growth

The system shall account for storage growth rather than sizing only for the initial corpus.

Expected growth should include:

```text
New documents
+
New versions
+
New chunks
+
New embeddings
+
Index growth
+
Logs
+
Audit records
```

Expected monthly storage growth:

**TBD**

---

# 31. Capacity Headroom

The system shall maintain capacity headroom above expected normal workload.

The exact headroom percentage is:

**TBD**

Capacity planning should consider:

* Traffic growth.
* Unexpected bursts.
* Deployment overhead.
* Dependency degradation.
* Reprocessing workloads.

---

# 32. Workload Isolation

The system has two fundamentally different workload classes.

## Online Workload

User-facing:

```text
Query
→ Retrieval
→ Reranking
→ Generation
→ Validation
→ Response
```

This workload is latency-sensitive.

## Knowledge Pipeline Workload

Background:

```text
Upload
→ Parse
→ Chunk
→ Embed
→ Index
```

This workload is throughput-sensitive.

These workloads should not be allowed to consume each other's resources without explicit capacity controls.

---

# 33. Peak Ingestion Scenario

The system must account for situations where many documents are submitted simultaneously.

Example:

```text
Large document update
        ↓
Many documents submitted
        ↓
Processing queue increases
        ↓
Parsing
        ↓
Embedding
        ↓
Indexing
```

The system must define:

* Maximum ingestion rate.
* Queue capacity.
* Processing concurrency.
* Maximum acceptable processing delay.

Values are currently **TBD**.

---

# 34. Workload Isolation During Reindexing

Large-scale reprocessing or reindexing must not unnecessarily degrade the online question-answering workload.

The system should provide mechanisms to control resource consumption between:

```text
Online Query Path
        ↕
Knowledge Processing Path
```

Specific isolation mechanisms will be defined during architecture design.

---

# 35. Capacity Model

The final capacity model shall follow:

```text
Business Users
      ↓
Active Users
      ↓
Queries/User
      ↓
Daily Queries
      ↓
Average QPS
      ↓
Peak Factor
      ↓
Peak QPS
      ↓
Request Duration
      ↓
Concurrency
      ↓
Component Capacity
```

For the knowledge pipeline:

```text
Documents
      ↓
Average Document Size
      ↓
Chunks/Document
      ↓
Total Chunks
      ↓
Embeddings
      ↓
Index Size
      ↓
Storage Capacity
```

---

# 36. Initial Workload Assumption Table

The current baseline is:

| Parameter                  | Value | Status              |
| -------------------------- | ----: | ------------------- |
| Registered users           |   TBD | Business validation |
| Daily active users         |   TBD | Business validation |
| Concurrent users           |   TBD | Business validation |
| Queries/day                |   TBD | Business validation |
| Average QPS                |   TBD | Calculated          |
| Peak factor                |   TBD | Business validation |
| Peak QPS                   |   TBD | Calculated          |
| Burst factor               |   TBD | Business validation |
| Average query duration     |   TBD | NFR                 |
| Concurrent requests        |   TBD | Calculated          |
| Initial documents          |   TBD | Business validation |
| Documents/day              |   TBD | Business validation |
| Document updates/day       |   TBD | Business validation |
| Average document size      |   TBD | Data validation     |
| Maximum document size      |   TBD | Product requirement |
| Average chunks/document    |   TBD | Data analysis       |
| Total chunks               |   TBD | Calculated          |
| Embeddings/day             |   TBD | Calculated          |
| Retrieval candidates/query |   TBD | Retrieval design    |
| Reranking candidates/query |   TBD | Retrieval design    |
| Average input tokens       |   TBD | Model testing       |
| Average output tokens      |   TBD | Model testing       |
| LLM calls/query            |   TBD | Architecture        |
| Total corpus size          |   TBD | Data validation     |
| Monthly storage growth     |   TBD | Calculated          |
| Capacity headroom          |   TBD | Architecture        |

---

# 37. Capacity Calculation Template

Once the unknown values are validated, the system shall calculate:

## Query Capacity

```text
Average QPS =
Daily Queries / 86,400

Peak QPS =
Average QPS × Peak Factor

Concurrent Requests =
Peak QPS × Average Request Duration
```

---

## Document Capacity

```text
Total Chunks =
Total Documents × Average Chunks/Document

Daily New Chunks =
Daily New Documents × Average Chunks/Document

Daily Updated Chunks =
Daily Updated Documents × Average Chunks/Document

Daily Embeddings =
Daily New Chunks + Daily Updated Chunks
```

---

## LLM Capacity

```text
Daily Input Tokens =
Daily Queries × Average Input Tokens

Daily Output Tokens =
Daily Queries × Average Output Tokens

Daily Total Tokens =
Daily Input Tokens + Daily Output Tokens
```

If multiple LLM calls are required:

```text
Total LLM Calls =
Daily Queries × LLM Calls/Query
```

---

# 38. Capacity Validation Strategy

The workload assumptions shall eventually be validated using:

1. Representative legal documents.
2. Representative user queries.
3. Historical usage data where available.
4. Load testing.
5. Retrieval benchmarking.
6. LLM performance measurements.
7. Document-processing benchmarks.

The system should not finalize production capacity using theoretical calculations alone.

---

# 39. Growth Planning

The system should be designed with an expected growth horizon.

The following values must eventually be defined:

| Growth Parameter      | Target |
| --------------------- | -----: |
| User growth/year      |    TBD |
| Query growth/year     |    TBD |
| Corpus growth/year    |    TBD |
| Document growth/month |    TBD |
| Storage growth/month  |    TBD |
| Peak traffic growth   |    TBD |

Architecture decisions should consider expected growth rather than only the initial deployment.

---

# 40. Assumption Classification

Every workload value must be classified as one of:

### Confirmed

Supported by actual business or production data.

### Measured

Obtained through testing or benchmarking.

### Estimated

Derived from reasonable business/data estimates.

### Assumed

Temporary value used for architectural modeling.

### TBD

Insufficient information exists to establish the value.

Example:

```text
Average chunks/document = 180
Status = Measured
Source = Benchmark using representative legal corpus
```

This classification prevents temporary assumptions from becoming accidental production requirements.

---

# 41. Capacity Risks

The following risks must be considered:

## Risk 1 — Unknown Peak Traffic

If peak traffic is underestimated, the online query path may become overloaded.

## Risk 2 — Large Documents

Unexpectedly large documents may increase processing time and memory consumption.

## Risk 3 — High Chunk Count

Poor chunking assumptions may significantly increase:

* Embedding workload.
* Index size.
* Retrieval cost.
* Storage requirements.

## Risk 4 — LLM Context Growth

Retrieving too many chunks can increase token consumption and generation latency.

## Risk 5 — Document Update Bursts

Large-scale document updates can create an ingestion/reindexing backlog.

## Risk 6 — LLM Dependency Capacity

LLM provider limits may become the effective system capacity rather than application infrastructure.

## Risk 7 — Retry Amplification

During dependency degradation, uncontrolled retries may multiply downstream load.

This will be addressed in the reliability architecture.

---

# 42. Capacity Acceptance Criteria

LG-RAG-004 is complete when:

* Expected user population is defined or explicitly marked TBD.
* Daily active users are defined or explicitly marked TBD.
* Concurrent users are defined.
* Daily query volume is defined.
* Average QPS is calculated.
* Peak QPS is calculated.
* Peak traffic assumptions are documented.
* Burst behavior is considered.
* Concurrency is calculated.
* Document volume is defined.
* Average and maximum document size are defined.
* Document ingestion rate is defined.
* Document update rate is defined.
* Chunk volume is estimated or measured.
* Embedding workload is calculated.
* Retrieval candidate volume is defined.
* Reranking workload is defined.
* LLM token workload is defined.
* LLM calls per query are defined.
* Storage requirements are estimated.
* Storage growth is estimated.
* Online and background workloads are distinguished.
* Capacity headroom is defined.
* Every assumption has a status.
* Calculated values can be traced back to their source assumptions.

---

# 43. Definition of Done

LG-RAG-004 is considered complete when the development team can answer:

> How many users are we supporting?

> How many queries per second do we expect?

> What is our peak traffic?

> How many requests can be concurrent?

> How many legal documents do we have?

> How large are those documents?

> How many chunks will they create?

> How many embeddings do we need?

> How much storage do we require?

> How much LLM capacity do we require?

> How much workload can the system handle before scaling is required?

And most importantly:

> **What assumptions did we make to arrive at those numbers?**

---

# 44. Relationship to Architecture

The workload model will be used as an input to architectural decisions.

The dependency chain is:

```text
LG-RAG-001
System Context
       ↓
LG-RAG-002
Functional Requirements
       ↓
LG-RAG-003
Non-Functional Requirements
       ↓
LG-RAG-004
Workload & Capacity
       ↓
Capacity Model
       ↓
Architecture Constraints
       ↓
High-Level Architecture
```

The architecture must be capable of handling the validated workload while meeting the NFR targets.

Technology selection must come after this analysis.

---

# 45. Core Principle

The system should not be designed around:

> "How much traffic can our chosen technology handle?"

Instead, the question must be:

> **"What workload must the system support, what guarantees must it provide, and what architecture is required to satisfy those constraints?"**

The workload model therefore becomes a direct input into system architecture, capacity planning, scaling strategy, reliability design, and cost estimation.
