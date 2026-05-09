import requests
import urllib.parse
import os

# ─── CONFIG ───────────────────────────────────────────────────────────────────
# Get your CallMeBot API key by sending this WhatsApp message to +34 644 59 78 79:
#   "I allow callmebot to send me messages"
# You'll receive your apikey in reply within 2 minutes.

PHONE_NUMBER = os.environ.get("WHATSAPP_PHONE", "+91XXXXXXXXXX")  # with country code
CALLMEBOT_APIKEY = os.environ.get("CALLMEBOT_APIKEY", "YOUR_CALLMEBOT_KEY")

def send_whatsapp(message: str) -> bool:
    """Send a WhatsApp message via CallMeBot (free, personal use)."""
    
    # CallMeBot has a 1600 char limit per message — split if needed
    chunks = split_message(message, max_len=1500)
    
    success = True
    for i, chunk in enumerate(chunks):
        encoded = urllib.parse.quote(chunk)
        url = f"https://api.callmebot.com/whatsapp.php?phone={PHONE_NUMBER}&text={encoded}&apikey={CALLMEBOT_APIKEY}"
        
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                print(f"  ✅ Part {i+1}/{len(chunks)} sent successfully")
            else:
                print(f"  ❌ Part {i+1} failed: {response.status_code} — {response.text}")
                success = False
        except Exception as e:
            print(f"  ❌ Error sending part {i+1}: {e}")
            success = False
        
        # Small delay between chunks
        if i < len(chunks) - 1:
            import time
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
    # Test with a simple message
    test_msg = "🤖 Test from your news agent! If you see this, WhatsApp delivery is working perfectly."
    print(f"Sending test message to {PHONE_NUMBER}...")
    send_whatsapp(test_msg)
