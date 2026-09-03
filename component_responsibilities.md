# LG-RAG-007 — Define Components & Responsibilities

## 1. Story Information

| Field              | Details                                           |
| ------------------ | ------------------------------------------------- |
| **Story ID**       | LG-RAG-007                                        |
| **Epic**           | Epic 1 — Requirements & Architecture              |
| **Title**          | Define Components & Responsibilities              |
| **Type**           | Architecture / Technical Design                   |
| **Priority**       | High                                              |
| **Status**         | To Do                                             |
| **Depends On**     | LG-RAG-006 — Design High-Level Architecture       |
| **Owner**          | Engineering / Architecture                        |
| **Primary Output** | Component Responsibility & Boundary Specification |

---

# 2. User Story

**As a system architect,**

I want each major component of the Legal Intelligence & Real-Time RAG System to have clearly defined responsibilities, interfaces, dependencies, data ownership, failure behavior, and scaling characteristics,

**so that development teams can implement the system without ambiguity, duplicated responsibilities, hidden coupling, or unclear ownership boundaries.**

---

# 3. Purpose

LG-RAG-006 defined the **shape of the architecture**.

LG-RAG-007 now defines **what each component actually owns**.

The objective is to answer:

* What does this component do?
* What does it not do?
* What data does it own?
* What does it consume?
* What does it produce?
* Which components does it depend on?
* What happens when a dependency fails?
* Can it scale independently?
* Is it part of the online request path or background processing path?
* What security boundary does it enforce?
* What requirements does it satisfy?

This document must prevent responsibilities from becoming mixed across components.

---

# 4. Architectural Rule

Each component must have:

> **One clear primary responsibility, explicit inputs and outputs, explicit dependencies, and a defined failure boundary.**

Components should not silently perform responsibilities belonging to another component.

For example:

* Retrieval should retrieve evidence.
* The LLM should generate language.
* Grounding validation should validate grounding.
* Authorization should determine access.
* Document processing should prepare knowledge.
* Storage should persist data.

The LLM must **not become the source of truth for legal information**.

---

# 5. Component Classification

The architecture is divided into the following logical components.

### Online Query Components

1. Client
2. API / Entry Layer
3. Query Orchestrator
4. Authentication
5. Authorization / Access Context
6. Query Processing
7. Retrieval Pipeline
8. Keyword Retrieval
9. Semantic Retrieval
10. Metadata Filtering
11. Ranking
12. Reranking
13. Evidence Selection
14. Evidence Sufficiency Decision
15. Context Construction
16. LLM Service
17. Grounding Validation
18. Citation Construction
19. Answer Response

### Knowledge Pipeline Components

20. Document Upload
21. Document Validation
22. Document Parsing
23. Legal-Aware Chunking
24. Metadata Processing
25. Embedding Generation
26. Indexing
27. Document Storage
28. Metadata Store
29. Knowledge Index
30. Version Management
31. Processing Queue

### Cross-Cutting Components

32. Observability
33. Audit Logging
34. Reliability Controls
35. Security Controls
36. Optional Cache

---

# 6. Component Responsibility Matrix

| Component             | Primary Responsibility                                      |
| --------------------- | ----------------------------------------------------------- |
| Client                | Capture questions and display answers/evidence              |
| API / Entry Layer     | Expose controlled system interfaces                         |
| Query Orchestrator    | Coordinate the online query workflow                        |
| Authentication        | Establish user identity                                     |
| Authorization         | Determine what the user is allowed to access                |
| Query Processing      | Normalize and interpret incoming queries                    |
| Retrieval Pipeline    | Coordinate evidence retrieval                               |
| Keyword Retrieval     | Retrieve lexical matches                                    |
| Semantic Retrieval    | Retrieve semantically relevant evidence                     |
| Metadata Filtering    | Apply metadata constraints                                  |
| Ranking               | Order candidate evidence                                    |
| Reranking             | Improve candidate ordering using richer relevance signals   |
| Evidence Selection    | Select evidence for context                                 |
| Evidence Sufficiency  | Decide whether evidence is adequate                         |
| Context Construction  | Build the bounded LLM context                               |
| LLM Service           | Generate an answer from supplied context                    |
| Grounding Validation  | Validate generated answer against evidence                  |
| Citation Construction | Associate answer with supporting evidence                   |
| Document Upload       | Accept new knowledge documents                              |
| Document Validation   | Verify document eligibility/integrity                       |
| Document Parsing      | Convert documents into structured content                   |
| Legal-Aware Chunking  | Create retrieval units while preserving legal context       |
| Metadata Processing   | Attach searchable/traceable metadata                        |
| Embedding Generation  | Create semantic representations                             |
| Indexing              | Make processed knowledge searchable                         |
| Document Storage      | Persist source documents                                    |
| Metadata Store        | Persist document/chunk/version metadata                     |
| Knowledge Index       | Support retrieval over indexed knowledge                    |
| Version Management    | Control document versions and active versions               |
| Processing Queue      | Decouple background processing stages                       |
| Observability         | Collect logs, metrics, traces and health data               |
| Audit Logging         | Record security and evidence-traceability events            |
| Reliability Controls  | Control retries, timeouts, circuit breakers and degradation |
| Security Controls     | Enforce security policies                                   |
| Cache                 | Reduce repeated computation where safe                      |

---

# 7. Detailed Component Responsibilities

## 7.1 Client

### Responsibility

The client provides the user-facing interface for:

* submitting legal questions
* receiving answers
* viewing citations
* inspecting supporting evidence
* viewing system errors
* providing feedback
* viewing processing status where applicable

### Owns

* User interaction
* Request presentation
* Answer presentation
* Citation presentation
* Client-side validation

### Does Not Own

* Legal reasoning
* Retrieval
* Authorization decisions
* Evidence selection
* Grounding validation
* Document processing

### Inputs

* User question
* User actions
* Answer response
* Citation information

### Outputs

* Query request
* User feedback

### Failure Behavior

If the backend is unavailable:

* display a controlled error
* do not fabricate an answer
* do not reuse stale information unless explicitly permitted by the system design

---

# 8. API / Entry Layer

## Responsibility

The API / Entry Layer provides the controlled boundary between clients and backend components.

It handles:

* request validation
* authentication integration
* request identification
* rate limiting where applicable
* routing
* response formatting
* API-level error handling

### Owns

* API contracts
* request/response validation
* correlation/request identifiers
* API-level access boundary

### Does Not Own

* retrieval logic
* LLM prompting
* document parsing
* grounding decisions

### Dependencies

* Authentication
* Authorization
* Query Orchestrator
* Observability

### Failure Behavior

Invalid requests should fail fast.

Backend failures should return controlled errors rather than expose internal implementation details.

---

# 9. Query Orchestrator

## Responsibility

The Query Orchestrator coordinates the online query lifecycle.

Primary flow:

**Receive Request → Validate Identity → Build Access Context → Process Query → Retrieve Evidence → Rank → Select Evidence → Check Sufficiency → Construct Context → Generate → Validate → Cite → Respond**

### Owns

* workflow coordination
* request-level state
* dependency sequencing
* request timeout budget
* controlled failure handling

### Does Not Own

* retrieval algorithms
* embedding generation
* LLM implementation
* grounding rules themselves

### Important Rule

The orchestrator coordinates components; it should not absorb their business logic.

---

# 10. Authentication

## Responsibility

Authentication establishes **who the requester is**.

### Owns

* identity verification
* authentication state
* identity claims required by downstream authorization

### Does Not Own

* document authorization
* retrieval ranking
* evidence selection

### Output

An authenticated identity/access context.

### Failure

If authentication fails:

**No query processing should proceed.**

---

# 11. Authorization / Access Context

## Responsibility

Authorization determines what information the authenticated user is allowed to access.

This includes:

* user permissions
* roles
* document-level access
* applicable tenant/security boundaries
* access context passed into retrieval

### Critical Rule

Authorization must happen **before evidence is exposed to the LLM**.

Unauthorized evidence must never enter the generation context.

### Owns

* authorization decision
* access filters
* access context

### Does Not Own

* authentication
* retrieval ranking
* answer generation

---

# 12. Query Processing

## Responsibility

Query Processing converts the user's raw question into a retrieval-ready representation.

Potential responsibilities include:

* normalization
* query cleanup
* query classification
* extraction of constraints
* metadata interpretation
* legal terminology handling
* retrieval query generation

### Does Not Own

* final evidence selection
* answer generation
* grounding validation

### Output

A structured retrieval request.

---

# 13. Retrieval Pipeline

## Responsibility

The Retrieval Pipeline coordinates retrieval from the knowledge base.

It may combine:

* keyword retrieval
* semantic retrieval
* metadata filtering
* candidate merging
* ranking
* reranking

### Core principle

Retrieval produces **candidate evidence**, not the final answer.

---

# 14. Keyword Retrieval

## Responsibility

Retrieve evidence using lexical matching.

Useful for:

* exact legal terms
* section numbers
* statute references
* document identifiers
* names
* specific phrases

### Output

Candidate chunks/documents with relevance information.

### Does Not Own

* semantic similarity
* final ranking
* answer generation

---

# 15. Semantic Retrieval

## Responsibility

Retrieve evidence based on semantic similarity.

It supports questions where the user's wording differs from the wording in source documents.

### Input

Processed query representation.

### Output

Semantically relevant candidate evidence.

### Does Not Own

* authorization policy
* final answer
* grounding validation

---

# 16. Metadata Filtering

## Responsibility

Apply constraints such as:

* document type
* jurisdiction
* source
* date
* version
* status
* access scope

### Critical Rule

Filtering must prevent invalid or unauthorized documents from becoming retrieval candidates.

---

# 17. Ranking

## Responsibility

Ranking orders retrieved candidates according to relevance and applicable retrieval signals.

Potential signals include:

* lexical relevance
* semantic relevance
* metadata match
* source authority
* document status
* version relevance

Exact ranking algorithms remain a detailed-design decision.

---

# 18. Reranking

## Responsibility

Reranking performs a second-stage relevance evaluation over a smaller candidate set.

### Purpose

Improve evidence quality before context construction.

### Input

Top retrieval candidates.

### Output

Reranked candidates.

### Does Not Own

* answer generation
* citation generation
* grounding validation

---

# 19. Evidence Selection

## Responsibility

Evidence Selection determines which retrieved candidates are eligible to enter the answer context.

Selection should consider:

* relevance
* authority
* version
* access permissions
* duplication
* context limits
* evidence diversity where appropriate

### Critical Rule

The system must not select evidence solely because it was retrieved.

---

# 20. Evidence Sufficiency Decision

## Responsibility

Determine whether available evidence is sufficient to support a grounded answer.

Possible outcomes:

### Outcome A — Sufficient Evidence

Continue to context construction.

### Outcome B — Insufficient Evidence

Return a controlled no-grounded-answer response.

### Outcome C — Retrieval Failure

Treat retrieval failure separately from an empty result.

### Important Distinction

**No evidence found ≠ retrieval system failed.**

The system must distinguish:

* successful retrieval with insufficient evidence
* retrieval failure
* authorization-filtered results
* knowledge-base absence
* dependency failure

---

# 21. Context Construction

## Responsibility

Build the context supplied to the LLM.

The context should include:

* selected evidence
* source metadata required for traceability
* version information where required
* citation identifiers
* instructions governing grounded generation

### Security Rule

Only authorized evidence may enter context.

### Reliability Rule

Context should be bounded to prevent uncontrolled token growth.

---

# 22. LLM Service

## Responsibility

Generate a response using the supplied context and system instructions.

### Owns

* model invocation
* generation request
* generation response
* model-specific error handling

### Does Not Own

* authoritative legal knowledge
* retrieval
* authorization
* evidence selection
* final grounding decision

### Critical Principle

The LLM is a **generation component, not the legal source of truth**.

---

# 23. Grounding Validation

## Responsibility

Validate whether the generated response is adequately supported by retrieved evidence.

Validation should consider:

* claims supported by evidence
* unsupported claims
* citation alignment
* evidence coverage
* grounding failures

### Possible Outcomes

**PASS**
→ Continue to response.

**FAIL**
→ Do not return the answer as a normal grounded answer.

The system may retry or return a controlled failure depending on detailed design.

---

# 24. Citation Construction

## Responsibility

Build traceable links between answer claims and supporting evidence.

Citation information should allow the user to understand:

* which document supports the answer
* which version applies
* which evidence/chunk was used
* where the supporting information came from

### Citation Principle

Citations are not decorative metadata.

They are part of the system's evidence traceability mechanism.

---

# 25. Document Upload

## Responsibility

Accept legal documents into the knowledge pipeline.

### Responsibilities

* receive document
* identify upload
* associate uploader
* initiate processing
* record initial status

### Does Not Own

* parsing
* chunking
* embedding
* indexing

---

# 26. Document Validation

## Responsibility

Verify that a document is acceptable for processing.

Validation may include:

* file integrity
* supported format
* required metadata
* authorization
* source eligibility
* duplicate detection where applicable

Invalid documents must not enter the searchable knowledge base.

---

# 27. Document Parsing

## Responsibility

Convert source documents into structured content suitable for downstream processing.

Parsing should preserve information necessary for legal traceability, such as:

* document structure
* sections
* headings
* paragraphs
* page/location information where available

---

# 28. Legal-Aware Chunking

## Responsibility

Divide parsed legal documents into retrieval units while preserving sufficient legal context.

Chunking should avoid blindly splitting text solely by character/token count when doing so would destroy important legal relationships.

The exact chunking strategy remains a detailed design decision.

### Output

Chunks with traceability to their source document and location.

---

# 29. Metadata Processing

## Responsibility

Attach metadata required for:

* retrieval filtering
* authorization
* versioning
* source identification
* traceability
* freshness
* ranking

Example metadata categories:

* document ID
* version ID
* source
* jurisdiction
* document type
* effective date
* status
* access scope
* ingestion timestamp

---

# 30. Embedding Generation

## Responsibility

Generate semantic representations for chunks.

### Input

Validated, parsed, chunked content.

### Output

Embeddings associated with specific chunks and versions.

### Failure

Failed embedding operations must not result in a falsely successful processing state.

---

# 31. Indexing

## Responsibility

Make successfully processed knowledge available to retrieval.

Indexing must maintain relationships between:

**Document → Version → Chunk → Metadata → Embedding → Index Entry**

### Critical Rule

Incomplete document versions must not become active searchable versions.

---

# 32. Document Storage

## Responsibility

Persist source documents and/or authoritative source representations.

### Owns

* source document persistence
* document retrieval
* storage lifecycle

### Does Not Own

* retrieval ranking
* semantic search
* answer generation

---

# 33. Metadata Store

## Responsibility

Persist structured information describing documents, versions, chunks, processing state, and related metadata.

It supports:

* version management
* filtering
* lifecycle management
* traceability
* processing state

---

# 34. Knowledge Index

## Responsibility

Provide searchable representations of processed knowledge.

It supports:

* lexical retrieval
* semantic retrieval
* metadata-aware retrieval

The specific indexing technology is intentionally not defined in this story.

---

# 35. Version Management

## Responsibility

Control document versions and identify the active/current version.

Version management must support:

* creation of versions
* activation
* deactivation
* historical versions
* version-specific retrieval
* current-version identification

### Critical Rule

A partially processed version must never become the active authoritative version.

---

# 36. Processing Queue

## Responsibility

Decouple background document processing from online query traffic.

It supports:

* asynchronous processing
* workload isolation
* retries
* processing state
* recovery
* controlled concurrency

### Failure Behavior

Persistent processing failures should be recoverable and must not result in false success.

Failed messages may eventually be moved to a dead-letter mechanism according to detailed design.

---

# 37. Observability

## Responsibility

Provide visibility into system behavior.

Must support:

### Logs

* structured application logs
* error information
* correlation IDs

### Metrics

Examples:

* request rate
* latency
* retrieval latency
* reranking latency
* LLM latency
* error rate
* retry count
* queue depth
* processing failures
* grounding failures

### Tracing

Trace important cross-component operations through the request lifecycle.

---

# 38. Audit Logging

## Responsibility

Maintain auditable records for important system events.

Potential events include:

* authentication events
* authorization decisions
* document uploads
* document version changes
* document activation/deactivation
* query events where required
* evidence selection
* answer generation
* grounding validation
* administrative actions

Audit logging must support evidence traceability and operational investigation.

---

# 39. Reliability Controls

## Responsibility

Provide common mechanisms for controlled failure handling.

This includes:

* timeouts
* retries
* exponential backoff
* jitter
* retry budgets
* circuit breakers
* graceful degradation
* backpressure
* dependency isolation

### Critical Rule

Retries must be bounded.

No component may implement uncontrolled or infinite retries.

---

# 40. Security Controls

Security controls enforce system-wide requirements such as:

* authentication
* authorization
* document-level access
* tenant isolation where applicable
* encryption/data protection
* secure secrets handling
* auditability

Security controls should be applied at the correct boundaries rather than relying on the LLM to enforce access.

---

# 41. Optional Cache

Caching may be introduced only where requirements demonstrate measurable value.

Potential cache candidates:

* repeated query processing
* retrieval results
* embeddings
* metadata
* safe reusable responses

### Critical Risk

Cached information can become stale.

Therefore, caching must respect:

* document version
* knowledge freshness
* authorization
* invalidation requirements

Caching must not return unauthorized or outdated legal information merely to improve latency.

---

# 42. Component Dependency Map

## Online Query Path

```text
Client
  |
  v
API / Entry Layer
  |
  v
Authentication
  |
  v
Authorization / Access Context
  |
  v
Query Orchestrator
  |
  v
Query Processing
  |
  v
Retrieval Pipeline
  |
  +--> Keyword Retrieval
  |
  +--> Semantic Retrieval
  |
  +--> Metadata Filtering
  |
  v
Ranking
  |
  v
Reranking
  |
  v
Evidence Selection
  |
  v
Evidence Sufficiency
  |
  +---- insufficient ----> Safe No-Grounded-Answer
  |
  v
Context Construction
  |
  v
LLM Service
  |
  v
Grounding Validation
  |
  +---- failed ---------> Controlled Failure / Recovery
  |
  v
Citation Construction
  |
  v
Response
  |
  v
Client
```

---

# 43. Knowledge Processing Path

```text
Knowledge Administrator
          |
          v
   Document Upload
          |
          v
  Document Validation
          |
          v
    Document Parsing
          |
          v
   Legal-Aware Chunking
          |
          v
   Metadata Processing
          |
          v
 Embedding Generation
          |
          v
       Indexing
          |
          v
   Knowledge Index
          |
          v
Searchable Knowledge
```

Persistent supporting stores:

```text
Document Storage
      |
      +--> Source Documents

Metadata Store
      |
      +--> Documents
      +--> Versions
      +--> Chunks
      +--> Processing State
      +--> Metadata

Knowledge Index
      |
      +--> Searchable Representations
```

---

# 44. Online vs Background Ownership

| Area                 | Online Query Path                   | Background Knowledge Path |
| -------------------- | ----------------------------------- | ------------------------- |
| Primary goal         | Answer user question                | Prepare knowledge         |
| Latency sensitivity  | High                                | Lower                     |
| Workload             | User-driven                         | Queue/batch-driven        |
| Retrieval            | Yes                                 | No                        |
| LLM generation       | Yes                                 | Normally no               |
| Grounding validation | Yes                                 | No                        |
| Document parsing     | No                                  | Yes                       |
| Chunking             | No                                  | Yes                       |
| Embeddings           | Usually consume existing embeddings | Generate                  |
| Index updates        | Consume                             | Produce                   |
| Scaling              | Independently scalable              | Independently scalable    |
| Failure isolation    | Required                            | Required                  |

This separation is mandatory because document processing must not consume resources required for user query traffic.

---

# 45. Data Ownership Principles

Each data category should have a clear owner.

| Data                | Logical Owner                        |
| ------------------- | ------------------------------------ |
| User identity       | Authentication / Identity System     |
| Access permissions  | Authorization                        |
| Raw documents       | Document Storage                     |
| Document metadata   | Metadata Store                       |
| Document versions   | Version Management                   |
| Processing status   | Knowledge Pipeline / Metadata Store  |
| Chunks              | Knowledge Pipeline / Metadata Store  |
| Embeddings          | Knowledge Index / Embedding Storage  |
| Search index        | Knowledge Index                      |
| Query state         | Query Orchestrator                   |
| Retrieved evidence  | Retrieval Pipeline / request context |
| Generated answer    | Query request lifecycle              |
| Grounding result    | Grounding Validation                 |
| Citations           | Citation Construction                |
| Audit events        | Audit Logging                        |
| Operational metrics | Observability                        |

---

# 46. Failure Ownership

Failure handling must have an explicit owner.

| Failure                    | Primary Handling Boundary         |
| -------------------------- | --------------------------------- |
| Invalid API request        | API Layer                         |
| Authentication failure     | Authentication                    |
| Authorization failure      | Authorization                     |
| Query-processing failure   | Query Processing / Orchestrator   |
| Keyword retrieval failure  | Retrieval Pipeline                |
| Semantic retrieval failure | Retrieval Pipeline                |
| Reranking failure          | Retrieval Pipeline / Orchestrator |
| Insufficient evidence      | Evidence Sufficiency              |
| LLM timeout                | LLM integration / Orchestrator    |
| LLM unavailable            | Reliability boundary              |
| Grounding failure          | Grounding Validation              |
| Parsing failure            | Document Processing               |
| Chunking failure           | Document Processing               |
| Embedding failure          | Embedding Pipeline                |
| Indexing failure           | Indexing                          |
| Queue failure              | Processing Queue                  |
| Storage failure            | Storage boundary                  |
| Unauthorized evidence      | Authorization boundary            |
| Observability failure      | Observability subsystem           |

---

# 47. Scaling Characteristics

Components should scale according to their workload.

### Online path

Potentially independently scalable:

* API
* Query Orchestrator
* Query Processing
* Retrieval
* Reranking
* Grounding Validation

### Background path

Potentially independently scalable:

* Parsing
* Chunking
* Embedding generation
* Indexing
* Queue consumers

### External dependencies

Capacity must account for:

* LLM provider limits
* embedding provider limits
* search/index capacity
* storage capacity

Exact instance counts and infrastructure sizing are deferred.

---

# 48. Security Boundaries

The architecture must enforce security at these boundaries:

### Boundary 1 — User → API

Authenticate requests.

### Boundary 2 — API → Backend

Propagate authenticated identity and access context.

### Boundary 3 — Retrieval

Apply authorization constraints.

### Boundary 4 — Evidence → Context

Verify that only authorized evidence is included.

### Boundary 5 — Generated Answer → User

Return only the validated response.

### Boundary 6 — Knowledge Administration

Restrict document-management operations to authorized users.

---

# 49. Traceability to Requirements

Component design must remain traceable to the earlier requirements.

Examples:

| Requirement Area        | Responsible Components                      |
| ----------------------- | ------------------------------------------- |
| Authentication          | Authentication, API                         |
| Authorization           | Authorization, Retrieval                    |
| Document ingestion      | Upload, Validation, Parsing                 |
| Chunking                | Legal-Aware Chunking                        |
| Embeddings              | Embedding Generation                        |
| Indexing                | Indexing, Knowledge Index                   |
| Version management      | Version Management, Metadata Store          |
| Query processing        | Query Processing                            |
| Keyword retrieval       | Keyword Retrieval                           |
| Semantic retrieval      | Semantic Retrieval                          |
| Hybrid retrieval        | Retrieval Pipeline                          |
| Ranking                 | Ranking                                     |
| Reranking               | Reranking                                   |
| Evidence selection      | Evidence Selection                          |
| Insufficient evidence   | Evidence Sufficiency                        |
| Context construction    | Context Construction                        |
| Grounded generation     | LLM + Context Construction                  |
| Citations               | Citation Construction                       |
| Grounding validation    | Grounding Validation                        |
| Auditability            | Audit Logging                               |
| Error handling          | API + Orchestrator + Reliability            |
| Processing status       | Knowledge Pipeline + Metadata Store         |
| End-to-end traceability | Orchestrator + Evidence + Citations + Audit |

---

# 50. Responsibility Anti-Patterns

The following are explicitly prohibited unless a later design decision provides a strong justification.

### Anti-pattern 1 — LLM as Source of Truth

The LLM must not independently determine authoritative legal facts.

### Anti-pattern 2 — Retrieval Bypassed

The system must not intentionally generate normal legal answers without required evidence.

### Anti-pattern 3 — Authorization After Generation

Unauthorized evidence must never reach the LLM and then be filtered afterward.

### Anti-pattern 4 — Orchestrator Doing Everything

The orchestrator must not contain all retrieval, ranking, validation, storage, and processing logic.

### Anti-pattern 5 — Background Work Blocking Online Work

Large document processing jobs must not uncontrolledly consume online query resources.

### Anti-pattern 6 — Shared Unbounded Retry

Multiple layers must not independently retry the same failed dependency without coordination.

### Anti-pattern 7 — False Processing Success

A document cannot be marked successfully searchable until all required processing stages have completed successfully.

### Anti-pattern 8 — Hidden Ownership

No important data or business decision should exist without a defined logical owner.

---

# 51. Architecture Decisions Still Deferred

LG-RAG-007 does **not** select implementation technologies.

The following remain open until detailed technical design:

* cloud provider
* API framework
* programming language
* relational database
* document database
* vector database
* search engine
* message broker
* cache technology
* LLM provider
* embedding model
* reranking model
* orchestration platform
* deployment platform
* infrastructure topology
* exact number of services
* instance sizes
* exact timeout values
* retry counts
* circuit-breaker thresholds
* cache TTLs

Technology selection must be justified against the requirements and workload assumptions.

---

# 52. Key Architectural Risks

| Risk                                  | Impact      | Mitigation                                             |
| ------------------------------------- | ----------- | ------------------------------------------------------ |
| Ambiguous component ownership         | High        | Explicit responsibility contracts                      |
| Excessive service decomposition       | Medium/High | Keep logical boundaries clear before physical services |
| Retrieval bottleneck                  | High        | Independent retrieval scaling                          |
| LLM bottleneck                        | High        | Capacity planning and bounded concurrency              |
| Unauthorized evidence leakage         | Critical    | Authorization before context                           |
| Stale evidence                        | Critical    | Version and freshness controls                         |
| Retry amplification                   | High        | Retry ownership and budgets                            |
| Background workload impacting queries | High        | Queue and workload isolation                           |
| Incomplete document becoming active   | Critical    | Version activation controls                            |
| Grounding failure                     | Critical    | Validation before response                             |
| Overengineering                       | Medium      | Architecture driven by requirements                    |

---

# 53. Acceptance Criteria

## AC-001 — All Major Components Defined

**Given** the high-level architecture from LG-RAG-006,

**When** the component responsibility design is reviewed,

**Then** every major architectural component has a documented responsibility.

---

## AC-002 — Clear Ownership

**Given** every major component,

**When** its responsibility is reviewed,

**Then** its primary ownership and non-responsibilities are explicitly documented.

---

## AC-003 — Inputs and Outputs

**Given** every major processing component,

**When** its interface is reviewed,

**Then** its major inputs and outputs are defined.

---

## AC-004 — Dependencies

**Given** every major component,

**When** its design is reviewed,

**Then** its important dependencies are identified.

---

## AC-005 — Failure Boundaries

**Given** a component dependency failure,

**When** the system handles the failure,

**Then** the responsible failure boundary is clearly identified and uncontrolled propagation is prevented.

---

## AC-006 — Online/Background Separation

**Given** the architecture,

**When** online query and knowledge-processing workloads are evaluated,

**Then** their responsibilities and scaling boundaries are clearly separated.

---

## AC-007 — Authorization Boundary

**Given** retrieved evidence,

**When** evidence is prepared for generation,

**Then** authorization has already been applied.

---

## AC-008 — LLM Responsibility

**Given** the LLM component,

**When** its responsibility is reviewed,

**Then** it is defined as a generation component and not the authoritative legal knowledge source.

---

## AC-009 — Evidence Sufficiency

**Given** insufficient retrieval evidence,

**When** the query workflow reaches the evidence sufficiency decision,

**Then** the system has a defined safe behavior that does not return an unsupported normal legal answer.

---

## AC-010 — Grounding Validation

**Given** a generated answer,

**When** grounding validation fails,

**Then** the system does not treat the answer as a successfully grounded answer.

---

## AC-011 — Version Integrity

**Given** a newly processed document version,

**When** processing is incomplete,

**Then** that version cannot become the active searchable authoritative version.

---

## AC-012 — Data Ownership

**Given** system data,

**When** ownership is reviewed,

**Then** important data categories have an identified logical owner.

---

## AC-013 — Scaling Characteristics

**Given** the workload assumptions from LG-RAG-004,

**When** component scaling is reviewed,

**Then** online and background components have identifiable scaling characteristics and boundaries.

---

## AC-014 — Reliability Alignment

**Given** the failure requirements from LG-RAG-005,

**When** component responsibilities are reviewed,

**Then** timeouts, retries, circuit breakers, graceful degradation, and failure handling have identifiable ownership boundaries.

---

## AC-015 — Requirement Traceability

**Given** the functional and non-functional requirements,

**When** the architecture is reviewed,

**Then** major requirements can be mapped to one or more responsible components.

---

## AC-016 — Technology Neutrality

**Given** the purpose of this story,

**When** the design is reviewed,

**Then** no technology is selected merely because it is common or popular.

Technology selection must occur in detailed design with explicit justification.

---

## AC-017 — No Contradiction With Previous Stories

**Given** LG-RAG-001 through LG-RAG-006,

**When** LG-RAG-007 is reviewed,

**Then** component responsibilities do not contradict:

* system scope
* functional requirements
* NFRs
* workload assumptions
* reliability requirements
* high-level architecture

---

# 54. Definition of Done

LG-RAG-007 is complete when:

* [ ] All major components are identified.
* [ ] Each component has a primary responsibility.
* [ ] Each component has explicit non-responsibilities.
* [ ] Inputs and outputs are documented.
* [ ] Dependencies are documented.
* [ ] Failure ownership is documented.
* [ ] Online/background boundaries are documented.
* [ ] Security boundaries are documented.
* [ ] Data ownership is documented.
* [ ] Scaling characteristics are documented.
* [ ] Retrieval responsibilities are separated from generation.
* [ ] Authorization occurs before evidence reaches the LLM.
* [ ] Evidence sufficiency behavior is defined.
* [ ] Grounding validation responsibility is defined.
* [ ] Citation responsibility is defined.
* [ ] Document version ownership is defined.
* [ ] Incomplete versions cannot become active.
* [ ] Reliability responsibility boundaries are defined.
* [ ] Requirement traceability is established.
* [ ] No unnecessary technology decisions are introduced.
* [ ] Architecture risks are documented.
* [ ] Acceptance criteria are satisfied.
* [ ] Technical design review is completed.

---

# 55. Expected Deliverables

The implementation/design team should produce:

### Deliverable 1 — Component Responsibility Matrix

A table showing:

```text
Component
Responsibility
Non-Responsibility
Inputs
Outputs
Dependencies
Failure Behavior
Scaling
Data Owned
Security Boundary
```

### Deliverable 2 — Component Dependency Diagram

Showing:

```text
Client
  ↓
API
  ↓
Query Orchestrator
  ↓
Retrieval
  ↓
Evidence
  ↓
LLM
  ↓
Validation
  ↓
Answer
```

and the independent knowledge-processing path.

### Deliverable 3 — Requirement Traceability Matrix

Mapping:

```text
FR / NFR
   ↓
Component
   ↓
Responsibility
   ↓
Acceptance Criteria
```

### Deliverable 4 — Failure Ownership Matrix

Showing:

```text
Failure
   ↓
Detection
   ↓
Responsible Component
   ↓
Recovery / Degradation
   ↓
User-visible Outcome
```

---

# 56. Final Architectural Principle

The final responsibility model must preserve this separation:

```text
                    LEGAL KNOWLEDGE
                         │
                         ▼
              ┌────────────────────┐
              │ Knowledge Pipeline  │
              │                    │
              │ Validate           │
              │ Parse              │
              │ Chunk              │
              │ Metadata           │
              │ Embed              │
              │ Index              │
              └─────────┬──────────┘
                        │
                        ▼
                 SEARCHABLE KB
                        │
                        ▼
User ──► Query ──► Retrieval ──► Evidence
                                  │
                                  ▼
                           Sufficiency Check
                              │        │
                         enough       not enough
                              │        │
                              ▼        ▼
                           Context   Safe Failure
                              │
                              ▼
                             LLM
                              │
                              ▼
                       Grounding Validation
                              │
                         ┌────┴────┐
                       pass       fail
                         │          │
                         ▼          ▼
                     Citations   Controlled
                         │         Failure
                         ▼
                       Answer
```

The architectural contract is:

> **Knowledge provides evidence. Retrieval finds evidence. Authorization controls evidence. The LLM generates language from evidence. Grounding validation checks the generated response. Citations expose the evidence.**

The system must never reverse that relationship.

---

# 57. Story Exit Criteria

LG-RAG-007 is the final architecture story of **Epic 1 — Requirements & Architecture**.

Once LG-RAG-007 is accepted, the project should have:

**LG-RAG-001**
→ System Context & Scope

**LG-RAG-002**
→ Functional Requirements

**LG-RAG-003**
→ Non-Functional Requirements

**LG-RAG-004**
→ Workload & Capacity Assumptions

**LG-RAG-005**
→ Reliability & Failure Requirements

**LG-RAG-006**
→ High-Level Architecture

**LG-RAG-007**
→ Component Responsibilities & Boundaries

Together these form the baseline required to begin detailed engineering work.

The next Epic should therefore move from:

**“What are we building?”**

to:

**“How exactly will the Legal Knowledge Pipeline work?”**
