import os
import requests
import time
import re
import html
from dotenv import load_dotenv

load_dotenv()

# --- Core Logic (For Scripts) ---

def clean_html_for_telegram(text: str) -> str:
    """
    更严格的 Telegram HTML 清洗 v3.0。
    - 检测并剥离完整的 HTML 文档结构。
    - 严格白名单过滤。
    - 确保标签正确闭合。
    """
    if not text:
        return ""
    
    # 0. 文档模式检测与剥离
    if "<!doctype" in text.lower() or "<html" in text.lower():
        body_match = re.search(r'<body[^>]*>(.*?)</body>', text, re.IGNORECASE | re.DOTALL)
        if body_match:
            text = body_match.group(1) # 只保留 body 内容
        else:
            return html.escape(text[:500]) # 如果没有 body，说明结构混乱，直接转义

    # 1. 预处理：将常见块标签转为换行或加粗
    text = re.sub(r'<(h1|h2|h3|h4|h5|h6)[^>]*>', '<b>', text, flags=re.IGNORECASE)
    text = re.sub(r'</(h1|h2|h3|h4|h5|h6)>', '</b>\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<(p|div)[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</(p|div)>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<hr\s*/?>', '\n---\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<li[^>]*>', '• ', text, flags=re.IGNORECASE)
    text = re.sub(r'</li>', '\n', text, flags=re.IGNORECASE)
    
    # 2. 白名单过滤 & 重构
    supported_tags = ['b', 'strong', 'i', 'em', 'code', 's', 'strike', 'del', 'u', 'pre', 'a']
    
    def process_tags(match):
        full_tag = match.group(0)
        is_closing = full_tag.startswith('</')
        tag_name_match = re.match(r'</?([a-zA-Z0-9]+)', full_tag)
        
        if not tag_name_match: return ""
        tag_name = tag_name_match.group(1).lower()
        if tag_name not in supported_tags: return ""
            
        if is_closing:
            return f"</{tag_name}>"
        else:
            if tag_name == 'a':
                href_match = re.search(r'href=["\']([^"\']+)["\']', full_tag, re.I)
                if href_match: return f'<a href="{html.escape(href_match.group(1))}">'
                return ""
            return f"<{tag_name}>"

    text = re.sub(r'</?[^>]+>', process_tags, text)
    
    # 3. 标签自动闭合检查
    tags_stack = []
    final_text = ""
    last_pos = 0
    # 正则需要匹配 <tag>, </tag>, <a href="...">
    tag_pattern = re.compile(r'(</?([a-z]+)[^>]*>)', re.IGNORECASE)
    
    for match in tag_pattern.finditer(text):
        final_text += text[last_pos:match.start()]
        tag_str = match.group(1)
        tag_name = match.group(2).lower()
        is_closing = tag_str.startswith('</')
        
        if not is_closing:
            tags_stack.append(tag_name)
            final_text += tag_str
        else:
            if tags_stack and tags_stack[-1] == tag_name:
                tags_stack.pop()
                final_text += tag_str
            else:
                # 忽略不匹配的闭合标签
                pass
                
        last_pos = match.end()
        
    final_text += text[last_pos:]
    while tags_stack:
        final_text += f"</{tags_stack.pop()}>"

    final_text = re.sub(r'\n\s*\n', '\n\n', final_text)
    return final_text.strip()

def send_telegram_core(text: str, token: str = None, chat_id: str = None) -> bool:
    """
    发送消息的核心逻辑。
    """
    token = token or os.getenv("TG_TOKEN")
    chat_id = chat_id or os.getenv("CHAT_ID")
    
    if not token or not chat_id:
        print("Error: TG_TOKEN or CHAT_ID not found.")
        return False

    cleaned_text = clean_html_for_telegram(text)

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": cleaned_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            return True
        else:
            # 如果还是失败，尝试作为纯文本发送（保底）
            print(f"Telegram HTML Send Failed, retrying as plain text: {response.text}")
            payload["text"] = re.sub(r'<[^>]+>', '', cleaned_text) # 粗暴去标签
            del payload["parse_mode"]
            response = requests.post(url, json=payload, timeout=15)
            return response.status_code == 200
    except Exception as e:
        print(f"Telegram Error: {e}")
        return False
    finally:
        time.sleep(1)

def send_telegram_tool(message: str) -> str:
    success = send_telegram_core(message)
    return "消息已成功发送到 Telegram。" if success else "发送失败。"