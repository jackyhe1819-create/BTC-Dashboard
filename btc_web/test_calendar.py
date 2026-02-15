
import requests
import json
from datetime import datetime

def test_calendar():
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    print(f"Fetching {url}...")
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            events = resp.json()
            print(f"Total events: {len(events)}")
            if events:
                print("First event sample:")
                print(json.dumps(events[0], indent=2))
                
                usd_events = [e for e in events if e.get('country') == 'USD']
                print(f"USD events count: {len(usd_events)}")
                
                high_impact = [e for e in usd_events if e.get('impact') in ['High', 'Medium']]
                print(f"High/Medium USD events: {len(high_impact)}")
                
                for e in high_impact[:3]:
                    print(f" - {e.get('title')} ({e.get('impact')}) Date: {e.get('date')}")
        else:
            print(f"Error: {resp.status_code}")
    except Exception as e:
        print(f"Exception: {e}")

def test_whale_link():
    # Test Blockchain.com link format
    tx_hash = "b6f6a739d454378f" # partial
    old_url = f"https://www.blockchain.com/btc/tx/{tx_hash}"
    new_url = f"https://www.blockchain.com/explorer/transactions/btc/{tx_hash}"
    
    print(f"\nTesting Whale Links:")
    print(f"Old: {old_url}")
    print(f"New: {new_url}")
    # We can't easily curl without full hash, but we can verify usually
    
if __name__ == "__main__":
    test_calendar()
    test_whale_link()
