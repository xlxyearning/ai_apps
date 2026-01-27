import os
import requests
import xml.etree.ElementTree as ET
import json
import html
import feedparser
import yfinance as yf
import akshare as ak
import pandas as pd
import time
import re
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from urllib.parse import quote

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={GEMINI_API_KEY}"

# --- Helper Functions ---

def is_within_hours(struct_time, hours=24):
    if not struct_time: return False
    try:
        dt = datetime.fromtimestamp(time.mktime(struct_time), tz=timezone.utc)
        return datetime.now(timezone.utc) - dt <= timedelta(hours=hours)
    except: return False

def deduplicate_items(items):
    seen_links = set()
    unique_items = []
    for item in items:
        link = item.get('link')
        if link not in seen_links:
            seen_links.add(link)
            unique_items.append(item)
    return unique_items

# --- Core Logic ---

def fetch_rss_news(url: str, hours: int = 24, max_count: int = 15):
    try:
        feed = feedparser.parse(url)
        news_items = []
        for entry in feed.entries:
            pub_parsed = getattr(entry, 'published_parsed', None) or getattr(entry, 'updated_parsed', None)
            if is_within_hours(pub_parsed, hours=hours):
                summary = entry.get('summary', '')
                if len(summary) > 300: summary = summary[:300] + "..."
                news_items.append({"title": entry.title, "link": entry.link, "summary": summary})
        
        if len(news_items) < 2 and hours == 24:
            return fetch_rss_news(url, hours=72, max_count=max_count)
        return news_items[:max_count]
    except Exception as e:
        print(f"Error fetching RSS from {url}: {e}")
        return []

def fetch_google_news(query: str, count: int = 20, hours: int = 24):
    safe_query = quote(query)
    url = f"https://news.google.com/rss/search?q={safe_query}+when:{3 if hours > 24 else 1}d&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        news_items = []
        for entry in feed.entries:
            pub_parsed = getattr(entry, 'published_parsed', None)
            if is_within_hours(pub_parsed, hours=hours):
                news_items.append({"title": entry.title, "link": entry.link})
        if not news_items and feed.entries:
            for entry in feed.entries[:3]:
                news_items.append({"title": entry.title, "link": entry.link})
        return news_items[:count]
    except Exception as e:
        print(f"Error fetching Google news for {query}: {e}")
        return []

def fetch_china_policy(hours: int = 24):
    all_items = []
    # Gov.cn
    all_items.extend(fetch_rss_news("http://www.gov.cn/rss/zhengce.xml", hours=hours))
    # Xinhua
    all_items.extend(fetch_rss_news("http://www.news.cn/rss/politics.xml", hours=hours))
    # Caixin
    caixin_search = fetch_google_news("site:caixin.com 政策", count=10, hours=hours)
    if caixin_search: all_items.extend(caixin_search)
    return deduplicate_items(all_items)

def fetch_us_market_depth():
    try:
        data = {}
        indices = {"S&P 500": "^GSPC", "Nasdaq": "^IXIC", "VIX": "^VIX"}
        index_summary = []
        for name, ticker in indices.items():
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if not hist.empty and len(hist) >= 2:
                close = hist['Close'].iloc[-1]
                change = ((close - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
                index_summary.append(f"{name}: {close:.2f} ({change:+.2f}%)")
        data['indices'] = index_summary

        sectors = {"Tech (XLK)": "XLK", "Finance (XLF)": "XLF", "Energy (XLE)": "XLE"}
        sector_summary = []
        for name, ticker in sectors.items():
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if not hist.empty and len(hist) >= 2:
                change = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
                sector_summary.append(f"{name}: {change:+.2f}%")
        data['sectors'] = sector_summary

        sp500 = yf.Ticker("^GSPC")
        news = []
        if sp500.news:
            for item in sp500.news[:8]:
                title = item.get('title') or item.get('content', {}).get('title', 'No Title')
                link = item.get('link') or item.get('content', {}).get('canonicalUrl', {}).get('url') or item.get('content', {}).get('clickThroughUrl', {}).get('url')
                if title: news.append({"title": title, "link": link})
        data['news'] = news
        return data
    except Exception as e:
        print(f"Error fetching US market depth: {e}")
        return {"error": str(e)}

def fetch_cn_market_depth():
    """
    Tiered Fallback Strategy: Akshare -> Yahoo Finance -> Google News
    """
    data = {"indices": [], "total_volume": "未知", "north_money": "未知", "news": []}
    
    # Tier 1: Akshare
    try:
        indices_df = ak.stock_zh_index_spot_em()
        target_indices = ["上证指数", "深证成指", "创业板指"]
        total_vol = 0
        for idx_name in target_indices:
            row = indices_df[indices_df['名称'] == idx_name]
            if not row.empty:
                current = row['最新价'].values[0]
                change = row['涨跌幅'].values[0]
                total_vol += float(row['成交额'].values[0])
                data['indices'].append(f"{idx_name}: {current} ({change:+.2f}%)")
        data['total_volume'] = f"{total_vol / 1e8:.2f} 亿"

        try:
            hsgt_df = ak.stock_hsgt_north_net_flow_em(symbol="北上")
            if not hsgt_df.empty:
                data['north_money'] = f"{hsgt_df.iloc[-1]['value']:.2f} 万"
        except: pass

        try:
            news_df = ak.stock_telegraph_cls() 
            for _, row in news_df.head(15).iterrows():
                data['news'].append({"title": row['title'], "content": row['content']})
        except: pass
        
        return data
        
    except Exception as e:
        print(f"Akshare failed ({e}), switching to fallback...")

    # Tier 2: Yahoo Finance
    try:
        yf_map = {"上证指数": "000001.SS", "深证成指": "399001.SZ"}
        for name, ticker in yf_map.items():
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if not hist.empty and len(hist) >= 2:
                close = hist['Close'].iloc[-1]
                change = ((close - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
                data['indices'].append(f"{name}: {close:.2f} ({change:+.2f}%)")
        
        # Yahoo News for A-Shares
        try:
            sz = yf.Ticker("000001.SS")
            if sz.news:
                 for item in sz.news[:5]:
                    title = item.get('title') or item.get('content', {}).get('title', 'No Title')
                    link = item.get('link') or item.get('content', {}).get('canonicalUrl', {}).get('url') or item.get('content', {}).get('clickThroughUrl', {}).get('url')
                    if title: data['news'].append({"title": title, "link": link})
        except: pass
        
        return data
        
    except Exception as e:
        print(f"Yahoo fallback failed ({e}), switching to emergency search...")

    # Tier 3: Google News Search
    try:
        emergency_news = fetch_google_news("A股收盘", count=5, hours=24)
        data['news'] = emergency_news
        data['indices'] = ["数据获取失败，仅提供新闻参考"]
        return data
    except:
        return {"indices": ["完全获取失败"], "news": []}

def analyze_news_with_ai(news_items, category: str):
    if not news_items: return []
    if not GEMINI_API_KEY: return ["AI Key 未配置"] * len(news_items)
    titles = [item.get('title', '') for item in news_items]
    titles_text = "\n".join([f"{i+1}. {t}" for i, t in enumerate(titles)])
    prompt = f"Analyze these '{category}' headlines from the last 24h in Chinese (Simplified). 3-5 sentences each. Return JSON array."
    payload = {"contents": [{"parts": [{"text": f"{prompt}\n\n{titles_text}"}]}], "generationConfig": {"responseMimeType": "application/json"}}
    try:
        response = requests.post(GEMINI_URL, json=payload, timeout=60)
        if response.status_code == 200:
            content = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(content.replace("```json", "").replace("```", "").strip())
    except: pass
    return ["AI 分析暂时不可用"] * len(news_items)

def analyze_stock_market_multi(us_data, cn_data):
    """
    综合研报生成。
    """
    prompt = f"""
    你是全球顶级策略分析师。请结合以下【美股数据】和【A股数据】，写一份全球视角的深度市场分析。
    
    【美股数据】：指数: {us_data.get('indices')}, 板块: {us_data.get('sectors')}, 新闻: {[n['title'] for n in us_data.get('news', [])]}
    【A股数据】：指数: {cn_data.get('indices')}, 成交额: {cn_data.get('total_volume')}, 北向: {cn_data.get('north_money')}, 电报: {[n.get('title') for n in cn_data.get('news', [])[:5]]}
    
    输出格式要求：
    - **直接输出HTML内容，但不要包含任何 <!DOCTYPE>, <html>, <head>, <body>, <h1>, <h3> 等网页结构标签**。
    - **使用 `<p>...</p>` 标签来包裹每个段落**，这对于邮件格式至关重要。
    - 仅可使用 `<b>...</b>` 对关键词进行加粗。
    - 严格分 5 个维度（宏观、A股情绪、热点板块、风险、策略），每个维度 200 字左右。
    """
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(GEMINI_URL, json=payload, timeout=120)
        if response.status_code == 200:
            result = response.json()
            content = result["candidates"][0]["content"]["parts"][0]["text"]
            # 即使 prompt 约束，也做一次清理，以防万一
            content = content.replace("```html", "").replace("```", "").strip()
            # 移除非预期的 HTML 结构
            content = re.sub(r'<!DOCTYPE[^>]*>|<html>|<head>.*?</head>|<body>|</body>|</html>', '', content, flags=re.IGNORECASE | re.DOTALL)
            return content.strip()
    except Exception as e:
        print(f"Global Stock Analysis Error: {e}")
        return "AI 深度分析生成失败。"

def get_news_data(query: str, display_name: str = None, count: int = 5, hours: int = 24) -> dict:
    display_name = display_name or query
    items = fetch_google_news(query, count, hours=hours)
    analyses = analyze_news_with_ai(items, display_name)
    results = []
    for i, item in enumerate(items):
        analysis = analyses[i] if i < len(analyses) else "暂无分析"
        results.append({"title": item['title'], "link": item['link'], "analysis": analysis})
    return {"topic": display_name, "items": results}

def fetch_news_tool(query: str, count: int = 5) -> str:
    report_data = get_news_data(query, count=count)
    if not report_data['items']: return f"未找到关于 '{query}' 的新闻。"
    output = f"🔹 <b>{report_data['topic']} 新闻简报</b>\n\n"
    for i, item in enumerate(report_data['items']):
        output += f"{i+1}. <a href=\"{item['link']}\">{html.escape(item['title'])}</a>\n   💡 <code>{html.escape(str(item['analysis']))}</code>\n\n"
    return output
