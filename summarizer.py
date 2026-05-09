import requests
import json
import os
import sqlite3
from datetime import datetime, timedelta
from fetcher import get_todays_articles, mark_used

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "YOUR_API_KEY_HERE")

CATEGORIES = [
    "AI & Big Tech",
    "Geopolitics & Military",
    "India & Indian Politics",
    "Social Media",
    "Major Economy Events",
]

CATEGORY_CONTEXT = {
    "AI & Big Tech": "Focus on OpenAI, Google DeepMind, Meta AI, Anthropic, Apple AI, Microsoft AI, model releases, AI policy, and major tech company moves.",
    "Geopolitics & Military": "Focus on wars, conflicts, diplomatic developments, sanctions, international alliances, defense deals, and major military events worldwide.",
    "India & Indian Politics": "Focus on Indian government decisions, parliament, Supreme Court, state elections, foreign policy, Modi government, opposition, and major domestic events.",
    "Social Media": "Focus on major platform changes (X/Twitter, Instagram, YouTube, TikTok, LinkedIn), viral trends, regulatory actions, and business moves by social platforms.",
    "Major Economy Events": "Focus ONLY on major events: Fed/RBI interest rate decisions, stock market crashes or rallies >2%, major trade wars, recession signals, and global financial crises.",
}

def call_claude(prompt):
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 4000,
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    return response.json()["content"][0]["text"]

def pick_and_summarize(category, articles):
    """Given raw articles for a category, pick top 5 and summarize each."""
    if not articles:
        return []

    # Build article list for Claude
    article_list = ""
    for i, (title, url, summary, cat, source) in enumerate(articles):
        article_list += f"\n[{i+1}] Title: {title}\nSource: {source}\nURL: {url}\nSnippet: {summary[:300]}\n"

    context = CATEGORY_CONTEXT.get(category, "")

    prompt = f"""You are a news curator for a personal daily digest. 

Category: {category}
Context: {context}

Here are today's articles for this category:
{article_list}

Your task:
1. Pick the TOP 5 most significant, interesting, and non-duplicate stories
2. For each, write a 3-4 line summary in simple, clear English
3. Prioritize: impact, recency, significance — avoid PR fluff and minor updates

Return ONLY valid JSON in this exact format, nothing else:
[
  {{
    "title": "Short punchy headline (max 10 words)",
    "summary": "3-4 line summary of the story. What happened, why it matters, what's next.",
    "source": "Source name",
    "url": "article url"
  }}
]

If fewer than 5 good stories exist, return what's available. Never make up stories."""

    try:
        result = call_claude(prompt)
        # Clean up response
        result = result.strip()
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        stories = json.loads(result)
        return stories[:5]
    except Exception as e:
        print(f"  ⚠️  Claude error for {category}: {e}")
        return []

def build_digest():
    """Build the full digest — 5 stories per category."""
    print(f"🧠 Building digest at {datetime.now().strftime('%H:%M')}...")
    
    all_articles = get_todays_articles()
    if not all_articles:
        print("❌ No articles found. Run fetcher.py first.")
        return None

    # Group by category
    by_category = {cat: [] for cat in CATEGORIES}
    for row in all_articles:
        title, url, summary, category, source = row
        if category in by_category:
            by_category[category].append(row)

    digest = {}
    used_urls = []

    for category in CATEGORIES:
        articles = by_category[category]
        print(f"  📂 {category}: {len(articles)} articles found → picking top 5...")
        stories = pick_and_summarize(category, articles)
        digest[category] = stories
        used_urls.extend([s["url"] for s in stories if "url" in s])
        print(f"     ✅ {len(stories)} stories selected")

    mark_used(used_urls)
    return digest

def format_whatsapp_message(digest):
    """Format digest into a clean WhatsApp message."""
    now = datetime.now().strftime("%B %d, %Y")
    
    ICONS = {
        "AI & Big Tech": "🤖",
        "Geopolitics & Military": "🌍",
        "India & Indian Politics": "🇮🇳",
        "Social Media": "📱",
        "Major Economy Events": "📉",
    }

    msg = f"📰 *DAILY DIGEST — {now}*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    for category in CATEGORIES:
        stories = digest.get(category, [])
        if not stories:
            continue
        icon = ICONS.get(category, "📌")
        msg += f"{icon} *{category.upper()}*\n\n"
        for i, story in enumerate(stories, 1):
            msg += f"*{i}. {story['title']}*\n"
            msg += f"{story['summary']}\n"
            msg += f"🔗 {story.get('source', '')} | {story.get('url', '')}\n\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    msg += f"_Sent by your personal news agent at 11 PM_ 🕚"
    return msg

if __name__ == "__main__":
    digest = build_digest()
    if digest:
        msg = format_whatsapp_message(digest)
        print("\n" + "="*50)
        print("PREVIEW OF TONIGHT'S WHATSAPP MESSAGE:")
        print("="*50)
        print(msg)
