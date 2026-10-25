"""
Agent Controller — Orchestration of the complete end-to-end Groww pulse pipeline.

Chains: Scraper -> DataPipeline -> ThemeClusterer -> QuoteScorer ->
        PulseGenerator -> MCPDocsPublisher -> MCPGmailDrafter -> Run Logging.
"""

from __future__ import annotations

import json
import time
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from src.config import config
from src.ingestion.scraper import ReviewScraper
from src.pipeline.pipeline import DataPipeline
from src.classification.clusterer import ThemeClusterer
from src.classification.quote_scorer import QuoteScorer
from src.generation.pulse_generator import PulseGenerator, PulseOutput
from src.delivery.mcp_docs import MCPDocsPublisher
from src.delivery.mcp_gmail import MCPGmailDrafter
from src.delivery.mcp_client import DeliveryError

logger = logging.getLogger(__name__)

RUN_LOG_PATH = Path("data/run_log.json")


@dataclass
class RunResult:
    """Outcome and metrics of a weekly pulse run."""
    success: bool
    week: str
    reviews_scraped: int
    reviews_clean: int
    top_themes: list[str]
    doc_url: str | None
    draft_id: str | None
    docs_action_id: str | None = None
    docs_approval_url: str | None = None
    gmail_action_id: str | None = None
    gmail_approval_url: str | None = None
    errors: list[str] = None
    duration_seconds: float = 0.0
    reviews_noise: int = 0
    reviews_spam: int = 0
    reviews_excluded_language: int = 0

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.gmail_action_id is None and self.draft_id is not None:
            self.gmail_action_id = self.draft_id
        elif self.draft_id is None and self.gmail_action_id is not None:
            self.draft_id = self.gmail_action_id


def _normalize_week(week_str: str | None) -> str:
    """Normalize week string, converting 'W40' -> '2026-W40' if missing year."""
    if not week_str:
        now = datetime.now(timezone.utc)
        iso_year, iso_week, _ = now.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"

    w = week_str.strip()
    if w.startswith("W") and len(w) <= 4:
        return f"2026-{w}"
    return w


def _get_previous_week_str(week_str: str) -> str | None:
    """Compute previous ISO week string, e.g. '2026-W40' -> '2026-W39'."""
    try:
        parts = week_str.split("-W")
        year = int(parts[0])
        week = int(parts[1])
        if week > 1:
            return f"{year}-W{week - 1:02d}"
        else:
            return f"{year - 1}-W52"
    except Exception:
        return None


class AgentController:
    """
    Main orchestrator for weekly app review pulse generation and delivery.
    """

    def __init__(self, cfg=None):
        self.config = cfg or config
        self.scraper = ReviewScraper(
            app_id=self.config.APP_ID,
            lookback_weeks=self.config.LOOKBACK_WEEKS,
            app_store_id=self.config.APP_STORE_APP_ID,
            app_store_name=self.config.APP_STORE_APP_NAME,
            app_store_country=self.config.APP_STORE_COUNTRY,
            min_words=getattr(self.config, "MIN_REVIEW_WORDS", 10),
        )
        self.pipeline = DataPipeline(self.config)
        self.clusterer = ThemeClusterer(batch_size=self.config.LLM_BATCH_SIZE)
        self.quote_scorer = QuoteScorer()
        self.pulse_generator = PulseGenerator()

        # MCP Delivery wrappers (gracefully initialize or handle missing configs)
        try:
            self.docs_publisher = MCPDocsPublisher()
        except Exception as e:
            logger.warning(f"MCP Docs publisher initialization warning: {e}")
            self.docs_publisher = None

        try:
            self.gmail_drafter = MCPGmailDrafter()
        except Exception as e:
            logger.warning(f"MCP Gmail drafter initialization warning: {e}")
            self.gmail_drafter = None

    def _load_previous_themes(self, previous_week: str) -> list[dict] | None:
        """Load and rank previous week's classified data if available."""
        classified_file = Path(f"data/classified/classified_{previous_week}.json")
        if classified_file.exists():
            try:
                with open(classified_file, "r", encoding="utf-8") as f:
                    prev_reviews = json.load(f)
                return self.clusterer.rank_themes(prev_reviews)
            except Exception as e:
                logger.warning(f"Could not load previous week themes from {classified_file}: {e}")
        return None

    def _append_run_log(self, result: RunResult) -> None:
        """Append run result to data/run_log.json."""
        RUN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        log_entries = []
        if RUN_LOG_PATH.exists():
            try:
                with open(RUN_LOG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        log_entries = data
            except Exception as e:
                logger.warning(f"Failed to read existing run log: {e}")

        log_item = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "week": result.week,
            "success": result.success,
            "reviews_scraped": result.reviews_scraped,
            "reviews_clean": result.reviews_clean,
            "reviews_noise": result.reviews_noise,
            "reviews_spam": result.reviews_spam,
            "reviews_excluded_language": result.reviews_excluded_language,
            "top_themes": result.top_themes,
            "doc_url": result.doc_url,
            "docs_action_id": result.docs_action_id,
            "docs_approval_url": result.docs_approval_url,
            "gmail_action_id": result.gmail_action_id or result.draft_id,
            "draft_id": result.draft_id or result.gmail_action_id,
            "gmail_approval_url": result.gmail_approval_url,
            "errors": result.errors,
            "duration_seconds": result.duration_seconds,
        }
        log_entries.append(log_item)

        try:
            with open(RUN_LOG_PATH, "w", encoding="utf-8") as f:
                json.dump(log_entries, f, indent=2, ensure_ascii=False)
            logger.info(f"Appended run result to {RUN_LOG_PATH}")
        except Exception as e:
            logger.error(f"Failed to save run log: {e}")

    async def run_weekly_pulse(
        self,
        week: str | None = None,
        dry_run: bool = False,
        scrape_only: bool = False,
    ) -> RunResult:
        """
        Execute the full automated weekly pulse pipeline.

        1. Scrape reviews (or load existing week data)
        2. Run data pipeline (6 stages)
        3. Classify themes
        4. Select quotes
        5. Generate pulse report (Markdown & HTML)
        6. Publish to Google Docs (unless dry_run)
        7. Draft Gmail email (unless dry_run)
        8. Log run metrics to data/run_log.json
        """
        start_time = time.time()
        errors: list[str] = []
        target_week = _normalize_week(week)
        logger.info(f"Starting weekly pulse run for week {target_week} (dry_run={dry_run}, scrape_only={scrape_only})...")

        raw_reviews: list[dict] = []
        scraped_count = 0

        # Step 1: Ingestion
        try:
            raw_file = Path(f"data/raw/reviews_{target_week}.json")
            if week and raw_file.exists():
                logger.info(f"Loading existing raw reviews for {target_week} from {raw_file}")
                with open(raw_file, "r", encoding="utf-8") as f:
                    raw_reviews = json.load(f)
                scraped_count = len(raw_reviews)
            else:
                logger.info(f"Scraping fresh reviews for app {self.config.APP_ID}...")
                raw_reviews = self.scraper.scrape()
                self.scraper.save(raw_reviews)
                scraped_count = len(raw_reviews)

            if scrape_only:
                duration = round(time.time() - start_time, 2)
                res = RunResult(
                    success=True,
                    week=target_week,
                    reviews_scraped=scraped_count,
                    reviews_clean=0,
                    top_themes=[],
                    doc_url=None,
                    draft_id=None,
                    errors=[],
                    duration_seconds=duration,
                )
                self._append_run_log(res)
                logger.info(f"Scrape-only complete. Scraped {scraped_count} reviews in {duration}s.")
                return res

        except Exception as e:
            logger.error(f"Ingestion step failed: {e}")
            errors.append(f"Ingestion error: {e}")

        # If no reviews fetched or available, return failure
        if not raw_reviews:
            logger.error("No reviews available to process.")
            duration = round(time.time() - start_time, 2)
            res = RunResult(
                success=False,
                week=target_week,
                reviews_scraped=0,
                reviews_clean=0,
                top_themes=[],
                doc_url=None,
                draft_id=None,
                errors=errors or ["No reviews available to process"],
                duration_seconds=duration,
            )
            self._append_run_log(res)
            return res

        # Step 2: Data Pipeline (Cleaning, Normalisation, Filtering, Sentiment, Enrichment)
        clean_reviews: list[dict] = []
        noise_count = 0
        spam_count = 0
        excluded_lang_count = 0

        try:
            clean_reviews = self.pipeline.run(raw_reviews)
            # Count filter stats
            for r in raw_reviews:
                qflag = r.get("quality_flag")
                if qflag == "noise":
                    noise_count += 1
                elif qflag == "spam":
                    spam_count += 1
                elif qflag == "excluded_language":
                    excluded_lang_count += 1
        except Exception as e:
            logger.error(f"Data pipeline stage failed: {e}")
            errors.append(f"Data pipeline error: {e}")

        clean_count = len(clean_reviews)
        if clean_count == 0:
            logger.warning("Pipeline yielded zero clean reviews.")

        # Step 3: Theme Classification
        classified_reviews: list[dict] = []
        top_themes: list[dict] = []
        try:
            classified_reviews = self.clusterer.classify(clean_reviews)
            top_themes = self.clusterer.rank_themes(classified_reviews)
            self.clusterer.save_classified(classified_reviews, week=target_week)
        except Exception as e:
            logger.error(f"Classification stage failed: {e}")
            errors.append(f"Classification error: {e}")

        top_theme_names = [t["theme"] for t in top_themes[:3]]

        # Step 4: Quote Selection
        selected_quotes: list[dict] = []
        try:
            selected_quotes = self.quote_scorer.select_quotes(
                reviews=classified_reviews,
                top_themes=top_themes,
                num_quotes=3,
            )
        except Exception as e:
            logger.error(f"Quote selection failed: {e}")
            errors.append(f"Quote selection error: {e}")

        # Step 5: Pulse Report Generation
        pulse_output: Optional[PulseOutput] = None
        try:
            prev_week = _get_previous_week_str(target_week)
            prev_themes = self._load_previous_themes(prev_week) if prev_week else None
            pulse_output = self.pulse_generator.generate(
                top_themes=top_themes[:3],
                selected_quotes=selected_quotes,
                week=target_week,
                previous_themes=prev_themes,
            )
        except Exception as e:
            logger.error(f"Pulse generation failed: {e}")
            errors.append(f"Pulse generation error: {e}")

        # Step 6 & 7: MCP Delivery (Google Docs & Gmail)
        doc_url = None
        draft_id = None
        docs_action_id = None
        docs_approval_url = None
        gmail_action_id = None
        gmail_approval_url = None

        if not dry_run and pulse_output:
            doc_title = f"{self.config.DOC_TITLE_PREFIX} — {target_week}"

            # Google Docs Delivery
            if self.docs_publisher:
                try:
                    if hasattr(self.docs_publisher, "preview_append"):
                        doc_res = await self.docs_publisher.preview_append(
                            content_md=pulse_output.markdown,
                        )
                        doc_url = getattr(doc_res, "target_url", None)
                        docs_action_id = getattr(doc_res, "action_id", None)
                        docs_approval_url = getattr(doc_res, "approval_url", None)
                        if docs_approval_url:
                            logger.info(f"Google Docs approval required: {docs_approval_url}")
                    else:
                        doc_url = await self.docs_publisher.publish(
                            title=doc_title,
                            content_md=pulse_output.markdown,
                        )
                except Exception as e:
                    logger.warning(f"Google Docs publication failed, falling back to local files: {e}")
                    errors.append(f"Google Docs error: {e}")
            else:
                logger.info("Docs publisher not initialized; skipping Google Docs upload.")

            # Gmail Email Delivery
            if self.gmail_drafter:
                try:
                    subject = f"Groww Weekly Review Pulse — {target_week}"
                    recipients_raw = getattr(self.config, "PULSE_EMAIL_RECIPIENTS", "") or self.config.EMAIL_TO or "user@example.com"
                    recipients = [e.strip() for e in recipients_raw.split(",") if e.strip()]
                    if hasattr(self.gmail_drafter, "preview_email"):
                        gmail_res = await self.gmail_drafter.preview_email(
                            subject=subject,
                            body_html=pulse_output.html,
                            to=recipients,
                            doc_url=doc_url,
                        )
                        gmail_action_id = getattr(gmail_res, "action_id", None)
                        draft_id = gmail_action_id
                        gmail_approval_url = getattr(gmail_res, "approval_url", None)
                        if gmail_approval_url:
                            logger.info(f"Gmail email approval required: {gmail_approval_url}")
                    else:
                        draft_id = await self.gmail_drafter.draft(
                            subject=subject,
                            body_html=pulse_output.html,
                            to=recipient,
                            doc_url=doc_url,
                        )
                        gmail_action_id = draft_id
                except Exception as e:
                    logger.warning(f"Gmail draft creation failed, falling back to local files: {e}")
                    errors.append(f"Gmail draft error: {e}")
            else:
                logger.info("Gmail drafter not initialized; skipping draft creation.")
        else:
            logger.info("Dry-run enabled or pulse output missing: skipping MCP delivery.")

        duration = round(time.time() - start_time, 2)
        success = pulse_output is not None and pulse_output.is_valid and clean_count > 0

        result = RunResult(
            success=success,
            week=target_week,
            reviews_scraped=scraped_count,
            reviews_clean=clean_count,
            top_themes=top_theme_names,
            doc_url=doc_url,
            draft_id=draft_id,
            docs_action_id=docs_action_id,
            docs_approval_url=docs_approval_url,
            gmail_action_id=gmail_action_id,
            gmail_approval_url=gmail_approval_url,
            errors=errors,
            duration_seconds=duration,
            reviews_noise=noise_count,
            reviews_spam=spam_count,
            reviews_excluded_language=excluded_lang_count,
        )

        self._append_run_log(result)
        logger.info(f"Run completed in {duration}s. Success: {success}. Top themes: {top_theme_names}")
        return result
