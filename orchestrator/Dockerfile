FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY orchestrator.py .
ENV AWS_DEFAULT_REGION=us-east-1
ENV BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0
ENV RESEARCH_AGENT_ARN=arn:aws:bedrock-agentcore:us-east-1:755400270916:runtime/ResearchAgent-H82lvg8nds
ENV CODE_AGENT_ARN=arn:aws:bedrock-agentcore:us-east-1:755400270916:runtime/CodeAgent-7E0rRmBWg2
CMD ["python", "orchestrator.py"]
