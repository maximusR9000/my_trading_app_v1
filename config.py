"""
config.py
---------
Static configuration: index definitions, lot sizes, and the underlying
security IDs Dhan uses to identify each index in the Option Chain API.

IMPORTANT: Verify these security IDs against Dhan's official Instrument
List (https://api.dhan.co/v2/instrument/{exchangeSegment}) before going
live. Dhan occasionally revises IDs, and a wrong ID means you fetch the
wrong instrument's option chain silently.
"""

# Exchange segment constants (as used by dhanhq library)
NSE_FNO = "NSE_FNO"
NSE_INDEX = "IDX_I"
BSE_FNO = "BSE_FNO"
BSE_INDEX = "IDX_I"

INDEX_CONFIG = {
    "NIFTY 50": {
        "underlying_security_id": "13",       # Nifty 50 index security id on Dhan
        "underlying_segment": NSE_INDEX,
        "exchange_segment": NSE_FNO,           # segment for placing the option order
        "lot_size": 75,
        "strike_step": 50,                     # gap between consecutive strikes
        "otm_offset_points": 200,               # how far OTM the hedge leg sits
    },
    "SENSEX": {
        "underlying_security_id": "51",        # Sensex index security id on Dhan
        "underlying_segment": BSE_INDEX,
        "exchange_segment": BSE_FNO,
        "lot_size": 20,
        "strike_step": 100,
        "otm_offset_points": 200,
    },
}

# How many lots the quantity dropdown should offer
LOT_CHOICES = list(range(1, 21))  # 1 to 20 lots

# Order safety defaults
DEFAULT_PRODUCT_TYPE = "INTRADAY"   # use INTRADAY (MIS) margin benefit applies here
DEFAULT_ORDER_TYPE = "MARKET"
DEFAULT_VALIDITY = "DAY"
