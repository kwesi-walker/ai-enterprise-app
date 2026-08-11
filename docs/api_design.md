# REST API Design — Enterprise AI Knowledge & Automation Platform

## 1. Conventions

- **Base URL:** `/api/v1`
- **Format:** JSON request and response bodies (`Content-Type: application/json`),
  except file uploads which use `multipart/form-data`.
- **Authentication:** Bearer JWT in the `Authorization: Bearer <token>` header for all
  protected endpoints. Tokens are obtained via `POST /api/v1/auth/login`.
- **Authorization (RBAC):** Roles are `ADMIN`, `MANAGER`, `EMPLOYEE`.
- **Timestamps:** ISO-8601 UTC.
- **IDs:** UUID v4 strings.
- **Errors:** Standard HTTP status codes with a JSON body:
  ```json
  { "detail": "Human readable error message" }
  ```

### Common status codes

| Code | Meaning |
|------|---------|
| 200 | OK |
| 201 | Created |
| 204 | No Content |
| 400 | Bad Request / validation error |
| 401 | Unauthorized (missing/invalid token) |
| 403 | Forbidden (role not permitted) |
| 404 | Not Found |
| 409 | Conflict (e.g. email already registered) |
| 422 | Unprocessable Entity (Pydantic validation) |
| 500 | Internal Server Error |

## 2. Health & Root

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | None | Root banner message. |
| GET | `/health` | None | Liveness/readiness probe. |

**`GET /health` response `200`**
```json
{ "status": "healthy" }
```

## 3. Authentication (`/api/v1/auth`)

| Method | Path | Auth | Roles | Description |
|--------|------|------|-------|-------------|
| POST | `/api/v1/auth/register` | None | — | Register a new user. |
| POST | `/api/v1/auth/login` | None | — | Obtain a JWT access token. |
| POST | `/api/v1/auth/logout` | JWT | any | Invalidate/aknowledge logout (client-side token discard; server logs the event). |
| GET | `/api/v1/auth/me` | JWT | any | Return the current authenticated user. |

**`POST /api/v1/auth/register`**
Request:
```json
{ "email": "user@corp.com", "password": "S3cret!", "role": "EMPLOYEE" }
```
Response `201`:
```json
{ "id": "uuid", "email": "user@corp.com", "role": "EMPLOYEE", "created_at": "2026-01-01T00:00:00Z" }
```
Errors: `409` email already registered, `422` validation.

**`POST /api/v1/auth/login`**
Request (form or JSON):
```json
{ "email": "user@corp.com", "password": "S3cret!" }
```
Response `200`:
```json
{ "access_token": "<jwt>", "token_type": "bearer" }
```
Errors: `401` invalid credentials.

**`POST /api/v1/auth/logout`**
Response `200`:
```json
{ "message": "Logged out" }
```

**`GET /api/v1/auth/me`**
Response `200`:
```json
{ "id": "uuid", "email": "user@corp.com", "role": "EMPLOYEE", "created_at": "2026-01-01T00:00:00Z" }
```

## 4. Documents (`/api/v1/documents`)

*Phase 3 — Document Ingestion Pipeline.*

| Method | Path | Auth | Roles | Description |
|--------|------|------|-------|-------------|
| POST | `/api/v1/documents` | JWT | ADMIN, MANAGER, EMPLOYEE | Upload a document for ingestion. |
| GET | `/api/v1/documents` | JWT | any | List documents visible to the user (paginated). |
| GET | `/api/v1/documents/{document_id}` | JWT | any (owner/role) | Get metadata + processing status of one document. |
| DELETE | `/api/v1/documents/{document_id}` | JWT | ADMIN, MANAGER, owner | Delete a document and its chunks/vectors. |

**`POST /api/v1/documents`** — `multipart/form-data`
Fields: `file` (PDF/DOCX), optional `title`.
Response `201`:
```json
{ "id": "uuid", "filename": "report.pdf", "status": "PENDING", "created_at": "2026-01-01T00:00:00Z" }
```
Errors: `400` unsupported file type, `413` too large.

**`GET /api/v1/documents?limit=20&offset=0`**
Response `200`:
```json
{
  "total": 42,
  "items": [
    { "id": "uuid", "filename": "report.pdf", "status": "INDEXED", "chunk_count": 128, "created_at": "2026-01-01T00:00:00Z" }
  ]
}
```

**`GET /api/v1/documents/{document_id}`**
Response `200`:
```json
{
  "id": "uuid",
  "filename": "report.pdf",
  "status": "INDEXED",
  "chunk_count": 128,
  "owner_id": "uuid",
  "created_at": "2026-01-01T00:00:00Z"
}
```
Errors: `404` not found.

**`DELETE /api/v1/documents/{document_id}`**
Response `204` (no content). Errors: `403`, `404`.

## 5. RAG (`/api/v1/rag`)

*Phase 5 — RAG Service.*

| Method | Path | Auth | Roles | Description |
|--------|------|------|-------|-------------|
| POST | `/api/v1/rag/query` | JWT | any | Ask a question; returns a grounded answer with citations. |

**`POST /api/v1/rag/query`**
Request:
```json
{ "question": "What is our data retention policy?", "top_k": 5, "document_ids": ["uuid"] }
```
Response `200`:
```json
{
  "answer": "The retention policy is 7 years ...",
  "sources": [
    { "document_id": "uuid", "chunk_id": "uuid", "score": 0.89, "snippet": "..." }
  ],
  "trace_id": "langsmith-trace-id"
}
```

## 6. Agents (`/api/v1/agents`)

*Phase 6 — AI Agent Service (LangGraph).*

| Method | Path | Auth | Roles | Description |
|--------|------|------|-------|-------------|
| GET | `/api/v1/agents` | JWT | any | List available agents/workflows. |
| POST | `/api/v1/agents/{agent_id}/run` | JWT | any | Execute an agent on a task; may be streamed. |
| GET | `/api/v1/agents/runs/{run_id}` | JWT | any (owner) | Get status/result of an agent run. |

**`POST /api/v1/agents/{agent_id}/run`**
Request:
```json
{ "input": "Summarize Q3 sales docs and draft an email", "stream": false }
```
Response `200`:
```json
{
  "run_id": "uuid",
  "status": "COMPLETED",
  "output": "...",
  "steps": [ { "node": "planner", "action": "..." } ],
  "trace_id": "langsmith-trace-id"
}
```

## 7. Admin (`/api/v1/admin`)

*User & role management — ADMIN only.*

| Method | Path | Auth | Roles | Description |
|--------|------|------|-------|-------------|
| GET | `/api/v1/admin/users` | JWT | ADMIN | List all users (paginated). |
| GET | `/api/v1/admin/users/{user_id}` | JWT | ADMIN | Get a single user. |
| POST | `/api/v1/admin/users` | JWT | ADMIN | Create a user with a specific role. |
| PATCH | `/api/v1/admin/users/{user_id}/role` | JWT | ADMIN | Update a user's role. |
| DELETE | `/api/v1/admin/users/{user_id}` | JWT | ADMIN | Delete a user. |
| GET | `/api/v1/admin/audit-logs` | JWT | ADMIN | List audit log entries (filter by user/action/date). |

**`PATCH /api/v1/admin/users/{user_id}/role`**
Request:
```json
{ "role": "MANAGER" }
```
Response `200`:
```json
{ "id": "uuid", "email": "user@corp.com", "role": "MANAGER" }
```
Errors: `403` non-admin, `404` user not found.

**`GET /api/v1/admin/audit-logs?user_id=&action=&limit=50&offset=0`**
Response `200`:
```json
{
  "total": 1200,
  "items": [
    { "id": "uuid", "user_id": "uuid", "action": "LOGIN", "timestamp": "2026-01-01T00:00:00Z" }
  ]
}
```

## 8. Endpoint Summary Matrix

| Domain | Endpoints | Phase |
|--------|-----------|-------|
| Health | `/`, `/health` | 1 |
| Auth | register, login, logout, me | 1 |
| Documents | upload, list, get, delete | 3 |
| RAG | query | 5 |
| Agents | list, run, run status | 6 |
| Admin | users CRUD, role update, audit logs | 1 / ongoing |
