# Fresh Mac setup guide (Naukri Resume Uploader)

This document lists all steps to restore the automation on a new or formatted Mac.

0) Prepare
- Sign in to OneDrive and confirm your resume folder exists:
  /Users/Mudassar.Hakim/Library/CloudStorage/OneDrive-EY/Documents/resume
- Open the Mail app and add your account (needed for email notifications).

1) Install tooling
```bash
# Command Line Tools (compiler, git)
xcode-select --install

# Optional but recommended: Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Python 3 and Git (if needed)
brew install python git
```

2) Clone the repository
```bash
git clone https://github.com/MudassarHakim/Automation_Naukri_Resume_Upload.git
cd Automation_Naukri_Resume_Upload
```

3) Create a virtualenv and install dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

4) Store the Naukri password securely in Keychain
```bash
read -s -p 'Naukri password: ' NAUKRI_PASSWORD; echo
security add-generic-password -U \
  -a "mudassar.hakim.jobs@gmail.com" \
  -s com.mudassar.naukri.password \
  -w "$NAUKRI_PASSWORD"
unset NAUKRI_PASSWORD
```

5) Prime the login session (one-time; complete any OTP in the opened browser)
```bash
python scripts/naukri_resume_uploader.py --setup-auto --storage storage_state.json
```

6) Test a manual run with notifications and email
```bash
python scripts/naukri_resume_uploader.py \
  --headed \
  --storage storage_state.json \
  --resume-path "/Users/Mudassar.Hakim/Library/CloudStorage/OneDrive-EY/Documents/resume" \
  --email-to "mudassar.hakim.jobs@gmail.com" \
  --email-on-success
```

7) Install the daily scheduled job (launchd)
Create a LaunchAgent that uses your repo’s venv and script:
```bash
REPO="$HOME/Automation_Naukri_Resume_Upload"
PY="$REPO/.venv/bin/python"
PLIST="$HOME/Library/LaunchAgents/com.mudassar.naukri.resume.plist"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.mudassar.naukri.resume</string>

  <key>ProgramArguments</key>
  <array>
    <string>${PY}</string>
    <string>${REPO}/scripts/naukri_resume_uploader.py</string>
    <string>--storage</string>
    <string>${REPO}/storage_state.json</string>
    <string>--resume-path</string>
    <string>/Users/Mudassar.Hakim/Library/CloudStorage/OneDrive-EY/Documents/resume</string>
    <string>--username</string>
    <string>mudassar.hakim.jobs@gmail.com</string>
    <string>--headed</string>
    <string>--email-to</string>
    <string>mudassar.hakim.jobs@gmail.com</string>
    <string>--email-on-success</string>
  </array>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>10</integer>
    <key>Minute</key><integer>30</integer>
  </dict>

  <key>StandardOutPath</key>
  <string>${REPO}/job.out.log</string>
  <key>StandardErrorPath</key>
  <string>${REPO}/job.err.log</string>
</dict>
</plist>
PLIST

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load -w "$PLIST"
```

8) Verify scheduling and logs
```bash
launchctl list | grep com.mudassar.naukri.resume
tail -n 200 ~/Automation_Naukri_Resume_Upload/job.out.log ~/Automation_Naukri_Resume_Upload/job.err.log
```

9) Day-to-day
- Nothing to do; it runs at 10:30 and sends both a macOS popup and an email.
- To refresh session if OTP is requested again:
```bash
cd ~/Automation_Naukri_Resume_Upload
source .venv/bin/activate
python scripts/naukri_resume_uploader.py --setup-auto --storage storage_state.json
```

10) Troubleshooting quick checks
- Resume folder path exists and contains a recent .pdf/.doc/.docx/.rtf.
- Keychain entry exists:
```bash
security find-generic-password -s com.mudassar.naukri.password -a "mudassar.hakim.jobs@gmail.com" -w >/dev/null && echo "OK" || echo "Missing"
```
- Manual headed run to observe any page changes:
```bash
python scripts/naukri_resume_uploader.py --headed --storage storage_state.json --email-to "mudassar.hakim.jobs@gmail.com" --email-on-success
```
