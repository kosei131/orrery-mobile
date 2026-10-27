# ORRERY FX — Windows v11 verification
Run the offline tests before attempting a broker or iPhone connection.

Download **all three** files from the GitHub repository into the **same Windows folder**:
- `VERIFY_MT5_WINDOWS.cmd`
- `mt5_local_dashboard.py`
- `test_mt5_local_dashboard.py`

Double-click `VERIFY_MT5_WINDOWS.cmd`. The command window checks Python, runs four or more offline tests, and **only if all pass** starts the simulated local dashboard. It will print a private URL of the form `http://127.0.0.1:8765/#...`. Open that complete URL in the browser on the **same Windows PC**. Never share the URL.

The test uses **SIMULATED TEST DATA**. There is no connection to any MT5 account. If it fails, copy only the error summary (remove usernames, paths and identifying details). The Python `MetaTrader5` package is only required for a later genuine demo-account test. No order sending, no remote synchronization, no automatic execution and no brokerage credentials are part of this launcher.

Important: a GitHub commit does not prove the program has run successfully. Verify the Windows test result separately.

If Windows SmartScreen cautions about a script downloaded from the Internet, inspect the text of the CMD file and run only if you trust its content.