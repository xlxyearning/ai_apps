import requests
import xml.etree.ElementTree as ET
import datetime
import time
import json
import re
import html
import smtplib
import os
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load environment variables from .env file
load_dotenv()

# Configuration
TG_TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-preview:generateContent?key={GEMINI_API_KEY}"

# Email Configuration
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECIPIENTS = os.getenv("EMAIL_RECIPIENTS", "").split(",")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

def send_telegram(text: str):
    """发送文本消息到用户的手机 Telegram"""
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"Failed to send message: {response.text}")
    except Exception as e:
        print(f"Error sending message: {e}")
    time.sleep(1)

def send_email(subject, html_body):
    """发送 HTML 邮件到指定邮箱"""
    if EMAIL_SENDER == "YOUR_EMAIL@gmail.com":
        print("Email configuration not set. Skipping email send.")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = ", ".join(EMAIL_RECIPIENTS)
    msg['Subject'] = subject

    msg.attach(MIMEText(html_body, 'html'))

    try:
        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        else:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENTS, msg.as_string())
        server.quit()
        print("Email sent successfully.")
    except Exception as e:
        print(f"Error sending email: {e}")

def get_google_news(query):
    # Using Google News RSS with English/US locale for global coverage
    # Adding when:1d to query to ensure news is from the last 24 hours
    url = f"https://news.google.com/rss/search?q={query}+when:1d&hl=en-US&gl=US&ceid=US:en"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = root.findall('.//item')
        # Return top 10 titles and links
        news_items = []
        for item in items[:10]:
            title = item.find('title').text
            link = item.find('link').text
            news_items.append({"title": title, "link": link})
        return news_items
    except Exception as e:
        print(f"Error fetching news for {query}: {e}")
        return []

def get_ai_analysis(items, category):
    if not items:
        return []
    
    titles = [item['title'] for item in items]
    titles_text = "\n".join([f"{i+1}. {t}" for i, t in enumerate(titles)])
    
    prompt = f"""
    You are a professional tech news analyst. 
    Below are recent news headlines about "{category}". 
    For each headline, provide a 1-sentence summary and analysis in Chinese (Simplified Chinese).
    Focus on the impact or significance.
    Return ONLY a JSON array of strings. No markdown formatting for the json code block, just raw JSON.
    Example: ["Summary 1", "Summary 2"]
    
    Headlines:
    {titles_text}
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    
    try:
        response = requests.post(GEMINI_URL, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if "candidates" in result and result["candidates"]:
                content = result["candidates"][0]["content"]["parts"][0]["text"]
                # Clean up any potential markdown code blocks if the model ignores the instruction
                content = content.replace("```json", "").replace("```", "").strip()
                analyses = json.loads(content)
                return analyses
        else:
            print(f"Gemini API Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"AI Analysis Error: {e}")
    
    # Fallback if AI fails
    return ["暂无分析"] * len(items)

def main():
    # Map display names to English queries for global reach
    topics = {
        "AI & Artificial Intelligence": "Artificial Intelligence",
        "Tech Giants": "Big Tech companies",
        "IPC (Network Cameras)": "IPC Network Camera security",
        "Embedded Development": "Embedded Systems Development",
        "US Stocks": "US Stock Market",
        "China A-Shares": "China A-Shares market",
        "Major Policies": "China Government Policy"
    }
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Send Telegram header
    send_telegram(f"📅 <b>Daily Global News Digest (AI Enhanced)</b>\n<i>{current_time}</i>")
    
    # Initialize full email report
    full_email_html = f"<h1>📅 Daily Global News Digest (AI Enhanced)</h1><p><i>{current_time}</i></p><hr>"
    
    for display_name, query in topics.items():
        print(f"Processing {display_name}...")
        news_items = get_google_news(query)
        
        category_html = f"<h2>🔹 {display_name}</h2>"
        
        if news_items:
            # Get AI analysis
            analyses = get_ai_analysis(news_items, display_name)
            
            # Send in chunks of 5 items to avoid message length limits
            chunk_size = 5
            for j in range(0, len(news_items), chunk_size):
                chunk_items = news_items[j:j+chunk_size]
                chunk_analyses = analyses[j:j+chunk_size]
                
                total_chunks = len(news_items)//chunk_size + (1 if len(news_items)%chunk_size else 0)
                report = f"🔹 <b>{display_name} ({j//chunk_size + 1}/{total_chunks})</b>\n"
                
                for i, item in enumerate(chunk_items):
                    title = html.escape(item['title'])
                    link = item['link']
                    
                    # Ensure analysis is a string
                    raw_analysis = chunk_analyses[i] if i < len(chunk_analyses) else "暂无分析"
                    if isinstance(raw_analysis, dict):
                        raw_analysis = json.dumps(raw_analysis, ensure_ascii=False)
                    analysis = html.escape(str(raw_analysis))
                    
                    # Telegram format
                    report += f"{j+i+1}. <a href=\"{link}\">{title}</a>\n"
                    report += f"   💡 <code>{analysis}</code>\n\n"
                    
                    # Email format (accumulate)
                    category_html += f"<p><b>{j+i+1}. <a href=\"{link}\">{title}</a></b><br>"
                    category_html += f"💡 <span style='background-color: #f0f0f0; padding: 2px;'>{analysis}</span></p>"
                
                send_telegram(report)
        else:
            send_telegram(f"🔹 <b>{display_name}</b>\n- No news found.\n")
            category_html += "<p>- No news found.</p>"
        
        full_email_html += category_html + "<hr>"
        time.sleep(1)
        
    # Send full email report
    send_email(f"Daily News Digest - {current_time}", full_email_html)

if __name__ == "__main__":
    main()
