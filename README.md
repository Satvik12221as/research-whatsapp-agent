# Personal News Agent

Phase-based project for building a daily research and WhatsApp news digest agent.

## Phase 1: Research Agent

The research agent collects articles from curated RSS feeds and global search sources, deduplicates them, scores them, stores them in a local SQLite database, and lets you inspect or export the collected research.

Current Phase 1 files:

```text
fetcher.py          RSS fetching, global search, scoring, deduplication, SQLite storage
research_agent.py   Command-line interface for fetch/search/refresh/list/stats/export
daily_agent.py      Daily runner: research first, WhatsApp digest at 11 PM
run_daily_agent.ps1 Windows launcher used by Task Scheduler
setup_daily_task.ps1 Creates the 10 PM daily Windows scheduled task
requirements.txt    Python dependencies
```

The database is created as `news.db` in this project folder by default. You can override it with:

```powershell
$env:NEWS_DB_PATH="C:\path\to\news.db"
```

## Categories

The research agent tracks five categories:

| # | Category |
|---|---|
| 1 | AI & Big Tech |
| 2 | Geopolitics & Military |
| 3 | India & Indian Politics |
| 4 | Social Media |
| 5 | Major Economy Events |

Use this command to see the configured RSS feeds:

```bash
python research_agent.py feeds
```

Use this command to see the global search queries:

```bash
python research_agent.py queries
```

## Research Strategy

The agent uses three discovery layers:

| Layer | Purpose |
|---|---|
| Curated RSS feeds | Reliable watchlist of known high-value sources |
| GDELT search | Global multilingual discovery across worldwide media |
| Google News RSS search | Broad region-aware query discovery |

Each article gets stored with:

- discovery method
- search query, when found by search
- region, when available
- research score
- published and fetched timestamps

The research score is a first-pass triage signal based on recency, high-signal sources, category-specific impact keywords, and discovery method. It is not a final truth score; it helps decide what to inspect first.

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Create your private `.env` file:

```powershell
Copy-Item .env.example .env
notepad .env
```

Fill these values:

```text
GROQ_API_KEY=...
WHATSAPP_PHONE=+91...
CALLMEBOT_APIKEY=...
```

To get the CallMeBot API key, use the currently active WhatsApp setup page:

```text
https://www.callmebot.com/?ae_global_templates=setup-whatsapp
```

Add the listed bot number to WhatsApp contacts and send this exact message:

```text
I allow callmebot to send me messages
```

If the bot does not reply with an API key in 2 minutes, CallMeBot says to try again after 24 hours.

If your system does not have Python on PATH, create a fresh virtual environment:

```bash
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Research Agent Commands

Fetch articles:

```bash
python research_agent.py fetch
```

Run global search discovery:

```bash
python research_agent.py search
```

Search only one category:

```bash
python research_agent.py search --category "Geopolitics & Military"
```

Search with one provider:

```bash
python research_agent.py search --provider gdelt
python research_agent.py search --provider google-news --region india --region asia
```

Run the full research refresh:

```bash
python research_agent.py refresh
```

Fetch fewer articles per source while testing:

```bash
python research_agent.py fetch --max-per-feed 3 --pause 0.2
```

Show database stats:

```bash
python research_agent.py stats
```

List ranked articles:

```bash
python research_agent.py list --hours 24 --limit 20
```

List newest articles instead of highest-scored articles:

```bash
python research_agent.py list --order-by recent --limit 20
```

List one category:

```bash
python research_agent.py list --category "AI & Big Tech" --limit 10
```

Export research to Markdown:

```bash
python research_agent.py export --format md --output research_export.md
```

Export research to JSON:

```bash
python research_agent.py export --format json --output research_export.json
```

## Daily Automation

Target behavior:

```text
10:00 PM  Windows starts the agent automatically
10:00 PM  Research phase runs: curated RSS + global search
11:00 PM  Digest is built and sent on WhatsApp
After send  The agent exits and writes logs
```

Test the full daily workflow without sending WhatsApp:

```powershell
.\run_daily_agent.ps1
```

For faster testing without waiting until 11 PM:

```bash
python daily_agent.py --dry-run --no-wait
```

Once approved, install the daily scheduled task:

```powershell
.\setup_daily_task.ps1
```

This creates a Windows Task Scheduler task named `Personal News Agent` that starts daily at `22:00`.

Logs are written to:

```text
logs/
```

## PC-Off Automation

If your PC is off, Windows Task Scheduler cannot run the agent. The workflow must run from an always-on environment such as:

- Codex cloud automation
- VPS cron job
- Railway/Render scheduled job
- another always-on server

This project now has a Codex cloud automation configured to start daily at 10:00 PM. For it to send WhatsApp successfully, the cloud run must have access to:

```text
GROQ_API_KEY
WHATSAPP_PHONE
CALLMEBOT_APIKEY
```

Check whether the local project is ready:

```bash
python check_setup.py
```

The cloud job can only send the WhatsApp message if those same secrets are available to the cloud execution environment. If the secrets are missing, the run will report which ones are missing instead of pretending it worked.

Useful checks:

```powershell
Get-ScheduledTask -TaskName "Personal News Agent"
Start-ScheduledTask -TaskName "Personal News Agent"
```

## Later Phases

Phase 2: Summarizer agent

- Use Claude or another LLM to rank and summarize the collected stories.
- Keep selection grounded in the `news.db` research database.
- Produce a structured digest object.

Phase 3: WhatsApp delivery

- Format the digest for WhatsApp.
- Send through CallMeBot or another delivery provider.
- Add delivery tests and message chunking.

Phase 4: Scheduler / automation

- Run research collection periodically.
- Build and send the digest at a fixed time.
- Add logging and operational safeguards.
