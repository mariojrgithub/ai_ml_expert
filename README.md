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
ai_ml_expert/
├── java-api/
├── python-agent/
├── streamlit-ui/
├── notebooks/
│   └── mongo_upload.ipynb   ← seeds books into MongoDB for RAG
├── books/                   ← PDF/text books to ingest via the notebook
├── .env.example
├── docker-compose.yml          ← base stack (no Ollama service)
├── docker-compose.gpu.yml      ← adds Ollama with NVIDIA GPU (Windows)
├── docker-compose.cpu.yml      ← adds Ollama CPU-only (Mac Docker)
├── Makefile                    ← deployment shortcuts
└── README.md
```

The project includes:
- `java-api/` for the Spring Boot gateway
- `python-agent/` for the Python agent service
- `streamlit-ui/` for the chat UI

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
- `GET /health` *(public — no auth required)*
- `GET /admin/prompts` *(requires `X-Admin-Api-Key` header)*
- `POST /admin/seed` *(requires `X-Admin-Api-Key` header)*
- `POST /admin/reindex` *(requires `X-Admin-Api-Key` header)*
- `POST /admin/evals/run` *(runs asynchronously in the background; requires `X-Admin-Api-Key` header)*
- `GET /admin/evals/reports` *(requires `X-Admin-Api-Key` header)*
- `GET /admin/health/detail` *(operational dashboard — chunk counts and execution stats; requires `X-Admin-Api-Key` header)*
- `POST /agent/chat`
- `POST /agent/chat/stream`  *(NDJSON token stream)*

The Java gateway exposes:
- `POST /api/auth/login` *(returns a JWT Bearer token — required for the endpoints below)*
- `POST /api/chat`  *(proxies to `/agent/chat`; requires Bearer token)*
- `POST /api/chat/stream`  *(proxies to `/agent/chat/stream`; returns SSE — Server-Sent Events; requires Bearer token)*

---

## Prerequisites

Before running locally, install:

- **Docker Desktop** (or Docker Engine + Compose)
- enough disk space to pull Ollama models (~8–15 GB depending on models)
- optionally, **Python 3.11+** and **Java 21** if you want to run services outside Docker

**Windows + NVIDIA GPU users** additionally need:
- NVIDIA driver installed
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) (`nvidia-ctk`)
- Docker Desktop with GPU support enabled

**Mac local Ollama users** additionally need:
- [Ollama for macOS](https://ollama.com/download) installed and running (`ollama serve`)

---

## Deployment modes

This project supports three deployment modes selected by a single `make` command:

| Mode | Who | Command |
|---|---|---|
| Windows + NVIDIA GPU | Ollama runs in Docker with GPU passthrough | `make up-gpu` |
| Mac + Docker CPU | Ollama runs in Docker, no GPU | `make up-mac-docker` |
| Mac + Local Ollama | Ollama runs natively on your Mac | `make up-mac-local` |

The Makefile wraps the correct compose override file for each mode. You can also run the compose commands directly if you don't have `make`:

```bash
# Windows GPU
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build

# Mac Docker CPU
docker compose -f docker-compose.yml -f docker-compose.cpu.yml up --build

# Mac Local Ollama
docker compose up --build
```

---

## Environment configuration

Copy the environment template if you want a local `.env`:

```bash
cp .env.example .env
```

The key variable to set based on your deployment mode is `OLLAMA_BASE_URL`:

| Mode | Value |
|---|---|
| Ollama in Docker (GPU or CPU) | `http://ollama:11434` |
| Mac local Ollama | `http://host.docker.internal:11434` *(default when unset)* |

Other available settings:
- `MONGO_URI`, `MONGO_DB`
- `GENERAL_MODEL`, `CODE_MODEL`, `EMBEDDING_MODEL`
- `WEB_SEARCH_ENABLED`
- `MCP_TRANSPORT`, `MCP_SERVER_COMMAND`, `MCP_SERVER_ARGS`, `MCP_WEB_SEARCH_TOOL`

The Python config reads these values using `pydantic-settings`.

---

## Run the full stack locally with Docker

### Step 1 — Choose your deployment mode and start the stack

**Windows + NVIDIA GPU:**
```bash
make up-gpu
```

**Mac + Docker (CPU-only Ollama):**
```bash
make up-mac-docker
```

**Mac + Local Ollama (Ollama running natively):**

First ensure Ollama is running on your Mac:
```bash
ollama serve   # or open the Ollama.app
```

Then start the stack:
```bash
make up-mac-local
```

The compose stack starts:
- `api` (Spring Boot gateway)
- `python-agent`
- `mongo`
- `ollama` *(only in GPU and Mac-Docker modes)*
- `streamlit-ui` (chat UI at `http://localhost:8501`)

### Step 2 — Pull the required Ollama models

**If Ollama is running inside Docker** (GPU or Mac-Docker mode):

```bash
make pull-models
```

Or manually:
```bash
docker exec -it engineering-copilot-v6-ollama ollama pull llama3.1:8b
docker exec -it engineering-copilot-v6-ollama ollama pull qwen2.5-coder:7b
docker exec -it engineering-copilot-v6-ollama ollama pull nomic-embed-text
```

**If Ollama is running locally on your Mac**, pull models directly on the host:
```bash
ollama pull llama3.1:8b
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text
```

### Step 3 — Seed sample internal documents

After the stack is up:

```bash
curl -X POST -H "X-Admin-Api-Key: $ADMIN_API_KEY" http://localhost:8000/admin/seed
```

This loads the sample internal documents into MongoDB.

### Step 4 — Generate embeddings for the sample chunks

```bash
curl -X POST -H "X-Admin-Api-Key: $ADMIN_API_KEY" http://localhost:8000/admin/reindex
```

This generates embeddings using `nomic-embed-text` and prepares the RAG dataset.

### Step 5 — (Optional) Seed books for RAG

Open `notebooks/mongo_upload.ipynb` in VS Code or Jupyter. Place your PDF/text books in the
`books/` folder and run the notebook to chunk, embed, and upload them into the `book_chunks`
collection. The notebook uses the same `nomic-embed-text` model configured in the agent.

> **Note:** If you change the embedding model after books have been ingested, you must
> re-run the notebook to regenerate all embeddings in the new vector space, then call
> `POST /admin/reindex` to regenerate the internal playbook embeddings as well.

### Step 6 — Authenticate and test chat through the Java gateway

The Java gateway requires a JWT Bearer token. First obtain a token:

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<your ADMIN_PASS>"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
```

Then send a chat request:

```bash
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sessionId":"demo-session","message":"What are the key CI/CD guardrails?"}'
```

The Spring Boot API forwards the request to the Python agent's `/agent/chat` endpoint.

> **Tip:** You can also send requests directly to the Python agent on port 8000 without authentication — useful during local development.

---

## Ports

By default, the project runs on:

- **Spring Boot API**: `http://localhost:8080`
- **Python agent**: `http://localhost:8000`
- **MongoDB**: `mongodb://localhost:27017`
- **Ollama**: `http://localhost:11434` *(Docker-managed modes only; in Mac local mode Ollama is on the host)*
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
curl -H "X-Admin-Api-Key: $ADMIN_API_KEY" http://localhost:8000/admin/prompts
```

### Run evaluations

```bash
curl -X POST -H "X-Admin-Api-Key: $ADMIN_API_KEY" http://localhost:8000/admin/evals/run
```

The eval run starts asynchronously. Dataset lives at `python-agent/app/evals/datasets/golden_eval_set.json`. Each eval case can be single-turn or multi-turn (`"multi_turn": true`). Reports are written as JSON and HTML to `python-agent/app/evals/reports/`.

### List generated eval reports

```bash
curl -H "X-Admin-Api-Key: $ADMIN_API_KEY" http://localhost:8000/admin/evals/reports
```

### Operational health dashboard

```bash
curl -H "X-Admin-Api-Key: $ADMIN_API_KEY" http://localhost:8000/admin/health/detail
```

All `/admin/*` endpoints require the `X-Admin-Api-Key` header matching the value of `ADMIN_API_KEY` in your environment. `GET /health` is public.

> **Tip:** Set `export ADMIN_API_KEY=<your-key>` in your shell before running the commands above so you do not have to paste the key repeatedly.

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
.\mvnw.cmd spring-boot:run
```

---

## Optional MCP / web search

Version 6 supports an optional MCP-backed external/web-search integration, but it is disabled by default.

To enable it with the Docker MCP gateway + DuckDuckGo server, configure:

```env
WEB_SEARCH_ENABLED=true
MCP_TRANSPORT=stdio
MCP_SERVER_COMMAND=docker
MCP_SERVER_ARGS=mcp gateway run --servers duckduckgo --secrets /.env
MCP_WEB_SEARCH_TOOL=search
```

If these values are not configured, the project still runs fully in local-only mode using internal retrieval.

---

## Session memory and conversational history

The agent maintains **durable, per-session chat history** stored in MongoDB. This enables multi-turn conversations — follow-up questions like "now convert it to Java" or "add error handling" automatically inherit context from earlier turns in the same session.

### How it works

1. **Every user and assistant message** is persisted to the `chat_messages` collection, keyed by `sessionId`.
2. Before each generation, the **most recent messages** are loaded and injected into the prompt via the `{conversation_history}` slot.
3. After each successful turn, an **LLM-generated rolling summary** is stored in `chat_session_summaries`. This gives the agent a compact view of earlier context that falls outside the recent-message window.
4. **Follow-up intent detection** — short queries (≤ 12 words) or queries containing pronouns like "it", "that", "the result" automatically inherit the intent of the previous turn (e.g., a follow-up to a SQL query keeps `intent=SQL`).

### MongoDB collections

| Collection | Purpose |
|---|---|
| `documents` | Source documents seeded via `/admin/seed` |
| `chunks` | Chunked text from internal playbook documents (with embeddings after reindex) |
| `book_chunks` | Chunks from externally ingested books (via notebook) |
| `executions` | Per-request execution records (intent, answer, trace, grounding metadata) |
| `eval_runs` | Records from eval harness runs |
| `sessions` | Legacy per-session turn log with TTL-based auto-expiry |
| `chat_messages` | Per-session message log (user + assistant turns; durable, no TTL) |
| `chat_session_summaries` | Rolling LLM-generated session summary (one document per session) |

### sessionId usage

All chat endpoints accept a `sessionId` field. Use a consistent value across turns to maintain conversational context:

```bash
# Turn 1
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sessionId":"my-session","message":"Write a Python function to sort a list."}'

# Turn 2 — follow-up; agent will use prior context
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sessionId":"my-session","message":"Now add type hints to it."}'
```

Or directly to the Python agent:

```bash
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"my-session","message":"Write a SQL query to list users."}'

curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"my-session","message":"Now add pagination to that query."}'
```

> **Note:** The Python agent accepts `sessionId` and `message` — the same field names as the Java gateway request body. There is no HTTP endpoint to clear a session; to start fresh simply use a new `sessionId` value.

### Configuration

Session memory behaviour is controlled by environment variables:

| Variable | Default | Description |
|---|---|---|
| `CHAT_HISTORY_ENABLED` | `true` | Enable/disable loading prior messages into context |
| `CHAT_HISTORY_RECENT_LIMIT` | `10` | Max messages loaded per request |
| `CHAT_HISTORY_MAX_CHARS` | `3000` | Max total characters in the conversation history block |
| `CHAT_SUMMARY_ENABLED` | `true` | Enable/disable the rolling LLM session summary |
| `SESSION_MEMORY_TTL_MINUTES` | `30` | TTL for legacy session turns (MongoDB TTL index) |

To disable all conversational history (stateless mode):

```env
CHAT_HISTORY_ENABLED=false
CHAT_SUMMARY_ENABLED=false
```

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
  "source_type": "book",
  "source": "book/book-effective-java-001",
  "domain": "java"
}
```

The `source` field is required — it is rendered by the retrieval layer and passed to the LLM
so it can cite its sources. The `domain` field activates the reranker's domain-match bonus
for queries that mention the same domain keyword.

---

## Running tests

### Python tests

```bash
cd python-agent
pytest -q
```

Most Python tests stub MongoDB, Ollama, and LangChain dependencies and do not require live services. Integration tests that exercise the full agent pipeline with a real database are in `test_integration.py` and require MongoDB to be reachable.

### Java tests

```bash
cd java-api
./mvnw test
```

Java unit tests do not require the Python agent or MongoDB to be running.

The project includes tests under:
- `python-agent/tests/`
- `java-api/src/test/java/...`

---

## Common issues

### Ollama model not found
Make sure you pulled all three required models. For Docker-managed Ollama:
```bash
make pull-models
```
For local Mac Ollama:
```bash
ollama pull llama3.1:8b
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text
```

### No grounded answers
Run:

```bash
curl -X POST -H "X-Admin-Api-Key: $ADMIN_API_KEY" http://localhost:8000/admin/seed
curl -X POST -H "X-Admin-Api-Key: $ADMIN_API_KEY" http://localhost:8000/admin/reindex
```

### Python agent can't reach Ollama (Mac local mode)
Ensure Ollama is running on your host before starting the stack:
```bash
ollama serve
```
The `python-agent` container connects to `host.docker.internal:11434`, which maps to your Mac's localhost. If you're on Linux, the `extra_hosts` entry in `docker-compose.yml` handles this automatically.

### Gateway returns errors
Make sure:
- Python agent is reachable on port `8000`
- Spring Boot is configured with the correct `AGENT_BASE_URL`

### MCP search doesn’t work
Verify that your environment uses the Docker MCP gateway defaults:

```env
WEB_SEARCH_ENABLED=true
MCP_TRANSPORT=stdio
MCP_SERVER_COMMAND=docker
MCP_SERVER_ARGS=mcp gateway run --servers duckduckgo --secrets /.env
MCP_WEB_SEARCH_TOOL=search
```

Then ensure Docker Desktop is running and restart the `python-agent` container.

---

## Minimal run order

If you just want the shortest possible startup flow, pick your mode:

**Mac + Local Ollama (fastest for Mac users):**
```bash
ollama serve
ollama pull llama3.1:8b && ollama pull qwen2.5-coder:7b && ollama pull nomic-embed-text
make up-mac-local
curl -X POST -H "X-Admin-Api-Key: $ADMIN_API_KEY" http://localhost:8000/admin/seed
curl -X POST -H "X-Admin-Api-Key: $ADMIN_API_KEY" http://localhost:8000/admin/reindex
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<your ADMIN_PASS>"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sessionId":"demo","message":"What are the key CI/CD guardrails?"}'
```

**Windows GPU or Mac Docker:**
```bash
make up-gpu        # or: make up-mac-docker
make pull-models
curl -X POST -H "X-Admin-Api-Key: $ADMIN_API_KEY" http://localhost:8000/admin/seed
curl -X POST -H "X-Admin-Api-Key: $ADMIN_API_KEY" http://localhost:8000/admin/reindex
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<your ADMIN_PASS>"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sessionId":"demo","message":"What are the key CI/CD guardrails?"}'
```

---

## Notes

This project is intentionally local-first and easy to modify. The retrieval layer, prompts, eval harness, MCP integration, and Java gateway are all designed to be extended as your internal RAG dataset grows.