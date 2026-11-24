# FinBrief AI — Automated Stock Market Research Agent

Multi-agent AI system built on AWS Bedrock AgentCore that automates 
daily Indian stock market research and delivers formatted email reports.

## Architecture

```
EventBridge (8am IST) → Trigger Lambda
                              ↓
                    Orchestration Agent (AgentCore Runtime 1)
                         ↓              ↓
              Research Agent         Code Agent
           (AgentCore Runtime 2)  (AgentCore Runtime 3)
                   ↓                     ↓
          AgentCore Gateway          AWS SES Email
          (Yahoo Finance,            Streamlit UI
           Tavily, SARIMAX,
           Prophet tools)
```

## Features

- **Live market data**: Nifty 50, Sensex, Nifty Bank, Nifty IT, Nasdaq, S&P 500, Gold, Crude Oil, USD/INR
- **Technical indicators**: RSI, MACD, SMA 50/200 via Yahoo Finance
- **Financial news**: SEBI/RBI updates via Tavily search
- **Short-term prediction**: SARIMAX(0,1,2)(0,0,1,5) with USD/INR, Crude Oil, Gold — MAE Rs 149
- **Long-term forecasting**: Prophet with Indian market seasonality (budget, Diwali, results seasons) — 30/90 day forecasts with 80% confidence intervals
- **Daily email**: HTML formatted report delivered at 8am IST via AWS SES
- **Chat interface**: Streamlit UI with Cognito authentication

## Tech Stack

- **LLM**: Amazon Nova Pro via AWS Bedrock Converse API
- **Agent Framework**: Strands Agents SDK
- **Infrastructure**: AWS AgentCore Runtime, Gateway (MCP), Lambda, ECR, EventBridge, SES, Cognito
- **ML Models**: SARIMAX (statsmodels), Prophet (Facebook), LSTM (TensorFlow)
- **Data Sources**: Yahoo Finance, Tavily, Twelve Data

## Model Comparison Results

Empirical comparison on 494 days of Nifty 50 data:

| Model | MAE (Rs) | RMSE (Rs) | Direction Accuracy |
|-------|----------|-----------|-------------------|
| SARIMA | 151 | 196 | 53.1% |
| LSTM | 254 | 340 | 59.3% |
| XGBoost | 190 | 244 | 54.7% |

SARIMA selected for production (lowest MAE after hyperparameter tuning).

## Setup

```bash
# Clone
git clone https://github.com/yourusername/finbrief-ai
cd finbrief-ai

# Install dependencies
pip install -r research_agent/requirements.txt

# Configure
cp .env.example research_agent/.env
# Fill in your AWS credentials and API keys

# Test tools
cd research_agent
python test_agent.py tools

# Run full agent
python test_agent.py agent
```

## Disclaimer

This system is for research and educational purposes only.
Not personalized investment advice. Always consult a SEBI-registered 
investment advisor before making investment decisions.
