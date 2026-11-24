
import streamlit as st
import boto3
import json
import uuid
import time
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
COGNITO_CLIENT_ID    = os.getenv("COGNITO_CLIENT_ID")
COGNITO_REGION       = os.getenv("COGNITO_REGION", "us-east-1")
ORCHESTRATOR_ARN     = os.getenv("ORCHESTRATOR_RUNTIME_ARN", "")

RESEARCH_LOCAL = not bool(ORCHESTRATOR_ARN)


st.set_page_config(
    page_title = "FinBrief AI",
    page_icon  = "📊",
    layout     = "wide"
)

st.markdown("""
<style>
    .metric-up   { color: #4CAF50; font-weight: bold; }
    .metric-down { color: #f44336; font-weight: bold; }
    .chat-user   { background: #2d2d4e; padding: 10px; border-radius: 8px; margin: 5px 0; }
    .chat-agent  { background: #1e2e1e; padding: 10px; border-radius: 8px; margin: 5px 0; }
</style>
""", unsafe_allow_html=True)


def login(email, password):
    """Authenticate user via Cognito public client"""
    try:
        cognito  = boto3.client(
            'cognito-idp',
            region_name=COGNITO_REGION
        )
        response = cognito.initiate_auth(
            AuthFlow       = "USER_PASSWORD_AUTH",
            AuthParameters = {
                "USERNAME": email,
                "PASSWORD": password
            },
            ClientId       = COGNITO_CLIENT_ID
        )

        if response.get('ChallengeName') == 'NEW_PASSWORD_REQUIRED':
            return {
                "success"  : False,
                "challenge": "NEW_PASSWORD_REQUIRED",
                "session"  : response['Session'],
                "error"    : "Password change required"
            }

        tokens = response['AuthenticationResult']
        return {
            "success"     : True,
            "access_token": tokens['AccessToken'],
            "id_token"    : tokens['IdToken']
        }

    except Exception as e:
        return {"success": False, "error": str(e)[:100]}


def change_password(email, new_password, session):
    """Handle new password required challenge"""
    try:
        cognito  = boto3.client(
            'cognito-idp',
            region_name=COGNITO_REGION
        )
        response = cognito.respond_to_auth_challenge(
            ClientId           = COGNITO_CLIENT_ID,
            ChallengeName      = "NEW_PASSWORD_REQUIRED",
            Session            = session,
            ChallengeResponses = {
                "USERNAME"    : email,
                "NEW_PASSWORD": new_password
            }
        )
        tokens = response['AuthenticationResult']
        return {
            "success"     : True,
            "access_token": tokens['AccessToken']
        }
    except Exception as e:
        return {"success": False, "error": str(e)[:100]}


@st.cache_data(ttl=300)
def get_market_data():
    """Fetch live market data from Yahoo Finance"""
    try:
        research_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', 'research_agent')
        )
        if research_dir not in sys.path:
            sys.path.insert(0, research_dir)

        from tools.yahoo_finance import get_market_indices, get_top_gainers_losers

        indices = get_market_indices()
        stocks  = get_top_gainers_losers()

        return {
            "indices"   : indices.get('indices', {}),
            "gainers"   : stocks.get('top_gainers', []),
            "losers"    : stocks.get('top_losers', []),
            "fetched_at": datetime.now().strftime("%H:%M IST")
        }

    except Exception as e:
        return {"error": str(e)[:100]}


def ask_agent(question: str, session_id: str) -> str:
    """Send question to Orchestrator"""
    try:
        if RESEARCH_LOCAL:
            orchestrator_dir = os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__),
                    '..', 'orchestrator'
                )
            )
            original = os.getcwd()
            os.chdir(orchestrator_dir)

            if orchestrator_dir not in sys.path:
                sys.path.insert(0, orchestrator_dir)

            from orchestrator import run_orchestrator
            os.chdir(original)

            return run_orchestrator(
                trigger = "chat",
                query   = question
            )
        else:
            # AWS Runtime mode
            client     = boto3.client('bedrock-agentcore', region_name='us-east-1')
            session_id_runtime = str(uuid.uuid4()).replace("-", "") + "AAAA"
            response   = client.invoke_agent_runtime(
                agentRuntimeArn  = ORCHESTRATOR_ARN,
                runtimeSessionId = session_id_runtime,
                payload          = json.dumps({
                    "trigger": "chat",
                    "query"  : question
                }).encode("utf-8")
            )
            result = json.loads(response["response"].read().decode("utf-8"))
            return result.get("output", "No response")

    except Exception as e:
        return f"Error: {str(e)[:100]}"


def show_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## 📊 FinBrief AI")
        st.markdown("### Financial Research Assistant")
        st.divider()

        email    = st.text_input("Email", placeholder="analyst@firm.com")
        password = st.text_input("Password", type="password")

        if st.button("Login", use_container_width=True, type="primary"):
            if not email or not password:
                st.error("Enter email and password")
                return

            with st.spinner("Logging in..."):
                result = login(email, password)

            if result['success']:
                st.session_state.logged_in    = True
                st.session_state.user_email   = email
                st.session_state.access_token = result['access_token']
                st.session_state.session_id   = str(uuid.uuid4())
                st.session_state.messages     = []
                st.success("✅ Login successful!")
                time.sleep(0.5)
                st.rerun()

            elif result.get('challenge') == 'NEW_PASSWORD_REQUIRED':
                st.session_state.change_password = True
                st.session_state.pwd_session     = result['session']
                st.session_state.user_email      = email
                st.rerun()

            else:
                st.error(f"Login failed: {result.get('error', 'Unknown')}")



def show_change_password():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## 🔐 Set New Password")
        st.caption("First login requires setting a permanent password")
        st.divider()

        new_pwd = st.text_input("New Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")

        if st.button("Set Password", use_container_width=True, type="primary"):
            if new_pwd != confirm:
                st.error("Passwords do not match")
                return
            if len(new_pwd) < 8:
                st.error("Password must be at least 8 characters")
                return

            result = change_password(
                st.session_state.user_email,
                new_pwd,
                st.session_state.pwd_session
            )

            if result['success']:
                st.session_state.logged_in       = True
                st.session_state.access_token    = result['access_token']
                st.session_state.session_id      = str(uuid.uuid4())
                st.session_state.messages        = []
                st.session_state.change_password = False
                st.success("Password set! Loading dashboard...")
                time.sleep(1)
                st.rerun()
            else:
                st.error(result.get('error', 'Failed'))


def show_dashboard():

    # Header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("## 📊 FinBrief AI Dashboard")
        st.caption(f"Logged in as: {st.session_state.user_email}")
    with col2:
        if st.button("Logout"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        if st.button("Refresh Data"):
            st.cache_data.clear()
            st.rerun()

    st.divider()

    # Market Data
    st.subheader("Market Indices")

    with st.spinner("Fetching live data..."):
        data = get_market_data()

    if "error" in data:
        st.error(f"Data error: {data['error']}")
    else:
        st.caption(f"Last updated: {data.get('fetched_at', '')}")
        indices = data.get('indices', {})

        # Indian Markets
        st.markdown("**🇮🇳 Indian Markets**")
        indian_keys = ["nifty_50", "sensex", "nifty_bank", "nifty_it"]
        cols        = st.columns(len(indian_keys))

        for col, key in zip(cols, indian_keys):
            vals = indices.get(key, {})
            if not vals or not isinstance(vals, dict):
                continue
            value = vals.get('value', 0)
            pct   = vals.get('change_percent', 0)
            is_up = str(vals.get('direction', '')).upper() == 'UP'
            arrow = "▲" if is_up else "▼"
            col.metric(
                label      = key.replace('_', ' ').upper(),
                value      = f"{value:,.2f}",
                delta      = f"{arrow} {pct:+.2f}%",
                delta_color= "normal" if is_up else "inverse"
            )

        st.markdown("")

        # Global Markets
        st.markdown("**🌍 Global Markets**")
        global_keys = ["nasdaq", "sp500", "crude_oil", "gold", "usd_inr"]
        gcols       = st.columns(len(global_keys))

        for col, key in zip(gcols, global_keys):
            vals = indices.get(key, {})
            if not vals or not isinstance(vals, dict):
                continue
            value = vals.get('value', 0)
            pct   = vals.get('change_percent', 0)
            is_up = str(vals.get('direction', '')).upper() == 'UP'
            arrow = "▲" if is_up else "▼"
            col.metric(
                label      = key.replace('_', ' ').upper(),
                value      = f"{value:,.2f}",
                delta      = f"{arrow} {pct:+.2f}%",
                delta_color= "normal" if is_up else "inverse"
            )

        st.divider()

        # Gainers and Losers
        col_g, col_l = st.columns(2)

        with col_g:
            st.markdown("**📈 Top Gainers**")
            for s in data.get('gainers', []):
                st.markdown(
                    f"🟢 **{s.get('stock')}**  "
                    f"Rs{s.get('price', 0):,.2f}  "
                    f"`+{s.get('change_percent', 0):.2f}%`"
                )

        with col_l:
            st.markdown("**📉 Top Losers**")
            for s in data.get('losers', []):
                st.markdown(
                    f"🔴 **{s.get('stock')}**  "
                    f"Rs{s.get('price', 0):,.2f}  "
                    f"`{s.get('change_percent', 0):.2f}%`"
                )

    st.divider()

    # Chatbot
    st.subheader("💬 Ask FinBrief AI")
    st.caption("Ask about markets, stocks, news, or anything financial")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Why is Nifty down? / Top gainers? / Gold price?"):
        st.session_state.messages.append({
            "role": "user", "content": prompt
        })
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Researching..."):
                answer = ask_agent(
                    question   = prompt,
                    session_id = st.session_state.get(
                        'session_id', str(uuid.uuid4())
                    )
                )
            st.markdown(answer)

        st.session_state.messages.append({
            "role": "assistant", "content": answer
        })


def main():
    if st.session_state.get('change_password'):
        show_change_password()
    elif st.session_state.get('logged_in'):
        show_dashboard()
    else:
        show_login()


if __name__ == "__main__":
    main()
