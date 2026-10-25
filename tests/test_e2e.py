"""
End-to-End Tests for Groww App Review Pulse Agent.

Tests the full orchestration flow:
Scrape -> Clean/Enrich -> Classify -> Quotes -> Pulse Gen -> MCP Delivery -> Run Log.
"""

import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

from src.agent.controller import AgentController, RunResult, RUN_LOG_PATH
from src.delivery.mcp_client import DeliveryApprovalResult
from src.generation.pulse_generator import PulseOutput

FIXTURE_REVIEWS = [
    {
        "review_id": "e2e_1",
        "author": "User One",
        "rating": 1,
        "title": "KYC stuck",
        "text": "KYC verification took 5 days and still not complete. Very frustrating.",
        "date": "2099-01-01T00:00:00Z",
        "thumbs_up": 10,
        "app_version": "6.2.1",
        "source": "playstore",
    },
    {
        "review_id": "e2e_2",
        "author": "User Two",
        "rating": 1,
        "title": "Crashes",
        "text": "App crashes every time I try to open the portfolio tab.",
        "date": "2099-01-02T00:00:00Z",
        "thumbs_up": 5,
        "app_version": "6.2.1",
        "source": "playstore",
    },
    {
        "review_id": "e2e_3",
        "author": "User Three",
        "rating": 2,
        "title": "Payment failed",
        "text": "UPI payment failed and money was deducted from my bank balance.",
        "date": "2099-01-03T00:00:00Z",
        "thumbs_up": 8,
        "app_version": "6.2.1",
        "source": "playstore",
    },
]

MOCK_PULSE_MARKDOWN = """# Groww Weekly Pulse — 2099-W99

**Executive Summary:** KYC delays and app stability are driving critical user dissatisfaction.

## 📊 Top Themes

### 1. Onboarding / KYC (1 reviews, 100.0% negative) ↑
Verification issues persist.

### 2. App Performance / Bugs (1 reviews, 100.0% negative) →
Crashes on portfolio render.

### 3. Payments / UPI (1 reviews, 100.0% negative) ↓
UPI gateway drop-offs.

## 💬 User Quotes

> ★☆☆☆☆ — "KYC verification took 5 days and still not complete. Very frustrating." — *User One, Sep 15*

> ★☆☆☆☆ — "App crashes every time I try to open the portfolio tab." — *User Two, Sep 16*

> ★★☆☆☆ — "UPI payment failed and money was deducted from my bank balance." — *User Three, Sep 17*

## 💡 Action Ideas

1. **[KYC]** Expedite vendor document review SLA.
2. **[Bugs]** Patch null-pointer crash on portfolio screen.
3. **[UPI]** Implement instant refund and status sync.
"""


class TestEndToEndPipeline:

    @pytest.mark.anyio
    async def test_full_pipeline_success(self, tmp_path):
        """Full pipeline executes end-to-end and creates run log and delivery artifacts."""
        log_file = tmp_path / "run_log.json"

        with patch("src.agent.controller.RUN_LOG_PATH", log_file), \
             patch("src.ingestion.scraper.ReviewScraper.scrape", return_value=FIXTURE_REVIEWS), \
             patch("src.ingestion.scraper.ReviewScraper.save"), \
             patch("src.pipeline.pipeline.DataPipeline._save_outputs"), \
             patch("src.classification.clusterer.ThemeClusterer.save_classified"), \
             patch("src.generation.pulse_generator.PulseGenerator.save"), \
             patch("src.classification.clusterer.ThemeClusterer._call_llm") as mock_cluster_llm, \
             patch("src.generation.pulse_generator.PulseGenerator._call_llm", return_value=MOCK_PULSE_MARKDOWN):

            # Mock LLM classification response
            mock_cluster_llm.return_value = [
                {"review_id": "e2e_1", "theme": "Onboarding / KYC", "sub_theme": "KYC verification delays", "confidence": 0.95},
                {"review_id": "e2e_2", "theme": "App Performance / Bugs", "sub_theme": "Crashes", "confidence": 0.92},
                {"review_id": "e2e_3", "theme": "Payments / UPI", "sub_theme": "UPI failures", "confidence": 0.90},
            ]

            controller = AgentController()

            # Mock delivery publishers
            controller.docs_publisher = MagicMock()
            controller.docs_publisher.preview_append = AsyncMock(return_value=DeliveryApprovalResult(
                status="pending_approval",
                action_id="act-docs-123",
                approval_url="https://aiagentserver.onrender.com/approve/act-docs-123",
                target_url="https://docs.google.com/document/d/mock123/edit",
            ))
            controller.gmail_drafter = MagicMock()
            controller.gmail_drafter.preview_email = AsyncMock(return_value=DeliveryApprovalResult(
                status="pending_approval",
                action_id="act-gmail-456",
                approval_url="https://aiagentserver.onrender.com/approve/act-gmail-456",
            ))

            result = await controller.run_weekly_pulse(week="2099-W99", dry_run=False)

            assert isinstance(result, RunResult)
            assert result.success is True
            assert result.week == "2099-W99"
            assert result.reviews_scraped == 3
            assert result.reviews_clean >= 1
            assert len(result.top_themes) >= 1
            assert result.doc_url == "https://docs.google.com/document/d/mock123/edit"
            assert result.draft_id == "act-gmail-456"
            assert result.docs_action_id == "act-docs-123"
            assert result.gmail_action_id == "act-gmail-456"
            assert result.docs_approval_url == "https://aiagentserver.onrender.com/approve/act-docs-123"
            assert result.gmail_approval_url == "https://aiagentserver.onrender.com/approve/act-gmail-456"

            # Check that run_log.json was written and populated
            assert log_file.exists()
            with open(log_file, "r", encoding="utf-8") as f:
                logs = json.load(f)
            assert len(logs) == 1
            assert logs[0]["week"] == "2099-W99"
            assert logs[0]["success"] is True
            assert logs[0]["doc_url"] == "https://docs.google.com/document/d/mock123/edit"
            assert logs[0]["docs_action_id"] == "act-docs-123"
            assert logs[0]["gmail_action_id"] == "act-gmail-456"
            assert logs[0]["docs_approval_url"] == "https://aiagentserver.onrender.com/approve/act-docs-123"
            assert logs[0]["gmail_approval_url"] == "https://aiagentserver.onrender.com/approve/act-gmail-456"

    @pytest.mark.anyio
    async def test_pipeline_dry_run(self, tmp_path):
        """Dry-run flag skips MCP delivery."""
        log_file = tmp_path / "run_log.json"

        with patch("src.agent.controller.RUN_LOG_PATH", log_file), \
             patch("src.ingestion.scraper.ReviewScraper.scrape", return_value=FIXTURE_REVIEWS), \
             patch("src.ingestion.scraper.ReviewScraper.save"), \
             patch("src.pipeline.pipeline.DataPipeline._save_outputs"), \
             patch("src.classification.clusterer.ThemeClusterer.save_classified"), \
             patch("src.generation.pulse_generator.PulseGenerator.save"), \
             patch("src.classification.clusterer.ThemeClusterer._call_llm") as mock_cluster_llm, \
             patch("src.generation.pulse_generator.PulseGenerator._call_llm", return_value=MOCK_PULSE_MARKDOWN):

            mock_cluster_llm.return_value = [
                {"review_id": "e2e_1", "theme": "Onboarding / KYC", "sub_theme": "KYC", "confidence": 0.9},
            ]

            controller = AgentController()
            controller.docs_publisher = MagicMock()
            controller.docs_publisher.preview_append = AsyncMock()
            controller.gmail_drafter = MagicMock()
            controller.gmail_drafter.preview_email = AsyncMock()

            result = await controller.run_weekly_pulse(week="2099-W99", dry_run=True)

            assert result.success is True
            assert result.doc_url is None
            assert result.draft_id is None
            controller.docs_publisher.preview_append.assert_not_called()
            controller.gmail_drafter.preview_email.assert_not_called()

    @pytest.mark.anyio
    async def test_mcp_failure_falls_back_to_local(self, tmp_path):
        """When MCP delivery fails, errors are captured and run completes with local output."""
        log_file = tmp_path / "run_log.json"

        with patch("src.agent.controller.RUN_LOG_PATH", log_file), \
             patch("src.ingestion.scraper.ReviewScraper.scrape", return_value=FIXTURE_REVIEWS), \
             patch("src.ingestion.scraper.ReviewScraper.save"), \
             patch("src.pipeline.pipeline.DataPipeline._save_outputs"), \
             patch("src.classification.clusterer.ThemeClusterer.save_classified"), \
             patch("src.generation.pulse_generator.PulseGenerator.save"), \
             patch("src.classification.clusterer.ThemeClusterer._call_llm") as mock_cluster_llm, \
             patch("src.generation.pulse_generator.PulseGenerator._call_llm", return_value=MOCK_PULSE_MARKDOWN):

            mock_cluster_llm.return_value = [
                {"review_id": "e2e_1", "theme": "Onboarding / KYC", "sub_theme": "KYC", "confidence": 0.9},
            ]

            controller = AgentController()
            controller.docs_publisher = MagicMock()
            controller.docs_publisher.preview_append = AsyncMock(side_effect=Exception("OAuth expired"))
            controller.gmail_drafter = MagicMock()
            controller.gmail_drafter.preview_email = AsyncMock(side_effect=Exception("Connection refused"))

            result = await controller.run_weekly_pulse(week="2099-W99", dry_run=False)

            # Local generation still succeeded
            assert result.success is True
            assert result.doc_url is None
            assert result.draft_id is None
            assert any("OAuth expired" in e for e in result.errors)
            assert any("Connection refused" in e for e in result.errors)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
