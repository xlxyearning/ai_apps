import sys
import os
import datetime
import time
import html
from dotenv import load_dotenv

# Add project root to path so we can import mcp_tools
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from mcp_tools.telegram.tools import send_telegram_core as send_telegram_message
from mcp_tools.news.tools import get_news_data as get_news_report, fetch_google_news, analyze_stock_market
from mcp_tools.email.tools import send_email_core

# Load environment variables
load_dotenv()

def main():
    # Map display names to English queries for global reach
    topics = {
        "AI": "Artificial Intelligence",
        "OS": "Operating Systems Linux Windows macOS",
        "Embedded Linux": "Embedded Linux Development",
        "Tech Giants": "Big Tech companies Google Apple Microsoft NVIDIA Meta SpaceX OpenAI Anthropic",
        "US Stock": "US Stock Market",
        "A-Shares": "China A-Shares market",
        "China Policy": "China Government Policy"
    }
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 1. Send Telegram Header
    send_telegram_message(f"📅 <b>Daily Global News Digest (AI Enhanced)</b>\n<i>{current_time}</i>")
    
    # 2. Initialize Email Body
    full_email_html = f"<h1>📅 Daily Global News Digest (AI Enhanced)</h1><p><i>{current_time}</i></p><hr>"
    
    # 3. Process Each Topic
    for display_name, query in topics.items():
        print(f"Processing {display_name}...")
        
        # Special handling for A-Shares Market Analysis
        if display_name == "A-Shares":
            print(f"Executing deep analysis for {display_name} (25 recent + 5 weekly)...")
            # 1. Fetch 25 items from last 24h
            items_recent = fetch_google_news(query, count=25, days=1)
            
            # 2. Fetch some items from last 5 days to pick 5 unique ones
            items_weekly = fetch_google_news(query, count=15, days=5)
            
            # 3. Combine and deduplicate
            seen_links = {item['link'] for item in items_recent}
            unique_weekly = [item for item in items_weekly if item['link'] not in seen_links][:5]
            
            raw_items = items_recent + unique_weekly
            
            if raw_items:
                # Generate deep report
                stock_report_html = analyze_stock_market(raw_items)
                
                # Send to Telegram (Whole report)
                tg_msg = f"🇨🇳 <b>A股深度复盘与展望</b>\n\n{stock_report_html}\n\n<i>(基于最近 24h 的 {len(items_recent)} 条及近 5 日的 {len(unique_weekly)} 条关键资讯分析)</i>"
                send_telegram_message(tg_msg)
                
                # Add to Email
                category_html = f"<h2>🇨🇳 A股深度复盘与展望</h2>{stock_report_html}<hr>"
                full_email_html += category_html
            else:
                send_telegram_message(f"🔹 <b>{display_name}</b>\n- No news found.\n")
            
            time.sleep(2)
            continue

        # Use common logic from mcp_tools for other topics
        report_data = get_news_report(query, display_name)
        items = report_data['items']
        
        category_html = f"<h2>🔹 {display_name}</h2>"
        
        if items:
            # Chunking for Telegram (limit message size)
            chunk_size = 5
            total_chunks = len(items)//chunk_size + (1 if len(items)%chunk_size else 0)
            
            for j in range(0, len(items), chunk_size):
                chunk_items = items[j:j+chunk_size]
                
                # Build Telegram Message
                tg_msg = f"🔹 <b>{display_name} ({j//chunk_size + 1}/{total_chunks})</b>\n"
                
                for i, item in enumerate(chunk_items):
                    idx = j + i + 1
                    title = html.escape(item['title'])
                    link = item['link']
                    analysis = html.escape(str(item['analysis']))
                    
                    # Add to Telegram chunk
                    tg_msg += f"{idx}. <a href=\"{link}\">{title}</a>\n"
                    tg_msg += f"   💡 <code>{analysis}</code>\n\n"
                    
                    # Add to Email HTML (accumulated)
                    category_html += f"<p><b>{idx}. <a href=\"{link}\">{title}</a></b><br>"
                    category_html += f"💡 <span style='background-color: #f0f0f0; padding: 2px;'>{analysis}</span></p>"
                
                send_telegram_message(tg_msg)
        else:
            send_telegram_message(f"🔹 <b>{display_name}</b>\n- No news found.\n")
            category_html += "<p>- No news found.</p>"
        
        full_email_html += category_html + "<hr>"
        time.sleep(1) # Be nice to APIs
        
    # 4. Send Email Report
    print("Sending email report...")
    # send_email_core reads env vars for recipients if to_addrs is not provided
    send_email_core(f"Daily News Digest - {current_time}", full_email_html, is_html=True)

if __name__ == "__main__":
    main()
