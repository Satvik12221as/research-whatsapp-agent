#check
import importlib.util
import os
from pathlib import Path

from daily_agent import load_env_file
from fetcher import DB_PATH


PROJECT_DIR = Path(__file__).resolve().parent


def check_dependency(name):
    return importlib.util.find_spec(name) is not None


def masked(value):
    if not value:
        return "missing"
    if len(value) <= 8:
        return "set"
    return f"{value[:4]}...{value[-4:]}"


def main():
    load_env_file()

    print("Personal News Agent setup check")
    print(f"Project: {PROJECT_DIR}")
    print(f"Database: {DB_PATH}")
    print()

    print("Dependencies")
    for package in ("feedparser", "requests"):
        status = "OK" if check_dependency(package) else "MISSING"
        print(f"- {package}: {status}")

    print()
    print("Secrets")
    for key in ("ANTHROPIC_API_KEY", "WHATSAPP_PHONE", "CALLMEBOT_APIKEY"):
        print(f"- {key}: {masked(os.environ.get(key))}")

    missing_secrets = [
        key
        for key in ("ANTHROPIC_API_KEY", "WHATSAPP_PHONE", "CALLMEBOT_APIKEY")
        if not os.environ.get(key)
    ]
    missing_deps = [
        package for package in ("feedparser", "requests") if not check_dependency(package)
    ]

    print()
    if missing_secrets or missing_deps:
        print("Status: NOT READY")
        if missing_deps:
            print("Install dependencies with: pip install -r requirements.txt")
        if missing_secrets:
            print("Add missing secrets to .env or the cloud automation environment.")
        return 1

    print("Status: READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
