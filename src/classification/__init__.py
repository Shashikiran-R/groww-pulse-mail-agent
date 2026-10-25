"""
Classification engine — Theme clustering & quote selection.
"""

from src.classification.taxonomy import THEME_TAXONOMY, VALID_THEMES, FALLBACK_THEME
from src.classification.clusterer import ThemeClusterer
from src.classification.quote_scorer import QuoteScorer

__all__ = [
    "THEME_TAXONOMY",
    "VALID_THEMES",
    "FALLBACK_THEME",
    "ThemeClusterer",
    "QuoteScorer",
]
