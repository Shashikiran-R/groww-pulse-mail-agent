from app_store_scraper import AppStore
import warnings
warnings.filterwarnings("ignore")

try:
    groww = AppStore(country='in', app_name='groww', app_id=1404871703)
    groww.review(how_many=10)
    print("Found reviews:", len(groww.reviews))
except Exception as e:
    print(f"Error: {e}")
