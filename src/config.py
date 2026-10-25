import os
import logging
from dataclasses import dataclass
from typing import Tuple, Dict
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq")
    APP_ID: str = os.getenv("APP_ID", "com.nextbillion.groww")
    APP_STORE_APP_ID: int = int(os.getenv("APP_STORE_APP_ID", "1404871703"))
    APP_STORE_APP_NAME: str = os.getenv("APP_STORE_APP_NAME", "groww-stocks-mutual-fund-ipo")
    APP_STORE_COUNTRY: str = os.getenv("APP_STORE_COUNTRY", "in")
    LOOKBACK_WEEKS: int = int(os.getenv("LOOKBACK_WEEKS", "12"))
    MIN_REVIEW_LENGTH: int = int(os.getenv("MIN_REVIEW_LENGTH", "10"))
    MIN_REVIEW_WORDS: int = int(os.getenv("MIN_REVIEW_WORDS", "10"))
    LANGUAGE_CONFIDENCE_THRESHOLD: float = float(os.getenv("LANGUAGE_CONFIDENCE_THRESHOLD", "0.8"))
    SPAM_SIMILARITY_THRESHOLD: float = float(os.getenv("SPAM_SIMILARITY_THRESHOLD", "0.95"))
    
    _sentiment_weights = os.getenv("SENTIMENT_WEIGHTS", "0.4,0.4,0.2").split(",")
    SENTIMENT_WEIGHTS: Tuple[float, float, float] = (
        float(_sentiment_weights[0]),
        float(_sentiment_weights[1]),
        float(_sentiment_weights[2])
    )
    
    LLM_BATCH_SIZE: int = int(os.getenv("LLM_BATCH_SIZE", "50"))
    CLASSIFICATION_CONFIDENCE_THRESHOLD: float = float(os.getenv("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.6"))
    
    EMAIL_TO: str = os.getenv("EMAIL_TO", "")
    PULSE_EMAIL_RECIPIENTS: str = os.getenv("PULSE_EMAIL_RECIPIENTS", "")
    DOC_TITLE_PREFIX: str = os.getenv("DOC_TITLE_PREFIX", "Groww Weekly Pulse")
    
    # --- MCP Server (Google Workspace MCP) ---
    MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL", "https://aiagentserver.onrender.com")
    MCP_AUTH_TOKEN: str = os.getenv("MCP_AUTH_TOKEN", "")
    MCP_TRANSPORT: str = os.getenv("MCP_TRANSPORT", "sse")
    GROWW_PULSE_DOC_URL: str = os.getenv("GROWW_PULSE_DOC_URL", "")
    GROWW_PULSE_DOC_ID: str = os.getenv("GROWW_PULSE_DOC_ID", "")
    
    RUN_DAY: str = os.getenv("RUN_DAY", "monday")
    RUN_HOUR: int = int(os.getenv("RUN_HOUR", "9"))

config = Config()

THEME_TAXONOMY = {
    "Onboarding / KYC": ["Account creation", "KYC verification delays", "document upload issues", "eKYC"],
    "Payments / UPI": ["UPI failures", "payment gateway errors", "auto-pay", "SIP payments", "refunds"],
    "Statements / Tax Reports": ["P&L statements", "tax harvesting", "capital gains report", "CDSL holding"],
    "Withdrawals / Redemptions": ["Withdrawal delays", "bank account linking", "failed redemptions", "settlement"],
    "App Performance / Bugs": ["Crashes", "slow loading", "UI glitches", "login issues", "OTP failures", "updates"],
    "Trading & Order Execution": ["F&O trading issues", "Stop loss and target triggers", "Order execution and slippage", "Charts and TradingView", "Option chain data", "Intraday position squaring"],
    "Brokerage & Charges": ["High brokerage charges", "Hidden fees and deductions", "DP charges", "Annual maintenance charges (AMC)", "GST and regulatory fees"],
    "Customer Support & Service": ["Helpline unresponsiveness", "Chatbot and automated replies", "Delayed ticket resolution", "Lack of human agent", "Account support complaints"],
    "Usability & Positive Feedback": ["User friendly UI", "Beginner-friendly investment", "Clean design and navigation", "General praise and satisfaction", "Portfolio tracking simplicity"]
}

ABBREVIATIONS = {
    "txn": "transaction",
    "amt": "amount",
    "govt": "government"
}

EMOJI_SENTIMENT_MAP = {
    "😡": -0.8, "🤬": -0.9, "😤": -0.6, "😢": -0.5, "😭": -0.7,
    "👎": -0.7, "💔": -0.6, "😞": -0.5, "😠": -0.7, "🤮": -0.8,
    "😊": 0.7,  "😍": 0.8,  "❤️": 0.7,  "👍": 0.7,  "🙏": 0.4,
    "🔥": 0.5,  "💯": 0.6,  "⭐": 0.5,  "🎉": 0.7,  "😀": 0.6,
    "👌": 0.5,  "🥳": 0.7,  "💪": 0.5,  "✨": 0.4,  "🙂": 0.3,
}

config.THEME_TAXONOMY = THEME_TAXONOMY
config.ABBREVIATIONS = ABBREVIATIONS
config.EMOJI_SENTIMENT_MAP = EMOJI_SENTIMENT_MAP


from logging.handlers import RotatingFileHandler

# Setup logging with rotating file handler + stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('app.log', maxBytes=10485760, backupCount=5),
        logging.StreamHandler()
    ]
)
