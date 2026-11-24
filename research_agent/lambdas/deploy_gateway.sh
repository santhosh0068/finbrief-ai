#!/bin/bash
# deploy_gateway.sh
# Deploys one Lambda + AgentCore Gateway with one target
# Run in AWS CloudShell

set -e

ACCOUNT_ID="755400270916"
REGION="us-east-1"
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/ResearchAgentCoreRole"
TAVILY_API_KEY="tvly-1ecpBO-NNVKAT9XzOmcpPfb5Fq31xBpxOfLD87acSjKNCbo7F"
S3_BUCKET="research-agent-schemas-${ACCOUNT_ID}"
AWS="/usr/local/bin/aws"

echo "========================================"
echo " Research Tools — Gateway Deployment"
echo "========================================"

# ── Step 1: Create S3 bucket ──────────────────────────────────────
echo ""
echo "Step 1: Creating S3 bucket for schemas..."
$AWS s3 mb s3://${S3_BUCKET} --region ${REGION} 2>/dev/null && \
  echo "Bucket created" || echo "Bucket already exists"

# ── Step 2: Create OpenAPI schema ────────────────────────────────
echo ""
echo "Step 2: Creating OpenAPI schema..."
cat > /tmp/research_tools_schema.json << 'SCHEMA'
{
  "openapi": "3.0.0",
  "info": {
    "title": "Research Tools",
    "version": "1.0.0",
    "description": "Financial research tools for Indian stock market"
  },
  "paths": {
    "/get_market_indices": {
      "post": {
        "operationId": "get_market_indices",
        "summary": "Fetch live market indices",
        "description": "Returns live prices for Nifty 50, Sensex, Nifty Bank, Nifty IT, Nasdaq, SP500, Crude Oil, Gold, USD/INR",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "action": {"type": "string", "enum": ["get_market_indices"]}
                },
                "required": ["action"]
              }
            }
          }
        },
        "responses": {"200": {"description": "Market indices data", "content": {"application/json": {"schema": {"type": "object"}}}}}
      }
    },
    "/get_top_gainers_losers": {
      "post": {
        "operationId": "get_top_gainers_losers",
        "summary": "Fetch top gainers and losers",
        "description": "Returns top gaining and losing Indian stocks today including SBI, TCS, Infosys, HDFC Bank, ICICI Bank, Reliance, Wipro",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "action": {"type": "string", "enum": ["get_top_gainers_losers"]}
                },
                "required": ["action"]
              }
            }
          }
        },
        "responses": {"200": {"description": "Gainers and losers data", "content": {"application/json": {"schema": {"type": "object"}}}}}
      }
    },
    "/search_financial_news": {
      "post": {
        "operationId": "search_financial_news",
        "summary": "Search latest financial news",
        "description": "Searches web for latest Indian stock market news, SEBI updates, RBI updates using Tavily",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "action": {"type": "string", "enum": ["search_financial_news"]},
                  "query": {"type": "string", "description": "Search query e.g. Indian stock market news today"}
                },
                "required": ["action", "query"]
              }
            }
          }
        },
        "responses": {"200": {"description": "News results", "content": {"application/json": {"schema": {"type": "object"}}}}}
      }
    },
    "/get_technical_indicators": {
      "post": {
        "operationId": "get_technical_indicators",
        "summary": "Get technical indicators for a stock",
        "description": "Returns RSI, MACD, SMA technical indicators for a stock. Use NSE symbols: INFY.NS, TCS.NS, SBIN.NS, ICICIBANK.NS, HDFCBANK.NS, RELIANCE.NS, WIPRO.NS",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "action": {"type": "string", "enum": ["get_technical_indicators"]},
                  "symbol": {"type": "string", "description": "Yahoo Finance ticker e.g. INFY.NS"}
                },
                "required": ["action", "symbol"]
              }
            }
          }
        },
        "responses": {"200": {"description": "Technical indicators", "content": {"application/json": {"schema": {"type": "object"}}}}}
      }
    }
  }
}
SCHEMA

# Upload schema to S3
$AWS s3 cp /tmp/research_tools_schema.json \
  s3://${S3_BUCKET}/research_tools_schema.json
echo "Schema uploaded to S3"

# ── Step 3: Package Lambda ────────────────────────────────────────
echo ""
echo "Step 3: Packaging Lambda function..."
cd /tmp
rm -rf lambda_pkg && mkdir lambda_pkg

# Copy handler and tools
cp ~/research_agent/lambdas/research_tools_lambda/handler.py lambda_pkg/
mkdir -p lambda_pkg/tools
cp ~/research_agent/tools/yahoo_finance.py        lambda_pkg/tools/
cp ~/research_agent/tools/tavily_search.py        lambda_pkg/tools/
cp ~/research_agent/tools/technical_indicators.py lambda_pkg/tools/
cp ~/research_agent/tools/__init__.py             lambda_pkg/tools/

# Install dependencies
pip install requests tavily-python python-dotenv strands-agents \
  -t lambda_pkg/ -q

# Zip it
cd lambda_pkg && zip -r /tmp/research_tools.zip . -q
echo "Lambda packaged: $(du -sh /tmp/research_tools.zip | cut -f1)"

# ── Step 4: Deploy Lambda ─────────────────────────────────────────
echo ""
echo "Step 4: Deploying Lambda..."
cd /tmp

$AWS lambda create-function \
  --function-name "research-tools" \
  --runtime python3.11 \
  --role ${ROLE_ARN} \
  --handler handler.handler \
  --zip-file fileb:///tmp/research_tools.zip \
  --timeout 60 \
  --memory-size 256 \
  --environment "Variables={TAVILY_API_KEY=${TAVILY_API_KEY}}" \
  --region ${REGION} 2>/dev/null && echo "Lambda created" || \
$AWS lambda update-function-code \
  --function-name "research-tools" \
  --zip-file fileb:///tmp/research_tools.zip \
  --region ${REGION} && echo "Lambda updated"

# Wait for Lambda to be active
sleep 5

LAMBDA_ARN=$($AWS lambda get-function \
  --function-name research-tools \
  --region ${REGION} \
  --query 'Configuration.FunctionArn' \
  --output text)
echo "Lambda ARN: ${LAMBDA_ARN}"

# ── Step 5: Add Lambda permission for Gateway ─────────────────────
echo ""
echo "Step 5: Adding Lambda permission for Gateway..."
$AWS lambda add-permission \
  --function-name research-tools \
  --statement-id AllowGateway \
  --action lambda:InvokeFunction \
  --principal bedrock-agentcore.amazonaws.com \
  --source-account ${ACCOUNT_ID} \
  --region ${REGION} 2>/dev/null && echo "Permission added" || echo "Permission already exists"

# ── Step 6: Create Gateway ────────────────────────────────────────
echo ""
echo "Step 6: Creating AgentCore Gateway..."
GATEWAY_RESPONSE=$($AWS bedrock-agentcore-control create-gateway \
  --name "ResearchToolsGateway" \
  --role-arn ${ROLE_ARN} \
  --protocol-type MCP \
  --region ${REGION})

GATEWAY_ID=$(echo ${GATEWAY_RESPONSE} | python3 -c \
  "import sys,json; print(json.load(sys.stdin)['gatewayId'])")
echo "Gateway ID: ${GATEWAY_ID}"

# Wait for gateway to be ready
sleep 10

# ── Step 7: Create Gateway Target ────────────────────────────────
echo ""
echo "Step 7: Creating Gateway Target..."
$AWS bedrock-agentcore-control create-gateway-target \
  --gateway-identifier ${GATEWAY_ID} \
  --name "research-tools-target" \
  --target-configuration "{
    \"lambdaConfiguration\": {
      \"lambdaArn\": \"${LAMBDA_ARN}\",
      \"toolSchema\": {
        \"s3\": {
          \"s3Uri\": \"s3://${S3_BUCKET}/research_tools_schema.json\"
        }
      }
    }
  }" \
  --credential-provider-configurations \
    '[{"credentialProviderType":"GATEWAY_IAM_ROLE"}]' \
  --region ${REGION}

echo "Gateway Target created"

# ── Done ──────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo " GATEWAY DEPLOYMENT COMPLETE"
echo "========================================"
echo " Gateway ID:  ${GATEWAY_ID}"
echo " Lambda ARN:  ${LAMBDA_ARN}"
echo " Schema S3:   s3://${S3_BUCKET}/research_tools_schema.json"
echo ""
echo " Add to .env:"
echo " GATEWAY_ID=${GATEWAY_ID}"
echo "========================================"
