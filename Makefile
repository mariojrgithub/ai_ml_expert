.PHONY: up-gpu up-mac-docker up-mac-local down pull-models help

# ---------------------------------------------------------------------------
# Deployment modes
# ---------------------------------------------------------------------------

## Windows + NVIDIA GPU  →  Ollama runs inside Docker with GPU passthrough
up-gpu:
	docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build

## Mac + Docker CPU  →  Ollama runs inside Docker, CPU-only
up-mac-docker:
	docker compose -f docker-compose.yml -f docker-compose.cpu.yml up --build

## Mac + Local Ollama  →  Ollama runs natively on your Mac (ollama serve)
## Ensure Ollama is already running before calling this target.
up-mac-local:
	docker compose up --build

# ---------------------------------------------------------------------------
# Teardown (works for all modes)
# ---------------------------------------------------------------------------
down:
	docker compose -f docker-compose.yml -f docker-compose.gpu.yml down --remove-orphans 2>/dev/null || true
	docker compose -f docker-compose.yml -f docker-compose.cpu.yml down --remove-orphans 2>/dev/null || true
	docker compose down --remove-orphans 2>/dev/null || true

# ---------------------------------------------------------------------------
# Pull required Ollama models into a running Ollama container.
# Only needed for docker-managed Ollama (up-gpu or up-mac-docker).
# For local Ollama, run `ollama pull <model>` directly on your host.
# ---------------------------------------------------------------------------
pull-models:
	docker exec engineering-copilot-v6-ollama ollama pull llama3.1:8b
	docker exec engineering-copilot-v6-ollama ollama pull qwen2.5-coder:7b
	docker exec engineering-copilot-v6-ollama ollama pull embeddinggemma

# ---------------------------------------------------------------------------
help:
	@echo ""
	@echo "  make up-gpu          Windows + NVIDIA GPU (Ollama in Docker w/ GPU)"
	@echo "  make up-mac-docker   Mac + Docker CPU     (Ollama in Docker, no GPU)"
	@echo "  make up-mac-local    Mac + Local Ollama   (Ollama running on host)"
	@echo "  make down            Stop and remove all containers"
	@echo "  make pull-models     Pull required models into the Ollama container"
	@echo ""
