import unicodedata
import re
from datetime import datetime
from typing import Optional

class TextNormaliser:
    def __init__(self, abbreviations: dict[str, str]):
        self.abbreviations = abbreviations
        # 3.10 Hinglish detection patterns
        # Some basic Latin-script Hindi words
        hinglish_words = ['hai', 'kya', 'nahi', 'bekar', 'bahut', 'bhi', 'app', 'yeh', 'mera']
        self.hinglish_pattern = re.compile(r'\b(?:' + '|'.join(hinglish_words) + r')\b', re.IGNORECASE)

    def normalise(self, review: dict) -> Optional[dict]:
        text = review.get('cleaned_text', '')
        
        # Preserve original
        review['original_text'] = review.get('text', '')
        
        # 3.8 Case normalisation
        text = text.lower()
        
        # 3.9 Unicode NFKC
        text = unicodedata.normalize('NFKC', text)
        
        # 3.10 Hinglish detection
        review['is_hinglish'] = bool(self.hinglish_pattern.search(text))
        
        # 3.11 Abbreviation expansion
        words = text.split()
        expanded_words = []
        for word in words:
            if word in self.abbreviations:
                expanded_words.append(self.abbreviations[word])
            else:
                expanded_words.append(word)
                

        text = ' '.join(expanded_words)
        review['normalised_text'] = text
        
        # 3.12 Date normalisation
        raw_date = review.get('date')
        if raw_date:
            try:
                if isinstance(raw_date, str):
                    # Trying to parse standard iso date from scraper
                    dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
                else:
                    dt = raw_date
                review['date'] = dt.isoformat()
            except Exception:
                pass # If parsing fails, just keep original
        
        # 3.13 Rating normalisation
        raw_rating = review.get('rating')
        if raw_rating is not None:
            try:
                rating = int(raw_rating)
                if rating < 1:
                    rating = 1
                elif rating > 5:
                    rating = 5
                review['rating'] = rating
            except ValueError:
                review['rating'] = None
                
        return review
