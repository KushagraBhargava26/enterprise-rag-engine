# API & Engineering Contract — Enterprise Multi-Tenant RAG Platform

- **Status:** Proposed contract for implementation
- **Version:** 0.1
- **Base path:** `/api/v1`
- **Companion document:** `architecture.md`

This contract defines the expected behavior between the web client, API, database, background workers, and RAG pipeline. It is intentionally implementation-oriented but does not replace a generated OpenAPI specification.

## 1. Contract Principles

1. **Authorization before access:** authenticate the caller and authorize tenant/resource access before returning metadata, issuing download links, querying indexed content, or mutating state.
2. **Tenant isolation is mandatory:** all tenant-owned resources are scoped to a verified tenant membership. A tenant ID in a URL is a selector, not proof of authorization.
3. **Asynchronous ingestion:** document upload returns before extraction and embedding finish.
4. **Explicit state:** document processing status is persisted and queryable.
5. **Grounded responses:** citations must refer to retrieved, authorized chunks; insufficient evidence must result in abstention rather than a fabricated answer.
6. **Stable errors:** errors use a predictable response structure and do not expose stack traces, secrets, raw prompts, or private content.
7. **Idempotent background work:** retries must not create duplicate indexed chunks or resurrect deleted documents.
8. **Versioned API:** breaking changes require a new API version or a documented migration.

## 2. Authentication and Authorization

The API assumes an authentication provider or a secure session layer supplies a verified user identity. The precise provider is a deployment choice.

- The frontend must not be trusted to assert its own user ID, role, or membership.
- The API resolves the authenticated subject to an internal `user_id`.
- Every tenant-scoped request verifies membership and the required role.
- Owner/admin-only actions include member management and workspace-level configuration.
- Members may upload, list, and query documents according to workspace policy.
- A viewer role, if enabled, is read/query-only.
- Resource IDs must be checked against the authorized tenant even if they are UUIDs.
- Background jobs use trusted database records and re-check resource state before processing.

### Suggested role matrix

| Action | Owner | Admin | Member | Viewer |
| --- | --- | --- | --- | --- |
| View workspace and members | Yes | Yes | Policy-based | Policy-based |
| Manage workspace settings | Yes | Yes | No | No |
| Invite/remove members | Yes | Yes | No | No |
| Upload documents | Yes | Yes | Yes | No |
| List/view permitted documents | Yes | Yes | Yes | Yes |
| Ask questions | Yes | Yes | Yes | Optional |
| Delete any workspace document | Yes | Policy-based | Own uploads or policy-based | No |
| Delete workspace | Yes | No | No | No |

Implement the exact policy centrally; do not scatter ad-hoc role comparisons across route handlers.

## 3. Common Conventions

### IDs and timestamps

- Public resource IDs are opaque identifiers, preferably UUIDs.
- Timestamps are ISO 8601 UTC strings, for example `2026-11-01T10:30:00Z`.
- JSON uses `snake_case` keys for the API.
- List endpoints use cursor pagination or a consistent `limit`/`cursor` scheme. Avoid unbounded result sets.
- API responses must not expose internal object-storage keys, database credentials, or raw provider secrets.

### Common error envelope

```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "The requested document was not found.",
    "request_id": "req_opaque_id",
    "details": {}
  }
}
```

- `code`: stable machine-readable code.
- `message`: safe, user-facing explanation.
- `request_id`: correlates the response with server logs.
- `details`: optional field-level validation information; never include secrets or private document contents.

### Expected HTTP status codes

| Status | Meaning |
| --- | --- |
| `200 OK` | Request succeeded |
| `201 Created` | Resource created |
| `202 Accepted` | Asynchronous task accepted |
| `204 No Content` | Successful operation with no response body |
| `400 Bad Request` | Invalid request semantics |
| `401 Unauthorized` | Missing or invalid authentication |
| `403 Forbidden` | Authenticated but not permitted |
| `404 Not Found` | Resource absent or intentionally concealed |
| `409 Conflict` | State conflict or duplicate operation |
| `413 Payload Too Large` | File/request exceeds configured limit |
| `415 Unsupported Media Type` | Unsupported file type |
| `422 Unprocessable Entity` | Schema or semantic validation failed |
| `429 Too Many Requests` | Rate or quota limit reached |
| `500 Internal Server Error` | Unexpected server error |
| `502/503/504` | Upstream provider or dependency failure/timeout |

For sensitive resource lookups, the implementation may return `404` rather than `403` to avoid confirming that another tenant's resource exists. Apply this consistently.

## 4. Tenant and Membership Endpoints

### `GET /me`

Returns the current authenticated user and the workspaces they can access, or use a separate tenant-list endpoint.

Example:

```json
{
  "id": "usr_uuid",
  "email": "user@example.com",
  "tenants": [
    {
      "id": "ten_uuid",
      "name": "Example Workspace",
      "role": "owner"
    }
  ]
}
```

Do not return authentication-provider access tokens or secrets.

### `POST /tenants`

Creates a workspace for the authenticated user and creates an owner membership in one transaction.

Request:

```json
{
  "name": "Example Workspace",
  "slug": "example-workspace"
}
```

Response: `201 Created`

```json
{
  "id": "ten_uuid",
  "name": "Example Workspace",
  "slug": "example-workspace",
  "created_at": "2026-11-01T10:30:00Z",
  "role": "owner"
}
```

The API must normalize and validate the slug and enforce uniqueness. The client cannot assign itself an arbitrary role.

### `GET /tenants/{tenant_id}/members`

Requires authorized tenant membership. Response includes only the fields needed by the UI.

### `POST /tenants/{tenant_id}/members`

Owner/admin only. Use an invitation workflow or verified account lookup. Never let an arbitrary caller attach another user to a tenant without permission.

Example request:

```json
{
  "email": "colleague@example.com",
  "role": "member"
}
```

Return `201 Created` or `202 Accepted` if an invitation must be sent. The implementation must define invitation expiry and acceptance behavior before shipping invitations.

## 5. Document Endpoints

### `POST /tenants/{tenant_id}/documents`

Creates a document and begins asynchronous ingestion. Implementation may use multipart upload for the MVP or a two-step presigned upload flow for larger files.

For multipart upload:
- Field: `file`
- Supported MVP type: PDF
- Enforce configurable maximum file size and upload limits.
- Verify content type and file signature where practical.
- Generate the object key server-side.
- Store files privately.
- Never use a user-provided filename as a storage path.

Response: `202 Accepted`

```json
{
  "document": {
    "id": "doc_uuid",
    "filename": "employee-handbook.pdf",
    "mime_type": "application/pdf",
    "size_bytes": 482103,
    "status": "queued",
    "created_at": "2026-11-01T10:30:00Z"
  },
  "job": {
    "id": "job_uuid",
    "status": "queued"
  }
}
```

The upload request is accepted only when the file has been safely stored and the document/job state is persisted. If queue publishing and database writes cannot be atomic, use a transactional outbox or another reliable enqueue pattern so a committed job is not silently lost.

### `GET /tenants/{tenant_id}/documents`

Returns a paginated list of documents visible to the caller.

Optional query parameters:
- `status`: `queued`, `processing`, `ready`, `failed`, `deleting`, `deleted`
- `limit`: bounded integer
- `cursor`: opaque pagination cursor

Each item should include ID, filename, size, status, creation time, completion time, and safe error information if failed. Do not include extracted document contents in the list response.

### `GET /tenants/{tenant_id}/documents/{document_id}`

Returns metadata and current processing status after verifying tenant and document access.

Example:

```json
{
  "id": "doc_uuid",
  "filename": "employee-handbook.pdf",
  "status": "ready",
  "page_count": 42,
  "chunk_count": 186,
  "created_at": "2026-11-01T10:30:00Z",
  "processed_at": "2026-11-01T10:31:14Z",
  "error": null
}
```

`page_count` and `chunk_count` may be `null` when unavailable.

### `DELETE /tenants/{tenant_id}/documents/{document_id}`

Requests deletion. The API must revoke access immediately, mark the document as `deleting` or `deleted`, and schedule cleanup of the original file, chunks, embeddings, extracted artifacts, and dependent citations as defined by the retention policy.

Preferred response: `202 Accepted`

```json
{
  "id": "doc_uuid",
  "status": "deleting",
  "message": "Document deletion has been queued."
}
```

Deletion must be idempotent. A worker must not re-index a document after deletion has begun. Backups may follow a separately documented expiry schedule, but deleted content must no longer be queryable through the live application.

### `POST /tenants/{tenant_id}/documents/{document_id}/reindex`

Requires permission to manage or reprocess the document. Creates a new ingestion job and returns `202 Accepted`. The worker must use a versioned extraction/chunking/embedding configuration and must not expose partial indexes as ready.

## 6. Ingestion Job Contract

### Status values

- `queued`: accepted and waiting for a worker.
- `processing`: a worker has claimed the job.
- `ready`: processing completed successfully and the index is queryable.
- `failed`: processing failed permanently or exhausted retries.
- `cancelled`: optional state for explicitly cancelled work.

The document status and job status are related but not identical; a document may have multiple historical jobs after re-indexing. The document is `ready` only when its active index version is complete.

### `GET /tenants/{tenant_id}/jobs/{job_id}`

Example:

```json
{
  "id": "job_uuid",
  "document_id": "doc_uuid",
  "status": "processing",
  "stage": "embedding",
  "progress": {
    "completed_units": 4,
    "total_units": 10
  },
  "attempt": 1,
  "created_at": "2026-11-01T10:30:00Z",
  "started_at": "2026-11-01T10:30:05Z",
  "completed_at": null,
  "error": null
}
```

Progress fields may be omitted if the stage cannot be measured reliably. Never fabricate a percentage. Error responses must be safe and concise.

### Worker guarantees

- Jobs may be delivered more than once; workers must be idempotent.
- Use bounded retries with exponential backoff for transient errors.
- Do not retry permanent parse/validation errors indefinitely.
- Persist stage transitions and failure codes.
- Use unique constraints or versioned index writes to prevent duplicate chunks.
- Re-check document state and tenant ownership before committing indexed results.
- Ensure only the active successful index version is queryable.
- Keep raw stack traces in protected logs, not API responses.

## 7. Conversation and Question Endpoints

### `POST /tenants/{tenant_id}/conversations`

Creates a conversation for the authenticated user in the selected tenant.

Request:

```json
{
  "title": "Contract review"
}
```

Response: `201 Created`

```json
{
  "id": "conv_uuid",
  "title": "Contract review",
  "created_at": "2026-11-01T10:30:00Z"
}
```

The title may be optional and generated from the first question if omitted. Conversations must be tenant-scoped and subject to the chosen workspace conversation-sharing policy.

### `POST /tenants/{tenant_id}/conversations/{conversation_id}/messages`

Submits a question and returns an answer. This endpoint may be synchronous for the MVP with a strict timeout, or asynchronous/streamed later. If using synchronous mode, return `200 OK` only after the answer and citations have been validated.

Request:

```json
{
  "question": "What is the termination notice period?",
  "document_ids": ["doc_uuid_1", "doc_uuid_2"],
  "top_k": 8
}
```

Rules:
- `question` must be non-empty and within a configured length limit.
- `document_ids`, when supplied, must all belong to the authorized tenant and be queryable by the caller.
- Omitted `document_ids` means all documents the caller is allowed to query, according to workspace policy.
- `top_k` is bounded server-side; clients cannot force unbounded retrieval.
- Only documents with a complete, active index are eligible.
- Tenant and document filters must be applied inside retrieval, not after results are returned.
- The LLM must not decide whether the caller is authorized.
- Treat question text and retrieved passages as untrusted data.

Response:

```json
{
  "message": {
    "id": "msg_uuid",
    "role": "assistant",
    "content": "The agreement requires 30 days' written notice before termination.",
    "created_at": "2026-11-01T10:32:00Z",
    "answer_status": "grounded"
  },
  "citations": [
    {
      "id": "cite_uuid",
      "document_id": "doc_uuid_1",
      "filename": "service-agreement.pdf",
      "page_number": 12,
      "section_title": "Termination",
      "excerpt": "Either party may terminate this agreement by providing thirty days' written notice...",
      "chunk_id": "chunk_uuid",
      "relevance_score": 0.87
    }
  ],
  "meta": {
    "retrieval_mode": "hybrid",
    "retrieved_count": 8,
    "model": "configured-model-alias"
  }
}
```

The sample answer and IDs are illustrative only. Do not expose internal reasoning or private chain-of-thought. The `model` field may be omitted if exposing provider/model details is undesirable.

### Abstention response

When retrieval does not provide enough relevant evidence, the API must not invent an answer. Example:

```json
{
  "message": {
    "id": "msg_uuid",
    "role": "assistant",
    "content": "I couldn't find enough evidence in the selected documents to answer that reliably.",
    "created_at": "2026-11-01T10:32:00Z",
    "answer_status": "insufficient_evidence"
  },
  "citations": [],
  "meta": {
    "retrieval_mode": "hybrid",
    "retrieved_count": 0
  }
}
```

Allowed `answer_status` values:
- `grounded`
- `insufficient_evidence`
- `generation_error` (only if the application intentionally persists a safe failure message)

Do not represent a response as grounded merely because the model produced citations. Citation references must be checked against the authorized retrieved set. Consider additional answer-grounding evaluation for production.

### `GET /tenants/{tenant_id}/conversations/{conversation_id}/messages`

Returns paginated history for a conversation the caller can access. Do not allow changing the conversation ID to read another user's private history unless the workspace policy explicitly supports shared conversations.

## 8. Retrieval and Citation Contract

The retrieval pipeline must:

1. Restrict candidates to the authorized tenant and permitted document IDs before ranking.
2. Run vector and keyword retrieval against eligible indexed chunks.
3. Merge/rerank candidates using a configurable, tested strategy.
4. Keep source metadata attached throughout the pipeline.
5. Pass bounded context to the answer model.
6. Validate returned citation IDs against the chunks actually supplied to the model.
7. Reject, repair, or omit citations that point to unknown or unauthorized chunks.
8. Abstain when relevance/evidence thresholds are not met.

Citation fields:
- `document_id`: stable document identifier.
- `filename`: display name.
- `page_number`: integer or `null` if unavailable.
- `section_title`: string or `null`.
- `excerpt`: short evidence snippet.
- `chunk_id`: stable chunk reference.
- `relevance_score`: optional internal/normalized score; it is not a probability of correctness.

The UI must not claim a citation guarantees correctness. Users should be able to inspect the original document when they have access.

## 9. File and Data Handling Contract

- Accept only explicitly supported file types and configured size limits.
- Use private object storage and generated storage keys.
- Do not execute uploaded content.
- Treat extracted text as untrusted input; prompt injection in a PDF must not change access controls or trigger privileged actions.
- Store document checksums to detect duplicate uploads if deduplication is enabled. Deduplication must not accidentally share content across tenants.
- Keep original files, extracted text, chunks, embeddings, and derived artifacts under a consistent retention/deletion policy.
- Define whether chat messages and citations are deleted with a source document or retained with the citation marked unavailable. The UI must not expose deleted source content from stale messages.
- Avoid writing full source text, secrets, or personal data to application logs.
- Use short-lived signed URLs and issue them only after authorization.
- Set retention periods and backup expiry behavior before production use.

## 10. Rate Limits, Quotas, and Resource Controls

Set configurable limits for:
- maximum upload size,
- uploads per user/tenant in a time window,
- number of concurrent ingestion jobs,
- question length,
- questions per user/tenant in a time window,
- maximum `top_k` and context size,
- model timeout and retry count,
- storage usage and token budget.

Return `429 Too Many Requests` when a rate limit is exceeded and include a safe retry hint when possible. Limits should be configurable rather than hard-coded in the UI.

## 11. Security and Acceptance Tests

The following are release-blocking tests:

### Tenant isolation
- A Tenant A user cannot list, download, delete, re-index, or query a Tenant B document.
- Changing `tenant_id`, `document_id`, `conversation_id`, `job_id`, or `chunk_id` cannot bypass authorization.
- Search results and citations never include unauthorized tenant content.
- A user cannot add themselves as owner/admin.
- Signed URLs are not issued for unauthorized documents.

### Ingestion reliability
- Oversized, corrupt, empty, and unsupported files fail safely.
- Duplicate queue delivery does not create duplicate active chunks.
- A transient provider outage retries within a bounded policy.
- A permanent parsing error ends in `failed` with a safe message.
- Deletion during processing prevents the worker from publishing a ready index.
- Re-indexing does not expose a partially written index.

### RAG quality and safety
- A question answered by the corpus returns citations to supporting passages.
- A question not answered by the corpus triggers abstention.
- Citation IDs not present in the retrieved context are rejected or omitted.
- A malicious instruction embedded in a PDF cannot override system instructions, reveal secrets, or access other tenants.
- Exact terms and semantic paraphrases are both tested for hybrid retrieval.
- Provider timeouts do not return fabricated success responses.

### API hygiene
- Invalid payloads receive structured errors.
- Internal stack traces and credentials never appear in responses.
- Pagination is bounded.
- Rate limits are enforced.
- Health checks do not reveal secrets or customer data.

## 12. Definition of Contract Compliance

An implementation is compliant with this contract when:
- API behavior matches the documented schemas and status semantics.
- Tenant membership and resource authorization are enforced server-side on every request.
- Ingestion is asynchronous, observable, and safe to retry.
- Retrieval is filtered before results can cross tenant boundaries.
- Responses return validated citations or explicit abstention.
- Deletion and re-indexing have deterministic state transitions.
- Security and failure-path tests pass in CI.
- Any intentional deviation is documented and reflected in the OpenAPI schema and tests.

## 13. Open Decisions Before Production

Resolve and document these choices during implementation:
- Authentication provider and session strategy.
- Object-storage provider and signed-URL behavior.
- PDF parser and optional OCR provider.
- Embedding and generation model providers, model versions, and data-processing terms.
- Chunking parameters and retrieval/reranking strategy based on evaluation.
- Workspace sharing policy for conversations and documents.
- Data retention, backup expiry, and deletion guarantees.
- Whether to add streaming responses, SSO, billing, quotas, and audit export.
- Required compliance controls for the target customers and jurisdictions.
