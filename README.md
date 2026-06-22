# Hedged Options Order Panel (Dhan + Streamlit)

A two-button Streamlit app that places a hedged options trade on your Dhan
account in one click:

- **BUY** (bullish view) → buys an OTM put 200 points below spot (hedge),
  then sells the ATM put.
- **SELL** (bearish view) → buys an OTM call 200 points above spot (hedge),
  then sells the ATM call.

The hedge leg is always placed and confirmed **before** the short leg, so
your account isn't briefly exposed as a naked short.

---

## ⚠️ Before you use this with real money

1. **Test with 1 lot first.** Run a full Buy and a full Sell cycle with
   the smallest possible size and verify the resulting positions in the
   Dhan app match what you expect.
2. **The margin check does not guarantee the order will succeed.** It's a
   sanity check, not a guarantee from the exchange. Always glance at your
   margin/positions in the Dhan app after every click.
3. **This places live, real orders the instant you click a button.**
   There is no confirmation dialog by design (you asked for one-click).
   Consider adding one yourself (see "Optional: confirmation step" below)
   if you want extra safety.
4. I (the assistant who wrote this) cannot test this against your live
   Dhan account — I don't have your credentials or network access to
   Dhan's API. You are the first person to ever run this code against
   real money. Go slowly.

---

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit UI — dropdowns, buttons, results display |
| `strategy.py` | The hedge-then-short order sequencing logic |
| `dhan_client.py` | Wrapper around Dhan's API: auth, option chain, margin, order placement |
| `config.py` | Index definitions, lot sizes, OTM offset, security IDs |
| `requirements.txt` | Python dependencies |

---

## 1. Get your Dhan API credentials

1. Log in to [web.dhan.co](https://web.dhan.co).
2. Go to **Profile → DhanHQ Trading APIs** (or similar, Dhan's menu wording
   changes occasionally).
3. Generate an **Access Token**. Note: Dhan access tokens expire in 24
   hours unless you set up TOTP-based auto-renewal — for daily manual use,
   you'll likely need to regenerate this token each morning before market
   open.
4. Note your **Client ID** (a numeric ID, shown on your profile).

**Never paste these into the code files.** Use environment variables or
Streamlit secrets, as below.

---

## 2. Run locally first (recommended before deploying)

```bash
git clone <your-repo-url>
cd dhan_hedge_app
pip install -r requirements.txt
```

Set your credentials as environment variables for the session:

**Mac/Linux:**
```bash
export DHAN_CLIENT_ID="your_client_id"
export DHAN_ACCESS_TOKEN="your_access_token"
streamlit run app.py
```

**Windows (PowerShell):**
```powershell
$env:DHAN_CLIENT_ID="your_client_id"
$env:DHAN_ACCESS_TOKEN="your_access_token"
streamlit run app.py
```

This opens the app at `http://localhost:8501` — open this URL on your
second phone's browser (both phones need to be on the same Wi-Fi network
as the computer running this command, OR you deploy it to the cloud as
in step 3 so it's reachable from anywhere).

---

## 3. Deploy to Streamlit Community Cloud (so it works from your phone anywhere)

1. Create a **private** GitHub repository and push this folder to it.
   ```bash
   git init
   git add .
   git commit -m "Initial hedge order app"
   git remote add origin <your-private-repo-url>
   git push -u origin main
   ```
   **Use a private repo** — even though credentials aren't in the code,
   there's no reason to make the strategy logic public.

2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with
   GitHub, and click **New app**. Point it at your repo and `app.py`.

3. Before deploying, click **Advanced settings → Secrets** and paste:
   ```toml
   DHAN_CLIENT_ID = "your_client_id"
   DHAN_ACCESS_TOKEN = "your_access_token"
   ```
   Streamlit Cloud exposes these as environment variables automatically —
   `dhan_client.py` already reads them via `os.environ`, so no code change
   needed.

4. Deploy. You'll get a URL like `https://yourapp.streamlit.app` — open
   that on your second phone's browser. Since your access token expires
   daily, you'll need to update the secret value each morning via the
   Streamlit Cloud dashboard (Settings → Secrets → edit → Save → app
   restarts automatically).

---

## 4. Verify your index security IDs

`config.py` has Nifty 50 and Sensex security IDs filled in based on Dhan's
published documentation, but **Dhan does revise these occasionally**.
Before relying on this, cross-check by downloading their instrument list:

```bash
curl https://api.dhan.co/v2/instrument/IDX_I -o instruments.csv
```

Open the CSV and confirm the `SECURITY_ID` for "NIFTY 50" and "SENSEX"
match what's in `config.py`. If they don't, update `config.py` accordingly.

---

## Optional: add a confirmation step

If you want a safety net before each click actually fires, wrap the order
logic in `app.py` with a two-click pattern using `st.session_state`:

```python
if buy_clicked:
    st.session_state["pending"] = "BUY"

if st.session_state.get("pending"):
    st.warning(f"Confirm {st.session_state['pending']} order?")
    if st.button("Yes, place it"):
        direction = st.session_state.pop("pending")
        # ... run_hedged_trade(...) as before
```

This is left out of the default app since you described wanting fast,
single-click execution — but it's a cheap addition if you want a guard
rail back in.

---

## Known limitations

- **No live price feed.** You manually enter the spot price from your
  charting phone. If you want this automated too, Dhan's Live Market Feed
  (websocket) can stream LTP — that's a separate, larger piece of work.
- **Token expiry.** Dhan access tokens last 24 hours by default. For a
  "set and forget" version, you'd want TOTP-based auto-renewal — ask if
  you want this added.
- **No automatic square-off.** This app only opens positions. Closing
  them (or end-of-day square-off) isn't built — flag if you want that
  added as a third button.
