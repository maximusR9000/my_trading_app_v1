import streamlit as st
from dhanhq import dhanhq, DhanContext

# ==========================================
# 1. SETUP AND CONNECTION
# ==========================================

CLIENT_ID = st.secrets["DHAN_CLIENT_ID"]
ACCESS_TOKEN = st.secrets["DHAN_ACCESS_TOKEN"]

# Connect to Dhan
dhan_context = DhanContext(CLIENT_ID, ACCESS_TOKEN)
dhan = dhanhq(dhan_context)

# ==========================================
# 2. LIVE API FETCH FUNCTION (NO MORE CSV)
# ==========================================

def get_live_option_data(index_name, strike_offset, option_type):
    """
    Fetches the live spot price and exact Security ID straight from Dhan's Option Chain API.
    """
    # 13 is the Dhan system ID for NIFTY 50. 51 is commonly used for BSE SENSEX.
    underlying_id = 13 if index_name == "Nifty 50" else 51 
    segment = "IDX_I"
    
    # 1. Ask Dhan for the nearest expiry date
    expiry_response = dhan.expiry_list(under_security_id=underlying_id, under_exchange_segment=segment)
    
    if 'data' not in expiry_response or not expiry_response['data']:
        st.error(f"Failed to fetch expiry dates for {index_name}.")
        return None, None
        
    nearest_expiry = expiry_response['data'][0] 
    
    # 2. Ask Dhan for the entire live option chain for that expiry
    oc_response = dhan.option_chain(under_security_id=underlying_id, under_exchange_segment=segment, expiry=nearest_expiry)
    
    if 'data' not in oc_response:
        st.error("Failed to fetch the Option Chain from Dhan.")
        return None, None
        
    # 3. Extract the live spot price
    live_spot = oc_response['data']['last_price']
    
    # 4. Calculate the target strike price
    step = 50 if index_name == "Nifty 50" else 100
    atm_strike = round(live_spot / step) * step
    target_strike = atm_strike + strike_offset
    
    # Dhan's option chain dictionary formats strikes like '22000.000000'
    strike_key = f"{float(target_strike):.6f}"
    
    # 5. Extract the exact Security ID
    try:
        opt_key = option_type.lower() # 'ce' or 'pe'
        exact_id = oc_response['data']['oc'][strike_key][opt_key]['security_id']
        return str(exact_id), target_strike
    except KeyError:
        st.error(f"Could not find ID for {index_name} {target_strike} {option_type} in the live Option Chain.")
        return None, target_strike

# ==========================================
# 3. USER INTERFACE
# ==========================================

st.title("1-Click Options Trader")

col_a, col_b = st.columns(2)

with col_a:
    index_choice = st.selectbox("Choose Index", ["Nifty 50", "Sensex"])

with col_b:
    num_lots = st.selectbox("Select Number of Lots", [1, 2, 3, 4, 5])

# Safety Check: Standard base lot sizes
base_lot_size = 25 if index_choice == "Nifty 50" else 10
order_quantity = base_lot_size * num_lots

st.caption(f"**Safe Trading Active:** You selected {num_lots} lot(s). Total order quantity will be {order_quantity} shares.")
st.divider()

col1, col2 = st.columns(2)

with col1:
    if st.button("BUY (Bull Put Spread)", type="primary"):
        # Put offsets: ATM is 0, OTM Put is a lower strike
        otm_offset = -200 if index_choice == "Nifty 50" else -400
        
        # Fetch directly from Dhan API
        otm_id, otm_strike = get_live_option_data(index_choice, otm_offset, "PE")
        atm_id, atm_strike = get_live_option_data(index_choice, 0, "PE")
        
        if otm_id and atm_id:
            exchange = dhan.NSE_FNO if index_choice == "Nifty 50" else dhan.BSE_FNO
            
            # 1. Buy OTM PE First
            dhan.place_order(security_id=otm_id, exchange_segment=exchange, transaction_type=dhan.BUY, quantity=order_quantity, order_type=dhan.MARKET, product_type=dhan.MARGIN, price=0)
            st.success(f"Bought {order_quantity}x {otm_strike} PE")
            
            # 2. Sell ATM PE Second
            dhan.place_order(security_id=atm_id, exchange_segment=exchange, transaction_type=dhan.SELL, quantity=order_quantity, order_type=dhan.MARKET, product_type=dhan.MARGIN, price=0)
            st.success(f"Sold {order_quantity}x {atm_strike} PE")
            
            # Save state
            st.session_state['active_trade'] = "BUY"
            st.session_state['atm_id'] = atm_id
            st.session_state['otm_id'] = otm_id
            st.session_state['trade_qty'] = order_quantity
            st.session_state['exchange'] = exchange

with col2:
    if st.button("SELL (Bear Call Spread)", type="primary"):
        # Call offsets: ATM is 0, OTM Call is a higher strike
        otm_offset = 200 if index_choice == "Nifty 50" else 400
        
        otm_id, otm_strike = get_live_option_data(index_choice, otm_offset, "CE")
        atm_id, atm_strike = get_live_option_data(index_choice, 0, "CE")
        
        if otm_id and atm_id:
            exchange = dhan.NSE_FNO if index_choice == "Nifty 50" else dhan.BSE_FNO
            
            # 1. Buy OTM CE First
            dhan.place_order(security_id=otm_id, exchange_segment=exchange, transaction_type=dhan.BUY, quantity=order_quantity, order_type=dhan.MARKET, product_type=dhan.MARGIN, price=0)
            st.success(f"Bought {order_quantity}x {otm_strike} CE")
            
            # 2. Sell ATM CE Second
            dhan.place_order(security_id=atm_id, exchange_segment=exchange, transaction_type=dhan.SELL, quantity=order_quantity, order_type=dhan.MARKET, product_type=dhan.MARGIN, price=0)
            st.success(f"Sold {order_quantity}x {atm_strike} CE")
            
            # Save state
            st.session_state['active_trade'] = "SELL"
            st.session_state['atm_id'] = atm_id
            st.session_state['otm_id'] = otm_id
            st.session_state['trade_qty'] = order_quantity
            st.session_state['exchange'] = exchange

st.divider()

# ==========================================
# 4. MTM AND EXIT SYSTEM
# ==========================================

st.subheader("Live Positions")

try:
    positions = dhan.get_positions()
    if 'data' in positions and positions['data']:
        total_mtm = sum(float(pos['realized_profit']) + float(pos['unrealized_profit']) for pos in positions['data'])
        st.metric("Total MTM", f"₹ {total_mtm}")
    else:
        st.write("No active positions tracked by Dhan right now.")
except Exception as e:
    st.write("Waiting for active trades to display MTM...")

if st.button("EXIT TRADE", type="secondary"):
    if 'active_trade' in st.session_state:
        atm_id = st.session_state['atm_id']
        otm_id = st.session_state['otm_id']
        exit_qty = st.session_state['trade_qty'] 
        exchange = st.session_state['exchange']
        
        # 1. Close the SELL leg first (buy it back)
        dhan.place_order(security_id=atm_id, exchange_segment=exchange, transaction_type=dhan.BUY, quantity=exit_qty, order_type=dhan.MARKET, product_type=dhan.MARGIN, price=0)
        st.warning(f"Closed Sold Leg ({exit_qty} qty).")
        
        # 2. Close the BUY leg second (sell it)
        dhan.place_order(security_id=otm_id, exchange_segment=exchange, transaction_type=dhan.SELL, quantity=exit_qty, order_type=dhan.MARKET, product_type=dhan.MARGIN, price=0)
        st.warning(f"Closed Bought Leg ({exit_qty} qty). Trade Exited.")
        
        # Clear the memory
        del st.session_state['active_trade']
        del st.session_state['atm_id']
        del st.session_state['otm_id']
        del st.session_state['trade_qty']
        del st.session_state['exchange']
    else:
        st.info("No active trades recorded in this window.")
