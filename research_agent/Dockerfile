# Dockerfile — Research Agent for AgentCore Runtime
# ─────────────────────────────────────────────────────────────────
# AgentCore Runtime requires:
#   - Python base image
#   - bedrock-agentcore package (HTTP server entry point)
#   - Your agent code + tools
#   - CMD starts the HTTP server AgentCore calls
# ─────────────────────────────────────────────────────────────────

FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer — only rebuilds if requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code
COPY research_agent.py .
COPY tools/ ./tools/

# Environment variables — overridden by AgentCore Runtime config
ENV AWS_DEFAULT_REGION=us-east-1
ENV BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0

# AgentCore Runtime calls this script via HTTP
# research_agent.py starts the BedrockAgentCoreApp HTTP server
CMD ["python", "research_agent.py", "serve"]
