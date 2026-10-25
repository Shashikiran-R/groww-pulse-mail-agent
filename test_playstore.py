from google_play_scraper import reviews, Sort
result, token = reviews('com.nextbillion.groww', count=5, sort=Sort.NEWEST)
print(f"Playstore reviews: {len(result)}")
