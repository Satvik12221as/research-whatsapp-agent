import os
import time
import urllib.parse

import requests


# Get your CallMeBot API key from the currently active WhatsApp setup page:
#   https://www.callmebot.com/?ae_global_templates=setup-whatsapp
# Send this exact WhatsApp message to the listed bot number:
#   I allow callmebot to send me messages
# If no API key arrives in 2 minutes, CallMeBot says to try again after 24 hours.


def load_env_file(path=".env"):
    if not os.path.exists(path):
        return

    with open(path, encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()
PHONE_NUMBER = os.environ.get("WHATSAPP_PHONE", "+91XXXXXXXXXX")
CALLMEBOT_APIKEY = os.environ.get("CALLMEBOT_APIKEY", "YOUR_CALLMEBOT_KEY")


def send_whatsapp(message: str) -> bool:
    """Send a WhatsApp message via CallMeBot."""
    chunks = split_message(message, max_len=1500)

    success = True
    for i, chunk in enumerate(chunks):
        encoded = urllib.parse.quote(chunk)
        url = (
            "https://api.callmebot.com/whatsapp.php"
            f"?phone={PHONE_NUMBER}&text={encoded}&apikey={CALLMEBOT_APIKEY}"
        )

        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                print(f"  Part {i + 1}/{len(chunks)} sent successfully")
            else:
                print(f"  Part {i + 1} failed: {response.status_code} - {response.text}")
                success = False
        except Exception as exc:
            print(f"  Error sending part {i + 1}: {exc}")
            success = False

        if i < len(chunks) - 1:
            time.sleep(3)

    return success


def split_message(message: str, max_len: int = 1500) -> list:
    """Split long messages into chunks at newline boundaries."""
    if len(message) <= max_len:
        return [message]

    chunks = []
    current = ""
    for line in message.split("\n"):
        if len(current) + len(line) + 1 > max_len:
            chunks.append(current.strip())
            current = line + "\n"
        else:
            current += line + "\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks


if __name__ == "__main__":
    test_msg = "Test from your news agent. If you see this, WhatsApp delivery is working."
    print(f"Sending test message to {PHONE_NUMBER}...")
    send_whatsapp(test_msg)
