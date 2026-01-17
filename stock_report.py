# %%
import subprocess
import sys

# List of packages you want to install
packages = [
    "yfinance",
    "sendgrid",
    "selenium",
    "webdriver_manager",
    "openai",
    "newspaper3k"
]

# Install all packages in one pip command
subprocess.check_call([sys.executable, "-m", "pip", "install", *packages])

# %%
import yfinance as yf
import pandas as pd

def get_pslv_metrics():
    # Fetch 1 year of historical data for PSLV
    pslv = yf.download("PSLV", period="5y")
    
    # Calculate 50-day and 200-day Simple Moving Averages (SMA)
    pslv['SMA50'] = pslv['Close'].rolling(window=50).mean()
    pslv['SMA200'] = pslv['Close'].rolling(window=200).mean()
    
    # Simple RSI Calculation (14-day)
    delta = pslv['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    pslv['RSI'] = 100 - (100 / (1 + rs))
    
    return pslv.tail(1)

# Current data point
latest_data = get_pslv_metrics()
print(f"Current PSLV RSI: {latest_data['RSI'].values[0]:.2f}")

# %%
def calculate_pslv_target(spot_target, premium_discount=-0.035, oz_per_share=0.3438):
    """
    Calculates estimated PSLV share price based on a spot silver target.
    
    :param spot_target: The target price of 1oz of silver (e.g., 90.00)
    :param premium_discount: The current % discount or premium (default -3.5% or -0.035)
    :param oz_per_share: The current amount of silver per share (approx 0.3438 in 2026)
    :return: Estimated PSLV share price
    """
    # 1. Calculate the Intrinsic Value (NAV)
    nav_price = spot_target * oz_per_share
    
    # 2. Apply the Market Premium/Discount
    estimated_price = nav_price * (1 + premium_discount)
    
    return round(estimated_price, 2)

# Example: If your target for spot silver is $100.00
target_spot = 100.00
estimated_pslv = calculate_pslv_target(target_spot)

print(f"If Spot Silver hits ${target_spot}, PSLV estimated price: ${estimated_pslv}")

# %%


# %%
import yfinance as yf
import pandas as pd
# import smtplib
# from email.mime.multipart import MIMEMultipart
# from email.mime.text import MIMEText

# -----------------------------
# Step 1: Calculate PSLV metrics + RSI
# -----------------------------
def get_pslv_metrics_rsi(period=14):
    pslv = yf.Ticker("PSLV")
    silver = yf.Ticker("SI=F")
    
    # Latest price
    pslv_price = pslv.history(period="1d")['Close'].iloc[-1]
    silver_spot = silver.history(period="1d")['Close'].iloc[-1]
    
    oz_per_share = 0.3401
    synthetic_nav = silver_spot * oz_per_share
    discount = ((pslv_price - synthetic_nav) / synthetic_nav) * 100

    # RSI calculation
    hist = pslv.history(period="60d")['Close']  # last 60 days
    delta = hist.diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    latest_rsi = rsi.iloc[-1]  # most recent RSI

    return pslv_price, synthetic_nav, discount, silver_spot, latest_rsi

price, nav, disc, spot, rsi = get_pslv_metrics_rsi()

# -----------------------------
# Step 2: Compose email (optional, not sending)
# -----------------------------
subject = "Daily PSLV Metrics"
body = f"""
Silver Spot Price: ${spot:.2f} ideally we want $100
PSLV Market Price: ${price:.2f} Sells at $33.18
PSLV Synthetic NAV: ${nav:.2f}
Current Discount: {disc:.2f}% Ideally 0% is the fair price
PSLV RSI (14-day): {rsi:.2f}  # <30 oversold, >70 overbought
"""

# -----------------------------
# Step 3: Skip sending email
# -----------------------------
# Everything below is commented out
"""
sender_email = "aarondooleykim@gmail.com"
receiver_email = "dkim4@macalester.edu"
app_password = "uxrx oeuf atsl xhba"

msg = MIMEMultipart()
msg['From'] = sender_email
msg['To'] = receiver_email
msg['Subject'] = subject
msg.attach(MIMEText(body, 'plain'))

try:
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(sender_email, app_password)
    server.send_message(msg)
    server.quit()
    print("Email sent successfully!")
except Exception as e:
    print("Error sending email:", e)
"""

# -----------------------------
# Step 4: Print PSLV metrics
# -----------------------------
print(f"Silver Spot Price: ${spot:.2f} — ideally we want $100 when we sell it")
print(f"PSLV Market Price: ${price:.2f} — Sells at $33.18")
print(f"PSLV Synthetic NAV: ${nav:.2f}")
print(f"Current Discount: {disc:.2f}% — Ideally it is negative but sell when it gets positive")
print(f"PSLV RSI (14-day): {rsi:.2f} — Sell when RSI>70")


# %%


# %%
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

# =============================
# CONFIGURATION
# =============================
NEWS_API_KEY = "a7f1d21177364f20a73c91f2c924b0fd"

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
silver_spot = yf.Ticker("SI=F").history(period="1d")["Close"].iloc[-1]
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



