"""
FastAPI Backend Server for Groww App Review Pulse Agent.
Provides REST APIs for:
- Viewing Weekly Pulses (executive summary, themes, verbatim quotes, action items)
- Exploring Reviews & Sentiment Analytics
- Triggering Agent Pipeline Runs & Streaming Live Execution Progress
- Checking MCP Server & Google Workspace Delivery Status
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import glob
import json
import logging
import os
import re
from typing import Any, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import httpx
import markdown

from src.config import config
from src.agent.controller import AgentController

logger = logging.getLogger(__name__)

# Data directory constants
BASE_DIR = os.getcwd()
DATA_DIR = os.getenv("DATA_DIR", os.path.join(BASE_DIR, "data"))
RAW_DATA_DIR = os.path.join(DATA_DIR, "raw")
CLEANED_DATA_DIR = os.path.join(DATA_DIR, "cleaned")
ENRICHED_DATA_DIR = os.path.join(DATA_DIR, "enriched")
CLASSIFIED_DATA_DIR = os.path.join(DATA_DIR, "classified")
PULSE_OUTPUT_DIR = os.path.join(DATA_DIR, "pulses")
RUN_LOG_PATH = os.path.join(DATA_DIR, "run_log.json")

# Ensure all data subdirectories exist at runtime
for _d in [DATA_DIR, RAW_DATA_DIR, CLEANED_DATA_DIR, ENRICHED_DATA_DIR, CLASSIFIED_DATA_DIR, PULSE_OUTPUT_DIR]:
    os.makedirs(_d, exist_ok=True)

# Auto-seed initial historical datasets if a fresh empty volume is mounted
_seed_dir = os.path.join(BASE_DIR, "data_seed")
if os.path.exists(_seed_dir) and not glob.glob(os.path.join(RAW_DATA_DIR, "reviews_*.json")):
    import shutil
    try:
        shutil.copytree(_seed_dir, DATA_DIR, dirs_exist_ok=True)
        logger.info("Seeded initial data from packaged data_seed into persistent volume")
    except Exception as _e:
        logger.warning(f"Could not copy seed data: {_e}")

app = FastAPI(
    title="Groww App Review Pulse Agent API",
    description="Backend API and Dashboard for Groww App Review Pulse Intelligence Agent",
    version="1.0.0",
)

# Enable CORS for local development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


executor = ThreadPoolExecutor(max_workers=2)

# Global execution state tracker
pipeline_state = {
    "status": "idle",  # "idle" | "running" | "completed" | "failed"
    "week": None,
    "dry_run": True,
    "started_at": None,
    "finished_at": None,
    "duration_seconds": None,
    "current_step": "Idle",
    "logs": [],
    "last_result": None,
}


def add_pipeline_log(message: str):
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    entry = f"[{timestamp}] {message}"
    pipeline_state["logs"].append(entry)
    if len(pipeline_state["logs"]) > 200:
        pipeline_state["logs"].pop(0)


# =====================================================================
# API Endpoints
# =====================================================================


@app.get("/api/status")
@app.head("/api/status")
async def get_system_status():
    """Returns agent configuration, models, MCP integration status, and data volume."""
    # Count data files
    raw_files = glob.glob(os.path.join(RAW_DATA_DIR, "reviews_*.json"))
    enriched_files = glob.glob(os.path.join(ENRICHED_DATA_DIR, "enriched_*.json"))
    pulse_files = glob.glob(os.path.join(PULSE_OUTPUT_DIR, "pulse_*.md"))

    return {
        "status": "online",
        "app_name": "Groww App Review Pulse Agent",
        "version": "1.0.0",
        "environment": {
            "llm_provider": "Groq",
            "llm_model": config.GROQ_MODEL,
            "google_play_app_id": config.APP_ID,
            "app_store_id": str(config.APP_STORE_APP_ID),
            "app_store_country": config.APP_STORE_COUNTRY,
            "lookback_weeks": config.LOOKBACK_WEEKS,
            "schedule": f"Every {config.RUN_DAY} at {config.RUN_HOUR:02d}:00",
        },
        "mcp": {
            "server_url": config.MCP_SERVER_URL,
            "auth_configured": bool(config.MCP_AUTH_TOKEN),
            "doc_url": config.GROWW_PULSE_DOC_URL,
            "doc_id": config.GROWW_PULSE_DOC_ID,
        },
        "storage": {
            "raw_batches": len(raw_files),
            "enriched_batches": len(enriched_files),
            "pulses_generated": len(pulse_files),
        },
    }


@app.get("/api/pulses")
async def list_pulses():
    """List all available weekly pulses sorted by week descending."""
    pulse_files = glob.glob(os.path.join(PULSE_OUTPUT_DIR, "pulse_*.md"))
    pulses = []

    for file_path in sorted(pulse_files, reverse=True):
        basename = os.path.basename(file_path)
        match = re.search(r"pulse_(\d{4}-W\d{2})\.md", basename)
        week = match.group(1) if match else basename.replace(".md", "")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            summary_match = re.search(r"\*\*Executive Summary:\*\*\s*(.+)", content)
            summary = summary_match.group(1).strip() if summary_match else "Weekly pulse generated."

            # Extract theme names
            theme_matches = re.findall(r"###\s*\d+\.\s*([^\(\n]+)", content)
            themes = [t.strip() for t in theme_matches]

            mtime = os.path.getmtime(file_path)
            created_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

            pulses.append({
                "week": week,
                "filename": basename,
                "summary": summary,
                "themes": themes,
                "created_at": created_at,
            })
        except Exception as e:
            logger.error(f"Error parsing pulse {file_path}: {e}")

    return {"pulses": pulses, "total": len(pulses)}


@app.get("/api/pulses/{week}")
async def get_pulse_detail(week: str):
    """Retrieve full pulse markdown, HTML rendering, and structured sections."""
    normalized_week = week if week.startswith("20") else f"2026-{week}"
    md_file = os.path.join(PULSE_OUTPUT_DIR, f"pulse_{normalized_week}.md")
    html_file = os.path.join(PULSE_OUTPUT_DIR, f"pulse_{normalized_week}.html")

    if not os.path.exists(md_file):
        raise HTTPException(status_code=404, detail=f"Pulse for week {week} not found")

    with open(md_file, "r", encoding="utf-8") as f:
        md_content = f.read()

    html_content = ""
    if os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as f:
            html_content = f.read()
    else:
        html_content = markdown.markdown(md_content, extensions=["extra", "tables"])

    # Parse structured content
    summary_match = re.search(r"\*\*Executive Summary:\*\*\s*(.+)", md_content)
    summary = summary_match.group(1).strip() if summary_match else ""

    # Parse themes: ### 1. Onboarding / KYC (142 reviews, 78.0% negative) ↑
    theme_blocks = re.findall(
        r"###\s*(\d+)\.\s*([^(]+)\s*\(([^)]+)\)\s*([↑→↓↔🆕]?)[^\n]*\n+([^\n#]+)",
        md_content,
    )
    themes = []
    for rank, title, stats, trend, desc in theme_blocks:
        themes.append({
            "rank": int(rank),
            "title": title.strip(),
            "stats": stats.strip(),
            "trend": trend.strip() or "→",
            "description": desc.strip(),
        })

    # Parse Quotes: > ★★☆☆☆ — "quote text" — *Author, Date*
    quote_matches = re.findall(
        r">\s*([★☆]+)\s*—\s*\"([^\"]+)\"\s*—\s*\*([^*]+)\*",
        md_content,
    )
    quotes = []
    for stars, text, attribution in quote_matches:
        rating = stars.count("★")
        quotes.append({
            "rating": rating,
            "stars": stars,
            "text": text.strip(),
            "attribution": attribution.strip(),
        })

    # Parse Actions: 1. **[KYC]** Action details
    action_matches = re.findall(
        r"\d+\.\s*\*\*\[([^\]]+)\]\*\*\s*([^\n]+)",
        md_content,
    )
    actions = []
    for tag, desc in action_matches:
        actions.append({
            "tag": tag.strip(),
            "description": desc.strip(),
        })

    # Check for approval URLs in latest run log
    doc_approval_url = None
    gmail_approval_url = None
    if os.path.exists(RUN_LOG_PATH):
        try:
            with open(RUN_LOG_PATH, "r", encoding="utf-8") as f:
                log_data = json.load(f)
                if isinstance(log_data, list):
                    for run_data in reversed(log_data):
                        if run_data.get("week") == normalized_week:
                            doc_approval_url = run_data.get("docs_approval_url") or doc_approval_url
                            gmail_approval_url = run_data.get("gmail_approval_url") or gmail_approval_url
                            break
        except Exception as e:
            logger.warning(f"Failed reading run logs: {e}")

    weekly = compute_weekly_metrics()

    return {
        "week": normalized_week,
        "summary": summary,
        "themes": themes,
        "quotes": quotes,
        "actions": actions,
        "metrics": weekly.get(normalized_week),
        "markdown": md_content,
        "html": html_content,
        "doc_url": config.GROWW_PULSE_DOC_URL,
        "docs_approval_url": doc_approval_url,
        "gmail_approval_url": gmail_approval_url,
    }


def compute_weekly_metrics() -> dict[str, dict[str, Any]]:
    """Compute week-by-week review count, store rating, WoW Delta, and dominant sentiment."""
    raw_files = sorted(glob.glob(os.path.join(RAW_DATA_DIR, "reviews_*.json")))
    enr_files = sorted(glob.glob(os.path.join(ENRICHED_DATA_DIR, "enriched_*.json")))

    weekly_data: dict[str, dict[str, Any]] = {}

    for rf in raw_files:
        basename = os.path.basename(rf)
        m = re.search(r"reviews_(\d{4}-W\d{2})\.json", basename)
        if not m:
            continue
        w = m.group(1)
        try:
            with open(rf, "r", encoding="utf-8") as fp:
                reviews = json.load(fp)
            ratings = [
                r.get("rating")
                for r in reviews
                if isinstance(r.get("rating"), (int, float)) and 1 <= r["rating"] <= 5
            ]
            avg_r = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
            weekly_data[w] = {
                "week": w,
                "total_reviews": len(reviews),
                "average_rating": avg_r,
                "ratings_count": len(ratings),
                "sentiment_distribution": {"positive": 0, "negative": 0, "neutral": 0},
                "dominant_sentiment": "Neutral",
                "dominant_sentiment_pct": 0,
            }
        except Exception as e:
            logger.warning(f"Failed parsing raw reviews from {rf}: {e}")

    for ef in enr_files:
        basename = os.path.basename(ef)
        m = re.search(r"enriched_(\d{4}-W\d{2})\.json", basename)
        if not m:
            continue
        w = m.group(1)
        if w not in weekly_data:
            weekly_data[w] = {
                "week": w,
                "total_reviews": 0,
                "average_rating": 0.0,
                "ratings_count": 0,
                "sentiment_distribution": {"positive": 0, "negative": 0, "neutral": 0},
                "dominant_sentiment": "Neutral",
                "dominant_sentiment_pct": 0,
            }
        try:
            with open(ef, "r", encoding="utf-8") as fp:
                reviews = json.load(fp)
            sents = {"positive": 0, "negative": 0, "neutral": 0}
            for r in reviews:
                lbl = str(r.get("sentiment_label", "")).lower()
                if "pos" in lbl:
                    sents["positive"] += 1
                elif "neg" in lbl:
                    sents["negative"] += 1
                else:
                    sents["neutral"] += 1

            total_s = sum(sents.values()) or 1
            dom = max(sents.items(), key=lambda x: x[1])[0]
            dom_pct = round((sents[dom] / total_s) * 100)
            weekly_data[w]["sentiment_distribution"] = sents
            weekly_data[w]["dominant_sentiment"] = dom.capitalize()
            weekly_data[w]["dominant_sentiment_pct"] = dom_pct
        except Exception as e:
            logger.warning(f"Failed parsing enriched reviews from {ef}: {e}")

    sorted_weeks = sorted(weekly_data.keys())
    for i, w in enumerate(sorted_weeks):
        if i > 0:
            prev_w = sorted_weeks[i - 1]
            prev_r = weekly_data[prev_w]["average_rating"]
            curr_r = weekly_data[w]["average_rating"]
            delta = round(((curr_r - prev_r) / prev_r) * 100, 1) if prev_r > 0 else 0.0
            weekly_data[w]["previous_week"] = prev_w
            weekly_data[w]["previous_rating"] = prev_r
            weekly_data[w]["wow_delta_pct"] = delta
        else:
            weekly_data[w]["previous_week"] = None
            weekly_data[w]["previous_rating"] = None
            weekly_data[w]["wow_delta_pct"] = None

    # Filter to only show data from 2026-W20 to latest week available, removing all older weeks
    enr_weeks = [
        re.search(r"(\d{4}-W\d{2})", f).group(1)
        for f in enr_files
        if re.search(r"(\d{4}-W\d{2})", f)
    ]
    latest_week = max(enr_weeks) if enr_weeks else "2026-W40"
    weekly_data = {
        w: data for w, data in weekly_data.items()
        if "2026-W20" <= w <= latest_week
    }

    return weekly_data


@app.get("/api/metrics")
async def get_metrics(week: Optional[str] = None):
    """Compute aggregate analytics across all enriched/cleaned review datasets and weekly stats."""
    enriched_files = glob.glob(os.path.join(ENRICHED_DATA_DIR, "enriched_*.json"))
    raw_files = glob.glob(os.path.join(RAW_DATA_DIR, "reviews_*.json"))
    weekly = compute_weekly_metrics()

    total_raw = 0
    for f in raw_files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                total_raw += len(data)
        except Exception:
            pass

    total_enriched = 0
    sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
    theme_counts: dict[str, int] = {}
    rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    source_counts = {"playstore": 0, "appstore": 0}

    for f in enriched_files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                reviews = json.load(fp)
                total_enriched += len(reviews)
                for r in reviews:
                    # Sentiment
                    label = r.get("sentiment_label", "neutral")
                    sentiment_counts[label] = sentiment_counts.get(label, 0) + 1

                    # Theme
                    th = r.get("theme") or "Unclassified"
                    theme_counts[th] = theme_counts.get(th, 0) + 1

                    # Rating
                    rt = r.get("rating")
                    if rt and isinstance(rt, int) and 1 <= rt <= 5:
                        rating_counts[rt] = rating_counts.get(rt, 0) + 1

                    # Source
                    src = r.get("source", "playstore")
                    source_counts[src] = source_counts.get(src, 0) + 1
        except Exception as e:
            logger.error(f"Failed parsing metrics from {f}: {e}")

    # Top themes sorted
    sorted_themes = sorted(
        [{"theme": k, "count": v} for k, v in theme_counts.items() if k != "Unclassified"],
        key=lambda x: x["count"],
        reverse=True,
    )

    avg_rating = 0.0
    total_rated = sum(rating_counts.values())
    if total_rated > 0:
        avg_rating = round(sum(k * v for k, v in rating_counts.items()) / total_rated, 2)

    return {
        "total_raw_reviews": total_raw,
        "total_enriched_reviews": total_enriched,
        "average_rating": avg_rating,
        "ratings_distribution": rating_counts,
        "sentiment_distribution": sentiment_counts,
        "top_themes": sorted_themes[:6],
        "sources": source_counts,
        "weekly": weekly,
        "week_metrics": weekly.get(week) if week else None,
    }


@app.get("/api/reviews")
async def list_reviews(
    week: Optional[str] = None,
    theme: Optional[str] = None,
    sentiment: Optional[str] = None,
    rating: Optional[int] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Filter and paginate through enriched review records."""
    files = []
    if week:
        normalized_week = week if week.startswith("20") else f"2026-{week}"
        target = os.path.join(ENRICHED_DATA_DIR, f"enriched_{normalized_week}.json")
        if os.path.exists(target):
            files.append(target)
    else:
        files = sorted(glob.glob(os.path.join(ENRICHED_DATA_DIR, "enriched_*.json")), reverse=True)

    all_reviews = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                all_reviews.extend(json.load(fp))
        except Exception:
            pass

    # Apply filters
    filtered = []
    for r in all_reviews:
        if theme and r.get("theme", "").lower() != theme.lower():
            continue
        if sentiment and r.get("sentiment_label", "").lower() != sentiment.lower():
            continue
        if rating and r.get("rating") != rating:
            continue
        if source and r.get("source", "").lower() != source.lower():
            continue
        if search:
            q = search.lower()
            text_match = q in (r.get("text") or "").lower()
            author_match = q in (r.get("author") or "").lower()
            if not (text_match or author_match):
                continue
        filtered.append(r)

    total_filtered = len(filtered)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_items = filtered[start_idx:end_idx]

    return {
        "page": page,
        "page_size": page_size,
        "total": total_filtered,
        "total_pages": (total_filtered + page_size - 1) // page_size if total_filtered > 0 else 1,
        "reviews": paginated_items,
    }


@app.get("/api/runs")
async def list_runs():
    """Retrieve execution history from run_log.json."""
    if not os.path.exists(RUN_LOG_PATH):
        return {"runs": [], "total": 0}

    runs = []
    try:
        with open(RUN_LOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                runs = data
    except Exception as e:
        logger.warning(f"Error loading runs: {e}")

    return {"runs": list(reversed(runs)), "total": len(runs)}


@app.get("/api/pipeline/status")
async def get_pipeline_status():
    """Current live execution status and stream of pipeline logs."""
    return pipeline_state


def _execute_pipeline_task(week: Optional[str], dry_run: bool, scrape_only: bool):
    """Background worker executing the weekly pulse pipeline."""
    pipeline_state["status"] = "running"
    pipeline_state["week"] = week
    pipeline_state["dry_run"] = dry_run
    pipeline_state["started_at"] = datetime.now(timezone.utc).isoformat()
    pipeline_state["finished_at"] = None
    pipeline_state["current_step"] = "Initializing Agent Controller..."
    pipeline_state["logs"] = []

    add_pipeline_log(f"Starting pipeline execution: week={week or 'current'}, dry_run={dry_run}, scrape_only={scrape_only}")

    start_time = datetime.now()
    try:
        controller = AgentController(config)
        add_pipeline_log("AgentController initialized successfully.")

        add_pipeline_log("Phase 2: Review Ingestion starting...")
        pipeline_state["current_step"] = "Ingesting Reviews..."

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            controller.run_weekly_pulse(
                week=week,
                dry_run=dry_run,
                scrape_only=scrape_only,
            )
        )
        loop.close()

        duration = round((datetime.now() - start_time).total_seconds(), 2)
        pipeline_state["status"] = "completed" if result.success else "failed"
        pipeline_state["finished_at"] = datetime.now(timezone.utc).isoformat()
        pipeline_state["duration_seconds"] = duration
        pipeline_state["current_step"] = "Completed" if result.success else "Failed with errors"
        pipeline_state["last_result"] = {
            "success": result.success,
            "week": result.week,
            "reviews_scraped": result.reviews_scraped,
            "reviews_clean": result.reviews_clean,
            "top_themes": result.top_themes,
            "doc_url": result.doc_url,
            "docs_approval_url": result.docs_approval_url,
            "gmail_approval_url": result.gmail_approval_url,
            "draft_id": result.draft_id,
            "duration_seconds": duration,
            "errors": result.errors,
        }
        add_pipeline_log(f"Pipeline finished in {duration}s! Success={result.success}. Top themes: {result.top_themes}")
    except Exception as e:
        logger.exception("Pipeline execution failed")
        duration = round((datetime.now() - start_time).total_seconds(), 2)
        pipeline_state["status"] = "failed"
        pipeline_state["finished_at"] = datetime.now(timezone.utc).isoformat()
        pipeline_state["duration_seconds"] = duration
        pipeline_state["current_step"] = f"Error: {str(e)}"
        add_pipeline_log(f"Execution Error: {str(e)}")


@app.post("/api/pipeline/run")
async def trigger_pipeline(
    background_tasks: BackgroundTasks,
    payload: dict[str, Any] = None,
):
    """Trigger a new weekly pulse run."""
    if pipeline_state["status"] == "running":
        raise HTTPException(status_code=409, detail="Pipeline run is already in progress.")

    payload = payload or {}
    week = payload.get("week")
    dry_run = payload.get("dry_run", False)
    scrape_only = payload.get("scrape_only", False)

    background_tasks.add_task(_execute_pipeline_task, week, dry_run, scrape_only)

    return {
        "message": "Pipeline run dispatched successfully.",
        "week": week or "current",
        "dry_run": dry_run,
        "scrape_only": scrape_only,
    }


@app.post("/api/mcp/ping")
async def ping_mcp_server():
    """Verify live HTTP health check of remote MCP server."""
    url = f"{config.MCP_SERVER_URL.rstrip('/')}/health"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            return {
                "server_url": config.MCP_SERVER_URL,
                "status_code": resp.status_code,
                "response": resp.json() if resp.status_code == 200 else resp.text,
                "healthy": resp.status_code == 200,
            }
    except Exception as e:
        return {
            "server_url": config.MCP_SERVER_URL,
            "healthy": False,
            "error": str(e),
        }


# Mount static files for the frontend dashboard
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    @app.head("/")
    async def serve_index():
        return FileResponse(os.path.join(static_dir, "index.html"))
