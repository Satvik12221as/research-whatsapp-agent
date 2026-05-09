import argparse
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from fetcher import fetch_all, search_global


PROJECT_DIR = Path(__file__).resolve().parent
LOG_DIR = PROJECT_DIR / "logs"
DEFAULT_SEND_TIME = "23:00"


def load_env_file(path=PROJECT_DIR / ".env"):
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def log(message):
    LOG_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line, flush=True)
    log_path = LOG_DIR / f"daily-agent-{datetime.now().strftime('%Y-%m-%d')}.log"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def parse_time_today(value):
    hour, minute = [int(part) for part in value.split(":", 1)]
    now = datetime.now()
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def wait_until(target):
    while True:
        remaining = (target - datetime.now()).total_seconds()
        if remaining <= 0:
            return
        sleep_for = min(remaining, 60)
        time.sleep(sleep_for)


def validate_delivery_config():
    missing = [
        name
        for name in ("GROQ_API_KEY", "WHATSAPP_PHONE", "CALLMEBOT_APIKEY")
        if not os.environ.get(name)
        or os.environ.get(name) in {"YOUR_API_KEY_HERE", "+91XXXXXXXXXX", "YOUR_CALLMEBOT_KEY"}
    ]
    if missing:
        raise RuntimeError(
            "Missing configuration: "
            + ", ".join(missing)
            + ". Add these values to .env or system environment variables."
        )


def run_research(args):
    log("Research phase started.")
    rss_count = fetch_all(max_per_feed=args.max_per_feed, pause_seconds=args.pause)
    log(f"Curated RSS fetch complete: {rss_count} new articles.")

    search_count = search_global(
        hours=args.hours,
        max_records=args.max_records,
        pause_seconds=args.pause,
    )
    log(f"Global search discovery complete: {search_count} new articles.")
    log("Research phase complete.")


def send_digest(dry_run=False):
    from sender import send_whatsapp
    from summarizer import build_digest, format_whatsapp_message

    log("Digest build started.")
    digest = build_digest()
    if not digest:
        log("No digest was built. WhatsApp send skipped.")
        return False

    message = format_whatsapp_message(digest)
    if dry_run:
        preview_path = LOG_DIR / f"digest-preview-{datetime.now().strftime('%Y-%m-%d-%H%M')}.txt"
        preview_path.write_text(message, encoding="utf-8")
        log(f"Dry run enabled. Digest preview written to {preview_path}.")
        return True

    validate_delivery_config()
    log("Sending digest to WhatsApp.")
    success = send_whatsapp(message)
    log("WhatsApp send complete." if success else "WhatsApp send failed.")
    return success


def run_daily(args):
    load_env_file()
    log("Daily agent started.")
    run_research(args)

    send_time = parse_time_today(args.send_time)
    if args.wait_for_send and datetime.now() < send_time:
        log(f"Waiting until {args.send_time} to send WhatsApp digest.")
        wait_until(send_time)
    elif args.wait_for_send:
        log(f"Send time {args.send_time} has already passed. Sending now.")

    success = send_digest(dry_run=args.dry_run)
    log("Daily agent finished successfully." if success else "Daily agent finished with issues.")
    return 0 if success else 1


def build_parser():
    parser = argparse.ArgumentParser(
        description="Daily agent runner: research at 10 PM, send WhatsApp digest at 11 PM."
    )
    parser.add_argument("--send-time", default=DEFAULT_SEND_TIME, help="HH:MM local send time.")
    parser.add_argument("--no-wait", dest="wait_for_send", action="store_false")
    parser.add_argument("--dry-run", action="store_true", help="Build a preview but do not send WhatsApp.")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--max-per-feed", type=int, default=10)
    parser.add_argument("--max-records", type=int, default=20)
    parser.add_argument("--pause", type=float, default=0.5)
    parser.set_defaults(wait_for_send=True)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        return run_daily(args)
    except Exception as exc:
        log(f"Fatal error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
