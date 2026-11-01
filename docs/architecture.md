# Architecture — Enterprise Multi-Tenant RAG & Document Intelligence Platform

- **Status:** Proposed architecture
- **Version:** 0.1
- **Purpose:** Define the system boundaries, components, data flow, security model, and implementation plan for a multi-tenant document intelligence SaaS.

## 1. Product Summary

The platform lets organizations create a workspace, invite authorized members, upload documents, and ask natural-language questions about the content. It processes documents asynchronously, indexes their content for retrieval, and answers questions with citations to the relevant source passages.

The product is designed around four principles:

1. **Tenant isolation by default:** a user can only access resources belonging to an authorized tenant.
2. **Grounded answers:** answers should be based on retrieved document passages, with citations that can be opened and verified.
3. **Asynchronous processing:** large files and embedding jobs must not block web requests.
4. **Observable, recoverable workflows:** ingestion and query operations have explicit states, errors, logs, and retry behavior.

This document describes a proposed design, not a claim that every feature has already been implemented.

## 2. Goals and Non-Goals

### Goals

- Support multiple organizations (tenants) on one hosted platform.
- Authenticate users and authorize access through tenant membership and roles.
- Upload PDF documents initially, with a design that can later support DOCX, TXT, and other formats.
- Validate files, store them securely, extract text, split it into chunks, create embeddings, and index chunks.
- Process uploads in background workers with status tracking and safe retries.
- Answer questions using hybrid retrieval: vector similarity plus PostgreSQL full-text search.
- Return source citations with document name, page number where available, and the supporting passage.
- Reduce unsupported answers through retrieval thresholds, prompt constraints, and an explicit "not enough evidence" response.
- Provide document lifecycle controls, including deletion and re-indexing.
- Track operational errors, latency, token usage, and ingestion progress.

### Non-Goals for the first MVP

- Training a foundation model from scratch.
- Guaranteeing zero hallucinations. Guardrails reduce risk but cannot eliminate it.
- Real-time collaborative editing of source documents.
- Complex enterprise SSO, SCIM provisioning, legal e-discovery, or region-specific data residency unless separately scoped.
- OCR for every scanned PDF in the first release. OCR can be added as a configurable processing stage.
- Fine-grained per-paragraph sharing rules. Initial authorization is tenant- and document-level.

## 3. Proposed Technology Stack

| Layer | Proposed technology | Responsibility |
| --- | --- | --- |
| Web application | Next.js + React + TypeScript | Workspace UI, uploads, document status, chat, citation viewer |
| API | Python + FastAPI | Authentication integration, authorization, document and chat APIs |
| Relational database | PostgreSQL | Tenants, users, memberships, documents, jobs, conversations, audit events |
| Vector search | pgvector extension for PostgreSQL | Store embeddings and perform semantic similarity retrieval |
| Keyword search | PostgreSQL full-text search | Match exact terms, identifiers, names, and technical phrases |
| Object storage | S3-compatible storage | Store original files and optionally derived artifacts |
| Queue and cache | Redis + a background-job library | Queue ingestion tasks, retry jobs, short-lived cache/rate-limit state |
| Document processing | Python workers | PDF parsing, chunking, metadata extraction, embedding generation |
| RAG orchestration | LangChain or a small explicit orchestration layer | Connect retrieval, prompt construction, model calls, and citations |
| Model provider | Provider adapter | Embeddings and answer generation; provider can be changed through configuration |
| Packaging | Docker / Docker Compose | Repeatable local development and deployment |
| Observability | Structured logs + metrics + error tracking | Diagnose failures, latency, queue health, and model usage |

**Design choice:** Keep the API and worker code in Python initially to reduce cross-language complexity for document processing and RAG. Next.js remains the frontend. Node.js is a viable alternative, but the MVP should avoid maintaining two backend stacks without a clear need.

## 4. High-Level System Architecture

```text
                         ┌──────────────────────────┐
                         │   Next.js Web Client     │
                         │ Upload / Documents / Chat│
                         └────────────┬─────────────┘
                                      │ HTTPS
                         ┌────────────▼─────────────┐
                         │       FastAPI API        │
                         │ AuthN + Tenant AuthZ     │
                         │ Validation + Rate Limits │
                         └─────┬─────────┬──────────┘
                               │         │
                 ┌─────────────▼─┐   ┌───▼────────────────┐
                 │ PostgreSQL    │   │ Object Storage     │
                 │ Metadata      │   │ Original Documents │
                 │ pgvector      │   └────────────────────┘
                 │ Full-text     │
                 └──────▲────────┘
                        │
                 ┌──────┴─────────┐        ┌────────────────┐
                 │ Redis Queue    │◄───────│ FastAPI API    │
                 └──────┬─────────┘        └────────────────┘
                        │
                 ┌──────▼─────────┐
                 │ Worker Process │
                 │ Parse → Chunk  │
                 │ Embed → Index  │
                 └──────┬─────────┘
                        │
                        ▼
                 ┌────────────────┐
                 │ Model Provider │
                 │ Embeddings / LLM│
                 └────────────────┘
```

### Component boundaries

- **Frontend:** presents data and collects user actions. It is not a trusted authorization boundary.
- **API:** validates requests, derives identity from verified authentication, checks tenant membership and role, and coordinates database/storage/queue operations.
- **PostgreSQL:** authoritative store for application metadata and tenant-scoped indexed chunks.
- **Object storage:** stores raw files under opaque object keys; access is mediated by the API or short-lived signed URLs after authorization.
- **Queue:** decouples upload requests from expensive parsing and embedding work.
- **Worker:** processes jobs idempotently and records progress and failures.
- **Model adapter:** isolates provider-specific SDKs, model names, timeouts, and usage metadata from core business logic.

## 5. Main Data Model

All tenant-owned rows must have a `tenant_id`, either directly or through a parent relationship that is checked during authorization. Do not trust a `tenant_id` supplied by the browser without validating membership.

### Core entities

- **User:** global identity record, usually linked to an authentication provider subject.
- **Tenant:** organization/workspace.
- **Membership:** joins a user to a tenant and stores a role.
- **Document:** tenant-owned metadata for an uploaded source file.
- **IngestionJob:** tracks asynchronous processing status, attempts, and error information.
- **DocumentChunk:** extracted text, page/section metadata, chunk order, and embedding.
- **Conversation:** tenant- and user-scoped chat session.
- **Message:** user question or assistant response.
- **Citation:** relationship between an answer and the retrieved chunk(s) used to support it.
- **AuditEvent:** security-sensitive actions such as upload, delete, membership changes, and access-denied events.

### Suggested fields

```text
Tenant(id, name, slug, created_at)
User(id, auth_subject, email, created_at)
Membership(id, tenant_id, user_id, role, created_at)
Document(id, tenant_id, uploaded_by, filename, object_key, mime_type,
         size_bytes, checksum, status, created_at, deleted_at)
IngestionJob(id, tenant_id, document_id, status, attempts,
             error_code, error_message, started_at, completed_at)
DocumentChunk(id, tenant_id, document_id, chunk_index, page_number,
              section_title, content, embedding, token_count, metadata)
Conversation(id, tenant_id, user_id, title, created_at)
Message(id, tenant_id, conversation_id, role, content, created_at)
Citation(id, tenant_id, message_id, chunk_id, quote, relevance_score)
AuditEvent(id, tenant_id, actor_user_id, action, resource_type,
           resource_id, metadata, created_at)
```

Use UUIDs or other non-guessable identifiers for externally exposed resource IDs. An opaque ID is not a substitute for authorization.

### Database protections

- Add indexes for common tenant-scoped filters, including `(tenant_id, created_at)` and `(tenant_id, document_id)`.
- Use foreign keys and appropriate delete behavior.
- Consider PostgreSQL Row-Level Security (RLS) as defense in depth. Application-level authorization is still required.
- If using RLS with connection pooling, set tenant context transaction-locally and test that context cannot leak between pooled requests.
- Ensure vector and full-text queries filter by the authorized tenant and permitted document set before returning results.
- Never perform a global vector search and rely on the UI to hide other tenants' results.

## 6. Document Ingestion Workflow

1. **Request upload:** client requests an upload session or submits a file to the API.
2. **Authenticate and authorize:** verify the user's identity, tenant membership, and upload permission.
3. **Validate:** enforce file-size and file-count limits; allow only supported MIME types and extensions; inspect file signatures where practical.
4. **Store:** create a document row with `status = queued` and place the raw file in private object storage using a generated object key.
5. **Enqueue:** create an ingestion job and enqueue its ID. The upload endpoint returns promptly with the document ID and current status.
6. **Claim job:** worker obtains the job using a safe retry/claim mechanism.
7. **Extract:** parse text and preserve page boundaries or other location metadata where available.
8. **Normalize and chunk:** remove unusable noise, preserve useful headings, and split content into bounded, overlapping chunks.
9. **Embed:** generate embeddings in batches; record model/version metadata to support future re-indexing.
10. **Index:** write chunks and embeddings to PostgreSQL in tenant-scoped transactions. Add/update full-text search data.
11. **Complete:** mark the document `ready` only after the index is usable. Store counts and processing timestamps.
12. **Failure handling:** record a safe error code, retry transient errors with bounded backoff, and mark permanent/exhausted jobs `failed`.
13. **Notify UI:** frontend polls document status initially; server-sent events or WebSockets can be added later.

### Ingestion state machine

```text
uploaded → queued → processing → ready
                       │
                       ├── retryable error → queued
                       └── permanent/exhausted error → failed

ready → deleting → deleted
ready → reindexing → ready | failed
```

The database is the source of truth for job status. Queue delivery may be at-least-once, so workers must be idempotent. Avoid creating duplicate chunks when a job is retried.

### Chunking policy

Start with a configurable recursive text splitter and record the configuration used. A reasonable initial experiment is approximately 700–1,000 tokens per chunk with 100–150 tokens of overlap, then evaluate on a small test set. These are starting values, not universal optimal settings.

Preserve:
- document ID and tenant ID,
- page number or page range where available,
- chunk index and extraction version,
- heading/section context,
- source filename and content checksum.

Do not silently claim page-level citations when the parser cannot reliably associate text with pages. Mark location metadata as unavailable where necessary.

## 7. Question Answering / RAG Workflow

1. Authenticate the caller and verify access to the selected tenant and conversation.
2. Validate the question length and rate limits.
3. Optionally rewrite the query for retrieval, without treating rewritten text as trusted instructions.
4. Run vector similarity search and PostgreSQL full-text search with tenant and document-permission filters.
5. Merge and rank results using a simple reciprocal-rank fusion or another measured strategy.
6. Optionally rerank the top candidates.
7. Apply retrieval-quality thresholds and limit context size.
8. Construct a prompt that clearly separates untrusted retrieved text from system instructions.
9. Ask the model to answer only from the supplied evidence and return structured citations.
10. Validate that every returned citation refers to a chunk actually retrieved for this request and is authorized for the tenant.
11. If evidence is insufficient, return a clear abstention such as: "I couldn't find enough evidence in the selected documents to answer that reliably."
12. Persist the question, answer, citations, and operational metadata. Avoid logging full sensitive document contents by default.

### Hybrid retrieval

- **Vector search** helps with semantic similarity and paraphrases.
- **Full-text search** helps with exact terms, names, identifiers, clause numbers, and error codes.
- **Fusion/reranking** combines candidate lists. Choose the approach based on a small evaluation set rather than assuming one strategy is best.

### Citation format

A citation should include:
- document ID and display filename,
- page number or section if available,
- short supporting excerpt,
- a stable chunk reference,
- optional relevance score for internal diagnostics.

The UI should let a user open the source document near the cited page when feasible. A citation is not proof that the answer is correct; it is a verification aid. The system should validate citation references and evaluate answer grounding.

## 8. Tenant Isolation and Authorization

### Roles for the MVP

- **Owner:** manage workspace, members, documents, and workspace settings.
- **Admin:** manage members and documents; cannot transfer or delete ownership unless explicitly allowed.
- **Member:** upload and query documents according to workspace policy.
- **Viewer (optional):** read/query only if granted access.

### Mandatory rules

- Derive user identity from a verified authentication session/token.
- Check membership and role on every tenant-scoped API request.
- Scope documents, jobs, chunks, conversations, messages, citations, and signed download URLs to the tenant.
- Never accept a client-supplied tenant ID as sufficient proof of access.
- Prevent cross-tenant access through guessed IDs, manipulated filters, search endpoints, exports, and background jobs.
- Workers must use tenant/document IDs from trusted database job records and re-check document state before writing results.
- Use short-lived signed URLs only after authorization; do not make uploaded files public.
- Record security-relevant operations in audit logs.

### Threats to test

- User from Tenant A queries Tenant B's document ID.
- User manipulates `tenant_id` in request body or query parameters.
- Vector search returns a chunk from another tenant.
- A background job retries after a document is deleted.
- A signed URL remains usable longer than intended.
- Prompt injection in a document attempts to reveal system prompts or data from other files.
- A citation points to a chunk not included in the authorized retrieval set.
- A pooled database connection retains stale tenant context.

## 9. Security, Privacy, and Reliability

- Use TLS in transit and encryption at rest for database, object storage, and backups.
- Store secrets in environment variables for local development and a secret manager in production; never commit secrets.
- Use short-lived authentication credentials, secure cookies where applicable, CSRF protection where relevant, and safe CORS settings.
- Enforce upload limits, request timeouts, content-type checks, and rate limits.
- Consider malware scanning and archive/decompression limits before supporting formats beyond PDF.
- Treat document text as untrusted input. Retrieved content must not override system instructions or authorize tool calls.
- Do not allow an LLM to decide whether a user is authorized to access a document.
- Minimize sensitive data in logs. Define retention and deletion behavior for files, chunks, embeddings, chat history, and backups.
- Use bounded retries, queue monitoring, idempotency keys where needed, and graceful handling of model-provider outages.
- Provide a delete workflow that removes access immediately and schedules removal of the original file, chunks, embeddings, derived artifacts, and related records in accordance with the retention policy.
- Document limitations: model output may be wrong, citations can be incomplete, and users must verify high-stakes legal or technical interpretations.

## 10. API Surface (Proposed)

Prefix: `/api/v1`

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/me` | Current authenticated user |
| `GET` | `/tenants` | Tenants the user belongs to |
| `POST` | `/tenants` | Create a workspace |
| `GET` | `/tenants/{tenant_id}/members` | List workspace members |
| `POST` | `/tenants/{tenant_id}/members` | Invite/add a member |
| `POST` | `/tenants/{tenant_id}/documents` | Create upload session or upload a document |
| `GET` | `/tenants/{tenant_id}/documents` | List documents with pagination |
| `GET` | `/tenants/{tenant_id}/documents/{document_id}` | Get document metadata and status |
| `DELETE` | `/tenants/{tenant_id}/documents/{document_id}` | Request document deletion |
| `POST` | `/tenants/{tenant_id}/documents/{document_id}/reindex` | Reprocess a document |
| `GET` | `/tenants/{tenant_id}/jobs/{job_id}` | Get ingestion job status |
| `POST` | `/tenants/{tenant_id}/conversations` | Create conversation |
| `GET` | `/tenants/{tenant_id}/conversations` | List conversations |
| `POST` | `/tenants/{tenant_id}/conversations/{conversation_id}/messages` | Ask a question |
| `GET` | `/tenants/{tenant_id}/conversations/{conversation_id}/messages` | Get conversation history |
| `GET` | `/tenants/{tenant_id}/documents/{document_id}/download` | Obtain authorized, short-lived download access |

Exact payloads, status codes, pagination conventions, and error formats are defined in `contract.md`.

## 11. Observability and Evaluation

### Operational metrics

- Upload success/failure rate and file-size distribution.
- Ingestion duration by stage, queue wait time, retry count, and failed-job count.
- Number of chunks and extraction failures per document.
- Query latency by retrieval, reranking, and generation stage.
- Model-provider errors, token usage, and estimated cost.
- Retrieval result counts, abstention rate, and citation-validation failures.
- Authorization failures and suspicious cross-tenant access attempts.

### Quality evaluation

Create a small, versioned test corpus containing representative PDFs and questions with known supporting pages. Measure:
- retrieval recall at K,
- citation precision / whether cited passages support the answer,
- answer correctness judged against a rubric,
- appropriate abstention when evidence is absent,
- latency and cost per query.

Run this evaluation when changing the chunking strategy, embedding model, retrieval weights, prompt, or answer model.

## 12. Suggested Repository Structure

```text
document-intelligence-platform/
├── apps/
│   └── web/                     # Next.js frontend
├── services/
│   ├── api/                     # FastAPI routes, auth, schemas
│   └── worker/                  # Ingestion jobs
├── packages/
│   └── shared-contracts/        # OpenAPI-generated or shared schemas if useful
├── infra/
│   ├── docker/
│   └── compose.yaml
├── migrations/                  # Database migrations
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── security/
│   └── evaluation/
├── docs/
│   ├── architecture.md
│   └── contract.md
├── .env.example
├── .gitignore
└── README.md
```

Keep secrets, uploaded customer files, model artifacts, local databases, and generated private data out of version control.

## 13. Implementation Phases

### Phase 1 — Foundation
- Set up repository, Docker Compose, PostgreSQL + pgvector, Redis, object storage emulator, FastAPI, and Next.js.
- Add migrations, health checks, structured logging, and configuration validation.
- Implement authentication integration and tenant membership checks.

### Phase 2 — Document lifecycle
- Add secure upload, document listing, background queue, status polling, PDF text extraction, chunking, embeddings, and indexing.
- Make processing idempotent and test retry/failure states.

### Phase 3 — RAG chat
- Add hybrid retrieval, context assembly, answer generation, citation validation, abstention, and chat history.
- Build a citation viewer and a basic evaluation set.

### Phase 4 — Hardening
- Add tenant-isolation integration tests, rate limits, audit events, deletion/re-index workflows, and observability.
- Test oversized/corrupt PDFs, provider outages, duplicate jobs, and concurrent requests.

### Phase 5 — SaaS readiness
- Add billing/quotas, workspace invitations, usage dashboards, retention controls, stronger admin tools, and optional SSO only after core security is reliable.

## 14. Definition of Done for the MVP

The MVP is ready for a portfolio demo when:
- A user can create or access a workspace and cannot access another tenant's data.
- An authorized user can upload a valid PDF and see asynchronous processing status.
- A ready document can be queried in chat.
- Answers include validated source citations or abstain when evidence is inadequate.
- Hybrid retrieval is tenant-filtered and has automated tests.
- Failed ingestion can be retried safely without duplicate chunks.
- Deleting a document makes it unavailable immediately and triggers cleanup of its stored/indexed content.
- Logs and tests cover the main failure paths.
- Setup instructions allow another developer to run the application locally.
