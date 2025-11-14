# Automation: Naukri Resume Upload (macOS)

[![CI](https://github.com/MudassarHakim/Automation_Naukri_Resume_Upload/actions/workflows/ci.yml/badge.svg)](https://github.com/MudassarHakim/Automation_Naukri_Resume_Upload/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/MudassarHakim/Automation_Naukri_Resume_Upload?display_name=tag&sort=semver)](https://github.com/MudassarHakim/Automation_Naukri_Resume_Upload/releases)

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
```
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

2) Store password in Keychain (recommended)
```
read -s -p "Naukri password: " NAUKRI_PASSWORD; echo
security add-generic-password -U \
  -a "mudassar.hakim.jobs@gmail.com" \
  -s com.mudassar.naukri.password \
  -w "$NAUKRI_PASSWORD"
unset NAUKRI_PASSWORD
```

3) Save session (one-time)
```
python scripts/naukri_resume_uploader.py --setup-auto --storage storage_state.json
```

4) Test a run
```
python scripts/naukri_resume_uploader.py \
  --headed \
  --storage storage_state.json \
  --resume-path "$HOME/naukri_job/resume" \
  --email-to "mudassar.hakim.jobs@gmail.com" \
  --email-on-success
```

## Scheduling (launchd)
1) Copy plist to LaunchAgents and load
```
cp launchd/com.mudassar.naukri.resume.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/com.mudassar.naukri.resume.plist 2>/dev/null || true
launchctl load -w ~/Library/LaunchAgents/com.mudassar.naukri.resume.plist
```
- Runs daily at 10:30 (system timezone)
- Passes --headed, --email-to, and --email-on-success

## Usage
```
python scripts/naukri_resume_uploader.py [--setup | --setup-auto] \
  [--resume-path PATH_OR_DIR] [--storage storage_state.json] [--headed] \
  [--username EMAIL] [--password-env NAUKRI_PASSWORD] \
  [--password-keychain-service com.mudassar.naukri.password] \
  [--email-to you@example.com] [--email-on-success] [--no-email-on-failure]
```

## Security
- Do not commit storage_state.json or credentials.
- Prefer Keychain over env vars.

## CI
A GitHub Action is included at `.github/workflows/ci.yml` to run linting and a basic syntax check on pushes/PRs to `main`.
