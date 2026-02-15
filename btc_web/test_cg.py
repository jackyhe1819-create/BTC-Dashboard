
import requests

def test_cg_derivatives():
    url = "https://api.coingecko.com/api/v3/derivatives"
    try:
        response = requests.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            # Find BTC futures
            btc_futures = [x for x in data if 'BTC' in x.get('symbol', '') or 'Bitcoin' in x.get('market', '')]
            print(f"Found {len(btc_futures)} BTC derivative pairs")
            for item in btc_futures[:5]:
                print(item)
    except Exception as e:
        print(f"Derivatives Error: {e}")

def test_cg_global():
    print("\nTesting Global (Dominance)...")
    url = "https://api.coingecko.com/api/v3/global"
    try:
        response = requests.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("Success!")
            # print(str(data)[:200])
    except Exception as e:
        print(f"Global Error: {e}")

def test_cg_companies():
    print("\nTesting Companies (Holdings)...")
    url = "https://api.coingecko.com/api/v3/companies/public_treasury/bitcoin"
    try:
        response = requests.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("Success!")
            print(f"Found {len(data.get('companies', []))} companies")
    except Exception as e:
        print(f"Companies Error: {e}")

test_cg_derivatives()
test_cg_global()
test_cg_companies()

def test_cg_exchanges():
    print("\nTesting Exchanges...")
    url = "https://api.coingecko.com/api/v3/exchanges"
    try:
        response = requests.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Found {len(data)} exchanges")
            # Check Binance (usually top)
            binance = next((x for x in data if x['id'] == 'binance'), None)
            if binance:
                print("Binance Data:", binance)
    except Exception as e:
        print(f"Exchanges Error: {e}")

test_cg_exchanges()
