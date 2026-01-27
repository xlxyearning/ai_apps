import sys
import os
import datetime
import time
import html
from dotenv import load_dotenv

# Add project root to path so we can import mcp_tools
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from mcp_tools.telegram.tools import send_telegram_core as send_telegram_message
from mcp_tools.news.tools import (
    get_news_data as get_news_report, 
    fetch_rss_news, 
    fetch_us_market_depth, 
    fetch_cn_market_depth, 
    fetch_china_policy,
    analyze_stock_market_multi,
    analyze_news_with_ai
)
from mcp_tools.email.tools import send_email_core

# Load environment variables
load_dotenv()

def main():
    # 混合配置表 v5.0 (24h 智能过滤版)
    topics_config = {
        "AI Focus": {"type": "rss", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed/"},
        "Tech Giants": {"type": "rss", "url": "https://techcrunch.com/feed/"},
        "OS Tech": {"type": "rss", "url": "https://www.phoronix.com/rss.php"},
        "Domestic OS": {"type": "rss", "url": "https://www.ithome.com/rss/"},
        "Market Analysis": {"type": "market_depth"},
        "China Policy": {"type": "china_policy"},
        "Embedded Linux": {"type": "search", "query": "Embedded Linux Development"}
    }
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 1. Send Telegram Header
    send_telegram_message(f"📅 <b>Daily Global News (24h Smart Window)</b>\n<i>{current_time}</i>")
    
    full_email_html = f"<h1>📅 Daily Global News (24h Smart Window)</h1><p><i>{current_time}</i></p><hr>"
    
    for display_name, config in topics_config.items():
        print(f"Processing {display_name}...")
        
        items = []
        category_html = f"<h2>🔹 {display_name}</h2>"
        
        # --- Type 1: Market Depth ---
        if config['type'] == "market_depth":
            us_data = fetch_us_market_depth()
            cn_data = fetch_cn_market_depth()
            report_html = analyze_stock_market_multi(us_data, cn_data)
            send_telegram_message(f"📊 <b>全球市场深度复盘与展望</b>\n\n{report_html}")
            full_email_html += f"<h2>📊 全球市场深度复盘与展望</h2>{report_html}<hr>"
            continue

        # --- Type 2: China Policy (Multi-Source + 24h Filter) ---
        elif config['type'] == "china_policy":
            raw_items = fetch_china_policy(hours=24)
            if raw_items:
                analyses = analyze_news_with_ai(raw_items, display_name)
                for i, item in enumerate(raw_items):
                    item['analysis'] = analyses[i] if i < len(analyses) else "暂无分析"
                items = raw_items

        # --- Type 3: RSS News (24h Filter) ---
        elif config['type'] == "rss":
            raw_items = fetch_rss_news(config['url'], hours=24)
            if raw_items:
                analyses = analyze_news_with_ai(raw_items, display_name)
                for i, item in enumerate(raw_items):
                    item['analysis'] = analyses[i] if i < len(analyses) else "暂无分析"
                items = raw_items
            
        # --- Type 4: Search (24h Filter) ---
        elif config['type'] == "search":
            report_data = get_news_report(config['query'], display_name, count=10, hours=24)
            items = report_data['items']

        # --- Output Formatting ---
        if items:
            for idx, item in enumerate(items):
                title = html.escape(item['title'])
                link = item['link']
                analysis = html.escape(str(item['analysis']))
                category_html += f"<p><b>{idx+1}. <a href=\"{link}\">{title}</a></b><br>"
                category_html += f"💡 <span style='background-color: #f0f0f0; padding: 2px;'>{analysis}</span></p>"

            chunk_size = 5
            for j in range(0, len(items), chunk_size):
                chunk_items = items[j:j+chunk_size]
                tg_msg = f"🔹 <b>{display_name}</b>\n"
                for i, item in enumerate(chunk_items):
                    tg_msg += f"{j+i+1}. <a href=\"{item['link']}\">{html.escape(item['title'])}</a>\n"
                    tg_msg += f"   💡 <code>{html.escape(str(item['analysis']))}</code>\n\n"
                send_telegram_message(tg_msg)
        else:
            send_telegram_message(f"🔹 <b>{display_name}</b>\n- No updates in the last 24h.\n")
            category_html += "<p>- No updates in the last 24h.</p>"
        
        full_email_html += category_html + "<hr>"
        # 增加延迟以尊重 API 速率限制，减少“暂无分析”的概率
        print("Waiting for 60 seconds before next topic...")
        time.sleep(60)
        
    # 4. Send Email Report
    print("Sending email report...")
    send_email_core(f"Daily News Digest - {current_time}", full_email_html, is_html=True)

if __name__ == "__main__":
    main()
