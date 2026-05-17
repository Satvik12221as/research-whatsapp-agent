import argparse
import json
from datetime import datetime
from pathlib import Path

from fetcher import (
    DB_PATH,
    FEEDS,
    SEARCH_LOCALES,
    SEARCH_PROFILES,
    fetch_all,
    get_articles,
    get_stats,
    search_global,
)


def print_stats(_args):
    total, rows = get_stats()
    print(f"Database: {DB_PATH}")
    print(f"Total articles: {total}")
    print()
    if not rows:
        print("No articles stored yet. Run: python research_agent.py fetch")
        return

    for row in rows:
        print(
            f"{row['category']}: {row['total']} total, "
            f"{row['unused']} unused, avg score {row['avg_score']}"
        )


def print_articles(args):
    rows = get_articles(
        hours=args.hours,
        category=args.category,
        unused_only=args.unused_only,
        limit=args.limit,
        order_by=args.order_by,
    )
    if not rows:
        print("No matching articles found.")
        return

    for index, row in enumerate(rows, start=1):
        published = row["published_at"] or row["fetched_at"]
        print(f"\n{index}. {row['title']}")
        print(f"   Category : {row['category']}")
        print(f"   Source   : {row['source']}")
        print(f"   Date     : {published}")
        print(f"   Method   : {row['discovery_method']} | Score: {row['research_score']}")
        if row["search_query"]:
            print(f"   Query    : {row['search_query']}")
        if row["region"]:
            print(f"   Region   : {row['region']}")
        print(f"   URL      : {row['url']}")
        if row["summary"]:
            print(f"   Summary  : {row['summary']}")


def export_articles(args):
    rows = get_articles(
        hours=args.hours,
        category=args.category,
        unused_only=args.unused_only,
        limit=args.limit,
        order_by=args.order_by,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "json":
        payload = [dict(row) for row in rows]
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    else:
        lines = [
            f"# Research Export - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            f"Articles: {len(rows)}",
            "",
        ]
        for index, row in enumerate(rows, start=1):
            lines.extend(
                [
                    f"## {index}. {row['title']}",
                    "",
                    f"- Category: {row['category']}",
                    f"- Source: {row['source']}",
                    f"- Published: {row['published_at'] or row['fetched_at']}",
                    f"- Method: {row['discovery_method']}",
                    f"- Score: {row['research_score']}",
                    f"- Query: {row['search_query'] or ''}",
                    f"- Region: {row['region'] or ''}",
                    f"- URL: {row['url']}",
                    "",
                    row["summary"] or "",
                    "",
                ]
            )
        output_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Exported {len(rows)} articles to {output_path}")


def fetch_articles(args):
    fetch_all(max_per_feed=args.max_per_feed, pause_seconds=args.pause)


def search_articles(args):
    providers = []
    if args.provider in ("all", "gdelt"):
        providers.append("gdelt")
    if args.provider in ("all", "google-news"):
        providers.append("google_news")
    search_global(
        categories=[args.category] if args.category else None,
        providers=providers,
        regions=args.region,
        hours=args.hours,
        max_records=args.max_records,
        pause_seconds=args.pause,
    )


def refresh_research(args):
    print("Step 1/2: Fetching curated RSS feeds")
    fetch_all(max_per_feed=args.max_per_feed, pause_seconds=args.pause)
    print("\nStep 2/2: Running global search discovery")
    search_global(
        categories=[args.category] if args.category else None,
        hours=args.hours,
        max_records=args.max_records,
        pause_seconds=args.pause,
    )


def build_parser():
    parser = argparse.ArgumentParser(
        description="Phase 1 research agent: fetch, globally search, rank, inspect, and export articles."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch = subparsers.add_parser("fetch", help="Fetch articles from all configured RSS feeds.")
    fetch.add_argument("--max-per-feed", type=int, default=10)
    fetch.add_argument("--pause", type=float, default=0.5, help="Delay between feed requests.")
    fetch.set_defaults(func=fetch_articles)

    search = subparsers.add_parser("search", help="Run global search discovery via GDELT/Google News.")
    search.add_argument("--category", choices=list(SEARCH_PROFILES.keys()))
    search.add_argument("--provider", choices=["all", "gdelt", "google-news"], default="all")
    search.add_argument("--region", choices=list(SEARCH_LOCALES.keys()), action="append")
    search.add_argument("--hours", type=int, default=24)
    search.add_argument("--max-records", type=int, default=20)
    search.add_argument("--pause", type=float, default=0.5, help="Delay between search requests.")
    search.set_defaults(func=search_articles)

    refresh = subparsers.add_parser("refresh", help="Run curated RSS fetch plus global search discovery.")
    refresh.add_argument("--category", choices=list(SEARCH_PROFILES.keys()))
    refresh.add_argument("--hours", type=int, default=24)
    refresh.add_argument("--max-per-feed", type=int, default=10)
    refresh.add_argument("--max-records", type=int, default=20)
    refresh.add_argument("--pause", type=float, default=0.5)
    refresh.set_defaults(func=refresh_research)

    stats = subparsers.add_parser("stats", help="Show stored article counts by category.")
    stats.set_defaults(func=print_stats)

    list_cmd = subparsers.add_parser("list", help="List stored articles.")
    add_article_filters(list_cmd)
    list_cmd.set_defaults(func=print_articles)

    export = subparsers.add_parser("export", help="Export stored articles to JSON or Markdown.")
    add_article_filters(export)
    export.add_argument("--format", choices=["json", "md"], default="md")
    export.add_argument("--output", default="research_export.md")
    export.set_defaults(func=export_articles)

    feeds = subparsers.add_parser("feeds", help="List configured categories and RSS feeds.")
    feeds.set_defaults(func=print_feeds)

    queries = subparsers.add_parser("queries", help="List global search queries by category.")
    queries.set_defaults(func=print_queries)

    return parser


def add_article_filters(parser):
    parser.add_argument("--hours", type=int, default=24, help="Look back this many fetched hours.")
    parser.add_argument("--category", choices=list(FEEDS.keys()))
    parser.add_argument("--unused-only", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--order-by", choices=["score", "recent"], default="score")


def print_feeds(_args):
    for category, feeds in FEEDS.items():
        print(f"\n{category}")
        for feed in feeds:
            print(f"  - {feed}")


def print_queries(_args):
    for category, queries in SEARCH_PROFILES.items():
        print(f"\n{category}")
        for query in queries:
            print(f"  - {query}")


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

