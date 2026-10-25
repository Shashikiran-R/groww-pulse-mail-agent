import pytest
from src.delivery.doc_formatter import format_for_google_doc

def test_format_empty_and_none():
    assert format_for_google_doc("") == ""
    assert format_for_google_doc("   ") == ""
    assert format_for_google_doc(None) == ""

def test_format_complete_pulse():
    sample_md = """# Groww Weekly Pulse — 2026-W40

**Executive Summary:** Trading functionality gaps and deteriorating support are the biggest pain points.

## 📊 Top Themes

### 1. Trading & Order Execution (31 reviews, 45.2% negative) ↑
Users repeatedly flag missing GTT stop-loss/target.

### 2. Usability & Positive Feedback (25 reviews, 24.0% negative) ↑
The majority applaud the clean design.

## 💬 User Quotes

> ★☆☆☆☆ — "This app is missing basic features" — *Naveen Kumar GV, Sep 30*

## 💡 Action Ideas

1. **[Trading & Order Execution]** Implement GTT stop-loss.
2. **[Usability & Positive Feedback]** Redesign onboarding.
"""
    formatted = format_for_google_doc(sample_md)
    
    # Assert header
    assert "📈 GROWW WEEKLY PULSE — 2026-W40" in formatted
    assert "════════" in formatted
    
    # Assert summary
    assert "📌 EXECUTIVE SUMMARY" in formatted
    assert "Trading functionality gaps" in formatted
    
    # Assert themes
    assert "📊 TOP CUSTOMER THEMES" in formatted
    assert "[1] TRADING & ORDER EXECUTION" in formatted
    assert "Volume & Sentiment: 31 reviews, 45.2% negative [Trend: ↑]" in formatted
    assert "Analysis: Users repeatedly flag" in formatted
    
    # Assert quotes (without raw markdown '>' or asterisks around author)
    assert "💬 VERBATIM CUSTOMER VOICES" in formatted
    assert "★☆☆☆☆ — \"This app is missing basic features\" — Naveen Kumar GV, Sep 30" in formatted
    assert ">" not in formatted
    
    # Assert actions
    assert "💡 STRATEGIC ACTION RECOMMENDATIONS" in formatted
    assert "[1] Trading & Order Execution:" in formatted
    assert "Implement GTT stop-loss." in formatted
    
    # End banner
    assert "End of Pulse Report" in formatted
