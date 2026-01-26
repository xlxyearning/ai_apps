import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()

# --- Core Logic (For Scripts) ---

def send_telegram_core(text: str, token: str = None, chat_id: str = None) -> bool:
    """
    发送消息的核心逻辑。返回布尔值表示成功与否。
    """
    token = token or os.getenv("TG_TOKEN")
    chat_id = chat_id or os.getenv("CHAT_ID")
    
    if not token or not chat_id:
        print("Error: TG_TOKEN or CHAT_ID not found.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return True
        else:
            print(f"Telegram Send Failed: {response.text}")
            return False
    except Exception as e:
        print(f"Telegram Error: {e}")
        return False
    finally:
        time.sleep(1)

# --- MCP Interface (For LLM Agent) ---

def send_telegram_tool(message: str) -> str:
    """
    发送消息到用户的 Telegram。
    
    Args:
        message: 消息内容（支持 HTML）。
    """
    success = send_telegram_core(message)
    if success:
        return "消息已成功发送到 Telegram。"
    else:
        return "发送失败，请检查服务器日志或网络连接。"
