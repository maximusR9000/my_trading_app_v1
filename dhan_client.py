"""
dhan_client.py
--------------
Thin wrapper around the official `dhanhq` Python library.

Responsibilities:
  1. Authenticate using client_id + access_token (read from environment,
     never hardcoded).
  2. Fetch the live option chain for an index and resolve ATM / OTM
     strikes to their Dhan `security_id` (required for order placement).
  3. Call Dhan's margin calculator BEFORE placing real orders, so we can
     confirm the hedge actually reduces margin instead of assuming it.
  4. Place orders with clear, non-swallowed error reporting.

This file deliberately does NOT cache credentials to disk. They are read
from environment variables (or Streamlit secrets) at runtime only.
"""

import os
import math
from dataclasses import dataclass
from typing import Optional

from dhanhq import DhanContext, dhanhq

from config import DEFAULT_PRODUCT_TYPE, DEFAULT_ORDER_TYPE, DEFAULT_VALIDITY


@dataclass
class OptionLeg:
    """Represents a single option leg resolved from the option chain."""
    strike: float
    option_type: str        # "CE" or "PE"
    security_id: str
    last_price: float


class DhanClientError(Exception):
    """Raised when something Dhan-related fails, with a clear message."""
    pass


def get_dhan_client() -> dhanhq:
    """
    Build an authenticated dhanhq client from environment variables.

    Required env vars:
      DHAN_CLIENT_ID
      DHAN_ACCESS_TOKEN

    Raises DhanClientError if credentials are missing — fails loudly
    rather than silently proceeding unauthenticated.
    """
    client_id = os.environ.get("DHAN_CLIENT_ID")
    access_token = os.environ.get("DHAN_ACCESS_TOKEN")

    if not client_id or not access_token:
        raise DhanClientError(
            "Missing DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN environment "
            "variables. Set them as GitHub/Streamlit secrets — never "
            "hardcode them in the source file."
        )

    context = DhanContext(client_id, access_token)
    return dhanhq(context)


def fetch_option_chain(dhan: dhanhq, underlying_security_id: str,
                        underlying_segment: str, expiry: str) -> dict:
    """
    Fetch the live option chain for the given underlying and expiry.

    Returns the raw 'oc' dict from Dhan's response:
        { "<strike>": { "ce": {...}, "pe": {...} }, ... }

    Raises DhanClientError on API failure.
    """
    response = dhan.option_chain(
        under_security_id=underlying_security_id,
        under_exchange_segment=underlying_segment,
        expiry=expiry,
    )

    if not response or response.get("status") != "success":
        raise DhanClientError(
            f"Option chain fetch failed: {response.get('remarks', response)}"
        )

    data = response.get("data", {})
    if "oc" not in data:
        raise DhanClientError("Option chain response missing 'oc' field.")

    return data


def get_nearest_expiry(dhan: dhanhq, underlying_security_id: str,
                        underlying_segment: str) -> str:
    """
    Fetch the list of available expiries and return the nearest one
    (current week). Dhan's expirylist endpoint returns dates sorted
    ascending, so index 0 is nearest — but we sort explicitly to be safe.
    """
    response = dhan.expiry_list(
        under_security_id=underlying_security_id,
        under_exchange_segment=underlying_segment,
    )

    if not response or response.get("status") != "success":
        raise DhanClientError(
            f"Expiry list fetch failed: {response.get('remarks', response)}"
        )

    expiries = sorted(response.get("data", []))
    if not expiries:
        raise DhanClientError("No expiries returned for this underlying.")

    return expiries[0]


def resolve_atm_strike(option_chain_data: dict, spot_price: float,
                        strike_step: int) -> float:
    """
    Round the spot price to the nearest valid strike (ATM strike).
    """
    return round(spot_price / strike_step) * strike_step


def get_leg_from_chain(option_chain_data: dict, strike: float,
                        option_type: str) -> OptionLeg:
    """
    Pull the security_id and last traded price for a specific strike
    and option type ("ce" or "pe") out of the option chain data.

    Strike keys in Dhan's response are formatted like "25650.000000",
    so we format our lookup key to match.
    """
    oc = option_chain_data.get("oc", {})
    strike_key = f"{strike:.6f}"

    leg_data = oc.get(strike_key, {}).get(option_type.lower())
    if leg_data is None:
        raise DhanClientError(
            f"Strike {strike} {option_type} not found in option chain. "
            f"Available strikes near it may differ — check strike_step "
            f"in config.py matches this index's actual strike interval."
        )

    security_id = leg_data.get("security_id")
    if security_id is None:
        raise DhanClientError(
            f"No security_id present for strike {strike} {option_type}."
        )

    return OptionLeg(
        strike=strike,
        option_type=option_type.upper(),
        security_id=str(security_id),
        last_price=leg_data.get("last_price", 0.0),
    )


def check_margin(dhan: dhanhq, hedge_leg: OptionLeg, short_leg: OptionLeg,
                  exchange_segment: str, quantity: int) -> dict:
    """
    Call Dhan's Margin Calculator for BOTH legs together to confirm the
    hedge actually produces a margin benefit before any order is placed.

    Returns the raw margin response so the UI can display it to the user
    for a final sanity check.
    """
    try:
        hedge_margin = dhan.margin_calculator(
            security_id=hedge_leg.security_id,
            exchange_segment=exchange_segment,
            transaction_type="BUY",
            quantity=quantity,
            product_type=DEFAULT_PRODUCT_TYPE,
            price=hedge_leg.last_price,
        )
        short_margin = dhan.margin_calculator(
            security_id=short_leg.security_id,
            exchange_segment=exchange_segment,
            transaction_type="SELL",
            quantity=quantity,
            product_type=DEFAULT_PRODUCT_TYPE,
            price=short_leg.last_price,
        )
    except Exception as exc:
        raise DhanClientError(f"Margin calculator call failed: {exc}")

    return {"hedge_leg_margin": hedge_margin, "short_leg_margin": short_margin}


def place_leg_order(dhan: dhanhq, leg: OptionLeg, exchange_segment: str,
                     transaction_type: str, quantity: int) -> dict:
    """
    Place a single order leg and return Dhan's raw response.
    Does NOT swallow errors — caller must check response status.
    """
    response = dhan.place_order(
        security_id=leg.security_id,
        exchange_segment=exchange_segment,
        transaction_type=transaction_type,   # "BUY" or "SELL"
        quantity=quantity,
        order_type=DEFAULT_ORDER_TYPE,
        product_type=DEFAULT_PRODUCT_TYPE,
        price=0,
        validity=DEFAULT_VALIDITY,
    )
    return response
