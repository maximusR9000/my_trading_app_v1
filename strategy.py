"""
strategy.py
-----------
The actual hedged-order strategy logic, kept separate from the Streamlit
UI so it can be tested independently and so the sequencing is easy to
audit.

Strategy recap (as specified by the user):
  BUY button (bullish view):
      1. BUY the OTM put (200 pts below spot)   -> hedge leg, placed FIRST
      2. SELL the ATM put                        -> income leg, placed SECOND
  SELL button (bearish view):
      1. BUY the OTM call (200 pts above spot)   -> hedge leg, placed FIRST
      2. SELL the ATM call                        -> income leg, placed SECOND

The hedge leg is always placed first and its fill is confirmed before the
short leg is sent. This matters: if the short leg were sent first (even by
a few hundred milliseconds), the account is briefly holding a naked short
and may attract full margin or get rejected for insufficient margin.
"""

import time
from dataclasses import dataclass
from typing import Literal

from config import INDEX_CONFIG
from dhan_client import (
    DhanClientError,
    fetch_option_chain,
    get_nearest_expiry,
    resolve_atm_strike,
    get_leg_from_chain,
    check_margin,
    place_leg_order,
)


@dataclass
class StrategyResult:
    success: bool
    message: str
    hedge_order_response: dict | None = None
    short_order_response: dict | None = None
    hedge_leg_strike: float | None = None
    short_leg_strike: float | None = None
    margin_check: dict | None = None


def run_hedged_trade(dhan, index_name: str, direction: Literal["BUY", "SELL"],
                      lots: int, spot_price: float,
                      confirm_margin_first: bool = True) -> StrategyResult:
    """
    Executes the full hedge-then-short sequence for one button press.

    direction:
        "BUY"  -> bullish: hedge with OTM put, short the ATM put
        "SELL" -> bearish: hedge with OTM call, short the ATM call

    confirm_margin_first:
        If True (recommended), runs the margin calculator on both legs
        and returns early WITHOUT placing real orders if it fails, so
        the user can inspect numbers before committing capital.
    """
    cfg = INDEX_CONFIG[index_name]
    quantity = lots * cfg["lot_size"]
    option_type = "PE" if direction == "BUY" else "CE"
    otm_direction = -1 if direction == "BUY" else 1  # PE hedge is below spot, CE hedge is above

    try:
        expiry = get_nearest_expiry(
            dhan, cfg["underlying_security_id"], cfg["underlying_segment"]
        )
        chain_data = fetch_option_chain(
            dhan, cfg["underlying_security_id"], cfg["underlying_segment"], expiry
        )

        atm_strike = resolve_atm_strike(chain_data, spot_price, cfg["strike_step"])
        otm_strike = atm_strike + (otm_direction * cfg["otm_offset_points"])
        # Round OTM strike to nearest valid step too
        otm_strike = round(otm_strike / cfg["strike_step"]) * cfg["strike_step"]

        hedge_leg = get_leg_from_chain(chain_data, otm_strike, option_type)
        short_leg = get_leg_from_chain(chain_data, atm_strike, option_type)

    except DhanClientError as exc:
        return StrategyResult(success=False, message=f"Setup failed: {exc}")

    margin_result = None
    if confirm_margin_first:
        try:
            margin_result = check_margin(
                dhan, hedge_leg, short_leg, cfg["exchange_segment"], quantity
            )
        except DhanClientError as exc:
            return StrategyResult(
                success=False,
                message=f"Margin check failed, no orders placed: {exc}",
                hedge_leg_strike=hedge_leg.strike,
                short_leg_strike=short_leg.strike,
            )

    # Step 1: place the hedge leg (BUY) first
    try:
        hedge_response = place_leg_order(
            dhan, hedge_leg, cfg["exchange_segment"], "BUY", quantity
        )
    except Exception as exc:
        return StrategyResult(
            success=False,
            message=f"Hedge leg order failed to send: {exc}",
            margin_check=margin_result,
        )

    if hedge_response.get("status") != "success":
        return StrategyResult(
            success=False,
            message=f"Hedge leg rejected, short leg NOT placed: "
                     f"{hedge_response.get('remarks', hedge_response)}",
            hedge_order_response=hedge_response,
            margin_check=margin_result,
        )

    # Small pause to let the hedge position register before shorting.
    # Dhan's own margin engine needs the BUY leg settled in positions
    # before the SELL leg gets the benefit recognized.
    time.sleep(1.5)

    # Step 2: place the short leg (SELL) second
    try:
        short_response = place_leg_order(
            dhan, short_leg, cfg["exchange_segment"], "SELL", quantity
        )
    except Exception as exc:
        return StrategyResult(
            success=False,
            message=(
                f"WARNING: Hedge leg filled but short leg failed to send: {exc}. "
                f"You are now holding an open hedge-only position — check your "
                f"positions tab and close manually if needed."
            ),
            hedge_order_response=hedge_response,
            hedge_leg_strike=hedge_leg.strike,
            margin_check=margin_result,
        )

    if short_response.get("status") != "success":
        return StrategyResult(
            success=False,
            message=(
                f"WARNING: Hedge leg filled but short leg was REJECTED: "
                f"{short_response.get('remarks', short_response)}. "
                f"You are now holding an open hedge-only position — check your "
                f"positions tab and close manually if needed."
            ),
            hedge_order_response=hedge_response,
            short_order_response=short_response,
            hedge_leg_strike=hedge_leg.strike,
            short_leg_strike=short_leg.strike,
            margin_check=margin_result,
        )

    return StrategyResult(
        success=True,
        message="Both legs placed successfully.",
        hedge_order_response=hedge_response,
        short_order_response=short_response,
        hedge_leg_strike=hedge_leg.strike,
        short_leg_strike=short_leg.strike,
        margin_check=margin_result,
    )
