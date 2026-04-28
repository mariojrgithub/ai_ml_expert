# Engineering Copilot Starter – Version 6

A local-first engineering copilot starter built with:

- **Java / Spring Boot** as the control-plane API
- **Python / FastAPI** as the agent runtime
- **LangGraph**-style orchestration in the Python layer
- **MongoDB** for documents, chunks, executions, and eval runs
- **Ollama** for local LLMs and embeddings
- **Optional MCP** integration for external/web search
- **Evaluation harness** with JSON + HTML reports

---

## Project structure

```text
ai-ml-expert/
├── java-api/
├── python-agent/
├── .env.example
├── docker-compose.yml
└── README.md
```

The project includes both:
- `java-api/` for the Spring Boot gateway
- `python-agent/` for the Python agent service

---

## What this project does

This starter supports:

- intent routing for:
  - QA
  - code generation
  - SQL generation
  - MongoDB query generation
- embedding-based retrieval over internal documents
- lightweight reranking before generation
- grounded QA behavior
- citations appended to grounded QA answers
- eval execution and report generation
- trace capture and run metadata persistence

The Python agent exposes endpoints such as:
- `GET /health`
- `GET /admin/prompts`
- `POST /admin/seed`
- `POST /admin/reindex`
- `POST /admin/evals/run`
- `GET /admin/evals/reports`
- `POST /agent/chat`

---

## Prerequisites

Before running locally, install:

- **Docker Desktop** (or Docker Engine + Compose)
- enough disk space to pull Ollama models
- optionally, **Python 3.11+** and **Java 21** if you want to run services outside Docker

---

## Environment configuration

Copy the environment template if you want a local `.env`:

```bash
cp .env.example .env
```

The template includes MongoDB, Ollama, and optional MCP settings such as:
- `MONGO_URI`
- `MONGO_DB`
- `OLLAMA_BASE_URL`
- `GENERAL_MODEL`
- `CODE_MODEL`
- `EMBEDDING_MODEL`
- `WEB_SEARCH_ENABLED`
- `MCP_TRANSPORT`
- `MCP_SERVER_COMMAND`
- `MCP_SERVER_ARGS`
- `MCP_WEB_SEARCH_TOOL`

The Python config reads these values using `pydantic-settings`.

---

## Run the full stack locally with Docker

### 1) Start Ollama first

Start only the Ollama container first:

```bash
docker compose up -d ollama
```

### 2) Pull the required Ollama models

Pull these models into Ollama:

```bash
docker exec -it engineering-copilot-v6-ollama ollama pull llama3.1:8b
docker exec -it engineering-copilot-v6-ollama ollama pull qwen2.5-coder:7b
docker exec -it engineering-copilot-v6-ollama ollama pull embeddinggemma
```

These model names match the configuration expected by the Python service.

### 3) Start the full stack

Now start everything:

```bash
docker compose up --build
```

The compose stack starts:
- `api` (Spring Boot gateway)
- `python-agent`
- `mongo`
- `ollama`
- `streamlit-ui` (chat UI)

### 4) Seed sample internal documents

After the stack is up:

```bash
curl -X POST http://localhost:8000/admin/seed
```

This loads the sample internal documents into MongoDB.

### 5) Generate embeddings for the sample chunks

```bash
curl -X POST http://localhost:8000/admin/reindex
```

This generates embeddings and prepares the RAG dataset.

### 6) Test chat through the Java gateway

Send a request through the Spring Boot gateway:

```bash
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"demo-session","message":"What are the key CI/CD guardrails?"}'
```

The Spring Boot API forwards the request to the Python agent’s `/agent/chat` endpoint.

---

## Ports

By default, the project runs on:

- **Spring Boot API**: `http://localhost:8080`
- **Python agent**: `http://localhost:8000`
- **MongoDB**: `mongodb://localhost:27017`
- **Ollama**: `http://localhost:11434`
- **Streamlit UI**: `http://localhost:8501`

---

## Admin endpoints

Use these endpoints while developing locally.

### Health check

```bash
curl http://localhost:8000/health
```

### List prompts

```bash
curl http://localhost:8000/admin/prompts
```

### Run evaluations

```bash
curl -X POST http://localhost:8000/admin/evals/run
```

### List generated eval reports

```bash
curl http://localhost:8000/admin/evals/reports
```

These endpoints are exposed directly by the Python agent service.

---

## Running the Python service without Docker (optional)

If you want to run only the Python agent locally:

### 1) Create and activate a virtual environment

```bash
cd python-agent
python -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
cd python-agent
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Start the Python service

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Running the Java gateway without Docker (optional)

If you want to run only the Spring Boot gateway locally:

### 1) Start the Python service first
The Java gateway expects the Python agent to be reachable.

### 2) Run the Spring Boot app

```bash
cd java-api
./mvnw spring-boot:run
```

On Windows PowerShell:

```powershell
cd java-api
mvn spring-boot:run
```

---

## Optional MCP / web search

Version 6 supports an optional MCP-backed external/web-search integration, but it is disabled by default.

To enable it, configure values such as:

```env
WEB_SEARCH_ENABLED=true
MCP_TRANSPORT=stdio
MCP_SERVER_COMMAND=python
MCP_SERVER_ARGS=-m your_mcp_server
MCP_WEB_SEARCH_TOOL=web_search
```

If these values are not configured, the project still runs fully in local-only mode using internal retrieval.

---

## Seeding your own books into MongoDB for RAG

You can seed your own coding books as chunk documents with embeddings.

Recommended workflow:

1. extract the book text
2. split into chunks
3. generate embeddings per chunk with Ollama
4. store chunk text + metadata + embedding in MongoDB

A good document shape is:

```json
{
  "book_id": "book-effective-java-001",
  "title": "Effective Java",
  "author": "Joshua Bloch",
  "chapter": "Creating and Destroying Objects",
  "chunk_index": 0,
  "text": "Prefer static factory methods to constructors...",
  "embedding": [0.1, -0.2, 0.3],
  "tags": ["java", "best-practices"],
  "source_type": "book"
}
```

If you have the notebook we created for seeding books, use that to load `.txt`, `.md`, or `.pdf` files into MongoDB.

---

## Running tests

### Python tests

```bash
cd python-agent
pytest -q
```

### Java tests

```bash
cd java-api
./mvnw test
```

The project includes tests under:
- `python-agent/tests/`
- `java-api/src/test/java/...`

---

## Common issues

### Ollama model not found
Make sure you pulled:
- `llama3.1:8b`
- `qwen2.5-coder:7b`
- `embeddinggemma`

### No grounded answers
Run:

```bash
curl -X POST http://localhost:8000/admin/seed
curl -X POST http://localhost:8000/admin/reindex
```

### Gateway returns errors
Make sure:
- Python agent is reachable on port `8000`
- Spring Boot is configured with the correct `AGENT_BASE_URL`

### MCP search doesn’t work
Leave MCP disabled until you have a valid MCP server configured.

---

## Minimal run order

If you just want the shortest possible startup flow:

```bash
docker compose up -d ollama
docker exec -it engineering-copilot-v6-ollama ollama pull llama3.1:8b
docker exec -it engineering-copilot-v6-ollama ollama pull qwen2.5-coder:7b
docker exec -it engineering-copilot-v6-ollama ollama pull embeddinggemma
docker compose up --build
curl -X POST http://localhost:8000/admin/seed
curl -X POST http://localhost:8000/admin/reindex
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"demo","message":"What are the key CI/CD guardrails?"}'
```

---

## Notes

This project is intentionally local-first and easy to modify. The retrieval layer, prompts, eval harness, MCP integration, and Java gateway are all designed to be extended as your internal RAG dataset grows.
``