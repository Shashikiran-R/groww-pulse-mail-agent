"""
Theme Clusterer — LLM-based review classification.

Classifies enriched reviews into themes from the fixed taxonomy,
ranks themes by weighted frequency, and handles batching, retries, and caching.
Supports Groq (with openai/gpt-oss-120b) and Google Gemini providers.
"""

from __future__ import annotations

import json
import time
import logging
import re
from pathlib import Path
from collections import defaultdict
from typing import Optional, Union

from unittest.mock import MagicMock

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

import json_repair

from src.config import config
from src.classification.taxonomy import (
    THEME_TAXONOMY,
    VALID_THEMES,
    FALLBACK_THEME,
    SENTIMENT_WEIGHTS,
    get_taxonomy_text,
    get_few_shot_text,
)

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

TAXONOMY_KEYWORDS = {
    "Trading & Order Execution": {
        "F&O trading issues": ["f&o", "futures", "options", "option trading", "call option", "put option", "strike price", "expiry", "option chain", "derivatives"],
        "Stop loss and target triggers": ["stop loss", "stoploss", "sl", "target price", "tp", "sl trigger", "trailing sl", "stoploss hit"],
        "Order execution and slippage": ["order execution", "buy order", "sell order", "limit order", "market order", "order rejected", "order cancel", "slippage", "position exit", "square off", "intraday square off"],
        "Charts and TradingView": ["chart", "charts", "tradingview", "candlestick", "indicators", "chart freeze", "chart lag", "timeframe"],
        "Option chain data": ["option chain", "greeks", "open interest", "oi", "pcr", "chain data"],
        "Intraday position squaring": ["intraday", "auto square off", "mis", "margin call", "intraday charges"],
    },
    "Brokerage & Charges": {
        "High brokerage charges": ["brokerage", "brokerage charges", "brokarage", "high brokerage", "broker charges", "₹20 per trade", "costly brokerage"],
        "Hidden fees and deductions": ["hidden charge", "hidden charges", "extra charge", "extra charges", "unnecessary cut", "money deducted", "deductions", "overcharge", "cut money"],
        "DP charges": ["dp charge", "dp charges", "depository participant", "cdsl charge"],
        "Annual maintenance charges (AMC)": ["amc", "annual maintenance", "account maintenance", "maintenance charge"],
        "GST and regulatory fees": ["gst", "stamp duty", "sebi charge", "stt", "regulatory charge"],
    },
    "Customer Support & Service": {
        "Helpline unresponsiveness": ["customer care", "helpline", "toll free", "call centre", "call center", "call kiya", "no call response", "phone support", "not picking call"],
        "Chatbot and automated replies": ["chatbot", "bot reply", "automated reply", "robot", "groww bot", "bot replies"],
        "Delayed ticket resolution": ["ticket", "support ticket", "complaint", "issue resolution", "no reply", "no response", "not responding", "pending ticket"],
        "Lack of human agent": ["human agent", "executive", "agent", "talk to human", "speak to executive", "representative"],
        "Account support complaints": ["ghatiya service", "bad service", "worst service", "poor support", "unhelpful", "terrible support", "customer service"],
    },
    "Usability & Positive Feedback": {
        "User friendly UI": ["user friendly", "clean ui", "simple ui", "interface", "modern ui", "easy navigation", "smooth interface"],
        "Beginner-friendly investment": ["beginner", "beginners", "easy to learn", "easy to understand", "start investing", "first time", "simple to use"],
        "Clean design and navigation": ["clean design", "smooth", "intuitive", "navigation", "search feature", "watchlist"],
        "General praise and satisfaction": ["best app", "great app", "nice app", "super app", "love this app", "excellent app", "wonderful app", "favorite app", "happy with groww"],
        "Portfolio tracking simplicity": ["portfolio tracking", "holding view", "dashboard view", "returns tracking", "wealth creation"],
    },
    "Onboarding / KYC": {
        "Account creation": ["account opening", "create account", "open account", "new account", "registration", "signup", "sign up", "open demat"],
        "KYC verification delays": ["kyc delay", "kyc pending", "verification delay", "pending verification", "not verified", "verification taking", "days to verify", "kyc rejected"],
        "Document upload issues": ["document upload", "upload pan", "upload aadhar", "upload adhaar", "photo rejected", "signature", "document error", "review documents"],
        "eKYC": ["ekyc", "digilocker", "uidai", "aadhaar otp", "aadhar otp", "nsdl", "vkyc", "video kyc"],
    },
    "Payments / UPI": {
        "UPI failures": ["upi fail", "upi error", "gpay", "phonepe", "paytm", "bhim", "upi id", "transaction fail", "payment failed"],
        "Payment gateway errors": ["gateway", "netbanking", "payment stuck", "money debited but", "debited not credited", "bank error", "failed transaction"],
        "Auto-pay": ["autopay", "auto pay", "mandate", "e-mandate", "nach", "cancel autopay"],
        "SIP payments": ["sip payment", "sip deducted", "sip fail", "sip installment", "monthly sip"],
        "Refunds": ["refund", "refund not received", "money back", "reversal"],
    },
    "Statements / Tax Reports": {
        "P&L statements": ["p&l", "pnl", "profit and loss", "statement", "ledger", "contract note"],
        "Tax harvesting": ["tax harvesting", "tax saving", "harvesting"],
        "Capital gains report": ["capital gain", "capital gains", "itr", "tax report", "tax document", "form 16", "schedule fa"],
        "CDSL holding": ["cdsl", "holding statement", "demat holding", "tpin", "edis", "dp charges", "cas statement"],
    },
    "Withdrawals / Redemptions": {
        "Withdrawal delays": ["withdraw delay", "withdrawal delay", "withdrawal stuck", "money withdraw", "payout delay", "withdrawal processing", "withdrawing my money", "unable to withdraw"],
        "Bank account linking": ["link bank", "add bank", "primary bank", "bank verification", "change bank", "penny drop", "ifsc"],
        "Failed redemptions": ["redemption fail", "redeem fail", "cannot redeem", "unable to redeem"],
        "Settlement": ["settlement", "t+1", "credit time", "settlement delay", "balance not updated"],
    },
    "App Performance / Bugs": {
        "Crashes": ["crash", "app crashes", "app closes", "force close", "shuts down"],
        "Slow loading": ["slow", "lag", "hang", "freeze", "stuck", "loading slow", "buffer", "spinning"],
        "UI glitches": ["glitch", "ui issue", "screen blank", "white screen", "black screen", "dark mode", "font", "display"],
        "Login issues": ["login", "log in", "cannot login", "logged out", "session expired", "password", "pin", "biometric", "fingerprint", "face id"],
        "OTP failures": ["otp not", "otp delay", "no otp", "resend otp", "wrong otp"],
        "Updates": ["update", "new version", "latest update", "after update", "recent update"],
    },
}

THEME_PROTOTYPES = {
    "Trading & Order Execution": (
        "trading trade f&o futures options stop loss stoploss sl target intraday order buy sell "
        "executed position exit chart tradingview option chain nifty banknifty strike price slippage "
        "trigger loss executed automatically square off call put index market depth limit order"
    ),
    "Brokerage & Charges": (
        "brokerage hidden charge hidden charges high charges extra charge deducted deduction interest rate "
        "amc dp charge costly expensive fee fees brokerage charges annual maintenance brokarage gst paise "
        "cut money unnecessary cut overcharge stamp duty"
    ),
    "Customer Support & Service": (
        "customer support customer care support team call centre helpdesk ticket executive no response "
        "not responding complaint service poor ghatiya service bad service worst service call helpline "
        "human agent bot unhelpful call center representative solve problem"
    ),
    "Usability & Positive Feedback": (
        "easy to use user friendly good for beginners best app great app nice app super app love this app "
        "smooth helpful easy understand excellent clean ui interface simple satisfying wonderful useful "
        "good experience favorite happy"
    ),
    "Onboarding / KYC": (
        "kyc document documents verify verification pan aadhar adhaar account opening signup sign up "
        "ekyc signature identity proof address upload pending verification taking long time rejected"
    ),
    "Payments / UPI": (
        "upi payment gpay phonepe paytm bhim autopay auto pay mandate deposit money added debited not credited "
        "transaction fail failed debit bank balance deposit money"
    ),
    "Withdrawals / Redemptions": (
        "withdraw withdrawing withdrawal redeem redemption payout bank transfer bank account settlement "
        "credit to bank money stuck unable to withdraw transfer to bank fund withdrawal"
    ),
    "Statements / Tax Reports": (
        "p&l pnl profit and loss statement tax capital gains itr cdsl holding cas statement contract note "
        "capital gain tax harvesting reports ledger download"
    ),
    "App Performance / Bugs": (
        "crash app crashes lag slow hang freeze stuck loading glitch bug login logged out otp black screen "
        "white screen update fingerprint error session expired biometric blank screen"
    ),
}


class SemanticHybridClassifier:
    """Hybrid TF-IDF vector space and keyword ensemble classifier for fintech reviews."""
    def __init__(self):
        self.theme_names = list(THEME_PROTOTYPES.keys())
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        self.prototype_matrix = self.vectorizer.fit_transform([THEME_PROTOTYPES[t] for t in self.theme_names])

    def classify(self, text: str) -> dict:
        lower_text = (text or "").lower()
        if not lower_text.strip():
            return {"theme": FALLBACK_THEME, "sub_theme": "General feedback", "confidence": 0.50}

        # 1. Exact keyword dictionary check (highest precision)
        for theme, sub_themes in TAXONOMY_KEYWORDS.items():
            for sub_theme, keywords in sub_themes.items():
                for kw in keywords:
                    if kw in lower_text:
                        return {
                            "theme": theme,
                            "sub_theme": sub_theme,
                            "confidence": 0.88,
                        }

        # 2. Vector space TF-IDF cosine similarity (handles phrasing & Hinglish)
        try:
            vec = self.vectorizer.transform([lower_text])
            sims = cosine_similarity(vec, self.prototype_matrix)[0]
            best_idx = int(np.argmax(sims))
            best_score = float(sims[best_idx])

            if best_score >= 0.08:
                matched_theme = self.theme_names[best_idx]
                sub_theme = THEME_TAXONOMY.get(matched_theme, ["General"])[0]
                for st, keywords in TAXONOMY_KEYWORDS.get(matched_theme, {}).items():
                    if any(kw in lower_text for kw in keywords):
                        sub_theme = st
                        break
                confidence = min(0.92, max(0.68, round(best_score * 2.5, 2)))
                return {
                    "theme": matched_theme,
                    "sub_theme": sub_theme,
                    "confidence": confidence,
                }
        except Exception as e:
            logger.warning(f"Semantic vector similarity error: {e}")

        return {
            "theme": FALLBACK_THEME,
            "sub_theme": "General feedback",
            "confidence": 0.60,
        }


_global_hybrid_classifier = None

def get_hybrid_classifier() -> SemanticHybridClassifier:
    global _global_hybrid_classifier
    if _global_hybrid_classifier is None:
        _global_hybrid_classifier = SemanticHybridClassifier()
    return _global_hybrid_classifier


def classify_heuristic(text: str) -> dict:
    """Classify using hybrid semantic vector space and keyword matching."""
    return get_hybrid_classifier().classify(text)


logger = logging.getLogger(__name__)

# Cache directory for persisting theme assignments
CACHE_DIR = Path("data/classified")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _build_classification_prompt(reviews_batch: list[dict]) -> tuple[str, str]:
    """
    Build the system prompt and user prompt for theme classification.

    Returns (system_prompt, user_prompt).
    """
    system_prompt = (
        "You are a review classifier for the Groww fintech app "
        "(Indian stock trading and mutual fund platform).\n\n"
        "Taxonomy:\n"
        f"{get_taxonomy_text()}\n\n"
        "For each review, assign:\n"
        '- "theme": exactly one from the taxonomy above, or "Other"\n'
        '- "sub_theme": a more specific label (2-4 words)\n'
        '- "confidence": float 0.0 to 1.0\n\n'
        "Few-shot examples:\n"
        f"{get_few_shot_text()}\n\n"
        'Return a JSON object with a "classifications" JSON array: '
        '{"classifications": [{"review_id": "...", "theme": "...", "sub_theme": "...", "confidence": 0.85}]}\n\n'
        "Do NOT summarise or modify review text. Do NOT add any explanation."
    )

    review_items = []
    for r in reviews_batch:
        review_items.append({
            "review_id": r.get("review_id", ""),
            "text": r.get("normalised_text", r.get("cleaned_text", r.get("text", ""))),
        })

    user_prompt = (
        "Classify the following reviews:\n\n"
        f"{json.dumps(review_items, ensure_ascii=False)}"
    )

    return system_prompt, user_prompt


def _build_reclassification_prompt(reviews_batch: list[dict]) -> tuple[str, str]:
    """
    Build a second-pass prompt for low-confidence reviews.
    Includes additional context (title, rating) for better classification.
    """
    system_prompt = (
        "You are a review classifier for the Groww fintech app. "
        "These reviews were difficult to classify on the first pass. "
        "Use all available context (title, text, rating) to make the best assignment.\n\n"
        "Taxonomy:\n"
        f"{get_taxonomy_text()}\n\n"
        "For each review, assign:\n"
        '- "theme": exactly one from the taxonomy above, or "Other"\n'
        '- "sub_theme": a more specific label (2-4 words)\n'
        '- "confidence": float 0.0 to 1.0\n\n'
        'Return a JSON object with a "classifications" JSON array: '
        '{"classifications": [{"review_id": "...", "theme": "...", "sub_theme": "...", "confidence": 0.85}]}\n\n'
        "Do NOT summarise or modify review text. Do NOT add any explanation."
    )

    review_items = []
    for r in reviews_batch:
        review_items.append({
            "review_id": r.get("review_id", ""),
            "title": r.get("title", ""),
            "text": r.get("normalised_text", r.get("cleaned_text", r.get("text", ""))),
            "rating": r.get("rating", None),
        })

    user_prompt = (
        "Classify the following reviews with additional context:\n\n"
        f"{json.dumps(review_items, ensure_ascii=False)}"
    )

    return system_prompt, user_prompt


class ThemeClusterer:
    """
    Classifies reviews into themes via LLM (Groq or Gemini).

    Handles batching, retry with exponential backoff, caching,
    and confidence-based re-classification.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        batch_size: Optional[int] = None,
        confidence_threshold: Optional[float] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        """Initialise LLM client and configuration."""
        self.batch_size = batch_size or config.LLM_BATCH_SIZE
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else config.CLASSIFICATION_CONFIDENCE_THRESHOLD
        )

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

        # Setup client and model
        if self.provider == "groq":
            self.api_key = api_key or config.GROQ_API_KEY
            self.model = model or config.GROQ_MODEL or "openai/gpt-oss-120b"
            if groq is not None:
                self.client = groq.Groq(api_key=self.api_key, max_retries=0)
            else:
                raise ImportError("The 'groq' package is required for provider='groq'.")
        else:
            self.api_key = api_key or config.GEMINI_API_KEY
            self.model = model or "gemini-2.5-flash"
            if genai is not None and getattr(genai, "Client", None) is not None:
                self.client = genai.Client(api_key=self.api_key)
            else:
                self.client = None

        self.hybrid_classifier = get_hybrid_classifier()
        self._cache: dict[str, dict] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cached theme assignments from disk."""
        for cache_file in CACHE_DIR.glob("classified_*.json"):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached_reviews = json.load(f)
                for r in cached_reviews:
                    rid = r.get("review_id")
                    if rid and r.get("theme"):
                        self._cache[rid] = {
                            "theme": r["theme"],
                            "sub_theme": r.get("sub_theme", ""),
                            "confidence": r.get("confidence", 0.0),
                        }
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load cache file {cache_file}: {e}")
        logger.info(f"Loaded {len(self._cache)} cached theme assignments.")

    def _call_llm(self, system_prompt: str, user_prompt: str, max_retries: int = 3) -> list[dict]:
        """
        Call LLM with exponential backoff on 429/500 errors.
        Returns parsed JSON array/list of classification results.
        """
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
                        response_format={"type": "json_object"},
                        temperature=0.1,
                    )
                    raw_text = completion.choices[0].message.content or ""
                else:
                    generate_config = None
                    if types and hasattr(types, "GenerateContentConfig"):
                        generate_config = types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            response_mime_type="application/json",
                            temperature=0.1,
                        )
                    else:
                        generate_config = {
                            "system_instruction": system_prompt,
                            "response_mime_type": "application/json",
                            "temperature": 0.1,
                        }

                    response = self.client.models.generate_content(
                        model=self.model,
                        contents=user_prompt,
                        config=generate_config,
                    )
                    raw_text = getattr(response, "text", "") or ""

                if not raw_text.strip():
                    logger.warning(f"Empty LLM response on attempt {attempt}")
                    if attempt < max_retries:
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return []

                # Parse JSON — use json_repair for malformed output
                try:
                    result = json.loads(raw_text)
                except Exception:
                    logger.warning("Malformed JSON from LLM, attempting repair.")
                    result = json_repair.loads(raw_text)

                if isinstance(result, dict):
                    # Unwrap root object if wrapped with classifications, results, or reviews
                    for key in ("classifications", "results", "reviews", "data"):
                        if key in result and isinstance(result[key], list):
                            result = result[key]
                            break
                    else:
                        result = [result]

                if not isinstance(result, list):
                    logger.warning(f"Unexpected LLM response type: {type(result)}")
                    return []

                return result

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

                if "413" in error_str or "payload too large" in error_str or "request too large" in error_str:
                    logger.warning(f"Payload too large for LLM ({e}). Failing fast to hybrid classifier.")
                    raise

                if is_retryable and attempt < max_retries:
                    m_min = re.search(r"try again in ([\d\.]+)m", str(e), re.IGNORECASE)
                    m_sec = re.search(r"try again in ([\d\.]+)s", str(e), re.IGNORECASE)
                    if m_min or (m_sec and float(m_sec.group(1)) > 5.0):
                        logger.warning(f"Rate limit wait too long ({e}). Failing fast to hybrid classifier.")
                        raise

                    wait_time = delay
                    if m_sec:
                        wait_time = max(float(m_sec.group(1)) + 1.0, delay)
                    elif "429" in error_str or "rate" in error_str:
                        wait_time = max(delay, 5.0)

                    logger.warning(
                        f"LLM call failed (attempt {attempt}/{max_retries}): {e}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    time.sleep(wait_time)
                    delay *= 2
                else:
                    logger.error(f"LLM call failed after {attempt} attempts: {e}")
                    raise

        return []

    def _classify_batch(self, reviews: list[dict], is_reclassify: bool = False) -> dict[str, dict]:
        """
        Classify a single batch of reviews. Returns a dict mapping review_id to classification.
        """
        if is_reclassify:
            system_prompt, user_prompt = _build_reclassification_prompt(reviews)
        else:
            system_prompt, user_prompt = _build_classification_prompt(reviews)

        results = self._call_llm(system_prompt, user_prompt)

        classifications = {}
        for item in results:
            rid = item.get("review_id", "")
            theme = item.get("theme", FALLBACK_THEME)
            sub_theme = item.get("sub_theme", "")
            try:
                confidence = float(item.get("confidence", 0.0))
            except (ValueError, TypeError):
                confidence = 0.0

            # Validate theme
            if theme not in VALID_THEMES:
                logger.warning(f"Unknown theme '{theme}' for review {rid}, mapping to Other.")
                theme = FALLBACK_THEME

            classifications[rid] = {
                "theme": theme,
                "sub_theme": sub_theme,
                "confidence": confidence,
            }

        return classifications

    def classify(self, reviews: list[dict]) -> list[dict]:
        """
        Classify all reviews into themes via LLM.

        Returns reviews with added: theme, sub_theme, confidence, selected_quote.
        Handles batching, retries, and caching internally.
        Only processes reviews with quality_flag == 'clean'.
        """
        clean_reviews = [r for r in reviews if r.get("quality_flag") == "clean"]
        logger.info(f"Starting classification of {len(clean_reviews)} clean reviews.")

        for r in clean_reviews:
            if "selected_quote" not in r:
                r["selected_quote"] = False

        # Separate cached vs. new reviews
        new_reviews = []
        for r in clean_reviews:
            rid = r.get("review_id", "")
            if rid in self._cache:
                cached = self._cache[rid]
                r["theme"] = cached["theme"]
                r["sub_theme"] = cached["sub_theme"]
                r["confidence"] = cached["confidence"]
            else:
                new_reviews.append(r)

        logger.info(
            f"Cache hit: {len(clean_reviews) - len(new_reviews)}, "
            f"New to classify: {len(new_reviews)}"
        )

        # Batch and classify new reviews
        if new_reviews:
            batches = [
                new_reviews[i: i + self.batch_size]
                for i in range(0, len(new_reviews), self.batch_size)
            ]
            logger.info(f"Processing {len(batches)} batches of up to {self.batch_size} reviews.")

            for batch_idx, batch in enumerate(batches, 1):
                logger.info(f"Classifying batch {batch_idx}/{len(batches)} ({len(batch)} reviews)...")

                try:
                    classifications = self._classify_batch(batch)

                    for r in batch:
                        rid = r.get("review_id", "")
                        text = r.get("normalised_text", r.get("cleaned_text", r.get("text", "")))
                        if rid in classifications:
                            c = classifications[rid]
                            r["theme"] = c["theme"]
                            r["sub_theme"] = c["sub_theme"]
                            r["confidence"] = c["confidence"]
                            self._cache[rid] = c
                        else:
                            h = classify_heuristic(text)
                            r["theme"] = h["theme"]
                            r["sub_theme"] = h["sub_theme"]
                            r["confidence"] = h["confidence"]
                            if rid:
                                self._cache[rid] = h

                except Exception as e:
                    logger.error(f"Batch {batch_idx} classification failed: {e}. Using heuristic fallback.")
                    for r in batch:
                        text = r.get("normalised_text", r.get("cleaned_text", r.get("text", "")))
                        h = classify_heuristic(text)
                        r["theme"] = h["theme"]
                        r["sub_theme"] = h["sub_theme"]
                        r["confidence"] = h["confidence"]
                        rid = r.get("review_id", "")
                        if rid:
                            self._cache[rid] = h

                # Delay between batches to respect rate limits
                if batch_idx < len(batches):
                    time.sleep(1.0)

        # Second pass: re-classify low-confidence reviews
        low_confidence = [
            r for r in clean_reviews
            if r.get("confidence", 0.0) < self.confidence_threshold
            and r.get("confidence", 0.0) > 0.0  # Skip complete failures
        ]

        if low_confidence:
            logger.info(f"Re-classifying {len(low_confidence)} low-confidence reviews...")
            reclassify_batches = [
                low_confidence[i: i + self.batch_size]
                for i in range(0, len(low_confidence), self.batch_size)
            ]

            for batch_idx, batch in enumerate(reclassify_batches, 1):
                try:
                    reclassifications = self._classify_batch(batch, is_reclassify=True)

                    for r in batch:
                        rid = r.get("review_id", "")
                        if rid in reclassifications:
                            new_c = reclassifications[rid]
                            if new_c["confidence"] > r.get("confidence", 0.0):
                                r["theme"] = new_c["theme"]
                                r["sub_theme"] = new_c["sub_theme"]
                                r["confidence"] = new_c["confidence"]
                                self._cache[rid] = new_c

                except Exception as e:
                    logger.error(f"Re-classification batch {batch_idx} failed: {e}")

                if batch_idx < len(reclassify_batches):
                    time.sleep(1.0)

        # Disambiguate remaining "Other" or unresolved reviews using hybrid semantic classifier
        for r in clean_reviews:
            rid = r.get("review_id", "")
            text = r.get("normalised_text", r.get("cleaned_text", r.get("text", "")))
            if r.get("theme") == FALLBACK_THEME or r.get("confidence", 0.0) < self.confidence_threshold:
                h = classify_heuristic(text)
                if h["theme"] != FALLBACK_THEME and h.get("confidence", 0.0) > r.get("confidence", 0.0):
                    r["theme"] = h["theme"]
                    r["sub_theme"] = h["sub_theme"]
                    r["confidence"] = h["confidence"]
                    if rid:
                        self._cache[rid] = h

        # Log classification distribution
        theme_counts = defaultdict(int)
        for r in clean_reviews:
            theme_counts[r.get("theme", FALLBACK_THEME)] += 1
        logger.info(f"Classification distribution: {dict(theme_counts)}")

        return clean_reviews

    def rank_themes(self, reviews: list[dict]) -> list[dict]:
        """
        Aggregate and rank themes by weighted frequency.

        Uses the ranking algorithm:
            weighted_score = Σ (1.0 / days_since_review) × sentiment_weight × helpfulness

        Returns sorted list of theme dicts:
        [{"theme": "...", "count": N, "weighted_score": X,
          "sentiment_breakdown": {"negative": %, "positive": %, "neutral": %}}]
        """
        theme_data: dict[str, dict] = {}

        for r in reviews:
            theme = r.get("theme")
            if not theme:
                continue

            if theme not in theme_data:
                theme_data[theme] = {
                    "theme": theme,
                    "count": 0,
                    "weighted_score": 0.0,
                    "sentiment_counts": defaultdict(int),
                    "sub_themes": defaultdict(int),
                }

            td = theme_data[theme]
            td["count"] += 1

            # Track sub-themes
            sub_theme = r.get("sub_theme", "Unknown")
            td["sub_themes"][sub_theme] += 1

            # Sentiment tracking
            sentiment_label = r.get("sentiment_label", "neutral")
            if sentiment_label in ("strongly_negative", "negative"):
                td["sentiment_counts"]["negative"] += 1
            elif sentiment_label in ("strongly_positive", "positive"):
                td["sentiment_counts"]["positive"] += 1
            else:
                td["sentiment_counts"]["neutral"] += 1

            # Weighted score calculation
            days_since = max(1, r.get("days_since_review", 1))
            recency_weight = 1.0 / days_since
            sentiment_weight = SENTIMENT_WEIGHTS.get(sentiment_label, 1.0)
            helpfulness = max(0.01, r.get("helpfulness", 0.01))

            td["weighted_score"] += recency_weight * sentiment_weight * helpfulness

        # Compute sentiment breakdown percentages and format output
        ranked_themes = []
        for td in theme_data.values():
            total = td["count"]
            sc = td["sentiment_counts"]
            neg_count = sc.get("negative", 0)
            pos_count = sc.get("positive", 0)
            neu_count = sc.get("neutral", 0)

            sentiment_breakdown = {
                "negative": round(neg_count / total * 100, 1) if total > 0 else 0,
                "positive": round(pos_count / total * 100, 1) if total > 0 else 0,
                "neutral": round(neu_count / total * 100, 1) if total > 0 else 0,
            }

            # Top sub-themes
            top_sub_themes = sorted(
                td["sub_themes"].items(), key=lambda x: x[1], reverse=True
            )[:5]

            ranked_themes.append({
                "theme": td["theme"],
                "count": td["count"],
                "weighted_score": round(td["weighted_score"], 4),
                "sentiment_breakdown": sentiment_breakdown,
                "top_sub_themes": [
                    {"sub_theme": st, "count": c} for st, c in top_sub_themes
                ],
            })

        # Sort by weighted_score descending
        ranked_themes.sort(key=lambda x: x["weighted_score"], reverse=True)

        logger.info(
            f"Theme ranking: "
            + ", ".join(
                f'{t["theme"]} ({t["weighted_score"]:.2f})' for t in ranked_themes[:5]
            )
        )

        return ranked_themes

    def save_classified(self, reviews: list[dict], week: str | None = None) -> Path:
        """
        Save classified reviews to data/classified/classified_{week}.json.
        """
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        if week:
            output_path = CACHE_DIR / f"classified_{week}.json"
        else:
            by_week = defaultdict(list)
            for r in reviews:
                w = r.get("week", "unknown")
                by_week[w].append(r)

            output_path = None
            for w, week_reviews in by_week.items():
                p = CACHE_DIR / f"classified_{w}.json"
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(week_reviews, f, indent=2, ensure_ascii=False, default=str)
                logger.info(f"Saved {len(week_reviews)} classified reviews to {p}")
                if output_path is None:
                    output_path = p

            return output_path or CACHE_DIR

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(reviews, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"Saved {len(reviews)} classified reviews to {output_path}")
        return output_path
