# app.py
# pip install dhanhq
import streamlit as st

st.set_page_config(
    page_title="Spread Trader",
    page_icon="📈",
    layout="centered"
)
from dhanhq import dhanhq
dhan = dhanhq(
    st.secrets["DHAN_CLIENT_ID"],
    st.secrets["DHAN_ACCESS_TOKEN"]
)

def get_index_price(index_name):
    try:
        if index_name == "NIFTY":
            security_id = "13"   # NIFTY 50 Index
            exchange_segment = "IDX_I"

        elif index_name == "SENSEX":
            security_id = "51"   # SENSEX Index
            exchange_segment = "IDX_I"

        response = dhan.quote_data(
            securities={
                exchange_segment: [security_id]
            }
        )

        return response["data"][exchange_segment][security_id]["last_price"]

    except Exception as e:
        st.error(f"Price Error: {e}")
        return None
# -----------------------------
# Session State
# -----------------------------
if "logs" not in st.session_state:
    st.session_state.logs = []

# -----------------------------
# Header
# -----------------------------
st.title("📈 Spread Trader")
st.caption("NIFTY / SENSEX Option Spread Execution Utility")

# -----------------------------
# Index Selection
# -----------------------------
index = st.selectbox(
    "Select Index",
    ["NIFTY", "SENSEX"]
)

# -----------------------------
# Market Information
# -----------------------------
ive_price = get_index_price(index)

col1, col2 = st.columns(2)

with col1:
    st.metric(
        label="Live Price",
        value=f"{live_price:,.2f}" if live_price else "N/A"
    )

with col2:
    st.metric(
        label="Nearest Expiry",
        value="Loading..."
    )

# -----------------------------
# Lot Selection
# -----------------------------
st.divider()

lots = st.number_input(
    "Number of Lots",
    min_value=1,
    max_value=100,
    value=1,
    step=1
)

# -----------------------------
# Trade Preview
# -----------------------------
st.divider()

st.subheader("Trade Preview")

col1, col2 = st.columns(2)

with col1:
    st.metric(
        "ATM Strike",
        "Loading..."
    )

with col2:
    st.metric(
        "Hedge Strike",
        "Loading..."
    )

st.info(
    """
BUY Strategy:
Buy Hedge PE → Sell ATM PE

SELL Strategy:
Buy Hedge CE → Sell ATM CE
"""
)

# -----------------------------
# Action Buttons
# -----------------------------
st.divider()

st.subheader("Execute Trade")

col1, col2 = st.columns(2)

with col1:
    if st.button(
        "🟢 BUY",
        use_container_width=True,
        type="primary"
    ):
        st.session_state.logs.append(
            "BUY button clicked"
        )
        st.success("BUY request initiated")

with col2:
    if st.button(
        "🔴 SELL",
        use_container_width=True
    ):
        st.session_state.logs.append(
            "SELL button clicked"
        )
        st.success("SELL request initiated")

# -----------------------------
# Position Summary
# -----------------------------
st.divider()

st.subheader("Position Summary")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Net MTM",
        "₹0"
    )

with col2:
    st.metric(
        "Realized P&L",
        "₹0"
    )

with col3:
    st.metric(
        "Unrealized P&L",
        "₹0"
    )

# -----------------------------
# Utility Buttons
# -----------------------------
st.divider()

col1, col2 = st.columns(2)

with col1:
    if st.button(
        "🔄 Refresh Positions",
        use_container_width=True
    ):
        st.info("Refreshing positions...")

with col2:
    if st.button(
        "⚠️ Square Off All",
        use_container_width=True
    ):
        st.warning("Square Off request initiated")

# -----------------------------
# Execution Logs
# -----------------------------
st.divider()

st.subheader("Execution Log")

if st.session_state.logs:
    for log in reversed(st.session_state.logs):
        st.write(log)
else:
    st.caption("No activity yet.")
