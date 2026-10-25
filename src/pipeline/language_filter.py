from langdetect import detect_langs
from langdetect.lang_detect_exception import LangDetectException

class LanguageFilter:
    def __init__(self, confidence_threshold: float = 0.8):
        self.confidence_threshold = confidence_threshold

    def filter(self, review: dict) -> dict:
        text = review.get("normalised_text", "")
        is_hinglish = review.get("is_hinglish", False)
        word_count = len(text.split())
        
        # 4.3 Short text handling
        if word_count < 5:
            review["detected_language"] = "en"
            review["language_confidence"] = 1.0
            return review
            
        try:
            langs = detect_langs(text)
            best_match = langs[0]
            detected_language = best_match.lang
            confidence = best_match.prob
        except LangDetectException:
            detected_language = "unknown"
            confidence = 0.0
            
        review["detected_language"] = detected_language
        review["language_confidence"] = confidence
        
        # 4.2 English filter logic
        if detected_language == "en" or is_hinglish:
            pass # Valid
        elif confidence > self.confidence_threshold:
            review["quality_flag"] = "excluded_language"
            review["quality_reason"] = f"Detected {detected_language} with high confidence"
            
        return review
