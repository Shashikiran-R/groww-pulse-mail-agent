import requests
import json
from pprint import pprint

url = "https://itunes.apple.com/in/rss/customerreviews/id=1404871703/sortBy=mostRecent/page=1/json"
response = requests.get(url)
data = response.json()

if 'feed' in data and 'entry' in data['feed']:
    entries = data['feed']['entry']
    print(f"Found {len(entries)} entries")
    if entries:
        pprint(entries[1] if len(entries) > 1 else entries[0])
else:
    print("No entries found")
    pprint(data)
