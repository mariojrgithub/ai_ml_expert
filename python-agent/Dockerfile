FROM python:3.11-slim

# Install Docker CLI so the agent can invoke `docker mcp gateway run`
# via the mounted /var/run/docker.sock.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg lsb-release \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg \
       | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
       https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Copy the docker-mcp CLI plugin from the official image so that
# `docker mcp gateway run --profile default` works inside the container.
COPY --from=docker/mcp-gateway:latest /docker-mcp /usr/local/lib/docker/cli-plugins/docker-mcp
RUN chmod +x /usr/local/lib/docker/cli-plugins/docker-mcp

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY tests ./tests
EXPOSE 8000
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]