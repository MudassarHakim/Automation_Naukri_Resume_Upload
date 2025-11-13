# Automation: Naukri Resume Upload (macOS)

Automates uploading your latest resume to your Naukri profile using Playwright.

- Language: Python 3 + Playwright (Chromium)
- OS: macOS
- Schedule: launchd (runs daily at 10:30)
- Notifications: macOS popup + Mail app email (success and failure)

## Features
- Uses macOS Keychain for password; no plaintext secrets.
- Saves a Playwright session to avoid repeated logins.
- Picks the most recent resume file from a folder by default.
- Sends success + failure emails and macOS notifications.

## Setup
1) Create a virtual environment and install dependencies
Requirement already satisfied: pip in ./.venv/lib/python3.9/site-packages (21.2.4)
Collecting pip
  Using cached pip-25.3-py3-none-any.whl (1.8 MB)
Installing collected packages: pip
  Attempting uninstall: pip
    Found existing installation: pip 21.2.4
    Uninstalling pip-21.2.4:
      Successfully uninstalled pip-21.2.4
Successfully installed pip-25.3
2) Store password in Keychain (recommended)

3) Save session (one-time)

4) Test a run

## Scheduling (launchd)
1) Copy plist to LaunchAgents and load

- Runs daily at 10:30 (system timezone)
- Passes --headed, --email-to, and --email-on-success

## Usage


## Security
- Do not commit storage_state.json or credentials.
- Prefer Keychain over env vars.
