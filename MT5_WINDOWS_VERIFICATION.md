# ORRERY FX — Windows verification (v12)

## One-file verification
1. On Windows, download `VERIFY_MT5_WINDOWS.cmd` from this repository.
2. Inspect the CMD script before running it. It downloads two **public Python source files** from `https://raw.githubusercontent.com/kosei131/orrery-mobile/main/` into the CMD file's folder. Those Python files do not need to be downloaded separately.
3. Double-click the CMD file on the Windows PC. It checks Python, downloads current scripts, compiles them, and runs simulated-data security tests.
4. If **all tests pass**, a private URL appears: `http://127.0.0.1:8765/#<temporary-token>`. Open this complete URL **on the same Windows PC** to see the TEST DATA dashboard.
5. Stop the dashboard with Ctrl+C.

**Important:** This does not touch MetaTrader 5 or connect an actual account. It has **no order execution**, broker credentials or cloud upload. The launch script executes code downloaded from the current public repository branch, so use it only if you trust the repository. Windows network access to raw.githubusercontent.com is required. No iPhone auto-sync is implemented.

If an offline test fails, do not proceed to actual MT5. Inspect the error lines (redact any local username before sharing). This document does not claim Windows real-device tests have passed.
