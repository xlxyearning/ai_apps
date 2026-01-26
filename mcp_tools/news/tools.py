import os
import requests
import xml.etree.ElementTree as ET
import json
import html
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={GEMINI_API_KEY}"

# --- Core Logic (For Scripts) ---

def fetch_google_news(query: str, count: int = 10, days: int = 1):
    """
    从 Google News RSS 获取新闻。
    """
    url = f"https://news.google.com/rss/search?q={query}+when:{days}d&hl=en-US&gl=US&ceid=US:en"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = root.findall('.//item')
        
        news_items = []
        for item in items[:count]:
            title = item.find('title').text
            link = item.find('link').text
            news_items.append({"title": title, "link": link})
        return news_items
    except Exception as e:
        print(f"Error fetching news for {query}: {e}")
        return []

def analyze_news_with_ai(news_items, category: str):
    if not news_items:
        return []
    
    if not GEMINI_API_KEY:
        return ["AI Key 未配置"] * len(news_items)

    titles = [item['title'] for item in news_items]
    titles_text = "\n".join([f"{i+1}. {t}" for i, t in enumerate(titles)])
    
    prompt = f"""
    You are a professional tech news analyst. 
    Below are recent news headlines about "{category}". 
    For each headline, provide a 3-5 sentences detailed summary and analysis in Chinese (Simplified Chinese).
    Focus on the background, current status, and future impact.
    Return ONLY a JSON array of strings. No markdown formatting for the json code block, just raw JSON.
    Example: ["Detailed Summary 1...", "Detailed Summary 2..."]
    
    Headlines:
    {titles_text}
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    
    try:
        response = requests.post(GEMINI_URL, json=payload, timeout=60)
        if response.status_code == 200:
            result = response.json()
            if "candidates" in result and result["candidates"]:
                content = result["candidates"][0]["content"]["parts"][0]["text"]
                content = content.replace("```json", "").replace("```", "").strip()
                return json.loads(content)
        else:
            print(f"Gemini API Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"AI Analysis Error: {e}")
    
    return ["AI 分析暂时不可用"] * len(news_items)

def analyze_stock_market(news_items):
    """
    专门针对股市新闻生成深度研报。
    返回一段格式化的 HTML 文本。
    """
    if not news_items:
        return "暂无股市新闻数据。"
    
    titles = [item['title'] for item in news_items]
    titles_text = "\n".join([f"- {t}" for t in titles])
    
    prompt = f"""
    你是顶级A股策略分析师。请阅读以下今日A股相关的新闻标题，并结合你的知识，写一份【深度市场复盘与展望】。
    
    新闻标题列表：
    {titles_text}
    
    请严格按照以下 5 个维度进行详细分析（每个维度 100-200 字）：
    1. 📊 **板块轮动**：哪些板块在领涨/领跌？资金流向哪里？
    2. 🔥 **短线情绪**：市场赚钱效应如何？连板股或妖股表现？
    3. 🤝 **并购重组**：是否有重大重组动态或预期？
    4. 🏛️ **国家政策**：政策面有何利好或监管信号？
    5. 📈 **市场趋势**：大盘技术面走势及明日策略建议。
    
    输出格式要求：
    - 直接输出 HTML 格式的内容（不要包含 ```html 代码块标记）。
    - 使用 <b>加粗重点</b>。
    - 结构清晰，分点陈述。
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
    }
    
    try:
        response = requests.post(GEMINI_URL, json=payload, timeout=90) # 进一步增加超时时间
        if response.status_code == 200:
            result = response.json()
            if "candidates" in result and result["candidates"]:
                content = result["candidates"][0]["content"]["parts"][0]["text"]
                # 清理可能存在的 markdown 标记
                content = content.replace("```html", "").replace("```", "").strip()
                return content
    except Exception as e:
        print(f"Stock Analysis Error: {e}")
        return "AI 深度分析生成失败。"

def get_news_data(query: str, display_name: str = None, count: int = 5) -> dict:
    """
    获取原始的新闻数据和 AI 分析结果。
    """
    display_name = display_name or query
    items = fetch_google_news(query, count)
    analyses = analyze_news_with_ai(items, display_name)
    
    results = []
    for i, item in enumerate(items):
        analysis = analyses[i] if i < len(analyses) else "暂无分析"
        if isinstance(analysis, dict):
            analysis = json.dumps(analysis, ensure_ascii=False)
            
        results.append({
            "title": item['title'],
            "link": item['link'],
            "analysis": analysis
        })
        
    return {
        "topic": display_name,
        "items": results
    }

# --- MCP Interface (For LLM Agent) ---

def fetch_news_tool(query: str, count: int = 5) -> str:
    """
    从 Google News 抓取指定主题的新闻，并使用 AI 生成简短总结。
    
    Args:
        query: 搜索关键词（例如 "AI", "US Stocks"）。
        count: 返回的新闻条数，默认为 5。
    """
    report_data = get_news_data(query, count=count)
    
    if not report_data['items']:
        return f"未找到关于 '{query}' 的新闻。"
        
    output = f"🔹 <b>{report_data['topic']} 新闻简报</b>\n\n"
    for i, item in enumerate(report_data['items']):
        output += f"{i+1}. <a href=\"{item['link']}\">{html.escape(item['title'])}</a>\n"
        output += f"   💡 <code>{html.escape(str(item['analysis']))}</code>\n\n"
        
    return output
