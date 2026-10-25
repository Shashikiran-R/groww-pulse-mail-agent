import json
from pathlib import Path
from src.pipeline.cleaner import TextCleaner
from src.pipeline.normaliser import TextNormaliser
from src.config import config

def main():
    raw_dir = Path("data/raw")
    cleaner = TextCleaner()
    normaliser = TextNormaliser(config.ABBREVIATIONS)
    
    total_reviews = 0
    hinglish_count = 0
    
    for file_path in raw_dir.glob("*.json"):
        with open(file_path, "r", encoding="utf-8") as f:
            reviews = json.load(f)
            
        for review in reviews:
            clean_review = cleaner.clean(review)
            norm_review = normaliser.normalise(clean_review)
            
            if norm_review is not None:
                total_reviews += 1
                if norm_review.get("is_hinglish"):
                    hinglish_count += 1

    print(f"Processed {total_reviews} reviews successfully.")
    print(f"Hinglish reviews detected: {hinglish_count}")

if __name__ == "__main__":
    main()
