# ORRERY FX v5 — Windows MT5 read-only diagnostic

This is a **local-only demonstration script**, not a cloud bridge or live syncing. **No orders are sent**, and the script checks that the active account is a DEMO account before returning account figures.

## Windows setup

1. Install Python for Windows, then open the Windows MetaTrader 5 desktop terminal and sign in to your **MetaQuotes-Demo** account.
2. In PowerShell run `py -m pip install MetaTrader5`.
3. Download `mt5_readonly.py` to your Windows PC and run `py mt5_readonly.py` from the same directory.
4. The terminal displays account balance, equity, free margin, positions and a count of deals from the past seven days. It does **not** write a file or send this information online.

**Privacy:** Do not paste account credentials, full financial output, or screenshots exposing identifying information into chat. The diagnostic prints only the last four digits of the account ID, but broker/account details and positions are still sensitive.

**Constraints:** Requires Windows PC with a compatible MetaTrader 5 terminal and Python package. The existing iPhone site does not automatically sync. The next stage will require authenticated, private transport to a server and an explicit security review; never publish account snapshots in GitHub Pages.

Docs: https://www.mql5.com/en/docs/python_metatrader5
