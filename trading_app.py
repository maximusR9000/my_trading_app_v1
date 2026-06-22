import streamlit as st
from dhanhq import dhanhq, DhanContext

# --- 1. SETUP ---
CLIENT_ID = st.secrets["DHAN_CLIENT_ID"]
ACCESS_TOKEN = st.secrets["DHAN_ACCESS_TOKEN"]
dhan_context = DhanContext(CLIENT_ID, ACCESS_TOKEN)
dhan = dhanhq(dhan_context)

# --- 2. LIVE DHAN API FETCH ---
def get_live_option_data(index_name, strike_offset, option_type):
    # Dhan uses ID 13 for Nifty 50 and 51 for Sensex
    underlying_id = 13 if index_name == "Nifty 50" else 51 
    segment = "IDX_I"
    
    # Get the nearest expiry date
    expiry_response = dhan.expiry_list(under_security_id=underlying_id, under_exchange_segment=segment)
    if 'data' not in expiry_response or not expiry_response['data']:
        st.error(f"Failed to fetch expiry dates for {index_name}.")
        return None, None, None
        
    nearest_expiry = expiry_response['data'][0] 
    
    # Get the live option chain
    oc_response = dhan.option_chain(under_security_id=underlying_id, under_exchange_segment=segment, expiry=nearest_expiry)
    if 'data' not in oc_response:
        st.error("Failed to fetch the live Option Chain from Dhan.")
        return None, None, None
        
    # Get the real-time spot price
    live_spot = oc_response['data']['last_price']
    
    # Calculate target strikes based on the live spot
    step = 50 if index_name == "Nifty 50" else 100
    atm_strike = round(live_spot / step) * step
    target_strike = atm_strike + strike_offset
    
    # Safely find the exact ID by checking the strike keys
    opt_key = option_type.lower()
    for strike_key, strike_data in oc_response['data']['oc'].items():
        if float(strike_key) == target_strike:
            if opt_key in strike_data:
                exact_id = strike_data[opt_key]['security_id']
                return str(exact_id), target_strike, live_spot
                
    st.error(f"Could not find {index_name} {target_strike} {option_type} in the live Option Chain.")
    return None, target_strike, live_spot

# --- 3. UI & LOGIC ---
st.title("1-Click Options Trader")

col_a, col_b = st.columns(2)
with col_a:
    index_choice = st.selectbox("Choose Index", ["Nifty 50", "Sensex"])
with col_b:
    num_lots = st.selectbox("Select Number of Lots", [1, 2, 3, 4, 5])

# Current 2026 Exchange Lot Sizes
base_lot_size = 65 if index_choice == "Nifty 50" else 20
order_quantity = base_lot_size * num_lots

st.caption(f"**Total Quantity:** {order_quantity} shares ({num_lots} lot)")
st.divider()

col1, col2 = st.columns(2)

with col1:
    if st.button("BUY (Bull Put Spread)", type="primary"):
        otm_offset = -200 if index_choice == "Nifty 50" else -400
        
        otm_id, otm_strike, live_spot = get_live_option_data(index_choice, otm_offset, "PE")
        atm_id, atm_strike, _ = get_live_option_data(index_choice, 0, "PE")
        
        if otm_id and atm_id:
            st.info(f"Live Spot Price: {live_spot}")
            exchange = dhan.NSE_FNO if index_choice == "Nifty 50" else dhan.BSE_FNO
            
            # 1. Buy OTM
            dhan.place_order(security_id=otm_id, exchange_segment=exchange, transaction_type=dhan.BUY, quantity=order_quantity, order_type=dhan.MARKET, product_type=dhan.MARGIN, price=0)
            st.success(f"Bought {order_quantity}x {otm_strike} PE")
            
            # 2. Sell ATM
            dhan.place_order(security_id=atm_id, exchange_segment=exchange, transaction_type=dhan.SELL, quantity=order_quantity, order_type=dhan.MARKET, product_type=dhan.MARGIN, price=0)
            st.success(f"Sold {order_quantity}x {atm_strike} PE")
            
            # Save data to exit later
            st.session_state['active_trade'] = "BUY"
            st.session_state['atm_id'] = atm_id
            st.session_state['otm_id'] = otm_id
            st.session_state['trade_qty'] = order_quantity
            st.session_state['exchange'] = exchange

with col2:
    if st.button("SELL (Bear Call Spread)", type="primary"):
        otm_offset = 200 if index_choice == "Nifty 50" else 400
        
        otm_id, otm_strike, live_spot = get_live_option_data(index_choice, otm_offset, "CE")
        atm_id, atm_strike, _ = get_live_option_data(index_choice, 0, "CE")
        
        if otm_id and atm_id:
            st.info(f"Live Spot Price: {live_spot}")
            exchange = dhan.NSE_FNO if index_choice == "Nifty 50" else dhan.BSE_FNO
            
            # 1. Buy OTM
            dhan.place_order(security_id=otm_id, exchange_segment=exchange, transaction_type=dhan.BUY, quantity=order_quantity, order_type=dhan.MARKET, product_type=dhan.MARGIN, price=0)
            st.success(f"Bought {order_quantity}x {otm_strike} CE")
            
            # 2. Sell ATM
            dhan.place_order(security_id=atm_id, exchange_segment=exchange, transaction_type=dhan.SELL, quantity=order_quantity, order_type=dhan.MARKET, product_type=dhan.MARGIN, price=0)
            st.success(f"Sold {order_quantity}x {atm_strike} CE")
            
            # Save data to exit later
            st.session_state['active_trade'] = "SELL"
            st.session_state['atm_id'] = atm_id
            st.session_state['otm_id'] = otm_id
            st.session_state['trade_qty'] = order_quantity
            st.session_state['exchange'] = exchange

st.divider()

st.subheader("Live Positions")

try:
    positions = dhan.get_positions()
    if 'data' in positions and positions['data']:
        total_mtm = sum(float(pos['realized_profit']) + float(pos['unrealized_profit']) for pos in positions['data'])
        st.metric("Total MTM", f"₹ {total_mtm}")
    else:
        st.write("No active positions right now.")
except Exception:
    st.write("Waiting for active trades...")

if st.button("EXIT TRADE", type="secondary"):
    if 'active_trade' in st.session_state:
        atm_id = st.session_state['atm_id']
        otm_id = st.session_state['otm_id']
        exit_qty = st.session_state['trade_qty'] 
        exchange = st.session_state['exchange']
        
        # 1. Buy back the sold leg
        dhan.place_order(security_id=atm_id, exchange_segment=exchange, transaction_type=dhan.BUY, quantity=exit_qty, order_type=dhan.MARKET, product_type=dhan.MARGIN, price=0)
        st.warning(f"Closed Sold Leg ({exit_qty} qty).")
        
        # 2. Sell the bought leg
        dhan.place_order(security_id=otm_id, exchange_segment=exchange, transaction_type=dhan.SELL, quantity=exit_qty, order_type=dhan.MARKET, product_type=dhan.MARGIN, price=0)
        st.warning(f"Closed Bought Leg ({exit_qty} qty). Trade Exited.")
        
        del st.session_state['active_trade']
        del st.session_state['atm_id']
        del st.session_state['otm_id']
        del st.session_state['trade_qty']
        del st.session_state['exchange']
    else:
        st.info("No active trades recorded in this window.")
