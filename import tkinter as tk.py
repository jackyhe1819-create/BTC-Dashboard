import requests
import time

# ANSI escape codes for colors
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def get_btc_price():
    """获取比特币的实时价格"""
    # 使用多个API来源以提高稳定性
    urls = [
        "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
        "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
        "https://api.kraken.com/0/public/Ticker?pair=XBTUSD"
    ]
    for url in urls:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if "coingecko" in url:
                return float(data['bitcoin']['usd'])
            elif "binance" in url:
                return float(data['price'])
            elif "kraken" in url:
                return float(data['result']['XXBTZUSD']['c'][0])
        except (requests.exceptions.RequestException, KeyError, ValueError) as e:
            print(f"{Colors.WARNING}从 {url} 获取价格失败: {e}{Colors.ENDC}")
            time.sleep(1)
    return None

def get_glassnode_data(url):
    """
    从Glassnode获取数据 (注意: 最新数据需要付费API密钥).
    为了演示分析框架，这里将使用硬编码的示例值。
    """
    # --- 模拟数据 ---
    if "mvrv" in url:
        # MVRV Z-Score 示例值: > 7 是历史顶部危险区
        return [{'v': 2.85}] # 模拟牛市中期的值
    if "puell" in url:
        # Puell Multiple 示例值: > 4 是历史顶部危险区
        return [{'v': 1.9}] # 模拟牛市中期的值
    
    return [{'v': 0.0}]

def get_fear_and_greed_index():
    """获取恐惧与贪婪指数"""
    try:
        response = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        response.raise_for_status()
        data = response.json()
        value = int(data['data'][0]['value'])
        classification = data['data'][0]['value_classification']
        return value, classification
    except (requests.exceptions.RequestException, KeyError, ValueError, IndexError) as e:
        print(f"{Colors.WARNING}获取恐惧贪婪指数失败: {e}{Colors.ENDC}")
        return None, "未知"

def get_funding_rate():
    """获取主要交易所的平均资金费率"""
    # 尝试直接从 Binance 获取，这是一个可靠的免费数据源
    try:
        response_binance = requests.get("https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=1", timeout=10)
        response_binance.raise_for_status()
        data_binance = response_binance.json()
        if data_binance and isinstance(data_binance, list):
            print(f"{Colors.OKCYAN}成功从 Binance 获取资金费率。{Colors.ENDC}")
            return float(data_binance[0]['fundingRate'])
    except (requests.exceptions.RequestException, KeyError, ValueError, IndexError) as e_binance:
        print(f"{Colors.FAIL}获取资金费率失败: {e_binance}{Colors.ENDC}")
        return None

def print_dashboard(price, mvrv_z, puell, fng_value, fng_class, funding_rate):
    """打印仪表盘"""
    print(Colors.HEADER + "="*50 + Colors.ENDC)
    print(Colors.HEADER + " " * 15 + "比特币牛市顶部观察仪表盘" + " " * 15 + Colors.ENDC)
    print(Colors.HEADER + "="*50 + Colors.ENDC)
    
    # --- 价格 ---
    price_str = f"${price:,.2f}" if price else "获取失败"
    print(f"{Colors.BOLD}当前价格:{Colors.ENDC} {Colors.OKCYAN}{price_str}{Colors.ENDC}")
    print("-"*50)

    # --- 核心链上估值指标 (框架参考) ---
    print(f"{Colors.BOLD}核心链上估值指标 (框架参考):{Colors.ENDC}")
    # MVRV Z-Score
    status = ""
    color = Colors.ENDC
    if mvrv_z < 0: status, color = "严重低估 (抄底区)", Colors.OKGREEN
    elif 0 <= mvrv_z < 3: status, color = "合理区间", Colors.OKBLUE
    elif 3 <= mvrv_z < 7: status, color = "高估/泡沫风险", Colors.WARNING
    else: status, color = "!!! 顶部危险区 !!!", Colors.FAIL
    print(f"  - MVRV Z-Score  : {color}{mvrv_z:.2f} - {status}{Colors.ENDC}")

    # Puell Multiple
    if puell < 0.5: status, color = "矿工投降 (抄底区)", Colors.OKGREEN
    elif 0.5 <= puell < 1.5: status, color = "矿工盈利健康", Colors.OKBLUE
    elif 1.5 <= puell < 4: status, color = "矿工盈利可观 (警惕)", Colors.WARNING
    else: status, color = "!!! 顶部危险区 !!!", Colors.FAIL
    print(f"  - Puell Multiple  : {color}{puell:.2f} - {status}{Colors.ENDC}")
    print("-"*50)
    
    # --- 实时市场情绪 ---
    print(f"{Colors.BOLD}实时市场情绪:{Colors.ENDC}")
    # Fear & Greed
    color = Colors.ENDC
    if fng_value is not None:
        if fng_value <= 25: color = Colors.FAIL
        elif fng_value <= 45: color = Colors.WARNING
        elif fng_value <= 75: color = Colors.OKGREEN
        else: color = Colors.OKGREEN + Colors.BOLD
    print(f"  - 恐惧贪婪指数: {color}{fng_value} ({fng_class}){Colors.ENDC}")

    # Funding Rate
    if funding_rate is not None:
        rate_pct = funding_rate * 100
        color = Colors.ENDC
        if rate_pct > 0.05: status, color = "极度贪婪", Colors.FAIL
        elif rate_pct > 0.01: status, color = "贪婪", Colors.WARNING
        elif rate_pct < -0.01: status, color = "恐慌", Colors.FAIL
        else: status, color = "中性", Colors.OKBLUE
        print(f"  - 平均资金费率: {color}{rate_pct:.4f}% ({status}){Colors.ENDC}")
    else:
        print(f"  - 平均资金费率: {Colors.WARNING}获取失败{Colors.ENDC}")

    print(Colors.HEADER + "="*50 + Colors.ENDC)
    print(f"{Colors.OKCYAN}* MVRV Z-Score > 7 和 Puell Multiple > 4 是历史顶部强信号。{Colors.ENDC}")
    print(f"{Colors.OKCYAN}* 链上数据为模拟值，仅供演示分析框架，不构成投资建议。{Colors.ENDC}")

if __name__ == "__main__":
    print("正在获取最新数据，请稍候...")
    
    # 获取数据
    btc_price = get_btc_price()
    
    # Glassnode API (使用模拟数据作为分析框架参考)
    mvrv_z_score = get_glassnode_data("https://api.glassnode.com/v1/metrics/market/mvrv_z_score")[-1]['v']
    puell_multiple = get_glassnode_data("https://api.glassnode.com/v1/metrics/mining/puell_multiple")[-1]['v']
    
    fng_index_value, fng_index_class = get_fear_and_greed_index()
    avg_funding_rate = get_funding_rate()

    # 打印仪表盘
    print_dashboard(
        price=btc_price,
        mvrv_z=mvrv_z_score,
        puell=puell_multiple,
        fng_value=fng_index_value,
        fng_class=fng_index_class,
        funding_rate=avg_funding_rate
    )

