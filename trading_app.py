import streamlit as st
from dhanhq import dhanhq, DhanContext

# --- 1. SETUP ---
CLIENT_ID = st.secrets["DHAN_CLIENT_ID"]
ACCESS_TOKEN = st.secrets["DHAN_ACCESS_TOKEN"]
dhan_context = DhanContext(CLIENT_ID, ACCESS_TOKEN)
dhan = dhanhq(dhan_context)

# --- 2. THE 5 SHARES ---
stock_ids = {
    "Reliance Industries": "2885",
    "HDFC Bank": "1333",
    "TCS": "11536",
    "Infosys": "1594",
    "ICICI Bank": "4193"
}

# --- 3. UI ---
st.title("API Connection Tester (Failsafe Version)")
st.write("Using a raw string workaround to avoid library errors.")

selected_stock = st.selectbox("Select a Share", list(stock_ids.keys()))
qty = st.number_input("Enter Quantity", min_value=1, value=5)

st.divider()

col1, col2 = st.columns(2)

with col1:
    if st.button("BUY", type="primary"):
        security_id = stock_ids[selected_stock]
        
        # WORKAROUND: Using pure text instead of dhan.CONSTANT
        response = dhan.place_order(
            security_id=security_id,
            exchange_segment="NSE_EQ",  
            transaction_type="BUY",
            quantity=qty,
            order_type="MARKET",
            product_type="CNC",         
            price=0
        )
        
        st.write("Buy Signal Sent! Raw response:")
        st.json(response)

with col2:
    if st.button("SELL", type="primary"):
        security_id = stock_ids[selected_stock]
        
        # WORKAROUND: Using pure text instead of dhan.CONSTANT
        response = dhan.place_order(
            security_id=security_id,
            exchange_segment="NSE_EQ", 
            transaction_type="SELL",
            quantity=qty,
            order_type="MARKET",
            product_type="CNC",         
            price=0
        )
        
        st.write("Sell Signal Sent! Raw response:")
        st.json(response)
