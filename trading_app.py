import streamlit as st
from dhanhq import dhanhq
import pandas as pd
import requests
import io
import time

# ==========================================
# 1. SETUP AND CONNECTION
# ==========================================

# Enter your Dhan API Details here
CLIENT_ID = st.secrets["DHAN_CLIENT_ID"]
ACCESS_TOKEN = st.secrets["DHAN_ACCESS_TOKEN"]
# Connect to Dhan
dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)

# ==========================================
# 2. DATA DOWNLOAD (RUNS ONLY ONCE)
# ==========================================

@st.cache_data
def load_scrip_master():
    """Downloads Dhan's daily ID list so the system can find exact option codes."""
    csv_url = "https://images.dhan.co/api-data/api-scrip-master.csv"
    response = requests.get(csv_url)
    df = pd.read_csv(io.StringIO(response.text))
    return df

# Load the file into memory
scrip_df = load_scrip_master()

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================

def get_current_price(index_name):
    """Fetches the live price. (Replace this with live API data later)."""
    # For now, we use a placeholder price
    if index_name == "Nifty 50":
        return 22000
    else:
        return 73000

def get_security_id(index_name, strike, option_type):
    """Searches the downloaded list to find the exact computer ID for the option."""
    symbol = "NIFTY" if index_name == "Nifty 50" else "SENSEX"
    
    # Filter for Index Options
    df = scrip_df[scrip_df['SEM_INSTRUMENT_NAME'] == 'OPTIDX']
    df = df[df['SEM_CUSTOM_SYMBOL'].str.contains(symbol, na=False)]
    
    # Search for exactly this symbol, strike, and type (CE/PE)
    search_pattern = f"{symbol}.*{int(strike)}{option_type}"
    matches = df[df['SEM_TRADING_SYMBOL'].str.contains(search_pattern, na=False, regex=True)]
    
    if not matches.empty:
        # Sort by date to get the closest weekly expiry
        matches = matches.sort_values(by='SEM_EXPIRY_DATE')
        exact_id = matches.iloc[0]['SEM_SMST_SECURITY_ID']
        return str(exact_id)
    else:
        st.error(f"Could not find ID for {symbol} {strike} {option_type}")
        return None

def place_market_order(security_id, transaction_type, quantity):
    """Sends the actual buy or sell signal to Dhan."""
    dhan.place_order(
        security_id=security_id,
        exchange_segment=dhan.NSE_FNO,
        transaction_type=transaction_type,
        quantity=quantity,
        order_type=dhan.MARKET,
        product_type=dhan.MARGIN, # MARGIN means NORMAL/Carryforward order
        price=0
    )

# ==========================================
# 4. USER INTERFACE
# ==========================================

st.title("1-Click Options Trader")

# Top Settings
col_a, col_b = st.columns(2)

with col_a:
    index_choice = st.selectbox("Choose Index", ["Nifty 50", "Sensex"])

with col_b:
    num_lots = st.selectbox("Select Number of Lots", [1, 2, 3, 4, 5, 10, 20])

# Calculate exact quantity
base_lot_size = 25 if index_choice == "Nifty 50" else 10
order_quantity = base_lot_size * num_lots

st.caption(f"**Total trading quantity:** {order_quantity} shares")
st.divider()

# Trade Buttons
col1, col2 = st.columns(2)

with col1:
    if st.button("BUY (Bull Put Spread)", type="primary"):
        current_price = get_current_price(index_choice)
        
        # Calculate Strikes
        atm_strike = round(current_price / 50) * 50 
        otm_strike = atm_strike - 200
        
        # Get exact IDs
        otm_id = get_security_id(index_choice, otm_strike, "PE")
        atm_id = get_security_id(index_choice, atm_strike, "PE")
        
        if otm_id and atm_id:
            # 1. Buy OTM PE First (For margin benefit)
            place_market_order(otm_id, dhan.BUY, order_quantity)
            st.success(f"Bought {order_quantity}x {otm_strike} PE")
            
            # 2. Sell ATM PE Second
            place_market_order(atm_id, dhan.SELL, order_quantity)
            st.success(f"Sold {order_quantity}x {atm_strike} PE")
            
            # Save trade details to memory for exiting later
            st.session_state['active_trade'] = "BUY"
            st.session_state['atm_id'] = atm_id
            st.session_state['otm_id'] = otm_id
            st.session_state['trade_qty'] = order_quantity

with col2:
    if st.button("SELL (Bear Call Spread)", type="primary"):
        current_price = get_current_price(index_choice)
        
        # Calculate Strikes
        atm_strike = round(current_price / 50) * 50
        otm_strike = atm_strike + 200
        
        # Get exact IDs
        otm_id = get_security_id(index_choice, otm_strike, "CE")
        atm_id = get_security_id(index_choice, atm_strike, "CE")
        
        if otm_id and atm_id:
            # 1. Buy OTM CE First
            place_market_order(otm_id, dhan.BUY, order_quantity)
            st.success(f"Bought {order_quantity}x {otm_strike} CE")
            
            # 2. Sell ATM CE Second
            place_market_order(atm_id, dhan.SELL, order_quantity)
            st.success(f"Sold {order_quantity}x {atm_strike} CE")
            
            # Save trade details to memory
            st.session_state['active_trade'] = "SELL"
            st.session_state['atm_id'] = atm_id
            st.session_state['otm_id'] = otm_id
            st.session_state['trade_qty'] = order_quantity

st.divider()

# ==========================================
# 5. MTM AND EXIT SYSTEM
# ==========================================

st.subheader("Live Positions")

# Show Running Profit/Loss
try:
    positions = dhan.get_positions()
    if 'data' in positions and positions['data']:
        total_mtm = sum(float(pos['realized_profit']) + float(pos['unrealized_profit']) for pos in positions['data'])
        st.metric("Total MTM", f"₹ {total_mtm}")
    else:
        st.write("No active positions tracked by Dhan right now.")
except Exception as e:
    st.write("Waiting for active trades to display MTM...")

# Exit Button
if st.button("EXIT TRADE", type="secondary"):
    if 'active_trade' in st.session_state:
        atm_id = st.session_state['atm_id']
        otm_id = st.session_state['otm_id']
        exit_qty = st.session_state['trade_qty'] 
        
        # 1. Close the SELL leg first (buy it back)
        place_market_order(atm_id, dhan.BUY, exit_qty)
        st.warning(f"Closed Sold Leg ({exit_qty} qty).")
        
        # 2. Close the BUY leg second (sell it)
        place_market_order(otm_id, dhan.SELL, exit_qty)
        st.warning(f"Closed Bought Leg ({exit_qty} qty). Trade Exited.")
        
        # Clear the memory
        del st.session_state['active_trade']
        del st.session_state['atm_id']
        del st.session_state['otm_id']
        del st.session_state['trade_qty']
    else:
        st.info("No active trades recorded in this window.")
