import os
import requests
import time
import re
from dotenv import load_dotenv

load_dotenv()

# --- Core Logic (For Scripts) ---

def clean_html_for_telegram(text: str) -> str:
    """
    Telegram only supports a subset of HTML tags: b, strong, i, em, code, s, strike, del, u, pre, a.
    This function removes or replaces unsupported tags.
    """
    # Replace common block elements with newlines or bold
    text = re.sub(r'<(h1|h2|h3|h4|h5|h6)[^>]*>', '<b>', text, flags=re.IGNORECASE)
    text = re.sub(r'</(h1|h2|h3|h4|h5|h6)>', '</b>\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<(p|div|span)[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</(p|div|span)>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<hr\s*/?>', '\n---\n', text, flags=re.IGNORECASE)
    
    # List of supported tags
    supported_tags = ['b', 'strong', 'i', 'em', 'code', 's', 'strike', 'del', 'u', 'pre', 'a']
    
    # Remove all other tags but keep content
    # This regex matches any tag. We use a function to filter out supported tags.
    def tag_fixer(match):
        full_tag = match.group(0)
        tag_name = match.group(1).lower()
        if tag_name in supported_tags:
            return full_tag
        return ""

    # Match opening or closing tags: <tag ...> or </tag>
    text = re.sub(r'</?([a-zA-Z1-6]+)[^>]*>', tag_fixer, text)
    
    # Final cleanup of multiple newlines
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    return text.strip()

def send_telegram_core(text: str, token: str = None, chat_id: str = None) -> bool:
    """
    发送消息的核心逻辑。返回布尔值表示成功与否。
    """
    token = token or os.getenv("TG_TOKEN")
    chat_id = chat_id or os.getenv("CHAT_ID")
    
    if not token or not chat_id:
        print("Error: TG_TOKEN or CHAT_ID not found.")
        return False

    # Clean the HTML content for Telegram
    cleaned_text = clean_html_for_telegram(text)

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": cleaned_text,
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
