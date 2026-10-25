from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

class SentimentAnalyser:
    def __init__(self, weights: tuple[float, float, float] = (0.4, 0.4, 0.2),
                 emoji_map: dict[str, float] = None):
        self.weights = weights
        self.emoji_map = emoji_map or {}
        self.analyzer = SentimentIntensityAnalyzer()

    def analyse(self, review: dict) -> dict:
        if review.get("quality_flag") != "clean":
            return review
            
        rating = review.get("rating")
        text = review.get("normalised_text", "")
        emojis = review.get("emojis", [])
        
        # 5.1 Rating-based sentiment
        rating_norm = 0.0
        if rating is not None:
            rating_norm = (rating - 3) / 2.0
            
        # 5.2 Text-based sentiment
        text_polarity = 0.0
        if text:
            scores = self.analyzer.polarity_scores(text)
            text_polarity = scores["compound"]
            
        # 5.3 Emoji sentiment
        emoji_sentiment = 0.0
        if emojis:
            valid_emojis = [self.emoji_map.get(e, 0.0) for e in emojis if e in self.emoji_map]
            if valid_emojis:
                emoji_sentiment = sum(valid_emojis) / len(valid_emojis)
                
        # 5.4 Composite sentiment
        w1, w2, w3 = self.weights
        composite_score = (w1 * rating_norm) + (w2 * text_polarity) + (w3 * emoji_sentiment)
        
        total_weight = w1 + w2 + w3
        if total_weight > 0:
            composite_score /= total_weight
            
        # 5.5 Sentiment label
        if composite_score < -0.5:
            label = "strongly_negative"
        elif composite_score < -0.1:
            label = "negative"
        elif composite_score <= 0.1:
            label = "neutral"
        elif composite_score <= 0.5:
            label = "positive"
        else:
            label = "strongly_positive"
            
        review["text_polarity"] = text_polarity
        review["emoji_sentiment"] = emoji_sentiment
        review["sentiment_score"] = composite_score
        review["sentiment_label"] = label
        
        return review
