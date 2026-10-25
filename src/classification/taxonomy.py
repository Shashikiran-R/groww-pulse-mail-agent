"""
Theme Taxonomy for Groww App Review Classification.

Defines the fixed 5-theme, 2-level taxonomy with few-shot examples
for LLM-based review classification.
"""

# Two-level theme taxonomy — keys are Level-1 themes, values are Level-2 sub-themes
THEME_TAXONOMY = {
    "Onboarding / KYC": [
        "Account creation",
        "KYC verification delays",
        "Document upload issues",
        "eKYC",
    ],
    "Payments / UPI": [
        "UPI failures",
        "Payment gateway errors",
        "Auto-pay",
        "SIP payments",
        "Refunds",
    ],
    "Statements / Tax Reports": [
        "P&L statements",
        "Tax harvesting",
        "Capital gains report",
        "CDSL holding",
    ],
    "Withdrawals / Redemptions": [
        "Withdrawal delays",
        "Bank account linking",
        "Failed redemptions",
        "Settlement",
    ],
    "App Performance / Bugs": [
        "Crashes",
        "Slow loading",
        "UI glitches",
        "Login issues",
        "OTP failures",
        "Updates",
    ],
    "Trading & Order Execution": [
        "F&O trading issues",
        "Stop loss and target triggers",
        "Order execution and slippage",
        "Charts and TradingView",
        "Option chain data",
        "Intraday position squaring",
    ],
    "Brokerage & Charges": [
        "High brokerage charges",
        "Hidden fees and deductions",
        "DP charges",
        "Annual maintenance charges (AMC)",
        "GST and regulatory fees",
    ],
    "Customer Support & Service": [
        "Helpline unresponsiveness",
        "Chatbot and automated replies",
        "Delayed ticket resolution",
        "Lack of human agent",
        "Account support complaints",
    ],
    "Usability & Positive Feedback": [
        "User friendly UI",
        "Beginner-friendly investment",
        "Clean design and navigation",
        "General praise and satisfaction",
        "Portfolio tracking simplicity",
    ],
}

# Fallback theme for reviews that don't match any predefined category
FALLBACK_THEME = "Other"

# All valid theme names (including fallback)
VALID_THEMES = list(THEME_TAXONOMY.keys()) + [FALLBACK_THEME]

# Few-shot examples for each theme — used in the LLM classification prompt
FEW_SHOT_EXAMPLES = [
    # Trading & Order Execution
    {
        "review_id": "example_trading_1",
        "text": "My stoploss order was not executed on time and got squared off at huge loss in F&O.",
        "theme": "Trading & Order Execution",
        "sub_theme": "Stop loss and target triggers",
        "confidence": 0.95,
    },
    {
        "review_id": "example_trading_2",
        "text": "TradingView charts keep freezing during market hours. Option chain does not refresh.",
        "theme": "Trading & Order Execution",
        "sub_theme": "Charts and TradingView",
        "confidence": 0.93,
    },
    # Brokerage & Charges
    {
        "review_id": "example_brokerage_1",
        "text": "Very high brokerage charges and hidden deductions. They cut ₹20 per trade plus GST without clear info.",
        "theme": "Brokerage & Charges",
        "sub_theme": "High brokerage charges",
        "confidence": 0.96,
    },
    {
        "review_id": "example_brokerage_2",
        "text": "Hidden DP charges deducted without any notification or contract note breakdown.",
        "theme": "Brokerage & Charges",
        "sub_theme": "Hidden fees and deductions",
        "confidence": 0.92,
    },
    # Customer Support & Service
    {
        "review_id": "example_support_1",
        "text": "Worst customer service. Raised support ticket 10 days ago but only getting automated bot replies.",
        "theme": "Customer Support & Service",
        "sub_theme": "Chatbot and automated replies",
        "confidence": 0.96,
    },
    {
        "review_id": "example_support_2",
        "text": "No human agent available on customer care number. Call gets disconnected automatically.",
        "theme": "Customer Support & Service",
        "sub_theme": "Helpline unresponsiveness",
        "confidence": 0.94,
    },
    # Usability & Positive Feedback
    {
        "review_id": "example_usability_1",
        "text": "Very smooth and user friendly app. Best platform for beginners to start investing in mutual funds.",
        "theme": "Usability & Positive Feedback",
        "sub_theme": "Beginner-friendly investment",
        "confidence": 0.95,
    },
    # Onboarding / KYC
    {
        "review_id": "example_kyc_1",
        "text": "KYC process took 5 days and still not verified. Very frustrating experience.",
        "theme": "Onboarding / KYC",
        "sub_theme": "KYC verification delays",
        "confidence": 0.95,
    },
    {
        "review_id": "example_kyc_2",
        "text": "I cannot create my account, the OTP for Aadhaar verification never arrives.",
        "theme": "Onboarding / KYC",
        "sub_theme": "Account creation",
        "confidence": 0.90,
    },
    {
        "review_id": "example_kyc_3",
        "text": "Document upload keeps failing. Tried uploading PAN card 10 times.",
        "theme": "Onboarding / KYC",
        "sub_theme": "Document upload issues",
        "confidence": 0.92,
    },
    # Payments / UPI
    {
        "review_id": "example_upi_1",
        "text": "UPI payment failed 3 times today. Money debited but not credited to Groww.",
        "theme": "Payments / UPI",
        "sub_theme": "UPI failures",
        "confidence": 0.95,
    },
    {
        "review_id": "example_upi_2",
        "text": "My SIP auto-pay is not working since last month. Getting payment gateway error.",
        "theme": "Payments / UPI",
        "sub_theme": "SIP payments",
        "confidence": 0.90,
    },
    {
        "review_id": "example_upi_3",
        "text": "Refund for failed transaction still pending after 2 weeks.",
        "theme": "Payments / UPI",
        "sub_theme": "Refunds",
        "confidence": 0.88,
    },
    # Statements / Tax Reports
    {
        "review_id": "example_tax_1",
        "text": "P&L statement shows wrong capital gains. Tax calculation is completely off.",
        "theme": "Statements / Tax Reports",
        "sub_theme": "P&L statements",
        "confidence": 0.93,
    },
    {
        "review_id": "example_tax_2",
        "text": "Where is the CDSL holding statement? I need it for ITR filing.",
        "theme": "Statements / Tax Reports",
        "sub_theme": "CDSL holding",
        "confidence": 0.88,
    },
    {
        "review_id": "example_tax_3",
        "text": "Capital gains report not available for this financial year. Very inconvenient.",
        "theme": "Statements / Tax Reports",
        "sub_theme": "Capital gains report",
        "confidence": 0.91,
    },
    # Withdrawals / Redemptions
    {
        "review_id": "example_withdraw_1",
        "text": "Withdrawal request pending for 7 days. Money stuck in the app.",
        "theme": "Withdrawals / Redemptions",
        "sub_theme": "Withdrawal delays",
        "confidence": 0.94,
    },
    {
        "review_id": "example_withdraw_2",
        "text": "Cannot link my bank account. Keeps showing verification failed error.",
        "theme": "Withdrawals / Redemptions",
        "sub_theme": "Bank account linking",
        "confidence": 0.89,
    },
    {
        "review_id": "example_withdraw_3",
        "text": "Mutual fund redemption failed twice. Settlement not happening.",
        "theme": "Withdrawals / Redemptions",
        "sub_theme": "Failed redemptions",
        "confidence": 0.90,
    },
    # App Performance / Bugs
    {
        "review_id": "example_perf_1",
        "text": "App crashes every time I open my portfolio. Latest update broke everything.",
        "theme": "App Performance / Bugs",
        "sub_theme": "Crashes",
        "confidence": 0.95,
    },
    {
        "review_id": "example_perf_2",
        "text": "App is extremely slow. Takes 30 seconds to load the dashboard.",
        "theme": "App Performance / Bugs",
        "sub_theme": "Slow loading",
        "confidence": 0.93,
    },
    {
        "review_id": "example_perf_3",
        "text": "Login OTP is never received. Tried 10 times, cannot access my account.",
        "theme": "App Performance / Bugs",
        "sub_theme": "OTP failures",
        "confidence": 0.91,
    },
]


def get_taxonomy_text() -> str:
    """Return a formatted string of the theme taxonomy for use in LLM prompts."""
    lines = []
    for i, (theme, sub_themes) in enumerate(THEME_TAXONOMY.items(), 1):
        sub_str = ", ".join(sub_themes)
        lines.append(f"{i}. {theme} — {sub_str}")
    return "\n".join(lines)


def get_few_shot_text() -> str:
    """Return formatted few-shot examples for use in LLM prompts."""
    lines = []
    for ex in FEW_SHOT_EXAMPLES:
        lines.append(
            f'  Review: "{ex["text"]}"\n'
            f'  → {{"review_id": "{ex["review_id"]}", "theme": "{ex["theme"]}", '
            f'"sub_theme": "{ex["sub_theme"]}", "confidence": {ex["confidence"]}}}'
        )
    return "\n\n".join(lines)


# Sentiment weights for theme ranking algorithm
SENTIMENT_WEIGHTS = {
    "strongly_negative": 2.0,
    "negative": 1.5,
    "neutral": 1.0,
    "positive": 0.8,
    "strongly_positive": 0.5,
}
