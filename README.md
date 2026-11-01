# Enterprise Multi-Tenant RAG & Document Intelligence Platform

A production-grade, multi-tenant document intelligence SaaS platform engineered for grounded, citation-backed question answering with strict tenant isolation, asynchronous document ingestion, and hybrid retrieval (vector similarity + PostgreSQL full-text search).

---

## Key Architectural Principles

1. **Tenant Isolation by Default**: Strict server-side verification of tenant membership and role on every API call. Tenant-scoped database queries, partitioned vectors, and authorization checks before any document access.
2. **Grounded Answers & Citations**: Hybrid reciprocal-rank fusion across pgvector and PostgreSQL FTS. Answers strictly grounded in retrieved evidence with validated citations or explicit abstention (`"insufficient_evidence"`).
3. **Asynchronous Ingestion Pipeline**: Decoupled parsing, chunking, embedding generation, and indexing powered by background workers and Redis.
4. **Observable & Recoverable Workflows**: Idempotent workers, explicit state machines (`queued` → `processing` → `ready` / `failed`), structured JSON logging, and audit tracking.

---

## Project Structure

```text
enterprise-rag-engine/
├── apps/
│   └── web/                     # Next.js frontend (React 19 / TypeScript / Tailwind)
├── services/
│   ├── api/                     # FastAPI backend (Auth, Tenant AuthZ, Ingestion, RAG Chat)
│   └── worker/                  # Python background worker (PDF parse, chunk, embed, index)
├── packages/
│   └── shared-contracts/        # Shared Pydantic / TypeScript schemas
├── infra/
│   ├── docker/                  # Dockerfiles for API, Worker, and Web
│   └── compose.yaml             # Multi-service composition (PostgreSQL+pgvector, Redis, MinIO)
├── migrations/                  # Alembic database migrations
├── tests/
│   ├── unit/                    # Unit tests for chunking, fusion, citations
│   ├── integration/             # API and worker integration tests
│   ├── security/                # Cross-tenant isolation and auth bypass tests
│   └── evaluation/              # RAG quality and retrieval evaluation
├── docs/
│   ├── architecture.md          # Complete system architecture specification
│   └── contract.md              # API & Engineering contract specification
├── .env.example                 # Environment configuration template
├── compose.yaml                 # Root Docker Compose include
└── README.md
```

---

## Tech Stack

- **Web Frontend**: Next.js 14+, React 19, TypeScript, Tailwind CSS, Lucide Icons
- **Backend API**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Asyncpg
- **Database & Search**: PostgreSQL 16 + `pgvector` + PostgreSQL Full-Text Search (TSVector)
- **Object Storage**: S3-compatible storage (MinIO for local dev, AWS S3 / Cloudflare R2 for production)
- **Queue & Background Jobs**: Redis 7 + Python async worker
- **Document Processing**: `pypdf` / `pdfplumber`, recursive token-aware chunking
- **RAG & Embeddings**: Pluggable provider adapter (Mock provider for zero-cost tests/CI, OpenAI, Gemini)

---

## Quickstart & Local Development

### Prerequisites

- Docker & Docker Compose
- Node.js 20+
- Python 3.12+

### 1. Clone & Configure Environment

```bash
cp .env.example .env
```

### 2. Run with Docker Compose

To spin up all services (PostgreSQL + pgvector, Redis, MinIO, API, Worker, Frontend):

```bash
docker compose up --build
```

- API Docs: `http://localhost:8000/docs`
- Web UI: `http://localhost:3000`
- MinIO Console: `http://localhost:9001` (user: `minioadmin`, pass: `minioadmin`)

### 3. Running Locally for Development

#### Database & Infrastructure
```bash
docker compose up -d postgres redis minio createbuckets
```

#### API & Worker
```bash
py -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

pip install -r services/api/requirements.txt
alembic upgrade head
uvicorn services.api.main:app --reload --port 8000
```

#### Frontend
```bash
cd apps/web
npm install
npm run dev
```

---

## Specification Documents

- [Architecture Specification](docs/architecture.md)
- [API & Engineering Contract](docs/contract.md)
