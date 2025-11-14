#!/usr/bin/env python3
import argparse
import os
import pathlib
import re
import subprocess
import sys
import time
from datetime import datetime
from typing import Optional

from playwright.sync_api import Playwright, sync_playwright, TimeoutError as PWTimeoutError

PROFILE_URL = "https://www.naukri.com/mnjuser/profile?id=&altresid"


def info(msg: str) -> None:
    print(f"[INFO] {msg}")


def warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def err(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)


def mac_notify(title: str, message: str) -> None:
    """Best-effort macOS user notification via AppleScript."""
    try:
        safe_title = title.replace('"', '\\"')
        safe_msg = message.replace('"', '\\"')
        subprocess.run([
            "osascript", "-e",
            f'display notification "{safe_msg}" with title "{safe_title}"'
        ], check=False, capture_output=True)
    except Exception:
        pass


def email_notify(to_address: str, subject: str, body: str) -> None:
    try:
        def esc(s: str) -> str:
            return s.replace("\\", "\\\\").replace("\"", r"\"")
        lines = [
            'tell application "Mail"',
            f'set newMessage to make new outgoing message with properties {{subject:"{esc(subject)}", content:"{esc(body)}\n", visible:false}}',
            f'tell newMessage to make new to recipient at end of to recipients with properties {{address:"{esc(to_address)}"}}',
            'send newMessage',
            'end tell'
        ]
        args = []
        for l in lines:
            args += ["-e", l]
        subprocess.run(["osascript", *args], check=False, capture_output=True)
    except Exception:
        pass


def setup_session(playwright: Playwright, storage_path: pathlib.Path) -> None:
    info("Launching Chromium in headed mode for initial login…")
    browser = playwright.chromium.launch(headless=False, slow_mo=200)
    context = browser.new_context()
    page = context.new_page()

    page.goto(PROFILE_URL, wait_until="load")
    info("Please complete login/OTP in the browser window.")
    input("Press Enter here after the page shows your profile…")

    # Save cookies/localStorage for future runs
    context.storage_state(path=str(storage_path))
    info(f"Saved session to {storage_path}")

    context.close()
    browser.close()


def setup_session_auto(playwright: Playwright, storage_path: pathlib.Path, timeout_sec: int = 600) -> int:
    info("Opening browser for login (auto-detect mode)…")
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto(PROFILE_URL, wait_until="load")
    info("In the browser, log in and complete OTP/CAPTCHA. I will save the session once your profile loads.")

    deadline = time.time() + timeout_sec
    success = False
    while time.time() < deadline:
        try:
            page.wait_for_load_state("networkidle", timeout=2000)
        except Exception:
            pass
        try:
            page.get_by_role("button", name=re.compile("update resume", re.I)).wait_for(timeout=2000)
            success = True
            break
        except Exception:
            pass
        time.sleep(1)

    if success:
        context.storage_state(path=str(storage_path))
        info(f"Saved session to {storage_path}")
        rc = 0
    else:
        err("Timed out waiting for profile page. Session not saved.")
        rc = 1

    context.close(); browser.close()
    return rc


def with_context(playwright: Playwright, storage_path: pathlib.Path, headless: bool = True, stealth_headed: bool = False, engine: str = "chromium"):
    # Launch with flags that reduce headless detection
    if engine == "chromium":
        browser = playwright.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
    elif engine == "webkit":
        browser = playwright.webkit.launch(headless=headless)
    elif engine == "firefox":
        browser = playwright.firefox.launch(headless=headless)
    else:
        browser = playwright.chromium.launch(headless=headless)

    context = browser.new_context(
        storage_state=str(storage_path) if storage_path.exists() else None,
        viewport={"width": 1366, "height": 850},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/118.0.0.0 Safari/537.36"
        ),
        locale="en-US",
    )
    try:
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
    except Exception:
        pass

    # If running in background mode (headed but hidden), try to hide the Chromium window
    if stealth_headed and not headless:
        try:
            for proc in ("Chromium", "Google Chrome"):
                subprocess.run([
                    "osascript", "-e",
                    f'tell application "System Events" to set visible of process "{proc}" to false'
                ], check=False, capture_output=True)
        except Exception:
            pass

    return browser, context


def get_keychain_secret(service: str, account: Optional[str] = None) -> Optional[str]:
    try:
        cmd = ["security", "find-generic-password"]
        if account:
            cmd += ["-a", account]
        cmd += ["-s", service, "-w"]
        out = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        return out.stdout.strip()
    except Exception:
        return None


def attempt_login(page, username: str, password: str) -> bool:
    # Navigate to login page explicitly to avoid dynamic redirects
    page.goto("https://www.naukri.com/nlogin/login", wait_until="load")

    # Fill email
    email_selectors = [
        'input[name="email"]',
        'input[name="emailId"]',
        'input#eLoginNew',
        'input[placeholder*="Email"]',
        'input[placeholder*="Username"]',
        'input[type="text"]'
    ]
    filled = False
    for sel in email_selectors:
        loc = page.locator(sel)
        if loc.count() > 0:
            try:
                loc.first.fill(username)
                filled = True
                break
            except Exception:
                pass
    if not filled:
        return False

    # Fill password
    pwd_selectors = [
        'input[name="password"]',
        'input#pwd1',
        'input[type="password"]'
    ]
    pfilled = False
    for sel in pwd_selectors:
        loc = page.locator(sel)
        if loc.count() > 0:
            try:
                loc.first.fill(password)
                pfilled = True
                break
            except Exception:
                pass
    if not pfilled:
        return False

    # Click login
    try:
        page.get_by_role("button", name=re.compile("login|submit", re.I)).click(timeout=5000)
    except Exception:
        try:
            page.locator('button:has-text("Login")').first.click(timeout=5000)
        except Exception:
            # Try pressing Enter in password field
            try:
                page.keyboard.press("Enter")
            except Exception:
                return False

    # Wait for either profile or OTP
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass

    content = ""
    try:
        content = page.content()
    except Exception:
        pass

    if re.search(r"OTP", content, re.I) or re.search(r"one[- ]time password", content, re.I):
        # OTP required; cannot proceed non-interactively
        return False

    # Heuristic: if we can see Update resume or profile avatar, consider logged-in
    try:
        page.goto(PROFILE_URL, wait_until="load", timeout=60000)
    except Exception:
        pass

    try:
        page.get_by_role("button", name=re.compile("update resume", re.I)).wait_for(timeout=5000)
        return True
    except Exception:
        # Fallback to checking if logout link or user menu is present
        try:
            if re.search(r"logout", page.content(), re.I):
                return True
        except Exception:
            pass
        return False


def try_set_file_via_input(page, file_path: str) -> bool:
    # Try common strategies to find the file input
    candidates = [
        'input[type="file"]',
        'input[type=file]'
    ]
    for sel in candidates:
        loc = page.locator(sel)
        try:
            if loc.count() > 0:
                loc.first.set_input_files(file_path)
                return True
        except PWTimeoutError:
            pass
        except Exception:
            pass
    return False


def resolve_resume_path(resume_path: pathlib.Path) -> Optional[pathlib.Path]:
    if resume_path.is_file():
        return resume_path
    if resume_path.is_dir():
        exts = {".pdf", ".doc", ".docx", ".rtf"}
        try:
            files = [p for p in resume_path.iterdir() if p.is_file() and p.suffix.lower() in exts]
        except PermissionError:
            # Propagate as None; caller will notify with context
            return None
        except Exception:
            return None
        if not files:
            return None
        # Pick the most recently modified
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files[0]
    return None


def upload_resume(playwright: Playwright, storage_path: pathlib.Path, resume_path: pathlib.Path, headed: bool = False, username: Optional[str] = None, password: Optional[str] = None, notify_email_to: Optional[str] = None, email_on_success: bool = False, email_on_failure: bool = True, background: bool = False, engine: str = "chromium") -> int:
    try:
        target = resolve_resume_path(resume_path)
    except Exception as e:
        target = None
    if not target:
        err(f"Resume not accessible/found at: {resume_path}")
        mac_notify("Naukri uploader failed", "Cannot access resume folder/file. Grant Full Disk Access or move resume outside protected folders.")
        if notify_email_to and email_on_failure:
            try:
                email_notify(notify_email_to, "Naukri resume upload: failed", f"Cannot access resume path: {resume_path}. Grant Full Disk Access to Python or choose a different folder.")
            except Exception:
                pass
        return 2

    browser, context = with_context(playwright, storage_path, headless=not headed, stealth_headed=background, engine=engine)
    page = context.new_page()

    info("Opening profile page…")
    page.goto(PROFILE_URL, wait_until="load", timeout=60000)

    # Try direct file input first (works even if input is hidden)
    info("Attempting to set the file on the hidden input…")
    tried_upload = False
    if try_set_file_via_input(page, str(target)):
        tried_upload = True
    else:
        info("Falling back to clicking the Update resume button and using file chooser…")
        try:
            with page.expect_file_chooser(timeout=10000) as fc_info:
                page.get_by_role("button", name=re.compile("update resume", re.I)).click()
            chooser = fc_info.value
            chooser.set_files(str(target))
            tried_upload = True
        except Exception:
            tried_upload = False

    # If we couldn't start an upload, we may not be logged in. Try credential login if available.
    if not tried_upload:
        if username and password:
            info("Could not find upload controls; attempting credential login…")
            if attempt_login(page, username, password):
                try:
                    context.storage_state(path=str(storage_path))
                except Exception:
                    pass
                # Re-open profile and try upload again
                info("Retrying upload after login…")
                try:
                    page.goto(PROFILE_URL, wait_until="load", timeout=60000)
                except Exception:
                    pass
                if try_set_file_via_input(page, str(target)):
                    tried_upload = True
                else:
                    try:
                        with page.expect_file_chooser(timeout=10000) as fc_info:
                            page.get_by_role("button", name=re.compile("update resume", re.I)).click()
                        chooser = fc_info.value
                        chooser.set_files(str(target))
                        tried_upload = True
                    except Exception:
                        tried_upload = False
        if not tried_upload:
            err("Could not access upload controls. You may need to re-run --setup or the site layout changed.")
            mac_notify("Naukri uploader failed", "Could not access upload controls. Try re-running setup.")
            if notify_email_to and email_on_failure:
                try:
                    email_notify(notify_email_to, "Naukri resume upload: failed", "Could not access upload controls. You may need to re-run setup.")
                except Exception:
                    pass
            context.close(); browser.close()
            return 3

    # Wait for upload completion indicators
    success = False
    indicators = [
        re.compile(r"uploaded\s+on", re.I),
        re.compile(r"resume uploaded successfully", re.I),
        re.compile(r"success", re.I),
    ]
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass

    # Scan page content heuristically
    try:
        content = page.content()
        for rx in indicators:
            if rx.search(content):
                success = True
                break
    except Exception:
        pass

    if not success:
        # Try to find a toast or label dynamically for a few seconds
        for _ in range(10):
            try:
                content = page.content()
                if any(rx.search(content) for rx in indicators):
                    success = True
                    break
            except Exception:
                pass
            time.sleep(1)

    if success:
        info("Resume upload appears to have succeeded.")
        mac_notify("Naukri uploader succeeded", f"Resume uploaded at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        if notify_email_to and email_on_success:
            try:
                email_notify(notify_email_to, "Naukri resume upload: success", f"Upload completed successfully at {time.strftime('%Y-%m-%d %H:%M:%S')}.")
            except Exception:
                pass
        rc = 0
    else:
        warn("Could not confirm success from the page. Please verify manually.")
        mac_notify("Naukri uploader warning", "Upload not confirmed. Please verify on Naukri.")
        if notify_email_to and email_on_failure:
            try:
                email_notify(notify_email_to, "Naukri resume upload: warning", "Upload not confirmed. Please check your Naukri profile.")
            except Exception:
                pass
        rc = 1

    if not headed:
        context.close(); browser.close()
    return rc


def attempt_upload_with_engine(pw: Playwright, storage_path: pathlib.Path, resume_path: pathlib.Path, engine: str) -> int:
    # Run headless with given engine; returns rc like upload_resume
    browser, context = with_context(pw, storage_path, headless=True, stealth_headed=False, engine=engine)
    page = context.new_page()
    try:
        page.goto(PROFILE_URL, wait_until="load", timeout=60000)
        if not try_set_file_via_input(page, str(resume_path)):
            try:
                with page.expect_file_chooser(timeout=8000) as fc_info:
                    page.get_by_role("button", name=re.compile("update resume", re.I)).click()
                chooser = fc_info.value
                chooser.set_files(str(resume_path))
            except Exception:
                context.close(); browser.close(); return 3
        page.wait_for_load_state("networkidle", timeout=10000)
        content = page.content()
        if re.search(r"uploaded\s+on|success", content, re.I):
            context.close(); browser.close(); return 0
        # brief retry scan
        for _ in range(5):
            time.sleep(1)
            try:
                content = page.content()
                if re.search(r"uploaded\s+on|success", content, re.I):
                    context.close(); browser.close(); return 0
            except Exception:
                pass
        context.close(); browser.close(); return 1
    except Exception:
        try:
            context.close(); browser.close()
        except Exception:
            pass
        return 3


def main():
    parser = argparse.ArgumentParser(description="Naukri resume uploader")
    parser.add_argument("--setup", action="store_true", help="Run interactive login and save session state (press Enter to confirm)")
    parser.add_argument("--setup-auto", action="store_true", help="Open a browser and auto-detect login success (no terminal input)")
    parser.add_argument("--resume-path", default=str(pathlib.Path.home() / "naukri_job" / "resume"), help="Path to the resume file or folder (pdf/doc/docx/rtf). If a folder is provided, the most recently modified supported file is used.")
    parser.add_argument("--storage", default=str(pathlib.Path.home() / "naukri_job" / "storage_state.json"), help="Path to storage_state file")
    parser.add_argument("--headed", action="store_true", help="Run with a visible browser window")
    parser.add_argument("--background", action="store_true", help="Run headed but hide the Chromium window (best-effort)")
    parser.add_argument("--engine", choices=["auto", "chromium", "webkit", "firefox"], default="auto", help="Browser engine to use; auto tries webkit headless first, then chromium headless, then headed if background/headed is set")
    parser.add_argument("--username", default=os.environ.get("NAUKRI_USERNAME", "mudassar.hakim.jobs@gmail.com"), help="Login email (or set NAUKRI_USERNAME)")
    parser.add_argument("--password-env", default="NAUKRI_PASSWORD", help="Name of env var that holds the password (default: NAUKRI_PASSWORD)")
    parser.add_argument("--password-keychain-service", default="com.mudassar.naukri.password", help="macOS Keychain service name to read password from if env var is not set")
    parser.add_argument("--email-to", default=os.environ.get("NAUKRI_NOTIFY_TO", "mudassar.hakim.jobs@gmail.com"), help="Email address to notify (default: your username)")
    parser.add_argument("--email-on-success", action="store_true", help="Send email on success as well")
    parser.add_argument("--no-email-on-failure", action="store_true", help="Disable email on failure")

    args = parser.parse_args()
    storage_path = pathlib.Path(args.storage)
    resume_path = pathlib.Path(args.resume_path)

    # Resolve password: env var first, then Keychain service
    password = os.environ.get(args.password_env)
    if not password:
        password = get_keychain_secret(args.password_keychain_service, account=args.username)

    with sync_playwright() as pw:
        if args.setup:
            setup_session(pw, storage_path)
            return 0
        if args.setup_auto:
            return setup_session_auto(pw, storage_path)
        else:
            # Automatic engine selection to keep background truly headless
            if not args.headed and not args.background and args.engine == "auto":
                target = resolve_resume_path(pathlib.Path(args.resume_path))
                if not target:
                    err(f"Resume not accessible/found at: {args.resume_path}")
                    return 2
                # Try WebKit headless first, then Chromium headless
                with sync_playwright() as pw2:
                    rc = attempt_upload_with_engine(pw2, storage_path, target, engine="webkit")
                    if rc == 0:
                        mac_notify("Naukri uploader succeeded", "Headless WebKit upload done")
                        return 0
                    rc = attempt_upload_with_engine(pw2, storage_path, target, engine="chromium")
                    if rc == 0:
                        mac_notify("Naukri uploader succeeded", "Headless Chromium upload done")
                        return 0
                    mac_notify("Naukri uploader warning", "Headless engines failed; consider enabling --background")
                    return 1
            # Otherwise follow normal path
            return upload_resume(
                pw,
                storage_path,
                resume_path,
                headed=(args.headed or args.background),
                username=args.username,
                password=password,
                notify_email_to=args.email_to,
                email_on_success=args.email_on_success,
                email_on_failure=not args.no_email_on_failure,
                background=args.background,
                engine=("chromium" if args.engine == "auto" else args.engine),
            )


if __name__ == "__main__":
    raise SystemExit(main())
