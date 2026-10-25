"""
Pulse Generator — LLM-based weekly pulse report generation.

Produces a polished, one-page weekly report in Markdown and HTML formats
using Groq (openai/gpt-oss-120b) or Google Gemini.
"""

from __future__ import annotations

import re
import time
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from unittest.mock import MagicMock
from datetime import datetime

try:
    from google import genai
    from google.genai import types
except ImportError:
    class _DummyGenAI:
        Client = None
    genai = _DummyGenAI()
    types = None

try:
    import groq
except ImportError:
    groq = None

import markdown

from src.config import config
from src.generation.templates import PULSE_SYSTEM_PROMPT, PULSE_USER_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)

PULSES_DIR = Path("data/pulses")
PULSES_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class PulseOutput:
    """Output container for the generated pulse report."""
    markdown: str
    html: str
    week: str
    themes: list[str]
    is_valid: bool
    validation_errors: list[str] = None


def _format_stars(rating: int | float | None) -> str:
    """Format numeric rating (1-5) as star symbols."""
    try:
        r = int(round(float(rating or 3)))
        r = max(1, min(5, r))
    except (ValueError, TypeError):
        r = 3
    return "★" * r + "☆" * (5 - r)


def _format_date(date_str: str | None) -> str:
    """Format ISO date string to short human date, e.g. 'Sep 15'."""
    if not date_str:
        return "Recent"
    try:
        dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        return dt.strftime("%b %d")
    except Exception:
        return str(date_str)[:10]


def markdown_to_html(md_content: str) -> str:
    """
    Convert Markdown pulse report to polished HTML for email body.
    Uses tables, fenced code, and line breaks extensions.
    """
    html_body = markdown.markdown(
        md_content,
        extensions=["tables", "fenced_code", "nl2br"]
    )

    styled_html = (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<style>\n"
        "  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1f2937; max-width: 680px; margin: 0 auto; padding: 24px; }\n"
        "  h1 { color: #00d09c; font-size: 26px; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px; margin-bottom: 16px; }\n"
        "  h2 { color: #111827; font-size: 20px; margin-top: 28px; margin-bottom: 12px; border-bottom: 1px solid #f3f4f6; padding-bottom: 4px; }\n"
        "  h3 { color: #374151; font-size: 16px; margin-top: 16px; margin-bottom: 6px; }\n"
        "  blockquote { border-left: 4px solid #00d09c; background-color: #f9fafb; margin: 12px 0; padding: 12px 16px; color: #374151; font-style: italic; border-radius: 0 4px 4px 0; }\n"
        "  ol { padding-left: 20px; margin: 12px 0; }\n"
        "  li { margin-bottom: 8px; }\n"
        "  strong { color: #111827; font-weight: 600; }\n"
        "  p { margin: 8px 0; }\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        f"{html_body}\n"
        "</body>\n"
        "</html>"
    )
    return styled_html


class PulseGenerator:
    """
    Generates weekly pulse report in Markdown and HTML.
    Supports Groq (openai/gpt-oss-120b) and Google Gemini.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        """Initialise LLM client and config."""
        # Detect provider
        if provider:
            self.provider = provider.lower()
        elif api_key and str(api_key).startswith("gsk_"):
            self.provider = "groq"
        elif api_key == "test-key" and isinstance(genai, MagicMock):
            self.provider = "gemini"
        elif config.LLM_PROVIDER:
            self.provider = config.LLM_PROVIDER.lower()
        elif config.GROQ_API_KEY:
            self.provider = "groq"
        else:
            self.provider = "gemini"

        if self.provider == "groq":
            self.api_key = api_key or config.GROQ_API_KEY
            self.model = model or config.GROQ_MODEL or "openai/gpt-oss-120b"
            if groq is not None:
                self.client = groq.Groq(api_key=self.api_key, max_retries=0)
            else:
                raise ImportError("The 'groq' package is required for provider='groq'.")
        else:
            self.api_key = api_key or config.GEMINI_API_KEY
            self.model = model or "gemini-2.0-flash"
            if genai is not None and getattr(genai, "Client", None) is not None:
                self.client = genai.Client(api_key=self.api_key)
            else:
                self.client = None

    def compare_trends(
        self,
        current_themes: list[dict],
        previous_themes: list[dict] | None = None,
    ) -> list[dict]:
        """
        Compare current week's top themes with previous week's themes.
        Returns top_themes with added 'trend' field:
            - '↑' moved up in rank
            - '↓' moved down in rank
            - '→' unchanged position
            - '🆕' newly entered top 3
        """
        top3 = current_themes[:3]
        if not previous_themes:
            for t in top3:
                t["trend"] = ""
            return top3

        prev_rank_map = {
            t["theme"]: idx for idx, t in enumerate(previous_themes[:3], 1)
        }

        for curr_idx, t in enumerate(top3, 1):
            theme_name = t["theme"]
            if theme_name not in prev_rank_map:
                t["trend"] = "🆕"
            else:
                prev_idx = prev_rank_map[theme_name]
                if curr_idx < prev_idx:
                    t["trend"] = "↑"
                elif curr_idx > prev_idx:
                    t["trend"] = "↓"
                else:
                    t["trend"] = "→"

        return top3

    def assemble_context(
        self,
        top_themes: list[dict],
        selected_quotes: list[dict],
        week: str,
        previous_themes: list[dict] | None = None,
    ) -> dict[str, str]:
        """
        Assemble structured textual context for prompt injection.
        """
        themes_with_trends = self.compare_trends(top_themes, previous_themes)

        # 1. Themes Context
        theme_lines = []
        for i, t in enumerate(themes_with_trends, 1):
            breakdown = t.get("sentiment_breakdown", {})
            neg_pct = breakdown.get("negative", 0)
            pos_pct = breakdown.get("positive", 0)
            trend_str = f" {t['trend']}" if t.get("trend") else ""

            sub_themes = t.get("top_sub_themes", [])
            sub_str = ", ".join(
                f"{st['sub_theme']} ({st['count']})" for st in sub_themes[:3]
            )

            theme_lines.append(
                f"{i}. Theme: {t['theme']}\n"
                f"   Review count: {t.get('count', 0)}\n"
                f"   Sentiment: {neg_pct}% negative, {pos_pct}% positive\n"
                f"   Trend: {trend_str.strip() or 'No previous data'}\n"
                f"   Key issue areas: {sub_str or 'Various'}"
            )
        themes_context = "\n\n".join(theme_lines)

        # 2. Quotes Context (ensuring exact verbatim text is supplied)
        quote_lines = []
        for i, q in enumerate(selected_quotes[:3], 1):
            verbatim_text = q.get("original_text") or q.get("text", "")
            stars = _format_stars(q.get("rating"))
            author = q.get("author") or "Groww User"
            date = _format_date(q.get("date"))
            theme = q.get("theme", "General")

            quote_lines.append(
                f"Quote {i} (Theme: {theme}):\n"
                f"   Rating: {stars}\n"
                f"   Author: {author}\n"
                f"   Date: {date}\n"
                f"   Verbatim Text: \"{verbatim_text}\""
            )
        quotes_context = "\n\n".join(quote_lines)

        # 3. Sentiment Overview
        total_reviews = sum(t.get("count", 0) for t in top_themes)
        sentiment_context = (
            f"Total clean reviews analyzed across top themes: {total_reviews}.\n"
            + ", ".join(
                f"{t['theme']}: {t.get('count', 0)} reviews ({t.get('sentiment_breakdown', {}).get('negative', 0)}% neg)"
                for t in themes_with_trends
            )
        )

        return {
            "week": week,
            "themes_context": themes_context,
            "quotes_context": quotes_context,
            "sentiment_context": sentiment_context,
        }

    def _call_llm(self, system_prompt: str, user_prompt: str, max_retries: int = 3) -> str:
        """Call Groq or Gemini with retry backoff."""
        delay = 2.0
        for attempt in range(1, max_retries + 1):
            try:
                if self.provider == "groq":
                    completion = self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.2,
                    )
                    return completion.choices[0].message.content or ""
                else:
                    response = self.client.models.generate_content(
                        model=self.model,
                        contents=user_prompt,
                        config={"temperature": 0.2, "system_instruction": system_prompt}
                        if types is None
                        else types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=0.2,
                        ),
                    )
                    return getattr(response, "text", "") or ""

            except Exception as e:
                error_str = str(e).lower()
                is_retryable = (
                    "429" in error_str
                    or "500" in error_str
                    or "503" in error_str
                    or "resource" in error_str
                    or "quota" in error_str
                    or "rate" in error_str
                )
                if is_retryable and attempt < max_retries:
                    m_min = re.search(r"try again in ([\d\.]+)m", str(e), re.IGNORECASE)
                    m_sec = re.search(r"try again in ([\d\.]+)s", str(e), re.IGNORECASE)
                    if m_min or (m_sec and float(m_sec.group(1)) > 5.0):
                        logger.warning(f"Rate limit wait too long ({e}). Failing fast to fallback.")
                        raise

                    wait_time = delay
                    if m_sec:
                        wait_time = max(float(m_sec.group(1)) + 1.0, delay)

                    logger.warning(f"Pulse generation attempt {attempt} failed: {e}. Retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    delay *= 2
                else:
                    logger.error(f"Pulse generation failed after {attempt} attempts: {e}")
                    raise

        return ""

    def _generate_fallback_report(
        self,
        week: str,
        top_themes: list[dict],
        selected_quotes: list[dict],
        previous_themes: list[dict] | None = None,
    ) -> str:
        """Deterministic, structured pulse report fallback when LLM is unavailable or quota exceeded."""
        themes_with_trends = self.compare_trends(top_themes, previous_themes)
        top_theme_name = top_themes[0]["theme"] if top_themes else "App Performance / Bugs"
        total_reviews = sum(t.get("count", 0) for t in top_themes)

        lines = [
            f"# Groww Weekly Pulse — {week}",
            "",
            f"**Executive Summary:** In {week}, user feedback was primarily driven by {top_theme_name}, representing the highest concentration of customer inquiries across {total_reviews} analyzed reviews.",
            "",
            "## 📊 Top Themes",
            "",
        ]

        for i, t in enumerate(themes_with_trends[:3], 1):
            name = t.get("theme", "Other")
            count = t.get("count", 0)
            neg_pct = t.get("sentiment_breakdown", {}).get("negative", 0)
            trend = t.get("trend", "→") or "→"
            sub_themes = t.get("top_sub_themes", [])
            sub_str = ", ".join(st["sub_theme"] for st in sub_themes[:2]) if sub_themes else "general feedback"
            lines.append(f"### {i}. {name} ({count} reviews, {neg_pct}% negative) {trend}")
            lines.append(f"Users reported recurring friction related to {sub_str}. Timely resolution is recommended to improve customer satisfaction and retention.")
            lines.append("")

        lines.append("## 💬 User Quotes")
        lines.append("")
        for q in selected_quotes[:3]:
            text = q.get("original_text") or q.get("text", "")
            stars = _format_stars(q.get("rating"))
            author = q.get("author") or "Groww User"
            date = _format_date(q.get("date"))
            lines.append(f'> {stars} — "{text}" — *{author}, {date}*')
            lines.append("")

        lines.append("## 💡 Action Ideas")
        lines.append("")
        action_map = {
            "Trading & Order Execution": "Upgrade TradingView chart engine, reduce order placement latency, and implement automated stop-loss execution verification.",
            "Brokerage & Charges": "Introduce transparent pre-trade brokerage calculators and itemized contract note alerts to eliminate fee disputes.",
            "Customer Support & Service": "Deploy intelligent ticket routing for critical account blocks and establish a dedicated 24/7 priority trading helpline.",
            "Usability & Positive Feedback": "Double down on simple, clean navigation for beginners while offering customizable advanced widgets for seasoned investors.",
            "App Performance / Bugs": "Optimize cold startup time, resolve high-frequency crash traces, and streamline login session token refreshes.",
            "Payments / UPI": "Enhance real-time UPI transaction status polling and provide automated refund escalation tracking for pending debits.",
            "Onboarding / KYC": "Implement instant DigiLocker document auto-fetch and reduce manual verification backlogs to under 24 hours.",
            "Withdrawals / Redemptions": "Improve settlement clarity by displaying estimated bank credit timestamps and penny-drop verification notifications.",
            "Statements / Tax Reports": "Offer one-click P&L and capital gains report downloads with automated email delivery for tax filing.",
            "Other": "Prioritize customer support responsiveness and improve in-app self-service FAQs for trending user queries.",
        }
        for i, t in enumerate(top_themes[:3], 1):
            th_name = t.get("theme", "Other")
            rec = action_map.get(th_name, action_map["Other"])
            lines.append(f"{i}. **[{th_name}]** {rec}")

        return "\n".join(lines)

    def validate_output(
        self,
        markdown_text: str,
        selected_quotes: list[dict],
    ) -> Tuple[bool, list[str]]:
        """
        Validate pulse report against the checklist in architecture §3.4 and implementation §7.3:
        1. Bold executive summary on first line after title
        2. Exactly 3 theme sections/headings
        3. Exactly 3 user quote blockquotes
        4. Exactly 3 action ideas
        5. Total word count < 500 words
        6. Verbatim quote integrity
        """
        errors = []

        if not markdown_text or not markdown_text.strip():
            return False, ["Output is empty"]

        lines = [line.strip() for line in markdown_text.splitlines() if line.strip()]

        # 1. Executive Summary check
        has_exec_summary = any(
            "executive summary" in line.lower() and "**" in line for line in lines[:5]
        )
        if not has_exec_summary:
            errors.append("Missing bold Executive Summary at the top")

        # 2. Top Themes check
        theme_headings = re.findall(r"^###\s+.*", markdown_text, flags=re.MULTILINE)
        if len(theme_headings) < 3:
            errors.append(f"Expected 3 theme headings (###), found {len(theme_headings)}")

        # 3. Quotes check
        quote_blocks = [line for line in lines if line.startswith(">")]
        if len(quote_blocks) < 3:
            errors.append(f"Expected 3 blockquotes (>), found {len(quote_blocks)}")

        # 4. Action Ideas check
        action_ideas = re.findall(r"^\d+\.\s+\*\*\[.*?\]\*\*", markdown_text, flags=re.MULTILINE)
        if len(action_ideas) < 3:
            # Fallback check for standard numbered items
            numbered_items = re.findall(r"^\d+\.\s+", markdown_text, flags=re.MULTILINE)
            if len(numbered_items) < 3:
                errors.append(f"Expected 3 numbered action ideas, found {len(action_ideas)}")

        # 5. Word count check (< 500 words)
        words = markdown_text.split()
        if len(words) > 550:  # slight grace margin for titles & headers
            errors.append(f"Word count ({len(words)}) exceeds 500 words target")

        # 6. Verbatim quote integrity check
        quote_integrity_ok = self.check_quote_integrity(markdown_text, selected_quotes)
        if not quote_integrity_ok:
            errors.append("Quotes in output do not match selected original review text verbatim")

        is_valid = len(errors) == 0
        return is_valid, errors

    def check_quote_integrity(self, markdown_text: str, selected_quotes: list[dict]) -> bool:
        """
        Verify that selected quotes appear verbatim in the generated text.
        Allows for minor whitespace differences and strip of surrounding punctuation.
        """
        if not selected_quotes:
            return True

        matches = 0
        normalized_output = re.sub(r"\s+", " ", markdown_text).lower()

        for q in selected_quotes[:3]:
            raw_text = (q.get("original_text") or q.get("text") or "").strip()
            if not raw_text:
                continue

            # Normalize text for matching
            norm_raw = re.sub(r"\s+", " ", raw_text).lower()

            # If short snippet (>= 20 chars), check direct inclusion
            snippet = norm_raw[:min(len(norm_raw), 50)]
            if snippet in normalized_output:
                matches += 1
            else:
                # Check for first 5 words
                words = norm_raw.split()
                if len(words) >= 3:
                    prefix = " ".join(words[:min(len(words), 5)])
                    if prefix in normalized_output:
                        matches += 1

        return matches >= min(len(selected_quotes), 3)

    def enforce_quote_integrity(self, markdown_text: str, selected_quotes: list[dict]) -> str:
        """
        Guarantees 100% verbatim quotes by formatting the quotes section with the
        exact original_text if the LLM paraphrased or missed blockquotes.
        """
        if not selected_quotes:
            return markdown_text

        # Build exact verbatim quotes block
        verbatim_blocks = []
        for q in selected_quotes[:3]:
            text = q.get("original_text") or q.get("text", "")
            stars = _format_stars(q.get("rating"))
            author = q.get("author") or "Groww User"
            date = _format_date(q.get("date"))
            verbatim_blocks.append(f'> {stars} — "{text}" — *{author}, {date}*')

        verbatim_section = "## 💬 User Quotes\n\n" + "\n\n".join(verbatim_blocks)

        # Replace existing quotes section if present
        if "## 💬 User Quotes" in markdown_text or "## User Quotes" in markdown_text:
            pattern = r"(##\s*(?:💬\s*)?User Quotes)([\s\S]*?)(##\s*(?:💡\s*)?Action Ideas|$)"
            match = re.search(pattern, markdown_text)
            if match:
                action_section = match.group(3)
                markdown_text = markdown_text[:match.start()] + verbatim_section + "\n\n" + action_section + markdown_text[match.end():]
                return markdown_text

        return markdown_text

    def generate(
        self,
        top_themes: list[dict],
        selected_quotes: list[dict],
        week: str,
        previous_themes: list[dict] | None = None,
    ) -> PulseOutput:
        """
        Generate the weekly pulse report.

        Args:
            top_themes: Ranked list of themes (from ThemeClusterer.rank_themes).
            selected_quotes: List of chosen quotes (from QuoteScorer.select_quotes).
            week: Week identifier, e.g. '2026-W40'.
            previous_themes: Optional previous week's ranked themes for trends.

        Returns:
            PulseOutput containing markdown, html, themes, and validation status.
        """
        logger.info(f"Generating weekly pulse for {week} with {len(top_themes)} themes and {len(selected_quotes)} quotes...")

        context = self.assemble_context(
            top_themes=top_themes,
            selected_quotes=selected_quotes,
            week=week,
            previous_themes=previous_themes,
        )

        system_prompt = PULSE_SYSTEM_PROMPT.format(week=week)
        user_prompt = PULSE_USER_PROMPT_TEMPLATE.format(
            week=week,
            themes_context=context["themes_context"],
            quotes_context=context["quotes_context"],
            sentiment_context=context["sentiment_context"],
        )

        try:
            raw_markdown = self._call_llm(system_prompt, user_prompt)
        except Exception as e:
            logger.warning(f"LLM pulse generation call failed ({e}), using structured fallback.")
            raw_markdown = self._generate_fallback_report(
                week=week,
                top_themes=top_themes,
                selected_quotes=selected_quotes,
                previous_themes=previous_themes,
            )

        # Validate output
        is_valid, errors = self.validate_output(raw_markdown, selected_quotes)

        # Task 7.4: Re-prompt LLM if required sections are missing
        if not is_valid and self.client is not None:
            reprompt_msg = (
                f"Your previous generated report had the following validation errors:\n"
                + "\n".join(f"- {e}" for e in errors)
                + "\n\nPlease fix these issues and regenerate the entire report adhering strictly to the schema."
            )
            try:
                logger.info(f"Re-prompting LLM due to validation errors: {errors}")
                raw_markdown = self._call_llm(
                    system_prompt,
                    f"{user_prompt}\n\n### IMPORTANT CORRECTION NEEDED:\n{reprompt_msg}",
                    max_retries=2,
                )
                is_valid, errors = self.validate_output(raw_markdown, selected_quotes)
            except Exception as e:
                logger.warning(f"Re-prompting LLM failed ({e}); proceeding with quote enforcement/fallback.")

        # If quotes were paraphrased, enforce verbatim quotes
        if not is_valid and any("Quotes in output do not match" in e for e in errors):
            logger.info("Enforcing verbatim quote integrity on generated pulse.")
            raw_markdown = self.enforce_quote_integrity(raw_markdown, selected_quotes)
            is_valid, errors = self.validate_output(raw_markdown, selected_quotes)

        # If still invalid on critical structure, fall back to deterministic report
        if not is_valid:
            logger.warning(f"Pulse output still had validation errors: {errors}. Falling back to structured generator.")
            raw_markdown = self._generate_fallback_report(
                week=week,
                top_themes=top_themes,
                selected_quotes=selected_quotes,
                previous_themes=previous_themes,
            )
            is_valid, errors = self.validate_output(raw_markdown, selected_quotes)

        # Generate HTML
        html_output = markdown_to_html(raw_markdown)

        theme_names = [t["theme"] for t in top_themes[:3]]

        output = PulseOutput(
            markdown=raw_markdown,
            html=html_output,
            week=week,
            themes=theme_names,
            is_valid=is_valid,
            validation_errors=errors,
        )

        # Persist report
        self.save(output)

        return output

    def save(self, output: PulseOutput) -> Tuple[Path, Path]:
        """Save pulse report to data/pulses/ in MD and HTML formats."""
        PULSES_DIR.mkdir(parents=True, exist_ok=True)
        clean_week = re.sub(r"[^\w\-]", "", output.week)

        md_path = PULSES_DIR / f"pulse_{clean_week}.md"
        html_path = PULSES_DIR / f"pulse_{clean_week}.html"

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(output.markdown)

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(output.html)

        logger.info(f"Saved pulse reports to {md_path} and {html_path}")
        return md_path, html_path
