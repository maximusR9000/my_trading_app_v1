"""
app.py
------
Streamlit UI: two dropdowns (index, lots) and two buttons (Buy, Sell)
that trigger the hedged order strategy defined in strategy.py.

RUN LOCALLY:
    1. pip install -r requirements.txt
    2. Set environment variables (see README.md for how):
         DHAN_CLIENT_ID
         DHAN_ACCESS_TOKEN
    3. streamlit run app.py

DEPLOY ON STREAMLIT COMMUNITY CLOUD:
    Push this folder to a GitHub repo, connect it at share.streamlit.io,
    and set DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN under App Settings -> Secrets
    (see README.md for exact format). Never commit credentials to GitHub.
"""

import streamlit as st

from config import INDEX_CONFIG, LOT_CHOICES
from dhan_client import get_dhan_client, DhanClientError
from strategy import run_hedged_trade

st.set_page_config(page_title="Hedged Options Trader", layout="centered")

st.title("Hedged Options Order Panel")
st.caption(
    "Buy = bullish (buy OTM put hedge, then sell ATM put). "
    "Sell = bearish (buy OTM call hedge, then sell ATM call)."
)

# --- Connection check -------------------------------------------------
try:
    dhan = get_dhan_client()
    st.success("Connected to Dhan.", icon="✅")
except DhanClientError as exc:
    st.error(str(exc))
    st.stop()

# --- Inputs -------------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    index_name = st.selectbox("Index", list(INDEX_CONFIG.keys()))
with col2:
    lots = st.selectbox("Quantity (lots)", LOT_CHOICES)

spot_price = st.number_input(
    "Current spot price (enter manually from your chart screen)",
    min_value=0.0,
    step=0.05,
    help=(
        "This app does not stream live prices — you're already watching "
        "charts on your other phone. Enter the current index value here "
        "so the app can compute the correct ATM/OTM strikes."
    ),
)

confirm_margin = st.checkbox(
    "Run margin check before placing orders (recommended)", value=True
)

st.divider()

# --- Action buttons -------------------------------------------------------
btn_col1, btn_col2 = st.columns(2)
buy_clicked = btn_col1.button("BUY (Bullish)", use_container_width=True, type="primary")
sell_clicked = btn_col2.button("SELL (Bearish)", use_container_width=True)

direction = None
if buy_clicked:
    direction = "BUY"
elif sell_clicked:
    direction = "SELL"

if direction:
    if spot_price <= 0:
        st.error("Enter the current spot price before placing an order.")
        st.stop()

    with st.spinner(f"Resolving strikes and running {direction} sequence..."):
        result = run_hedged_trade(
            dhan=dhan,
            index_name=index_name,
            direction=direction,
            lots=lots,
            spot_price=spot_price,
            confirm_margin_first=confirm_margin,
        )

    if result.margin_check:
        with st.expander("Margin check details"):
            st.json(result.margin_check)

    if result.success:
        st.success(result.message)
        st.write(f"Hedge leg strike: {result.hedge_leg_strike}")
        st.write(f"Short leg strike: {result.short_leg_strike}")
        with st.expander("Raw order responses"):
            st.json({
                "hedge_order": result.hedge_order_response,
                "short_order": result.short_order_response,
            })
    else:
        st.error(result.message)
        if result.hedge_order_response or result.short_order_response:
            with st.expander("Raw order responses"):
                st.json({
                    "hedge_order": result.hedge_order_response,
                    "short_order": result.short_order_response,
                })

st.divider()
st.caption(
    "⚠️ This tool places real, live orders on your Dhan account the moment "
    "you click a button. Test with 1 lot first. Always verify positions in "
    "the Dhan app after every click."
)
