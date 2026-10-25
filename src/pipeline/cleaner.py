import html
import re

class TextCleaner:
    def __init__(self):
        # 3.2 URL removal regex
        self.url_pattern = re.compile(r'https?://\S+')
        # 3.3 Email removal regex
        self.email_pattern = re.compile(r'\S+@\S+\.\S+')
        # 3.4 Punctuation collapse regex
        self.punct_pattern = re.compile(r'([!?.]){2,}')
        # 3.6 Control character strip regex (excluding standard whitespace)
        self.control_pattern = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u200b\ufeff]')
        # 3.7 Emoji regex (basic range for common emojis)
        self.emoji_pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\u2600-\u26FF\u2700-\u27BF]')
        
    def clean(self, review: dict) -> dict:
        text = review.get('text', '') or ''
        
        # 3.1 HTML entity decoding
        text = html.unescape(text)
        
        # 3.2 URL removal
        text = self.url_pattern.sub('', text)
        
        # 3.3 Email removal
        text = self.email_pattern.sub('', text)
        
        # 3.6 Control character strip
        text = self.control_pattern.sub('', text)
        
        # 3.7 Emoji separation
        emojis = self.emoji_pattern.findall(text)
        review['emojis'] = emojis
        text = self.emoji_pattern.sub('', text)
        
        # 3.4 Punctuation collapse
        text = self.punct_pattern.sub(r'\1', text)
        
        # 3.5 Whitespace normalisation
        text = re.sub(r'\s+', ' ', text).strip()
        
        review['cleaned_text'] = text
        return review
