# Enterprise AI Knowledge & Automation Platform

> Query your private documents with AI. Get instant, cited answers from your own knowledge base — without sending sensitive data to public search engines.

---

## The Problem

Every company and academic institution sits on a mountain of private documents — internal policies, research papers, legal contracts, clinical guidelines, onboarding manuals, lecture notes, project reports. The knowledge is there. Getting to it is the problem.

**For companies:**
- A new employee needs to understand the leave policy. They ask HR. HR finds the document. Twenty minutes gone.
- A manager needs to know what the contract with a vendor says about liability. Legal searches through hundreds of PDFs.
- A support agent needs to answer a customer question. They don't know which internal wiki page has the answer.

**For students and researchers:**
- A student has 40 research papers to review before their thesis. Reading all of them takes weeks.
- A researcher needs to find every paper in their collection that mentions a specific methodology.
- A lecturer wants to quickly check what their course materials say about a topic a student just asked about.

The common thread: **the information already exists, but it is locked inside documents that humans have to manually search through**. This is slow, error-prone, and scales poorly as document collections grow.

Existing solutions fall short in different ways. Public AI tools like ChatGPT cannot access private documents. Enterprise search tools return a list of documents — they don't answer the question. Building a custom solution requires specialist ML engineering that most teams don't have in-house.

---

## The Solution

The Enterprise AI Knowledge & Automation Platform lets organisations upload their private documents and query them in plain language. Instead of searching for a document, you ask a question and get a direct answer — with citations showing exactly which document and section the answer came from.

```
"What is the company's policy on remote work expenses?"
↓
Answer: "Employees may claim up to €500 per year for home office equipment,
subject to manager approval. [Source: HR Policy Manual v3, Section 4.2]"
```

The system never sends your documents to public AI services. Everything is processed and stored within your own infrastructure — on your servers, in your cloud account, under your control.

---

## Who It Is For

| User | Use Case |
|---|---|
| Companies | Query internal policies, contracts, HR documents, technical specs |
| Law firms | Search case law, contracts, and legal briefs instantly |
| Hospitals & clinics | Retrieve clinical guidelines and medical protocols |
| Universities | Let students and researchers query academic paper collections |
| Consulting firms | Search project reports, frameworks, and client deliverables |
| Government agencies | Navigate large regulatory and compliance document libraries |

---

## The Technology Stack

Every technology choice was made deliberately. Here is what we use and why.

### Backend — FastAPI (Python)
FastAPI is the industry standard for building ML-adjacent APIs. It is asynchronous, handles file uploads natively, generates automatic documentation, and integrates cleanly with every major AI library in the Python ecosystem. It is what most production RAG systems are built on.

### Database — PostgreSQL
A battle-tested relational database that stores user accounts, document metadata, audit logs, and text chunks. PostgreSQL's reliability and ACID compliance make it the right choice for enterprise data — you never lose a record.

### ORM — SQLAlchemy
Lets us define database tables as Python classes and query them without writing raw SQL. Migrations via Alembic mean the database schema evolves safely as the system grows.

### Vector Database — Qdrant
When a user asks a question, the system needs to find the most relevant chunks of text from potentially thousands of documents. This is not a keyword search problem — it is a semantic similarity problem. Qdrant stores document chunks as mathematical vectors and finds the ones that are closest in meaning to the question, even if the exact words don't match.

### Embeddings — Sentence Transformers / OpenAI
Before text can be stored in Qdrant it must be converted into a vector — a list of numbers that captures its meaning. Embedding models do this conversion. We benchmark multiple models (MiniLM, BGE, OpenAI) to find the best trade-off between speed, cost, and accuracy for each deployment.

### RAG Framework — LangChain / LlamaIndex
RAG stands for Retrieval-Augmented Generation. It is the core technique that makes this system work: retrieve the relevant document chunks, then pass them to a language model as context, then generate an answer grounded in that context. LangChain and LlamaIndex are the leading frameworks for building RAG pipelines.

### LLM Layer — OpenAI / Anthropic / Ollama
The system is model-agnostic. A factory pattern routes each request to the appropriate language model. Cloud models (GPT-4, Claude) give the best answers. Local models (Ollama) keep everything on-premise for maximum data privacy. Cost and latency are tracked per request.

### AI Agents — LangGraph
Beyond simple question-answering, agents can execute multi-step workflows: search across multiple document collections, synthesise findings from different sources, and produce structured reports. LangGraph manages the state of these multi-step processes.

### Frontend — Next.js / React / TypeScript
A clean, responsive interface with a chat-style document query experience, streaming responses, source attribution, and an admin panel for managing users and documents.

### Containerisation — Docker / Docker Compose
Every service runs in an isolated container. A single `docker compose up` command starts the entire platform on any machine. This eliminates environment inconsistencies and is the foundation for cloud deployment.

### Cloud — AWS / Azure
The containerised services deploy directly to managed cloud infrastructure — ECS Fargate or Azure Container Apps for the backend, RDS or Azure Database for PostgreSQL, S3 or Blob Storage for raw document files. The platform scales horizontally: add more backend containers as load increases.

### CI/CD — GitHub Actions
Every push to main runs automated tests, builds a new Docker image, and deploys to the target environment. No manual deployments.

### Observability — LangSmith / Prometheus / Grafana
AI applications fail in subtle ways — the answer is factually wrong, the source citation is hallucinated, the response is too slow. LangSmith traces every LLM call. Prometheus collects metrics. Grafana visualises system health. Ragas and DeepEval measure answer quality automatically.

---

## System Architecture

```
                        ┌─────────────────┐
                        │   Next.js UI    │
                        │  (Chat / Admin) │
                        └────────┬────────┘
                                 │ HTTPS
                        ┌────────▼────────┐
                        │   FastAPI       │
                        │   API Gateway   │
                        └────────┬────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
    ┌─────────▼──────┐  ┌───────▼────────┐  ┌──────▼───────┐
    │  Auth Service  │  │  Doc Ingestion │  │  RAG Service │
    │  JWT + RBAC    │  │  ETL Pipeline  │  │  LangChain   │
    └─────────┬──────┘  └───────┬────────┘  └──────┬───────┘
              │                  │                  │
    ┌─────────▼──────┐  ┌───────▼────────┐  ┌──────▼───────┐
    │  PostgreSQL    │  │  Embeddings    │  │  AI Agents   │
    │  Users / Logs  │  │  Sentence      │  │  LangGraph   │
    │  Doc Metadata  │  │  Transformers  │  └──────┬───────┘
    └────────────────┘  └───────┬────────┘         │
                                │           ┌──────▼───────┐
                        ┌───────▼────────┐  │  LLM Layer   │
                        │    Qdrant      │  │  OpenAI /    │
                        │ Vector Store   │  │  Anthropic / │
                        └────────────────┘  │  Ollama      │
                                            └──────────────┘
```

---

## How a Query Works — Step by Step

```
1. User types:  "What does our contract say about payment terms?"

2. The question is converted into a vector (embedding)

3. Qdrant finds the 5 most semantically similar document chunks

4. Those chunks are passed to the LLM as context:
   "Using only the following excerpts, answer the question..."

5. The LLM generates a grounded answer

6. The answer is returned with source citations:
   "Payment is due within 30 days of invoice.
    [Source: Vendor Contract 2024, Section 8.1]"
```

The LLM never invents facts — it can only use what is in the retrieved chunks. This is why RAG dramatically reduces hallucination compared to asking a plain LLM.

---

## Security & Governance

Enterprise data requires enterprise-grade security.

**Authentication** — JWT tokens with 30-minute expiry. Every API request is authenticated.

**Role-Based Access Control** — three roles (ADMIN, MANAGER, EMPLOYEE) with different permissions. A manager cannot access another manager's documents. An employee cannot access admin functions.

**Document Ownership** — every document is linked to its owner. Queries only search documents the requesting user has access to.

**Audit Logging** — every login, upload, query, and deletion is logged with a timestamp and user ID. Full compliance trail.

**Data Privacy** — documents never leave your infrastructure. No third-party service sees your raw text unless you explicitly configure a cloud LLM. Local models via Ollama provide a fully air-gapped option.

**Compliance** — the architecture supports GDPR (data deletion, ownership) and HIPAA concepts (audit trails, access controls) out of the box.

---

## Build Phases

The platform is built in structured phases, each adding a layer of capability.

| Phase | What Gets Built |
|---|---|
| 0 | System design, architecture docs, repository setup |
| 1 | FastAPI backend, PostgreSQL, authentication, RBAC |
| 2 | Docker containerisation, portable deployment |
| 3 | Document ingestion pipeline — PDF, DOCX, TXT parsing |
| 4 | Text chunking and cleaning for LLM consumption |
| 5 | Embedding generation and model benchmarking |
| 6 | Qdrant vector database, semantic search |
| 7 | RAG system — retrieval, prompting, answer generation |
| 8 | Multi-LLM platform — OpenAI, Anthropic, Ollama routing |
| 9 | AI agents — research, reporting, multi-source synthesis |
| 10 | Next.js frontend — chat UI, admin panel, streaming |
| 11 | Observability — LangSmith, Prometheus, Grafana |
| 12 | Evaluation — Ragas, DeepEval, hallucination detection |
| 13 | Security hardening, compliance features |
| 14 | Cloud deployment — AWS / Azure |
| 15 | CI/CD — GitHub Actions automated pipeline |
| 16 | Healthcare extension — clinical guidelines assistant |

---

## Future Scalability

The architecture is designed to scale at every layer.

**Horizontal scaling** — the FastAPI backend is stateless. Add more containers behind a load balancer to handle more concurrent users. No code changes required.

**Multi-tenancy** — the RBAC and document ownership system extends naturally to organisation-level isolation. Each company gets their own namespace, their own document collection, their own user pool.

**Model flexibility** — the LLM factory pattern means switching from GPT-4 to Claude to a fine-tuned open-source model is a configuration change, not a rewrite. As better models are released they can be adopted immediately.

**Collection sharding** — as document collections grow into millions of chunks, Qdrant supports distributed deployment with sharding across multiple nodes.

**Async processing** — large document uploads can be moved to a background queue (Celery + Redis) so the API returns immediately and processing happens asynchronously. Users get notified when their document is ready.

**Fine-tuning** — once enough query data has been collected, domain-specific models can be fine-tuned on real user questions and answers, improving accuracy for specialised fields like law, medicine, or finance.

**Plugin architecture** — the agent system can be extended with new tools: web search, database queries, API calls, calendar access. The platform becomes a general-purpose AI assistant that happens to have deep knowledge of your private documents.

---

## Getting Started

```bash
# Clone the repository
git clone https://github.com/your-username/enterprise-ai-platform.git
cd enterprise-ai-platform

# Configure environment
cp .env.example .env
# Edit .env with your database password and secret key

# Start the platform
docker compose up --build

# Visit the API documentation
open http://localhost:8000/docs
```

---

## Skills Demonstrated

This project covers the full stack of a modern AI engineering role.

| Domain | Technologies |
|---|---|
| Software Engineering | FastAPI, REST APIs, Python, clean architecture |
| Data Engineering | ETL pipelines, document parsing, chunking |
| Machine Learning | Embeddings, model benchmarking, fine-tuning concepts |
| Generative AI | RAG, prompt engineering, hallucination mitigation |
| AI Agents | LangGraph, multi-step reasoning, tool use |
| Databases | PostgreSQL, Qdrant, SQLAlchemy, vector search |
| Frontend | Next.js, React, TypeScript, streaming UI |
| DevOps | Docker, Docker Compose, GitHub Actions |
| Cloud | AWS ECS / Azure Container Apps, managed databases |
| Security | JWT, RBAC, audit logging, data privacy |
| MLOps | LangSmith, Ragas, DeepEval, Grafana |

---

*Built as a portfolio project demonstrating end-to-end AI engineering capability — from raw document ingestion to production-ready cloud deployment.*