import streamlit as st
from dhanhq import dhanhq, DhanContext

# --- 1. SETUP ---
CLIENT_ID = st.secrets["DHAN_CLIENT_ID"]
ACCESS_TOKEN = st.secrets["DHAN_ACCESS_TOKEN"]
dhan_context = DhanContext(CLIENT_ID, ACCESS_TOKEN)
dhan = dhanhq(dhan_context)

# --- 2. THE 5 SHARES ---
# These are the standard NSE Security IDs for these stocks
stock_ids = {
    "Reliance Industries": "2885",
    "HDFC Bank": "1333",
    "TCS": "11536",
    "Infosys": "1594",
    "ICICI Bank": "4193"
}

# --- 3. USER INTERFACE ---
st.title("API Connection Tester")
st.write("Test your Dhan API connection with simple stock orders.")

# Dropdowns and inputs
selected_stock = st.selectbox("Select a Share", list(stock_ids.keys()))
qty = st.number_input("Enter Quantity", min_value=1, value=5)

st.divider()

col1, col2 = st.columns(2)

with col1:
    if st.button("BUY", type="primary"):
        security_id = stock_ids[selected_stock]
        
        # Placing order with Dhan
        response = dhan.place_order(
            security_id=security_id,
            exchange_segment=dhan.NSE_EQ,     # Equity Cash Segment
            transaction_type=dhan.BUY,
            quantity=qty,
            order_type=dhan.MARKET,
            product_type=dhan.CNC,            # CNC = Cash & Carry (Standard Delivery)
            price=0
        )
        
        st.write("Buy Signal Sent! Here is what Dhan said:")
        st.json(response)

with col2:
    if st.button("SELL", type="primary"):
        security_id = stock_ids[selected_stock]
        
        # Placing order with Dhan
        response = dhan.place_order(
            security_id=security_id,
            exchange_segment=dhan.NSE_EQ,     # Equity Cash Segment
            transaction_type=dhan.SELL,
            quantity=qty,
            order_type=dhan.MARKET,
            product_type=dhan.CNC,            # CNC = Cash & Carry (Standard Delivery)
            price=0
        )
        
        st.write("Sell Signal Sent! Here is what Dhan said:")
        st.json(response)
