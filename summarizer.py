import json
import os
import time
from datetime import datetime

import requests

from fetcher import get_todays_articles, mark_used


GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "YOUR_API_KEY_HERE")
MAX_ARTICLES_PER_CATEGORY_PROMPT = 12

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


def call_groq(prompt, retries=2):
    if not GROQ_API_KEY or GROQ_API_KEY in {"YOUR_API_KEY_HERE", "your-groq-key-here"}:
        raise RuntimeError("GROQ_API_KEY is missing.")

    for attempt in range(retries + 1):
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
            },
            timeout=45,
        )

        if response.status_code == 429 and attempt < retries:
            retry_after = response.headers.get("Retry-After")
            wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else 20
            print(f"  Groq rate limit hit. Waiting {wait_seconds}s before retry...")
            time.sleep(wait_seconds)
            continue

        response.raise_for_status()
        payload = response.json()
        if "choices" not in payload:
            raise RuntimeError(f"Unexpected Groq response: {payload}")
        return payload["choices"][0]["message"]["content"]

    raise RuntimeError("Groq request failed after retries.")


def text_or_empty(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def normalize_stories(payload):
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        candidates = (
            payload.get("stories")
            or payload.get("articles")
            or payload.get("items")
            or payload.get("digest")
            or []
        )
    else:
        candidates = []

    stories = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        title = text_or_empty(item.get("title") or item.get("headline")).strip()
        summary = text_or_empty(item.get("summary") or item.get("description")).strip()
        url = text_or_empty(item.get("url") or item.get("link")).strip()
        source = text_or_empty(item.get("source")).strip()
        if not title or not summary:
            continue
        stories.append(
            {
                "title": title,
                "summary": summary,
                "source": source,
                "url": url,
            }
        )
    return stories[:5]


def fallback_stories(articles):
    stories = []
    for title, url, summary, _cat, source in articles[:5]:
        title = text_or_empty(title).strip()
        summary = text_or_empty(summary).strip() or title
        source = text_or_empty(source).strip()
        url = text_or_empty(url).strip()
        if not title:
            continue
        stories.append(
            {
                "title": title[:90],
                "summary": summary[:450],
                "source": source,
                "url": url,
            }
        )
    return stories


def pick_and_summarize(category, articles):
    """Given raw articles for a category, pick top 5 and summarize each."""
    if not articles:
        return []

    prompt_articles = articles[:MAX_ARTICLES_PER_CATEGORY_PROMPT]
    article_list = ""
    for i, (title, url, summary, _cat, source) in enumerate(prompt_articles):
        snippet = text_or_empty(summary)[:300]
        article_list += (
            f"\n[{i + 1}] Title: {title}\n"
            f"Source: {source}\n"
            f"URL: {url}\n"
            f"Snippet: {snippet}\n"
        )

    context = CATEGORY_CONTEXT.get(category, "")

    prompt = f"""You are a news curator for a personal daily digest.

Category: {category}
Context: {context}

Here are today's articles for this category:
{article_list}

Your task:
1. Pick the TOP 5 most significant, interesting, and non-duplicate stories
2. For each, write a 3-4 line summary in simple, clear English
3. Prioritize: impact, recency, significance - avoid PR fluff and minor updates

Return ONLY valid JSON in this exact format, nothing else:
{{
  "stories": [
    {{
      "title": "Short punchy headline (max 10 words)",
      "summary": "3-4 line summary of the story. What happened, why it matters, what's next.",
      "source": "Source name",
      "url": "article url"
    }}
  ]
}}

If fewer than 5 good stories exist, return what's available. Never make up stories."""

    try:
        result = call_groq(prompt).strip()
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        payload = json.loads(result)
        return normalize_stories(payload)
    except Exception as exc:
        print(f"  ! Groq error for {category}: {exc}")
        print("  Using fallback article snippets for this category.")
        return fallback_stories(articles)


def build_digest():
    """Build the full digest - 5 stories per category."""
    print(f"Building digest at {datetime.now().strftime('%H:%M')}...")

    all_articles = get_todays_articles()
    if not all_articles:
        print("No articles found. Run fetcher.py first.")
        return None

    by_category = {cat: [] for cat in CATEGORIES}
    for row in all_articles:
        title, url, summary, category, source = row
        if category in by_category:
            by_category[category].append((title, url, summary, category, source))

    digest = {}
    used_urls = []

    for category in CATEGORIES:
        articles = by_category[category]
        print(f"  {category}: {len(articles)} articles found -> picking top 5...")
        stories = pick_and_summarize(category, articles)
        digest[category] = stories
        used_urls.extend([s["url"] for s in stories if s.get("url")])
        print(f"     {len(stories)} stories selected")
        time.sleep(4)

    mark_used(used_urls)
    if not any(digest.values()):
        return None
    return digest


def format_whatsapp_message(digest):
    """Format digest into a clean WhatsApp message."""
    now = datetime.now().strftime("%B %d, %Y")

    labels = {
        "AI & Big Tech": "[AI]",
        "Geopolitics & Military": "[WORLD]",
        "India & Indian Politics": "[INDIA]",
        "Social Media": "[SOCIAL]",
        "Major Economy Events": "[ECON]",
    }

    msg = f"*DAILY DIGEST - {now}*\n"
    msg += "------------------------------\n\n"

    for category in CATEGORIES:
        stories = digest.get(category, [])
        if not stories:
            continue
        label = labels.get(category, "[NEWS]")
        msg += f"{label} *{category.upper()}*\n\n"
        for i, story in enumerate(stories, 1):
            title = text_or_empty(story.get("title")).strip()
            summary = text_or_empty(story.get("summary")).strip()
            if not title or not summary:
                continue
            msg += f"*{i}. {title}*\n"
            msg += f"{summary}\n"
            msg += f"Source: {story.get('source', '')} | {story.get('url', '')}\n\n"
        msg += "------------------------------\n\n"

    msg += "_Sent by your personal news agent at 11 PM_"
    return msg


if __name__ == "__main__":
    digest = build_digest()
    if digest:
        msg = format_whatsapp_message(digest)
        print("\n" + "=" * 50)
        print("PREVIEW OF TONIGHT'S WHATSAPP MESSAGE:")
        print("=" * 50)
        print(msg)
