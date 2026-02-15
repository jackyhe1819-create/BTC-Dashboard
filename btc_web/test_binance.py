
import requests
import sys

def test_api(name, url, params=None):
    print(f"Testing {name}...")
    print(f"URL: {url}")
    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("Success! Response sample:")
            print(str(response.json())[:200])
        else:
            print("Failed!")
            print(f"Response: {response.text[:200]}")
    except Exception as e:
        print(f"Exception: {e}")
    print("-" * 40)

# 1. Funding Rate
test_api(
    "Funding Rate", 
    "https://fapi.binance.com/fapi/v1/fundingRate",
    params={"symbol": "BTCUSDT", "limit": 1}
)

# 2. Long/Short Ratio
test_api(
    "Long/Short Ratio",
    "https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
    params={"symbol": "BTCUSDT", "period": "1d", "limit": 1}
)
