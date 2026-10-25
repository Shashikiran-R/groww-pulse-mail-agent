import requests
import json
from pprint import pprint

url = "https://itunes.apple.com/in/rss/customerreviews/page=1/id=1404871703/sortby=mostrecent/json"
response = requests.get(url)
data = response.json()
entries = data.get('feed', {}).get('entry', [])
if entries:
    pprint(entries[1])
