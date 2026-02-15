
import sys
import os
import pandas as pd
import requests

# Add current directory to path
# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), '..')))

from btc_dashboard import calc_lth_supply, IndicatorResult

print("Running calc_lth_supply()...")
result = calc_lth_supply()
print(f"Result: {result}")
if result:
    print(f"Name: {result.name}")
    print(f"Status: {result.status}")
    print(f"Value: {result.value}")
    print(f"Desc: {result.description}")
