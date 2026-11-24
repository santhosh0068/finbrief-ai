FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY code_agent_v2.py .
COPY tools/ ./tools/
ENV AWS_DEFAULT_REGION=us-east-1
ENV BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0
CMD ["python", "code_agent_v2.py", "serve"]
