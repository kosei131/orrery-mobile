# ORRERY FX — Windows offline verification

1. Download `VERIFY_MT5_WINDOWS.cmd` and inspect it before running.
2. Run it on Windows with Python (`py`), curl.exe and PowerShell available.
3. It creates a new temporary folder, downloads four public Python source files from the immutable revision named in the script, and checks their SHA-256 hashes before executing anything. Existing source files beside the launcher are not overwritten. Network failure or hash mismatch stops execution.
4. It compiles the sources and runs 13 offline tests. Only after success does it start the **SIMULATED TEST DATA** dashboard.
5. Open the complete private localhost URL on the same PC. Do not save it in logs, screenshots or GitHub. Stop with Ctrl+C.

This launcher never connects to MT5, installs the MT5 package, sends orders, or uploads account data. Temporary source files remain in the newly created folder for inspection. Updating source requires reviewing and updating both the pinned revision and hashes. Hash checks establish consistency with this launcher; inspect and trust the launcher itself first.

The offline tests cover HTTP authentication, hostile Host/Origin headers, malformed tokens, account masking, DEMO-only gates, cleanup after failures, and absence of trading API calls. Fake MT5 objects cannot verify a real terminal connection. Actual Windows MT5 DEMO integration and browser UI operation require separate device verification. No iPhone synchronization is implemented.

## Non-interactive Windows verification

Run `VERIFY_MT5_WINDOWS.cmd --verify-only` to download and verify pinned sources and execute offline tests without starting the interactive dashboard or printing its private URL. Failures return a nonzero exit code without pausing. The normal double-click behavior is unchanged.

Windows Actions additionally executes the real CMD launcher in this mode, verifies that neighboring files remain untouched, and checks that a deliberately incorrect source hash prevents Python execution. This tests Windows launcher behavior, not an installed MT5 terminal or the graphical browser.
