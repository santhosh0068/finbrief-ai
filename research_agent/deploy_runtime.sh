#!/bin/bash
# deploy_runtime.sh
# Deploys Research Agent to AgentCore Runtime
# Run this in AWS CloudShell

set -e

ACCOUNT_ID="755400270916"
REGION="us-east-1"
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/ResearchAgentCoreRole"
ECR_REPO="research-agent"
IMAGE_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}:latest"
AWS="/usr/local/bin/aws"

echo "========================================"
echo " Research Agent — AgentCore Deployment"
echo "========================================"

# ── Step 1: Create ECR repository ────────────────────────────────
echo ""
echo "Step 1: Creating ECR repository..."
$AWS ecr create-repository \
  --repository-name ${ECR_REPO} \
  --region ${REGION} 2>/dev/null && echo "ECR repo created" || echo "ECR repo already exists"

# ── Step 2: Login to ECR ──────────────────────────────────────────
echo ""
echo "Step 2: Logging into ECR..."
$AWS ecr get-login-password --region ${REGION} | \
  docker login --username AWS --password-stdin \
  ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com
echo "ECR login successful"

# ── Step 3: Build arm64 image ─────────────────────────────────────
echo ""
echo "Step 3: Building arm64 Docker image..."
cd ~/research_agent

# Enable buildx for arm64
docker buildx create --use --name multiarch 2>/dev/null || \
  docker buildx use multiarch
docker buildx inspect --bootstrap

docker buildx build \
  --platform linux/arm64 \
  --tag ${IMAGE_URI} \
  --push \
  .
echo "Image built and pushed: ${IMAGE_URI}"

# ── Step 4: Create AgentCore Runtime ─────────────────────────────
echo ""
echo "Step 4: Creating AgentCore Runtime..."
RESPONSE=$($AWS bedrock-agentcore-control create-agent-runtime \
  --agent-runtime-name "ResearchAgent" \
  --agent-runtime-artifact "{\"containerConfiguration\":{\"containerUri\":\"${IMAGE_URI}\"}}" \
  --role-arn "${ROLE_ARN}" \
  --network-configuration '{"networkMode":"PUBLIC"}' \
  --environment-variables "{
    \"BEDROCK_MODEL_ID\":\"us.amazon.nova-pro-v1:0\",
    \"AWS_DEFAULT_REGION\":\"us-east-1\",
    \"TAVILY_API_KEY\":\"tvly-1ecpBO-NNVKAT9XzOmcpPfb5Fq31xBpxOfLD87acSjKNCbo7F\"
  }" \
  --region ${REGION})

echo "Runtime creation response:"
echo ${RESPONSE} | python3 -c "import sys,json; r=json.load(sys.stdin); print('Runtime ID:', r.get('agentRuntimeId','N/A')); print('Status:', r.get('status','N/A'))"

RUNTIME_ID=$(echo ${RESPONSE} | python3 -c "import sys,json; print(json.load(sys.stdin).get('agentRuntimeId',''))")

# ── Step 5: Poll until READY ──────────────────────────────────────
echo ""
echo "Step 5: Waiting for Runtime to become READY..."
echo "(This takes 2-5 minutes)"

for i in {1..20}; do
  STATUS=$($AWS bedrock-agentcore-control get-agent-runtime \
    --agent-runtime-id ${RUNTIME_ID} \
    --region ${REGION} | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('status','UNKNOWN'))")

  echo "  Attempt ${i}/20 — Status: ${STATUS}"

  if [ "${STATUS}" = "READY" ]; then
    echo "Runtime is READY!"
    break
  elif [ "${STATUS}" = "FAILED" ]; then
    echo "Runtime FAILED. Check CloudWatch logs."
    exit 1
  fi

  sleep 30
done

# ── Step 6: Test invoke ───────────────────────────────────────────
echo ""
echo "Step 6: Testing invoke..."
SESSION_ID=$(python3 -c "import uuid; print(str(uuid.uuid4()).replace('-','') + 'AAAA')")

$AWS bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-id ${RUNTIME_ID} \
  --runtime-session-id ${SESSION_ID} \
  --payload '{"task": "Get market indices only"}' \
  --region ${REGION}

echo ""
echo "========================================"
echo " DEPLOYMENT COMPLETE"
echo "========================================"
echo " Runtime ID: ${RUNTIME_ID}"
echo " Image URI:  ${IMAGE_URI}"
echo " Region:     ${REGION}"
echo ""
echo " Save Runtime ID — needed to invoke the agent"
echo "========================================"
