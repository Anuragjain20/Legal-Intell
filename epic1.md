Yes. We’re starting **Epic 1: Requirements & Architecture**. I checked the build plan we established: Epic 1 has six core pieces—functional requirements, non-functional requirements, traffic assumptions, latency/availability targets, high-level architecture, and service responsibilities. 

I want you to **not touch architecture yet**. Senior-engineer rule: **requirements → constraints → assumptions → architecture**. The source material also emphasizes that a requirement must be checkable, and that assumptions are risks until verified. 

# EPIC 1 — Requirements & Architecture

## Epic objective

By the end of Epic 1, you should be able to answer:

> **"What exactly are we building, for whom, under what constraints, and why does the architecture look the way it does?"**

Before writing code, we need a **System Requirements & Architecture Specification**.

---

# Jira Story Breakdown

We'll make Epic 1 into **7 stories**.

| ID         | Story                                     | Priority |
| ---------- | ----------------------------------------- | -------: |
| LG-RAG-001 | Define System Context & Scope             |       P0 |
| LG-RAG-002 | Define Functional Requirements            |       P0 |
| LG-RAG-003 | Define Non-Functional Requirements        |       P0 |
| LG-RAG-004 | Define Workload & Capacity Assumptions    |       P0 |
| LG-RAG-005 | Define Reliability & Failure Requirements |       P0 |
| LG-RAG-006 | Design High-Level Architecture            |       P0 |
| LG-RAG-007 | Define Components & Responsibilities      |       P0 |

**We start with LG-RAG-001.**

But before you begin, I want you to have all the information you'll eventually need.

---

# 1. LG-RAG-001 — System Context & Scope

### Your job

Define **what this Legal RAG system actually is**.

You need to establish:

### A. Problem

Answer:

* What problem are we solving?
* Who has the problem?
* Why is a normal keyword search insufficient?
* Why is an LLM involved?
* Why does this need RAG?
* What happens if the system gives a wrong answer?

### B. Users

Define the actors.

For example:

```text
User
Legal Analyst
Administrator
Document Manager
System
LLM
```

Don't blindly use these. **You decide who actually exists in our system.**

### C. Scope

Define:

**In scope**

Things our system will do.

**Out of scope**

Things we explicitly refuse to build.

This is extremely important.

Otherwise six weeks later you'll say:

> "Should we add an autonomous legal agent?"

No.

If it wasn't in scope, it's not getting built.

### D. Primary use cases

Define approximately **5–8 major use cases**.

For example:

```text
Upload legal document
        ↓
Process document
        ↓
Ask legal question
        ↓
Retrieve relevant clauses
        ↓
Generate grounded answer
        ↓
Return citations
```

But **you need to define the actual use cases**, not copy this blindly.

---

# 2. LG-RAG-002 — Functional Requirements

Now describe **what the system must do**.

The requirement needs to be testable.

The source material gives the important principle:

> A good functional requirement specifies input, output shape, quality bar, and failure behavior. 

So don't write:

❌ "System should answer legal questions."

Write something structurally like:

```text
Given:
    user question
    authorized legal documents

System:
    retrieves relevant evidence
    generates an answer

Output:
    answer + citations

Failure:
    if sufficient evidence is unavailable,
    system must not invent an answer.
```

### Your functional-requirement categories

At minimum investigate:

1. User authentication
2. Document upload
3. Document validation
4. Document processing
5. Document storage
6. Document indexing
7. Query submission
8. Query understanding
9. Retrieval
10. Answer generation
11. Citation generation
12. Access control
13. Conversation/history
14. Document updates
15. Document deletion
16. Error handling
17. Feedback

Don't implement them yet.

**Define them.**

---

# 3. LG-RAG-003 — Non-Functional Requirements

This is where I will start pushing you harder.

Define:

### Performance

* P50 latency
* P95 latency
* P99 latency
* time-to-first-token
* retrieval latency
* generation latency

### Availability

Example question:

> Is the system expected to operate 99%, 99.9%, or 99.99% of the time?

Don't randomly choose.

**Justify it.**

### Scalability

Define:

* concurrent users
* requests/sec
* documents/day
* document size
* total corpus size
* indexing rate

### Security

Define:

* authentication
* authorization
* tenant isolation
* encryption
* auditability
* sensitive legal information

### Correctness / quality

Define:

* retrieval quality
* answer correctness
* citation correctness
* hallucination tolerance
* refusal behavior

### Data freshness

Very important for our system.

Ask:

> If a legal document changes at 10:00 AM, how long can the old version remain searchable?

The architecture depends on this.

---

# 4. LG-RAG-004 — Workload & Capacity Assumptions

Now we need numbers.

Create a table like:

| Parameter             | Value | Reason |
| --------------------- | ----: | ------ |
| Registered users      |     ? |        |
| Concurrent users      |     ? |        |
| Queries/sec average   |     ? |        |
| Queries/sec peak      |     ? |        |
| Documents/day         |     ? |        |
| Average document size |     ? |        |
| Maximum document size |     ? |        |
| Total corpus          |     ? |        |
| Document updates/day  |     ? |        |
| Query tokens          |     ? |        |
| Response tokens       |     ? |        |

### Then calculate

At minimum:

**Average QPS**

```text
requests per day
----------------
86,400
```

**Peak QPS**

```text
average QPS × peak factor
```

Then think about:

```text
Peak QPS
   ↓
API capacity
   ↓
Retrieval capacity
   ↓
LLM concurrency
   ↓
Database capacity
```

This will later drive scaling decisions.

---

# 5. LG-RAG-005 — Reliability & Failure Requirements

This is particularly important because we've already decided that production reliability is a major part of this project.

The later Epic 5 covers:

* timeout
* retry
* exponential backoff + jitter
* circuit breaker
* queue recovery
* partial-state recovery
* fallback
* graceful degradation
* DLQ. 

**Don't design those yet.**

For Epic 1, define **what the system should do when things fail.**

Create a failure matrix:

| Failure                 | Expected behavior |
| ----------------------- | ----------------- |
| LLM unavailable         | ?                 |
| Vector DB unavailable   | ?                 |
| Database unavailable    | ?                 |
| Document parser fails   | ?                 |
| Embedding service fails | ?                 |
| Request timeout         | ?                 |
| Invalid document        | ?                 |
| No relevant documents   | ?                 |
| Unauthorized document   | ?                 |
| Partial indexing        | ?                 |

This becomes the contract for our later reliability architecture.

---

# 6. LG-RAG-006 — High-Level Architecture

**Only after Stories 001–005 are approved.**

You'll produce the first architecture.

Something conceptually like:

```text
                    ┌──────────────┐
                    │    Client    │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ API Gateway  │
                    └──────┬───────┘
                           │
                           ▼
                  ┌───────────────────┐
                  │ Application Layer │
                  └─────────┬─────────┘
                            │
                ┌───────────┴───────────┐
                │                       │
                ▼                       ▼
        Query / RAG Path        Document Pipeline
                │                       │
                ▼                       ▼
           Retrieval               Processing
                │                       │
                ▼                       ▼
          Reranking               Embeddings
                │                       │
                └──────────┬────────────┘
                           ▼
                         LLM
                           │
                           ▼
                       Response
```

**But this is NOT our final architecture.**

You will derive the actual architecture from your requirements.

---

# 7. LG-RAG-007 — Component Responsibilities

For every component you introduce, answer:

### What does it own?

### What does it NOT own?

### What does it communicate with?

### What data does it store?

### What happens if it fails?

Example:

| Component         | Responsibility      | Owns                  | Doesn't own       |
| ----------------- | ------------------- | --------------------- | ----------------- |
| API Gateway       | Request entry       | Routing/auth boundary | RAG logic         |
| Query Service     | Query orchestration | Query lifecycle       | Documents         |
| Retrieval Service | Evidence retrieval  | Retrieval logic       | LLM generation    |
| Document Service  | Document lifecycle  | Document metadata     | Answer generation |
| Vector DB         | Vector index        | Embeddings/chunks     | Business workflow |

Again: **you'll fill this in yourself.**

---

# Information You Need Before Starting

Here is your actual **Epic 1 input checklist**.

You need to establish:

### Business

* [ ] Who is the user?
* [ ] What legal problem are we solving?
* [ ] What is the primary business outcome?
* [ ] What does success look like?
* [ ] What is explicitly out of scope?

### Data

* [ ] What types of legal documents?
* [ ] PDF?
* [ ] DOCX?
* [ ] HTML?
* [ ] Scanned documents?
* [ ] Tables?
* [ ] Images?
* [ ] Document size?
* [ ] Number of documents?
* [ ] How frequently documents change?

### Query

* [ ] What questions will users ask?
* [ ] Short questions?
* [ ] Multi-hop questions?
* [ ] Exact clause lookup?
* [ ] Comparisons between documents?
* [ ] Summarization?
* [ ] Aggregations?
* [ ] Historical versions?

### Retrieval

Eventually we need to know whether we're dealing with:

* semantic queries
* exact identifiers
* structured data
* multi-hop questions
* rapidly changing information

The architecture should follow query/data shape rather than automatically choosing vector search. 

### Quality

* [ ] What constitutes a correct answer?
* [ ] Must every answer have citations?
* [ ] What happens when evidence isn't found?
* [ ] What accuracy target?
* [ ] Human review?
* [ ] How do we evaluate retrieval separately from generation?

### Performance

* [ ] Average QPS
* [ ] Peak QPS
* [ ] Concurrent users
* [ ] P95
* [ ] P99
* [ ] TTFT
* [ ] Indexing latency

### Reliability

* [ ] Availability target
* [ ] RTO
* [ ] RPO
* [ ] Retry expectations
* [ ] Fallback expectations
* [ ] Data-loss tolerance
* [ ] Stale-data tolerance

### Security

* [ ] Authentication
* [ ] Authorization
* [ ] Tenant isolation
* [ ] Document-level permissions
* [ ] Encryption
* [ ] Audit logging
* [ ] Prompt injection
* [ ] Data leakage

---

# What I want you to do RIGHT NOW

Don't start all seven stories.

We are doing this **one Jira story at a time**.

## 🟢 STORY 1 — LG-RAG-001

### Deliverable

Create:

**`docs/requirements/system-context.md`**

with these sections:

```text
# Legal RAG System — System Context

## 1. Problem Statement

## 2. Target Users

## 3. Primary Business Goal

## 4. System Goal

## 5. Primary Use Cases

## 6. In Scope

## 7. Out of Scope

## 8. Actors

## 9. System Boundary

## 10. Key Assumptions

## 11. Key Constraints

## 12. Success Criteria
```

### Acceptance Criteria

* [ ] Problem is clearly stated.
* [ ] Target users are identified.
* [ ] Business goal is measurable.
* [ ] System goal is measurable.
* [ ] At least 5 primary use cases are defined.
* [ ] In-scope functionality is explicit.
* [ ] Out-of-scope functionality is explicit.
* [ ] Actors are identified.
* [ ] System boundary is clear.
* [ ] Assumptions are separated from facts.
* [ ] Constraints are separated from assumptions.
* [ ] Success criteria are measurable.
* [ ] Every important requirement is **checkable**, not vague. 

### Definition of Done

I should be able to read your document and answer:

> **What are we building?
> Who is it for?
> What does it do?
> What doesn't it do?
> How do we know it works?**

**without asking you five follow-up questions.**

---

### One rule before you start

**Do not Google architecture diagrams. Do not choose LangChain, LlamaIndex, Pinecone, PostgreSQL, Redis, Kafka, etc. yet.**

You're going to learn the most important architectural habit:

> **Requirements → Constraints → Workload → Architecture.**

Not:

> **Cool technology → find a problem for it.**

That's also consistent with the project material's principle that the architecture shape should come **last**, after the binding constraint is identified. 

**Your first assignment is only LG-RAG-001.** Write the `system-context.md` and bring it to me. I'll review it line-by-line and either approve it or send it back.
