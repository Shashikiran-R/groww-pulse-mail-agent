"""
Main entry point for Groww App Review Pulse Agent.

Supports CLI flags:
  --now         Run pulse pipeline immediately
  --week W40    Process a specific ISO week (e.g., 2026-W40 or W40)
  --dry-run     Skip MCP delivery (Google Docs & Gmail) and keep files local
  --scrape-only Fetch reviews without downstream processing
  (no flags)    Start APScheduler to run automatically on config.RUN_DAY at config.RUN_HOUR
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from apscheduler.schedulers.blocking import BlockingScheduler

from src.config import config
from src.agent.controller import AgentController

logger = logging.getLogger(__name__)


def run_pipeline_sync(controller: AgentController, week: str | None, dry_run: bool, scrape_only: bool):
    """Run async pipeline synchronously."""
    return asyncio.run(controller.run_weekly_pulse(
        week=week,
        dry_run=dry_run,
        scrape_only=scrape_only,
    ))


def main():
    parser = argparse.ArgumentParser(description="Groww App Review Pulse Agent")
    parser.add_argument("--now", action="store_true", help="Run pulse pipeline immediately")
    parser.add_argument("--week", type=str, help="Process a specific week (e.g., 2026-W40 or W40)")
    parser.add_argument("--dry-run", action="store_true", help="Run pipeline but skip MCP delivery (local only)")
    parser.add_argument("--scrape-only", action="store_true", help="Only fetch reviews and save to raw data")
    parser.add_argument("--web", action="store_true", help="Launch interactive Web Dashboard & Backend API")
    parser.add_argument("--port", type=int, default=8000, help="Port for web dashboard (default: 8000)")
    args = parser.parse_args()

    if args.web:
        import uvicorn
        print("=" * 60)
        print("📈 GROWW APP REVIEW PULSE AGENT — DASHBOARD & BACKEND API")
        print("=" * 60)
        print(f"🌐 Dashboard UI : http://localhost:{args.port}")
        print(f"📑 OpenAPI Docs  : http://localhost:{args.port}/docs")
        print("=" * 60)
        uvicorn.run("src.web.app:app", host="0.0.0.0", port=args.port, reload=False)
        return

    controller = AgentController(config)

    if args.now or args.week or args.dry_run or args.scrape_only:
        logger.info(f"Triggering one-off execution (now={args.now}, week={args.week}, dry_run={args.dry_run}, scrape_only={args.scrape_only})")
        result = run_pipeline_sync(controller, args.week, args.dry_run, args.scrape_only)
        print(f"\n==========================================")
        print(f"Run Finished: Success={result.success} | Duration={result.duration_seconds}s")
        print(f"Week: {result.week} | Scraped: {result.reviews_scraped} | Clean: {result.reviews_clean}")
        print(f"Top Themes: {', '.join(result.top_themes) if result.top_themes else 'None'}")
        if result.doc_url:
            print(f"Google Doc: {result.doc_url}")
        if result.docs_approval_url:
            print(f"📄 Docs Approval URL  : {result.docs_approval_url}")
        if result.gmail_approval_url:
            print(f"✉️  Gmail Approval URL : {result.gmail_approval_url}")
        if result.draft_id:
            print(f"Gmail Draft/Action ID : {result.draft_id}")
        if result.errors:
            print(f"Errors/Warnings: {result.errors}")
        print(f"==========================================\n")
    else:
        scheduler = BlockingScheduler()
        scheduler.add_job(
            lambda: run_pipeline_sync(controller, None, False, False),
            'cron',
            day_of_week=config.RUN_DAY.lower(),
            hour=config.RUN_HOUR,
        )
        print(f"Scheduler started. Will run every {config.RUN_DAY} at {config.RUN_HOUR}:00")
        logger.info(f"Scheduler started. Cron: day_of_week={config.RUN_DAY}, hour={config.RUN_HOUR}")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped by user.")


if __name__ == "__main__":
    main()
