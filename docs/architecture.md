# System Architecture — Enterprise AI Knowledge & Automation Platform

## 1. Overview

The Enterprise AI Knowledge & Automation Platform is a modular, service-oriented
system that ingests enterprise documents, indexes them into a vector store, and
exposes Retrieval-Augmented Generation (RAG) and autonomous AI-agent capabilities
through a secured API. It is designed to demonstrate the full skill set of a modern
Data/AI Engineer: software engineering, data engineering, ML, GenAI, RAG, AI agents,
MLOps/LLMOps, cloud engineering, DevOps, and enterprise security & governance.

This document describes the target architecture across all project phases. Not every
layer is implemented yet — see the [Implementation Status](#7-implementation-status)
section for what exists today versus what is planned.

## 2. High-Level Architecture

```mermaid
flowchart TD
    U[User / Browser] --> FE[Frontend<br/>Next.js]
    FE --> GW[API Gateway<br/>FastAPI]

    GW --> AUTH[Authentication Service<br/>User Management + RBAC]
    GW --> DOC[Document Processing Service<br/>ETL - Chunking - Embeddings]
    GW --> RAG[RAG Service<br/>LangChain + LlamaIndex]
    GW --> AGENT[AI Agent Service<br/>LangGraph]

    AUTH --> DB[(PostgreSQL<br/>Users - Audit - Metadata)]
    DOC --> DB
    DOC --> VDB[(Vector Database<br/>Qdrant)]

    RAG --> VDB
    RAG --> LLM[LLM Provider<br/>OpenAI / Azure OpenAI]
    AGENT --> RAG
    AGENT --> LLM
    AGENT --> TOOLS[External Tools / APIs]

    subgraph Observability
        MON[Monitoring & Evaluation<br/>LangSmith - Ragas - Grafana]
    end

    GW -.traces.-> MON
    RAG -.traces.-> MON
    AGENT -.traces.-> MON
    DB -.metrics.-> MON
    VDB -.metrics.-> MON

    subgraph Cloud[Cloud Infrastructure - AWS / Azure]
        GW
        AUTH
        DOC
        RAG
        AGENT
        DB
        VDB
        MON
    end
```

## 3. Request & Data Flow

### 3.1 Document Ingestion Flow

```mermaid
sequenceDiagram
    participant User
    participant FE as Frontend (Next.js)
    participant GW as API Gateway (FastAPI)
    participant Auth as Auth/RBAC
    participant Doc as Document Service
    participant PG as PostgreSQL
    participant VDB as Qdrant

    User->>FE: Upload document (PDF/DOCX)
    FE->>GW: POST /api/v1/documents (JWT)
    GW->>Auth: Validate JWT + role
    Auth-->>GW: Authorized
    GW->>Doc: Persist file + enqueue processing
    Doc->>PG: Insert document metadata (status=PENDING)
    Doc->>Doc: Extract text (PyMuPDF / python-docx)
    Doc->>Doc: Chunk text (overlapping windows)
    Doc->>Doc: Generate embeddings (embedding model)
    Doc->>VDB: Upsert vectors + payload
    Doc->>PG: Insert document_chunks + status=INDEXED
    Doc-->>GW: 201 Created (document_id)
    GW-->>FE: Document accepted
```

### 3.2 RAG Query Flow

```mermaid
sequenceDiagram
    participant User
    participant GW as API Gateway
    participant RAG as RAG Service
    participant VDB as Qdrant
    participant LLM as LLM Provider
    participant MON as LangSmith/Ragas

    User->>GW: POST /api/v1/rag/query {question} (JWT)
    GW->>RAG: Forward query
    RAG->>RAG: Embed question
    RAG->>VDB: Similarity search (top-k)
    VDB-->>RAG: Relevant chunks + scores
    RAG->>LLM: Prompt (question + retrieved context)
    LLM-->>RAG: Grounded answer
    RAG->>MON: Log trace + evaluation
    RAG-->>GW: Answer + source citations
    GW-->>User: Response
```

### 3.3 AI Agent Flow (LangGraph)

```mermaid
flowchart LR
    Q[User Task] --> P[Planner Node]
    P --> R{Needs Retrieval?}
    R -- Yes --> RT[RAG Tool]
    R -- No --> TL[Tool Selection]
    RT --> TL
    TL --> EX[Execute Tool]
    EX --> RF{Task Complete?}
    RF -- No --> P
    RF -- Yes --> ANS[Final Answer]
    ANS --> MON[Trace to LangSmith]
```

## 4. Component & Technology Choices

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | Next.js (React, TypeScript) | SSR/CSR hybrid, strong ecosystem, easy auth integration and streaming UI for chat. |
| API Gateway | FastAPI (Python) | Async, high performance, native OpenAPI/Swagger, Pydantic validation, ideal for AI/ML Python stack. |
| Authentication | JWT (python-jose) + passlib/bcrypt | Stateless tokens scale horizontally; bcrypt for secure password hashing. |
| Authorization | Role-Based Access Control (ADMIN/MANAGER/EMPLOYEE) | Simple, auditable enterprise access model. |
| Relational DB | PostgreSQL + SQLAlchemy 2.0 | ACID guarantees for users, audit logs, and document metadata; mature ORM. |
| Migrations | Alembic | Versioned, reproducible schema changes instead of `create_all`. |
| Document Parsing | PyMuPDF, python-docx | Reliable extraction from PDF and Word documents. |
| Vector Database | Qdrant | High-performance ANN search, payload filtering, easy self-hosting and cloud options. |
| RAG Framework | LangChain + LlamaIndex | LangChain for orchestration/chains; LlamaIndex for advanced indexing/retrieval strategies. |
| Agent Framework | LangGraph | Graph-based, stateful multi-step agent orchestration with cycles and checkpointing. |
| LLM Provider | OpenAI / Azure OpenAI | State-of-the-art models; Azure option for enterprise compliance. |
| Observability | LangSmith, Ragas, Grafana | LangSmith for LLM tracing; Ragas for RAG quality metrics; Grafana for infra/metrics dashboards. |
| Containerization | Docker + Docker Compose | Reproducible local & CI environments; parity with production. |
| Orchestration | Kubernetes (target) | Scalable production deployment. |
| Cloud | AWS / Azure | Managed compute, storage, secrets, and networking. |

## 5. Security & Governance

- **Authentication:** Stateless JWT bearer tokens with configurable expiry.
- **Authorization:** RBAC enforced at the API layer; least-privilege per role.
- **Audit Logging:** All security-relevant actions recorded in `audit_logs`.
- **Secrets Management:** Environment variables (`.env`), never committed; `.env.example`
  documents required keys. Production uses cloud secret managers (AWS Secrets Manager /
  Azure Key Vault).
- **Data Isolation:** Document access scoped by ownership and role.
- **Transport Security:** TLS termination at the gateway/load balancer.

## 6. Deployment Topology

```mermaid
flowchart TB
    subgraph Client
        BROWSER[Browser]
    end
    subgraph Edge
        LB[Load Balancer / TLS]
    end
    subgraph Services
        FE[Next.js]
        API[FastAPI Gateway]
    end
    subgraph Data
        PG[(PostgreSQL)]
        QD[(Qdrant)]
    end
    subgraph Ext
        LLM[LLM Provider]
        OBS[LangSmith / Grafana]
    end
    BROWSER --> LB --> FE --> API
    API --> PG
    API --> QD
    API --> LLM
    API -.-> OBS
```

## 7. Implementation Status

| Phase | Scope | Status |
|-------|-------|--------|
| 0 | Planning & system design (this docs set) | In progress |
| 1 | Backend foundation: FastAPI, PostgreSQL, JWT auth, RBAC, audit logging, Alembic | Core complete |
| 2 | Containerization: Dockerfile + docker-compose | Complete |
| 3 | Document ingestion pipeline (ETL, chunking, embeddings) | Planned |
| 4 | Vector database integration (Qdrant) | Planned |
| 5 | RAG service (LangChain + LlamaIndex) | Planned |
| 6 | AI agent service (LangGraph) | Planned |
| 7+ | Monitoring/evaluation, MLOps, cloud deployment, hardening | Planned |

> This architecture is the north star for the roadmap. Layers marked *Planned* define
> the intended integration contracts so that current services (auth, persistence) are
> built with the full system in mind.
