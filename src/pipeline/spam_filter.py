import re
import math
from collections import Counter
import logging

logger = logging.getLogger(__name__)

class SpamFilter:
    def __init__(self, min_length: int = 10, similarity_threshold: float = 0.95, min_words: int = 10):
        self.min_length = min_length
        self.min_words = min_words
        self.similarity_threshold = similarity_threshold
        
        # 4.7 Repetitive char
        self.rep_char_regex = re.compile(r'(.)\1{5,}')
        
        # 4.8 Incentivised review
        self.incentive_patterns = [
            re.compile(r'5\s*star.*reward', re.IGNORECASE),
            re.compile(r'rate.*cashback', re.IGNORECASE),
            re.compile(r'giving.*star.*coin', re.IGNORECASE)
        ]
        
        # 4.10 Mismatch keywords
        self.negative_words = {"worst", "terrible", "hate", "scam", "bad", "fake", "fraud", "useless", "pathetic"}
        self.positive_words = {"love", "best", "amazing", "great", "awesome", "excellent", "good", "nice", "superb"}
        
    def filter_batch(self, reviews: list[dict]) -> list[dict]:
        # TF-IDF computation for the batch
        documents = []
        for r in reviews:
            documents.append(r.get("normalised_text", "").split())
            
        # Compute IDF
        df = Counter()
        for doc in documents:
            df.update(set(doc))
            
        N = len(documents)
        idf = {word: math.log(N / count) + 1.0 for word, count in df.items()} if N > 0 else {}
        
        # Compute TF-IDF vectors
        tf_idfs = []
        for doc in documents:
            tf = Counter(doc)
            vector = {word: (count / len(doc)) * idf[word] for word, count in tf.items()} if doc else {}
            # Compute norm
            norm = math.sqrt(sum(v*v for v in vector.values()))
            tf_idfs.append((vector, norm))
            
        stats = {"clean": 0, "noise": 0, "spam": 0, "mismatch": 0, "excluded_language": 0}
            
        for i, review in enumerate(reviews):
            # If already flagged (e.g., by language filter), count and skip
            if "quality_flag" in review:
                stats[review["quality_flag"]] = stats.get(review["quality_flag"], 0) + 1
                continue
                
            text = review.get("normalised_text", "")
            words = text.split()
            emojis = review.get("emojis", [])
            rating = review.get("rating")
            
            # Keep only reviews which have more than min_words (default 10)
            if len(words) <= self.min_words or len(text) < self.min_length:
                review["quality_flag"] = "noise"
                if len(words) == 0:
                    review["quality_reason"] = "Emoji only" if emojis else "Empty review"
                elif len(words) == 1:
                    review["quality_reason"] = "Single word"
                else:
                    review["quality_reason"] = f"Text too short ({len(words)} words, min > {self.min_words} required)"
            # 4.7 Repetitive chars
            elif self.rep_char_regex.search(text):
                review["quality_flag"] = "noise"
                review["quality_reason"] = "Repetitive characters"
            # 4.8 Incentivised
            elif any(p.search(text) for p in self.incentive_patterns):
                review["quality_flag"] = "spam"
                review["quality_reason"] = "Incentivised review"
            # 4.10 Mismatch
            elif rating == 5 and any(w in words for w in self.negative_words):
                review["quality_flag"] = "mismatch"
                review["quality_reason"] = "5 star rating with negative text"
            elif rating == 1 and any(w in words for w in self.positive_words):
                review["quality_flag"] = "mismatch"
                review["quality_reason"] = "1 star rating with positive text"
            else:
                # 4.9 Bot-like duplicate detection
                is_duplicate = False
                if len(words) > 3:
                    vec_i, norm_i = tf_idfs[i]
                    if norm_i > 0:
                        for j in range(i):
                            vec_j, norm_j = tf_idfs[j]
                            if norm_j > 0:
                                dot = sum(vec_i[w] * vec_j.get(w, 0) for w in vec_i)
                                sim = dot / (norm_i * norm_j)
                                if sim > self.similarity_threshold:
                                    is_duplicate = True
                                    break
                
                if is_duplicate:
                    review["quality_flag"] = "spam"
                    review["quality_reason"] = "Duplicate review detected"
                else:
                    review["quality_flag"] = "clean"
                    
            stats[review["quality_flag"]] = stats.get(review["quality_flag"], 0) + 1

        logger.info(f"Processed {len(reviews)} reviews: {stats.get('clean', 0)} clean, {stats.get('noise', 0)} noise, {stats.get('spam', 0)} spam, {stats.get('mismatch', 0)} mismatches, {stats.get('excluded_language', 0)} excluded_language")
        
        return reviews
