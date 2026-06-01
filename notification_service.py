import os
import requests
import asyncio
from dotenv import load_dotenv

# Loading environment variables from file
load_dotenv()

def execute_emergency_stop():
    url = os.getenv("PRINTER_API_URL")
    api_key = os.getenv("PRINTER_API_KEY")
    
    if not url or not api_key:
        return False, "Printer credentials missing in .env"

    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    payload = {"command": "cancel"}
    
    try:
        response = requests.post(f"{url}/api/job", headers=headers, json=payload)
        response.raise_for_status()
        return True, "Printer stopped successfully!"
    except Exception as e:
        print(f"Error stopping printer: {e}")
        return False, "Failed to communicate with printer."
    
def send_telegram_alert(defect_type, confidence):
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    if not TOKEN or not CHAT_ID: return
        
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    text = f"⚠️ *Aegis Alert!*\nDefect: {defect_type}\nConfidence: {confidence*100:.1f}%\nStatus: Requires Attention."
    keyboard = {"inline_keyboard": [[{"text": "🛑 EMERGENCY STOP", "callback_data": "stop_printer"}]]}
    
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown", "reply_markup": keyboard})
    except Exception as e:
        print(f"Telegram error: {e}")

async def telegram_bot_listener():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN: return

    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    offset = None

    while True:
        try:
            params = {"timeout": 30, "offset": offset}
            # Request updates from Telegram without crashing the server 
            response = await asyncio.to_thread(requests.get, url, params=params, timeout=35)
            data = response.json()

            if data.get("ok"):
                for update in data["result"]:
                    # Update the offset so we don't get the same click twice
                    offset = update["update_id"] + 1

                    # someone clicked a button in a message
                    if "callback_query" in update:
                        callback = update["callback_query"]
                        
                        if callback["data"] == "stop_printer":
                            print("[Telegram] Received Emergency Stop command!")
                            
                            # 1. Stop the printer 
                            success, msg = execute_emergency_stop()
                            
                            # 2. Send a pop-up on Telegram confirming that the click was received
                            answer_url = f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery"
                            requests.post(answer_url, json={
                                "callback_query_id": callback["id"], 
                                "text": "🛑 Printer Halted Successfully!" if success else "❌ Error stopping printer.",
                                "show_alert": True
                            })
                            
                            # 3. Update the message so that the button disappears (so that it is not clicked twice)
                            edit_url = f"https://api.telegram.org/bot{TOKEN}/editMessageText"
                            requests.post(edit_url, json={
                                "chat_id": callback["message"]["chat"]["id"],
                                "message_id": callback["message"]["message_id"],
                                "text": callback["message"]["text"] + "\n\n⛔ *ACTION TAKEN: PRINTER HALTED BY USER*",
                                "parse_mode": "Markdown"
                            })

        except Exception as e:
            print(f"[Telegram] Listener error: {e}")

        await asyncio.sleep(1)
