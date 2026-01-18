# =============================
# Required packages
# =============================
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
import os

# =============================
# CONFIGURATION
# =============================
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "a7f1d21177364f20a73c91f2c924b0fd")

SENDER_EMAIL = "aarondooleykim@gmail.com"
SENDER_PASSWORD = "uxrx oeuf atsl xhba"
RECIPIENT_EMAIL = "dkim4@macalester.edu"

# =============================
# HELPERS
# =============================
def get_stock_metrics_rsi(ticker, period=14):
    stock = yf.Ticker(ticker)
    price = stock.history(period="1d")["Close"].iloc[-1]

    hist = stock.history(period="60d")["Close"]
    delta = hist.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    rs = gain.rolling(period).mean() / loss.rolling(period).mean()
    rsi = 100 - (100 / (1 + rs))

    return price, rsi.iloc[-1]

def fetch_article_text(url):
    """Try to extract meaningful text from the article URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        res = requests.get(url, timeout=10, headers=headers)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text from paragraphs
        paragraphs = soup.find_all("p")
        text = " ".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 50])
        
        return text[:3000] if text else ""
    except Exception as e:
        return ""

def create_summary(title, description, url=None):
    """Create a summary from available content without OpenAI"""
    # Try to fetch full article
    content = description or ""
    
    if url and len(content) < 100:
        full_text = fetch_article_text(url)
        if full_text and len(full_text) > len(content):
            content = full_text
    
    # If we don't have content, return None to skip this article
    if not content or len(content) < 30:
        return None
    
    # Clean up content - remove common boilerplate
    content = re.sub(r'See the rest of the story here.*', '', content, flags=re.IGNORECASE)
    content = re.sub(r'Read more:.*', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\(Reuters\).*?-\s*', '', content)
    content = re.sub(r'Known as a leader in.*', '', content, flags=re.IGNORECASE)
    content = re.sub(r'The Fly.*real-time.*', '', content, flags=re.IGNORECASE)
    content = re.sub(r'streaming news feed.*', '', content, flags=re.IGNORECASE)
    content = re.sub(r'thefly\.com provides.*', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\.\.\.$', '', content).strip()
    
    # Extract first meaningful sentence only
    sentences = re.split(r'(?<=[.!?])\s+', content)
    
    # Filter out very short sentences and common fluff
    fluff_patterns = [
        r'^thefly\.com',
        r'^the fly',
        r'^known as a leader',
        r'^sign up for',
        r'^subscribe',
        r'^click here',
        r'^read more',
        r'^follow us',
        r'^market intelligence',
        r'^streaming news',
        r'real-time.*feed'
    ]
    
    for sentence in sentences:
        # Skip if too short or is fluff
        if len(sentence) < 30:
            continue
        if any(re.search(pattern, sentence, re.IGNORECASE) for pattern in fluff_patterns):
            continue
        # Return just the first good sentence
        return sentence
    
    # Not enough quality content, skip this article
    return None

def normalize_title(title):
    title = title.lower()
    title = re.sub(r"[^a-z0-9\s]", "", title)
    return re.sub(r"\s+", " ", title).strip()

def fetch_filtered_news(query, keywords, days=7, max_articles=10):
    """Fetch news articles and create summaries"""
    print(f"\n🔍 Searching news for: {query}")
    from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    params = {
        "q": query,
        "from": from_date,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 50,
        "apiKey": NEWS_API_KEY
    }

    response = requests.get("https://newsapi.org/v2/everything", params=params)
    data = response.json()

    if data.get("status") != "ok":
        print(f"❌ News API error: {data.get('message', 'Unknown error')}")
        return pd.DataFrame()

    print(f"Found {len(data.get('articles', []))} articles, filtering...")
    seen = set()
    rows = []

    for article in data.get("articles", []):
        title = article.get("title") or ""
        description = article.get("description") or ""
        url = article.get("url")
        content = article.get("content") or ""

        title_lower = title.lower()
        combined = f"{title} {description} {content}".lower()
        
        # Check if ANY keyword is in title OR description
        matched = []
        for k in keywords:
            if k.lower() in title_lower or k.lower() in description.lower():
                matched.append(k)
        
        if not matched:
            continue
        
        # Only skip the most obvious junk
        skip_phrases = ['airline', 'gray market', 'grey market']
        if any(skip in title_lower for skip in skip_phrases):
            print(f"   ⚠️ Skipping (filtered): {title[:60]}...")
            continue

        norm = normalize_title(title)
        if norm in seen:
            continue
        seen.add(norm)

        print(f"📄 Processing: {title[:60]}...")
        summary = create_summary(title, description, url=url)
        
        # Skip article if no good summary could be created
        if summary is None:
            print(f"   ⚠️ Skipping - insufficient content for summary")
            continue
            
        print(f"   Summary: {summary[:100]}...")

        rows.append({
            "title": title,
            "summary": summary,
            "url": url,
            "source": article.get("source", {}).get("name"),
            "publishedAt": article.get("publishedAt"),
            "matched_keywords": matched
        })

        if len(rows) >= max_articles:
            break

    print(f"✓ Collected {len(rows)} articles")
    return pd.DataFrame(rows)

# =============================
# METRICS
# =============================
print("📊 Fetching stock metrics...")
pslv_price, pslv_rsi = get_stock_metrics_rsi("PSLV")

# Try multiple silver tickers with fallback
silver_spot = None
silver_tickers = ["SI=F", "SLV"]  # Silver futures, then SLV ETF as backup

for ticker in silver_tickers:
    try:
        print(f"Trying {ticker}...")
        data = yf.Ticker(ticker).history(period="5d")
        if not data.empty:
            silver_spot = data["Close"].iloc[-1]
            # If using SLV, convert to approximate silver spot price
            if ticker == "SLV":
                silver_spot = silver_spot / 0.95  # SLV holds ~0.95 oz per share
            print(f"✓ Got silver price from {ticker}: ${silver_spot:.2f}")
            break
    except Exception as e:
        print(f"Failed to get {ticker}: {e}")
        continue

if silver_spot is None:
    raise Exception("Could not fetch silver price from any source")

pslv_nav = silver_spot * 0.3401
pslv_discount = (pslv_price - pslv_nav) / pslv_nav * 100

# Novo Nordisk - just stock metrics
nvo_price, nvo_rsi = get_stock_metrics_rsi("NVO")
nvo_stock = yf.Ticker("NVO")
nvo_hist = nvo_stock.history(period="1mo")
nvo_volume = nvo_hist["Volume"].mean()
nvo_info = nvo_stock.info
nvo_52w_high = nvo_info.get("fiftyTwoWeekHigh", 0)
nvo_52w_low = nvo_info.get("fiftyTwoWeekLow", 0)

# =============================
# NEWS - Middle ground keywords
# =============================
pslv_keywords = [
    "PSLV", "silver price", "silver market", "silver demand",
    "silver supply", "silver ETF", "silver investment"
]
nvo_keywords = [
    "novo nordisk", "wegovy",
    "novo nordisk earnings", "novo nordisk revenue", "novo nordisk sales", "novo nordisk stock",
    "novo nordisk supply", "novo nordisk shortage", "novo nordisk production"
]

pslv_news = fetch_filtered_news("PSLV OR silver", pslv_keywords, days=30, max_articles=5)
nvo_news = fetch_filtered_news("Novo Nordisk OR Wegovy OR GLP-1", nvo_keywords, days=7, max_articles=5)

# =============================
# EMAIL BODY
# =============================
def build_email_body():
    body = f"<html><body style='font-family:Arial; max-width:800px; margin:0 auto;'>"
    body += f"<h2>📊 PSLV Metrics</h2>"
    body += f"<p><strong>Silver Spot:</strong> ${silver_spot:.2f}<br>"
    body += f"<strong>PSLV Price:</strong> ${pslv_price:.2f}<br>"
    body += f"<strong>Synthetic NAV:</strong> ${pslv_nav:.2f}<br>"
    body += f"<strong>Discount:</strong> {pslv_discount:.2f}%<br>"
    body += f"<strong>RSI:</strong> {pslv_rsi:.1f}</p>"
    body += "<h3>📰 PSLV News</h3>"

    if not pslv_news.empty:
        for _, r in pslv_news.iterrows():
            body += f"<div style='margin-bottom:20px; padding:10px; background:#f5f5f5; border-radius:5px;'>"
            body += f"<h4 style='margin:0 0 10px 0;'>{r['title']}</h4>"
            body += f"<p style='margin:0 0 10px 0;'>{r['summary']}</p>"
            body += f"<a href='{r['url']}' style='color:#0066cc;'>Read full article →</a>"
            body += f"</div>"
    else:
        body += "<p>No PSLV articles found.</p>"

    body += f"<h2>📊 Novo Nordisk Metrics</h2>"
    body += f"<p><strong>Stock Price:</strong> ${nvo_price:.2f}<br>"
    body += f"<strong>RSI:</strong> {nvo_rsi:.1f}<br>"
    body += f"<strong>52-Week High:</strong> ${nvo_52w_high:.2f}<br>"
    body += f"<strong>52-Week Low:</strong> ${nvo_52w_low:.2f}<br>"
    body += f"<strong>Avg Volume (30d):</strong> {nvo_volume:,.0f}</p>"
    body += "<h3>📰 Novo Nordisk News</h3>"

    if not nvo_news.empty:
        for _, r in nvo_news.iterrows():
            body += f"<div style='margin-bottom:20px; padding:10px; background:#f5f5f5; border-radius:5px;'>"
            body += f"<h4 style='margin:0 0 10px 0;'>{r['title']}</h4>"
            body += f"<p style='margin:0 0 10px 0;'>{r['summary']}</p>"
            body += f"<a href='{r['url']}' style='color:#0066cc;'>Read full article →</a>"
            body += f"</div>"
    else:
        body += "<p>No Novo Nordisk articles found.</p>"

    return body + "</body></html>"

email_body = build_email_body()

# =============================
# SEND EMAIL
# =============================
def send_email(subject, body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())

# Send the email
send_email(f"PSLV & Novo Nordisk Report - {datetime.now():%B %d, %Y}", email_body)
print("\n✉️ Email sent successfully!")

# =============================
# CONSOLE OUTPUT
# =============================
print("\n" + "="*60)
print("📊 PSLV Metrics")
print("="*60)
print(f"Silver Spot: ${silver_spot:.2f}")
print(f"PSLV Price: ${pslv_price:.2f}")
print(f"Synthetic NAV: ${pslv_nav:.2f}")
print(f"Discount: {pslv_discount:.2f}%")
print(f"RSI: {pslv_rsi:.1f}")

print("\n📰 PSLV News")
print("-"*60)
if not pslv_news.empty:
    for i, r in pslv_news.iterrows():
        print(f"\n{i+1}. {r['title']}")
        print(f"   {r['summary']}")
        print(f"   🔗 {r['url']}")
else:
    print("No PSLV articles found.\n")

print("\n" + "="*60)
print("📊 Novo Nordisk Metrics")
print("="*60)
print(f"Stock Price: ${nvo_price:.2f}")
print(f"RSI: {nvo_rsi:.1f}")
print(f"52-Week High: ${nvo_52w_high:.2f}")
print(f"52-Week Low: ${nvo_52w_low:.2f}")
print(f"Avg Volume (30d): {nvo_volume:,.0f}")

print("\n📰 Novo Nordisk News")
print("-"*60)
if not nvo_news.empty:
    for i, r in nvo_news.iterrows():
        print(f"\n{i+1}. {r['title']}")
        print(f"   {r['summary']}")
        print(f"   🔗 {r['url']}")
else:
    print("No Novo Nordisk articles found.\n")

print("\n" + "="*60)
print("✅ Report complete!")
print("="*60)

# =============================
# SAVE TEXT REPORT FOR GITHUB ACTIONS
# =============================
with open('report.txt', 'w', encoding='utf-8') as f:
    f.write(f"Daily Stock Report - {datetime.now().strftime('%Y-%m-%d %I:%M %p PST')}\n")
    f.write("=" * 60 + "\n\n")
    
    # PSLV Metrics
    f.write("📊 PSLV METRICS\n")
    f.write("-" * 60 + "\n")
    f.write(f"Silver Spot: ${silver_spot:.2f}\n")
    f.write(f"PSLV Price: ${pslv_price:.2f}\n")
    f.write(f"Synthetic NAV: ${pslv_nav:.2f}\n")
    f.write(f"Discount: {pslv_discount:.2f}%\n")
    f.write(f"RSI: {pslv_rsi:.1f}\n\n")
    
    # PSLV News
    f.write("📰 PSLV NEWS\n")
    f.write("-" * 60 + "\n")
    if not pslv_news.empty:
        for i, r in pslv_news.iterrows():
            f.write(f"\n{i+1}. {r['title']}\n")
            f.write(f"   {r['summary']}\n")
            f.write(f"   🔗 {r['url']}\n")
    else:
        f.write("No PSLV articles found.\n")
    
    f.write("\n" + "=" * 60 + "\n\n")
    
    # Novo Nordisk Metrics
    f.write("📊 NOVO NORDISK METRICS\n")
    f.write("-" * 60 + "\n")
    f.write(f"Stock Price: ${nvo_price:.2f}\n")
    f.write(f"RSI: {nvo_rsi:.1f}\n")
    f.write(f"52-Week High: ${nvo_52w_high:.2f}\n")
    f.write(f"52-Week Low: ${nvo_52w_low:.2f}\n")
    f.write(f"Avg Volume (30d): {nvo_volume:,.0f}\n\n")
    
    # Novo Nordisk News
    f.write("📰 NOVO NORDISK NEWS\n")
    f.write("-" * 60 + "\n")
    if not nvo_news.empty:
        for i, r in nvo_news.iterrows():
            f.write(f"\n{i+1}. {r['title']}\n")
            f.write(f"   {r['summary']}\n")
            f.write(f"   🔗 {r['url']}\n")
    else:
        f.write("No Novo Nordisk articles found.\n")
    
    f.write("\n" + "=" * 60 + "\n")
    f.write("✅ Report complete!\n")

print("📄 Report saved to report.txt")
