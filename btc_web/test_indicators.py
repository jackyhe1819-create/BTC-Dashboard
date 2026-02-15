
import sys
import os
import requests
import json

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), '..')))

from btc_dashboard import calc_funding_rate, calc_lth_supply

def test_funding():
    print("\n--- Testing Funding Rate ---")
    result = calc_funding_rate()
    print(f"Result: {result}")
    if result.value != result.value: # Check for NaN
        print("Funding Rate returned NaN!")
    else:
        print(f"Value: {result.value}")

def test_lth():
    print("\n--- Testing LTH Supply (CDD) ---")
    result = calc_lth_supply()
    print(f"Result: {result}")
    if result.value != result.value: # Check for NaN
        print("LTH Supply returned NaN!")
    else:
        print(f"Value: {result.value}")

if __name__ == "__main__":
    test_funding()
    test_lth()
