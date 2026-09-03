# LG-RAG-006 — High-Level Architecture

## 1. Purpose

This document defines the high-level architecture of the Legal Intelligence & Real-Time RAG System.

The architecture translates the requirements established in:

* LG-RAG-001 — System Context
* LG-RAG-002 — Functional Requirements
* LG-RAG-003 — Non-Functional Requirements
* LG-RAG-004 — Workload & Capacity Assumptions
* LG-RAG-005 — Reliability & Failure Requirements

into a logical system architecture.

This document defines:

* Major system components.
* Major data flows.
* Online query flow.
* Document ingestion flow.
* Knowledge update flow.
* Retrieval architecture.
* Generation architecture.
* Reliability boundaries.
* Security boundaries.
* Observability boundaries.
* High-level scaling boundaries.

It does not yet define detailed implementation-level designs such as database schemas, deployment manifests, exact retry values, or specific infrastructure products.

---

# 2. Architecture Goals

The architecture must support the following goals:

1. Provide grounded legal answers.
2. Retrieve information from an approved legal knowledge base.
3. Preserve document and version traceability.
4. Support real-time or near-real-time knowledge updates according to the defined freshness requirement.
5. Support keyword, semantic, and hybrid retrieval.
6. Support ranking and reranking.
7. Provide citations.
8. Validate generated answers against retrieved evidence.
9. Prevent unauthorized information from entering the answer context.
10. Isolate failures between major components.
11. Support horizontal scaling where required.
12. Provide observability across the complete request lifecycle.
13. Support asynchronous document processing.
14. Prevent document-processing workloads from unnecessarily affecting online query workloads.
15. Allow individual components to evolve independently where practical.

---

# 3. Architecture Principles

## AP-001 — Retrieval Before Generation

The LLM is not the authoritative source of legal information.

The architecture must retrieve approved evidence before generation.

```text id="6t7x4q"
User Question
      ↓
Retrieval
      ↓
Evidence
      ↓
LLM
      ↓
Answer
```

---

## AP-002 — Evidence Is First-Class Data

Retrieved evidence must preserve its relationship to:

```text id="qf9n3r"
Source Document
      ↓
Document Version
      ↓
Chunk
      ↓
Retrieved Evidence
      ↓
Generation Context
      ↓
Answer
      ↓
Citation
```

---

## AP-003 — Authorization Before Exposure

Access control must be applied before protected information becomes generation context.

The LLM must not be responsible for deciding whether a user is authorized to see a document.

---

## AP-004 — Online and Offline Workloads Are Separated

The architecture distinguishes between:

### Online

User question answering.

### Background

Document processing and knowledge updates.

This prevents a large ingestion workload from unnecessarily consuming resources required for interactive queries.

---

## AP-005 — Fail Safely

When sufficient evidence cannot be obtained, the system must prefer an explicit failure or no-grounded-answer response over an unsupported answer.

---

## AP-006 — Architecture Follows Requirements

Components exist because they satisfy a functional, non-functional, reliability, security, or operational requirement.

No component should be introduced merely because a technology or architectural pattern is popular.

---

# 4. High-Level System Context

The system can be represented as:

```text id="4xqf2h"
                       ┌──────────────────────┐
                       │      Legal User      │
                       └──────────┬───────────┘
                                  │
                                  │ Query
                                  ▼
                       ┌──────────────────────┐
                       │   API / Entry Point  │
                       └──────────┬───────────┘
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │   Query Orchestrator │
                       └──────────┬───────────┘
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │ Authorization /      │
                       │ Access Context       │
                       └──────────┬───────────┘
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │  Retrieval Pipeline  │
                       └──────────┬───────────┘
                                  │
                  ┌───────────────┼────────────────┐
                  │               │                │
                  ▼               ▼                ▼
             Keyword         Semantic          Metadata
             Retrieval       Retrieval          Filtering
                  │               │                │
                  └───────────────┼────────────────┘
                                  ▼
                       ┌──────────────────────┐
                       │ Ranking / Reranking  │
                       └──────────┬───────────┘
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │ Evidence Selection   │
                       └──────────┬───────────┘
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │ Context Construction │
                       └──────────┬───────────┘
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │         LLM          │
                       └──────────┬───────────┘
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │ Grounding Validation │
                       └──────────┬───────────┘
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │ Answer + Citations  │
                       └──────────┬───────────┘
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │      Legal User      │
                       └──────────────────────┘
```

---

# 5. Major Architectural Components

The high-level system consists of the following logical components.

## 5.1 Client

Provides the user interface for:

* Submitting legal questions.
* Viewing answers.
* Viewing citations.
* Reviewing supporting evidence.
* Managing supported user interactions.

The client is not trusted to enforce authorization.

---

## 5.2 API / Entry Layer

The API layer is the system entry point.

Responsibilities include:

* Receiving requests.
* Request validation.
* Authentication integration.
* Authorization integration.
* Rate limiting where required.
* Request correlation.
* Routing requests to appropriate application components.

The API layer should not contain the core retrieval or generation logic.

---

# 6. Query Orchestrator

The Query Orchestrator coordinates the online question-answering workflow.

Responsibilities include:

1. Accept the validated query.
2. Establish request context.
3. Obtain authorization context.
4. Invoke query processing.
5. Invoke retrieval.
6. Coordinate ranking/reranking.
7. Select evidence.
8. Construct generation context.
9. Invoke the LLM.
10. Invoke grounding validation.
11. Construct the final response.
12. Return answer and citations.

The orchestrator coordinates the workflow but should not unnecessarily own the internal implementation of every subsystem.

---

# 7. Authorization / Access Context

The authorization layer determines what information the current user is allowed to access.

The access context may include information such as:

```text id="m6e6pu"
User
 ↓
Role
 ↓
Tenant / Organization
 ↓
Permissions
 ↓
Accessible Documents / Sources
```

This context must be available to the retrieval pipeline.

---

# 8. Query Processing

The Query Processing component transforms the raw user query into a form suitable for retrieval.

Responsibilities may include:

* Query validation.
* Query normalization.
* Intent identification.
* Search-term extraction.
* Metadata filter identification.
* Retrieval strategy selection.

The exact query-processing implementation will be determined during retrieval design.

---

# 9. Retrieval Pipeline

The retrieval pipeline is one of the core components of the system.

It is responsible for finding relevant evidence from the approved knowledge base.

The high-level flow is:

```text id="0xg3fy"
Processed Query
      ↓
Access Constraints
      ↓
Metadata Filtering
      ↓
Keyword Retrieval
      +
Semantic Retrieval
      ↓
Candidate Combination
      ↓
Ranking
      ↓
Reranking
      ↓
Evidence Selection
```

---

# 10. Keyword Retrieval

Keyword retrieval supports queries where exact terminology matters.

Potential examples include:

* Clause identifiers.
* Section numbers.
* Regulation identifiers.
* Exact legal terms.
* Names.
* Document identifiers.

Keyword retrieval provides lexical matching capability.

---

# 11. Semantic Retrieval

Semantic retrieval supports queries where the user's wording differs from the exact wording in the source document.

It provides concept-level matching over indexed legal content.

The exact semantic retrieval implementation is intentionally left open.

---

# 12. Hybrid Retrieval

The architecture supports combining:

```text id="9h9f39"
Keyword Retrieval
        +
Semantic Retrieval
        ↓
Combined Candidate Set
```

Hybrid retrieval is intended to improve retrieval coverage across different query types.

The exact combination and weighting strategy will be determined through retrieval evaluation.

---

# 13. Metadata Filtering

Metadata filtering can constrain retrieval using properties associated with legal documents.

Potential dimensions include:

* Document identity.
* Document type.
* Jurisdiction.
* Version.
* Effective date.
* Source.
* Access permissions.

The exact metadata model will be defined during knowledge-pipeline design.

---

# 14. Ranking

Candidate evidence is ranked according to relevance.

The architecture separates candidate retrieval from final evidence ordering.

```text id="9d1xvq"
Many Candidates
      ↓
Ranking
      ↓
Fewer Candidates
```

---

# 15. Reranking

Where required, a reranking component evaluates the most promising candidates in greater detail.

```text id="8w0gk4"
Initial Candidates
       ↓
Ranking
       ↓
Top Candidate Set
       ↓
Reranking
       ↓
Final Evidence Candidates
```

Reranking is intentionally a separate logical component because it may have different performance and scaling characteristics from initial retrieval.

---

# 16. Evidence Selection

The system selects the final evidence that will be provided to the generation layer.

Evidence selection must consider:

* Relevance.
* User authorization.
* Document version.
* Source traceability.
* Context size.
* Evidence diversity where appropriate.

The output is:

```text id="6c93cp"
Final Evidence Set
```

---

# 17. Insufficient Evidence Decision

Before generation, the system must determine whether sufficient evidence exists.

```text id="f7y7e4"
Retrieved Evidence
        ↓
Evidence Threshold
        │
        ├── Sufficient → Generation
        │
        └── Insufficient → Safe No-Grounded-Answer
```

This is a critical architecture boundary.

The system must not automatically invoke the LLM simply because a user submitted a question.

---

# 18. Context Construction

The Context Construction component transforms selected evidence into the context supplied to the LLM.

The context should include:

* User query.
* Relevant evidence.
* Source information.
* Version information.
* Citation metadata.
* Required generation instructions.

The context must remain within defined model and system limits.

---

# 19. LLM Service

The LLM is responsible for generating a natural-language answer based on the supplied context.

The LLM should not be responsible for:

* Selecting unauthorized documents.
* Determining authoritative sources independently.
* Acting as the primary knowledge store.
* Deciding whether retrieved information is current.
* Replacing retrieval.

The LLM is therefore a **generation component**, not the system's source of truth.

---

# 20. Grounding Validation

Generated answers pass through a grounding-validation stage.

```text id="k6b0zq"
Generated Answer
       ↓
Grounding Validation
       ↓
     Valid?
     /    \
   YES     NO
   ↓        ↓
Return    Reject /
Answer    Remediate
```

The validation layer determines whether the generated response is sufficiently supported by the retrieved evidence.

---

# 21. Citation Service / Citation Construction

Citation information must be constructed from the evidence used during generation.

The architecture must preserve:

```text id="1vktb0"
Answer Claim
    ↓
Supporting Evidence
    ↓
Chunk
    ↓
Document
    ↓
Document Version
    ↓
Source Location
```

This enables users to inspect the basis of an answer.

---

# 22. Knowledge Management Architecture

The document pipeline is separate from the online query path.

High-level flow:

```text id="5dfqhp"
Knowledge Administrator
          │
          ▼
   Document Upload
          │
          ▼
      Validation
          │
          ▼
       Parsing
          │
          ▼
  Legal-Aware Chunking
          │
          ▼
      Metadata
          │
          ▼
     Embeddings
          │
          ▼
       Indexing
          │
          ▼
   Searchable Knowledge
```

---

# 23. Document Storage

Original legal documents must be retained in an appropriate source-of-record storage system.

The storage layer is responsible for:

* Original document preservation.
* Document identity.
* Document version relationship.
* Document lifecycle state.

The exact storage technology is not defined at this architectural level.

---

# 24. Metadata Store

A metadata store maintains information about:

* Documents.
* Versions.
* Processing state.
* Source information.
* Permissions.
* Lifecycle state.
* Other retrieval metadata.

The metadata store provides information required by both knowledge management and retrieval.

---

# 25. Processing Pipeline

Document processing should be separated into logical stages:

```text id="a3oqo8"
Validation
    ↓
Parsing
    ↓
Chunking
    ↓
Metadata Enrichment
    ↓
Embedding
    ↓
Indexing
```

The pipeline should support asynchronous execution for long-running operations.

---

# 26. Processing Queue

A queue or equivalent asynchronous mechanism may be used between major document-processing stages.

Conceptually:

```text id="7q9j2h"
Document Upload
      ↓
Processing Queue
      ↓
Worker
      ↓
Parsing
      ↓
Processing Queue
      ↓
Worker
      ↓
Embedding
      ↓
Processing Queue
      ↓
Indexing
```

The exact queue technology is intentionally not specified.

The purpose is to:

* Decouple processing stages.
* Absorb bursts.
* Support retries.
* Support recovery.
* Protect online query capacity.

---

# 27. Knowledge Index

The retrieval system requires an index containing searchable representations of processed legal content.

The logical index contains:

```text id="xj0e47"
Document Chunk
     +
Metadata
     +
Version
     +
Access Information
     +
Semantic Representation
```

The exact index implementation will be selected later.

---

# 28. Version Management

Document versions must be represented throughout the knowledge pipeline.

A document update follows:

```text id="m4f3q5"
Existing Document
       ↓
New Version
       ↓
Process New Version
       ↓
Create New Chunks
       ↓
Generate Representations
       ↓
Update Index
       ↓
Mark Correct Version Active
```

The architecture must prevent incomplete new versions from silently becoming the active searchable version.

---

# 29. Real-Time / Near-Real-Time Knowledge Updates

When an authoritative document changes, the architecture should support propagation through the processing pipeline.

```text id="6trb41"
Document Change
      ↓
Version Created
      ↓
Processing
      ↓
Embedding
      ↓
Index Update
      ↓
New Version Searchable
```

The time between document change and searchable availability must satisfy the freshness requirement established in the NFR and capacity models.

---

# 30. Online Query Path

The primary online path is:

```text id="d4q1h9"
User
 ↓
API
 ↓
Authentication
 ↓
Authorization
 ↓
Query Processing
 ↓
Metadata / Access Filtering
 ↓
Keyword + Semantic Retrieval
 ↓
Ranking
 ↓
Reranking
 ↓
Evidence Selection
 ↓
Evidence Sufficiency Check
 ↓
Context Construction
 ↓
LLM
 ↓
Grounding Validation
 ↓
Citation Construction
 ↓
Answer
 ↓
User
```

This path is latency-sensitive.

---

# 31. Background Knowledge Path

The background path is:

```text id="e4e9c1"
Knowledge Administrator
       ↓
Document Upload
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
       ↓
Searchable Knowledge
```

This path is throughput-sensitive.

---

# 32. Online vs Background Isolation

The architecture must prevent large background workloads from unnecessarily consuming all resources required by online requests.

Conceptually:

```text id="xqfjv6"
                   System Capacity
                         │
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
       Online Capacity       Processing Capacity
              │                     │
              ▼                     ▼
          Queries             Documents
```

The exact resource-isolation mechanism will be determined during deployment and scaling design.

---

# 33. Reliability Architecture

Reliability boundaries exist around major dependencies.

```text id="2a8a9s"
Query
  ↓
Retrieval
  ↓
Reranking
  ↓
LLM
  ↓
Validation
```

Each boundary may require:

* Timeout.
* Retry.
* Circuit breaker.
* Concurrency limit.
* Fallback.
* Observability.

These mechanisms must be applied according to the failure characteristics of each dependency.

---

# 34. LLM Failure

High-level behavior:

```text id="e5a6b7"
LLM Request
     ↓
Failure
     ↓
Retryable?
   /     \
 YES      NO
  ↓        ↓
Retry    Fail
  ↓
Retry exhausted?
   /       \
 NO        YES
 ↓          ↓
Retry     Fallback /
           Safe Failure
```

If a safe grounded answer cannot be produced, the system returns an explicit failure/no-grounded-answer response.

---

# 35. Retrieval Failure

If the retrieval subsystem fails:

```text id="8d0b3g"
Retrieval Failure
       ↓
Retry / Recovery
       ↓
Evidence Available?
     /       \
   YES        NO
    ↓          ↓
Continue    Safe Failure
```

The system must not treat an unavailable retrieval system as equivalent to an empty knowledge base.

This distinction is operationally important.

---

# 36. Circuit Breaker Boundary

Circuit breakers may be applied to dependencies where repeated failures could create cascading load.

Conceptually:

```text id="r3i7ub"
Healthy Dependency
      ↓
Normal Requests
      ↓
Repeated Failures
      ↓
Circuit Opens
      ↓
Stop / Limit Requests
      ↓
Recovery Test
      ↓
Dependency Healthy
      ↓
Normal Operation
```

Exact thresholds are implementation parameters and are not fixed by this document.

---

# 37. Retry Boundary

Retries occur at controlled dependency boundaries rather than indiscriminately at every layer.

The architecture must avoid:

```text id="8a7jpd"
Service A retries
    ↓
Service B retries
    ↓
Service C retries
    ↓
Dependency
```

because nested retries can multiply traffic during failure.

Retry ownership must therefore be clearly defined during detailed design.

---

# 38. Queue-Based Recovery

The architecture supports asynchronous recovery for processing workloads.

```text id="4yx7yr"
Processing Failure
      ↓
Retry Policy
      ↓
Retry Exhausted
      ↓
Recoverable?
   /       \
 YES        NO
  ↓          ↓
Recovery   Failed /
Queue      Dead Letter
```

This allows failed background work to be recovered without blocking the online query path.

---

# 39. Idempotency

Processing operations that can be retried must be designed so that repeated execution does not unintentionally create:

* Duplicate document versions.
* Duplicate chunks.
* Duplicate embeddings.
* Duplicate index entries.

The exact idempotency key strategy will be defined during detailed design.

---

# 40. Security Architecture

The security boundary is:

```text id="f7z5rm"
User
 ↓
Authentication
 ↓
Authorization
 ↓
Query
 ↓
Access-Aware Retrieval
 ↓
Authorized Evidence
 ↓
Context
 ↓
LLM
 ↓
Answer
```

The architecture must prevent unauthorized information from entering the context provided to the LLM.

---

# 41. Observability Architecture

Observability must cover the complete request lifecycle.

A request should be traceable through:

```text id="h9t1pp"
Request
 ↓
API
 ↓
Query Processing
 ↓
Retrieval
 ↓
Ranking
 ↓
Reranking
 ↓
LLM
 ↓
Validation
 ↓
Response
```

Similarly, document-processing jobs should be traceable through:

```text id="4p6l4x"
Document
 ↓
Validation
 ↓
Parsing
 ↓
Chunking
 ↓
Embedding
 ↓
Indexing
```

---

# 42. Caching Boundary

Caching may be introduced where it provides measurable performance or cost benefits.

Potential cacheable information includes:

* Repeated query results.
* Frequently accessed metadata.
* Other safe derived data.

However, caching must respect:

* User authorization.
* Document version.
* Data freshness.
* Cache invalidation requirements.

A cached answer based on an outdated legal document must not silently be treated as current.

---

# 43. Scaling Boundaries

The architecture should allow independent scaling of components with different workload characteristics.

Potential scaling boundaries include:

```text id="g3n5g8"
API / Query
      │
      ├── Retrieval
      │
      ├── Reranking
      │
      ├── Generation
      │
      └── Validation
```

and:

```text id="qj1q7w"
Document Processing
      │
      ├── Parsing
      ├── Chunking
      ├── Embedding
      └── Indexing
```

The actual number of service instances will be determined using the capacity model from LG-RAG-004.

---

# 44. High-Level Data Flow

The complete system contains two major data flows.

## Query Flow

```text id="k5g5ip"
User
 ↓
Query
 ↓
Authorization
 ↓
Retrieval
 ↓
Evidence
 ↓
Generation
 ↓
Validation
 ↓
Citation
 ↓
Answer
```

## Knowledge Flow

```text id="i3n9jr"
Document
 ↓
Validation
 ↓
Processing
 ↓
Chunking
 ↓
Metadata
 ↓
Embedding
 ↓
Index
 ↓
Retrieval
```

The two flows meet at the knowledge index.

---

# 45. Architecture Dependency Map

```text id="y5qf9p"
                         ┌──────────────┐
                         │    Client    │
                         └──────┬───────┘
                                │
                                ▼
                         ┌──────────────┐
                         │     API      │
                         └──────┬───────┘
                                │
                                ▼
                      ┌───────────────────┐
                      │ Query Orchestrator│
                      └─────────┬─────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
       Authorization       Query Processing    Metadata
              │                 │                 │
              └─────────────────┼─────────────────┘
                                │
                                ▼
                      ┌───────────────────┐
                      │ Retrieval Pipeline│
                      └─────────┬─────────┘
                                │
                  ┌─────────────┼─────────────┐
                  ▼             ▼             ▼
               Keyword       Semantic      Filtering
                  │             │             │
                  └─────────────┼─────────────┘
                                ▼
                           Reranking
                                │
                                ▼
                        Evidence Selection
                                │
                                ▼
                      Context Construction
                                │
                                ▼
                              LLM
                                │
                                ▼
                      Grounding Validation
                                │
                                ▼
                      Citation Construction
                                │
                                ▼
                             Answer
```

Knowledge pipeline:

```text id="p7kqv8"
Knowledge Administrator
          │
          ▼
    Document Upload
          │
          ▼
      Validation
          │
          ▼
       Parsing
          │
          ▼
       Chunking
          │
          ▼
      Metadata
          │
          ▼
      Embedding
          │
          ▼
       Indexing
          │
          ▼
      Knowledge Index
          │
          └──────────────→ Retrieval Pipeline
```

---

# 46. Major Architectural Boundaries

The following boundaries are intentionally established:

| Boundary                   | Purpose                                             |
| -------------------------- | --------------------------------------------------- |
| Client / API               | External request boundary                           |
| API / Application          | Request handling vs business workflow               |
| Query / Retrieval          | Question orchestration vs evidence discovery        |
| Retrieval / Generation     | Evidence vs language generation                     |
| Generation / Validation    | Generation vs correctness verification              |
| User / Knowledge           | User interaction vs knowledge management            |
| Online / Background        | Latency-sensitive vs throughput-sensitive workloads |
| Application / Dependencies | Failure isolation                                   |
| Authorization / Retrieval  | Prevent unauthorized evidence                       |
| Document / Index           | Source-of-record vs derived searchable data         |

---

# 47. Architecture Quality Attributes

The architecture is designed to satisfy the major NFR categories:

| Requirement     | Architectural Response                               |
| --------------- | ---------------------------------------------------- |
| Grounding       | Retrieval + evidence selection + validation          |
| Citations       | Evidence traceability                                |
| Security        | Authentication + authorization-aware retrieval       |
| Freshness       | Versioned document-processing pipeline               |
| Reliability     | Timeouts + retries + circuit breakers + recovery     |
| Scalability     | Independent scaling boundaries                       |
| Performance     | Separate online path + controlled retrieval pipeline |
| Observability   | Request/job tracing and metrics                      |
| Maintainability | Logical component boundaries                         |
| Cost control    | Caching + workload isolation + controlled LLM usage  |

---

# 48. Architecture Decisions Deliberately Deferred

The following decisions are intentionally not finalized in LG-RAG-006:

* Specific cloud provider.
* Specific database.
* Specific vector database.
* Specific message broker.
* Specific cache technology.
* Specific LLM provider.
* Specific embedding model.
* Specific reranking model.
* Specific API framework.
* Specific container orchestration platform.
* Exact service count.
* Exact instance sizes.
* Exact retry values.
* Exact circuit-breaker thresholds.
* Exact cache TTLs.

These decisions must be supported by the requirements, workload, testing results, and cost analysis.

---

# 49. Architectural Risks

## Risk 1 — Retrieval Becomes the Bottleneck

High query volume or expensive retrieval may increase end-to-end latency.

**Mitigation:** Independent retrieval scaling and retrieval benchmarking.

---

## Risk 2 — LLM Becomes the Bottleneck

LLM latency, concurrency limits, or provider availability may dominate the request path.

**Mitigation:** Explicit dependency limits, timeout/retry controls, fallback behavior, and capacity planning.

---

## Risk 3 — Knowledge Updates Affect Query Performance

Large reindexing operations could compete with online retrieval resources.

**Mitigation:** Workload isolation and asynchronous processing.

---

## Risk 4 — Stale Cached Answers

Caching can cause users to receive information from an older document version.

**Mitigation:** Version-aware cache invalidation and freshness requirements.

---

## Risk 5 — Unauthorized Evidence Leakage

If authorization is applied too late, protected information could enter the generation context.

**Mitigation:** Authorization-aware retrieval before context construction.

---

## Risk 6 — Retry Amplification

Multiple layers independently retrying the same failure can create a retry storm.

**Mitigation:** Clearly defined retry ownership and bounded retry policies.

---

## Risk 7 — Partial Document Processing

A document may be partially processed but incorrectly treated as fully indexed.

**Mitigation:** Explicit processing state and atomic/controlled activation of document versions.

---

# 50. Architecture Acceptance Criteria

LG-RAG-006 is complete when:

* [ ] Major system components are identified.
* [ ] System boundaries are defined.
* [ ] Online query flow is defined.
* [ ] Document ingestion flow is defined.
* [ ] Retrieval architecture is defined.
* [ ] Keyword retrieval is represented.
* [ ] Semantic retrieval is represented.
* [ ] Hybrid retrieval is represented.
* [ ] Ranking/reranking is represented.
* [ ] Evidence selection is defined.
* [ ] Insufficient-evidence behavior is represented.
* [ ] Context construction is defined.
* [ ] LLM generation is defined.
* [ ] Grounding validation is defined.
* [ ] Citation traceability is defined.
* [ ] Document versioning is represented.
* [ ] Knowledge update flow is represented.
* [ ] Online and background workloads are separated.
* [ ] Reliability boundaries are identified.
* [ ] Security boundaries are identified.
* [ ] Observability boundaries are identified.
* [ ] Scaling boundaries are identified.
* [ ] Major architectural risks are documented.
* [ ] Architecture decisions can be traced back to requirements.
* [ ] No technology has been selected without architectural justification.

---

# 51. Definition of Done

LG-RAG-006 is complete when a developer or architect can look at the architecture and answer:

> Where does a user request enter the system?

> Where is authentication performed?

> Where is authorization enforced?

> Where is the legal knowledge stored?

> How are documents processed?

> How are documents updated?

> How does retrieval work?

> Where does keyword retrieval happen?

> Where does semantic retrieval happen?

> Where does reranking happen?

> How is evidence selected?

> What happens when evidence is insufficient?

> Where does the LLM fit?

> How is the answer validated?

> How are citations generated?

> What happens when the LLM fails?

> What happens when retrieval fails?

> How are background document-processing workloads isolated?

> Which components scale independently?

> Where are the reliability boundaries?

> Where are the security boundaries?

> How can we trace a request through the system?

If those questions can be answered from this architecture, the high-level architecture is sufficiently defined for detailed component design.

---

# 52. Architectural Summary

The Legal RAG System is organized around two major pipelines:

```text id="f9d1kq"
                 LEGAL KNOWLEDGE PIPELINE

Documents
   ↓
Validation
   ↓
Parsing
   ↓
Legal-Aware Chunking
   ↓
Metadata
   ↓
Embeddings
   ↓
Index
   ↓
Searchable Knowledge
```

and:

```text id="c1f2t5"
                  ONLINE RAG PIPELINE

User Question
   ↓
Authentication
   ↓
Authorization
   ↓
Query Processing
   ↓
Hybrid Retrieval
   ↓
Ranking / Reranking
   ↓
Evidence Selection
   ↓
Evidence Sufficiency Check
   ↓
Context Construction
   ↓
LLM
   ↓
Grounding Validation
   ↓
Citations
   ↓
Answer
```

The two pipelines meet at the searchable legal knowledge layer.

The central architectural principle is:

> **The knowledge pipeline establishes the evidence. The retrieval pipeline selects the evidence. The LLM generates the language. The validation layer verifies the result.**

The LLM is therefore a component of the system, **not the source of truth**.
