#!/Users/jack/opt/anaconda3/bin/python
# -*- coding: utf-8 -*-
"""
BTC 长期指标仪表盘
==================
基于需求文档实现的 P0 + P1 指标监控系统

指标列表:
- P0: Pi Cycle Top, 减半周期, Ahr999, 长期持有者(CDD)
- P1: 幂律走廊
- (P0 MVRV 需 Glassnode API，暂用占位)

运行要求:
    pip install yfinance pandas matplotlib
"""

import pandas as pd
import numpy as np
import yfinance as yf
import requests
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Tuple, Dict, Optional
import warnings
warnings.filterwarnings('ignore')


def fetch_realtime_btc_price() -> Optional[float]:
    """
    从多个 API 获取实时 BTC 价格
    优先级: CoinGecko -> Binance -> Coinbase
    """
    apis = [
        {
            "name": "CoinGecko",
            "url": "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            "parser": lambda r: r.json()["bitcoin"]["usd"]
        },
        {
            "name": "Binance",
            "url": "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
            "parser": lambda r: float(r.json()["price"])
        },
        {
            "name": "Coinbase",
            "url": "https://api.coinbase.com/v2/prices/BTC-USD/spot",
            "parser": lambda r: float(r.json()["data"]["amount"])
        }
    ]
    
    for api in apis:
        try:
            response = requests.get(api["url"], timeout=10)
            if response.status_code == 200:
                price = api["parser"](response)
                print(f"✅ 实时价格 ({api['name']}): ${price:,.2f}")
                return price
        except Exception as e:
            print(f"⚠️ {api['name']} API 失败: {e}")
            continue
    
    return None


# ============================================================
# 配置常量
# ============================================================

# 比特币创世日期
GENESIS_DATE = datetime(2009, 1, 3)

# 历史减半日期
HALVING_DATES = [
    datetime(2012, 11, 28),  # 第一次减半
    datetime(2016, 7, 9),    # 第二次减半
    datetime(2020, 5, 11),   # 第三次减半
    datetime(2024, 4, 20),   # 第四次减半
]

# 预计下次减半（约4年后）
NEXT_HALVING_ESTIMATE = datetime(2028, 4, 20)


# 幂律参数
POWER_LAW_INTERCEPT = -17.67
POWER_LAW_SLOPE = 5.93

# Ahr999 参数 (九神原版参数)
AHR999_A = -17.01  # 截距
AHR999_B = 5.84    # 斜率


# ============================================================
# 数据类定义
# ============================================================

@dataclass
class IndicatorResult:
    """单个指标的结果"""
    name: str           # 指标名称
    value: float        # 原始值
    score: int          # 评分: -1, 0, 1
    color: str          # 颜色: 🟢, 🟡, 🔴
    status: str         # 状态描述
    priority: str       # 优先级: P0, P1, P2
    description: str = "" # 指标定义
    method: str = ""    # 计算方式
    url: Optional[str] = None  # 外部链接 (可选)


@dataclass
class DashboardResult:
    """仪表盘总结果"""
    timestamp: datetime
    btc_price: float
    indicators: Dict[str, IndicatorResult]
    total_score: float
    recommendation: str


# ============================================================
# 数据获取
# ============================================================

def fetch_btc_data(start_date: str = "2013-01-01", max_retries: int = 3) -> pd.DataFrame:
    """获取 BTC 历史价格数据（带重试机制，多数据源）"""
    import time
    
    print("📥 正在获取 BTC 价格数据...")
    
    # 方法1: Yahoo Finance
    for attempt in range(max_retries):
        try:
            btc = yf.download("BTC-USD", start=start_date, progress=False)
            
            # 处理多重索引
            if isinstance(btc.columns, pd.MultiIndex):
                btc.columns = btc.columns.get_level_values(0)
            
            btc = btc[['Close']].dropna()
            
            if btc.empty:
                raise ValueError("获取到空数据")
            
            btc.columns = ['price']
            print(f"✅ Yahoo Finance: 获取到 {len(btc)} 条数据，最新日期: {btc.index[-1].date()}")
            return btc
            
        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ Yahoo Finance 尝试 {attempt + 1}/{max_retries} 失败: {error_msg}")
            
            # 如果是限流错误，直接停止重试
            if "Rate limited" in error_msg or "Too Many Requests" in error_msg:
                print("⛔️ Yahoo Finance API 限流，尝试备用数据源...")
                break
                
            if attempt < max_retries - 1:
                time.sleep(1)
    
    # 方法2: CoinGecko API (获取最近365天数据，足够计算主要指标)
    print("📡 尝试 CoinGecko API...")
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
            params={"vs_currency": "usd", "days": "max", "interval": "daily"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            prices = data.get("prices", [])
            
            if prices:
                df = pd.DataFrame(prices, columns=["timestamp", "price"])
                df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
                df.set_index("date", inplace=True)
                df = df[["price"]]
                print(f"✅ CoinGecko: 获取到 {len(df)} 条数据，最新日期: {df.index[-1].date()}")
                return df
        else:
            print(f"⚠️ CoinGecko API Error: Status {response.status_code}")
    except Exception as e:
        print(f"⚠️ CoinGecko API 失败: {e}")
    
    # 方法3: Binance Klines (Public API, Reliable)
    print("📡 尝试 Binance API (Klines)...")
    try:
        # 获取最近 1000 天 (约3年) 数据
        response = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": "BTCUSDT", "interval": "1d", "limit": 1000},
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            # Binance format: [Open time, Open, High, Low, Close, Volume, ...]
            # We need Close Price (Index 4) and Open Time (Index 0)
            prices = []
            for item in data:
                prices.append({
                    "timestamp": item[0],
                    "price": float(item[4])
                })
            
            df = pd.DataFrame(prices)
            df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("date", inplace=True)
            df = df[["price"]]
            print(f"✅ Binance: 获取到 {len(df)} 条数据，最新日期: {df.index[-1].date()}")
            return df
        else:
            print(f"⚠️ Binance API Error: Status {response.status_code}")
    except Exception as e:
        print(f"⚠️ Binance API 失败: {e}")

    # 方法4: 所有来源都失败，使用示例数据
    print("⚠️ 无法获取实时数据，使用示例数据演示...")
    return generate_sample_data()


def generate_sample_data() -> pd.DataFrame:
    """生成示例数据用于演示（当 API 不可用时）"""
    # 使用一些典型的 BTC 价格数据点
    dates = pd.date_range(start='2020-01-01', end=datetime.now(), freq='D')
    
    # 模拟价格走势（基于幂律增长 + 周期波动）
    days = np.arange(len(dates))
    base_price = 7000  # 2020年初价格
    
    # 添加增长趋势和周期性
    trend = base_price * (1.002 ** days)  # 日均0.2%增长
    cycle = np.sin(days / 365 * 2 * np.pi) * 0.3  # 年度周期
    noise = np.random.normal(0, 0.02, len(days))  # 随机噪声
    
    prices = trend * (1 + cycle + noise)
    
    # 最新价格设为约 $95000
    prices = prices * (95000 / prices[-1])
    
    df = pd.DataFrame({'price': prices}, index=dates)
    print(f"📊 生成了 {len(df)} 条示例数据")
    return df

# 指标计算函数
# ============================================================

def calc_two_year_ma_multiplier(df: pd.DataFrame) -> IndicatorResult:
    """
    2-Year MA Multiplier (2年均线乘数)
    - 绿线: 2年移动平均线 (730日线) -> 世代买点
    - 红线: 2年均线 x 5倍 -> 世代卖点
    """
    if df.empty or len(df) < 730:
        return IndicatorResult(name="2-Year MA Mult", value=0, score=0, color="⚪", status="数据不足", priority="P0")

    current_price = df['price'].iloc[-1]
    
    # 计算 MA730 (2 Year MA)
    # 确保使用足够的历史数据
    ma2y = df['price'].rolling(window=730).mean().iloc[-1]
    ma2y_x5 = ma2y * 5
    
    # 状态判断
    if current_price < ma2y:
        score = 1
        color = "🟢"
        status = f"低于绿线 (${ma2y:,.0f}) - 世代抄底"
    elif current_price > ma2y_x5:
        score = -1
        color = "🔴"
        status = f"高于红线 (${ma2y_x5:,.0f}) - 世代逃顶"
    elif current_price < ma2y * 1.5:
        score = 0.5
        color = "🟢"
        status = f"接近买入区 (${ma2y:,.0f})"
    elif current_price > ma2y_x5 * 0.8:
        score = -0.5
        color = "🟠"
        status = f"接近卖出区 (${ma2y_x5:,.0f})"
    else:
        score = 0
        color = "🟡"
        status = "区间震荡"
        
    return IndicatorResult(
        name="2-Year MA Mult",
        value=current_price / ma2y,  # 返回倍数作为 Value
        score=score,
        color=color,
        status=status,
        priority="P0",
        url="https://www.lookintobitcoin.com/charts/bitcoin-investor-tool/",
        description="2年均线乘数指标用于识别比特币市场周期中的买卖机会。",
        method="由2年移动平均线（730日线）及其5倍线构成。价格低于2年均线为买入区，高于5倍线为卖出区。"
    )


def calc_200w_ma_heatmap(df: pd.DataFrame) -> IndicatorResult:
    """
    200-Week MA Heatmap (200周均线热力图)
    - 200周均线 (1400天) 是比特币的历史绝对底部
    - 颜色根据价格偏离度变化
    """
    if df.empty or len(df) < 1400:
        return IndicatorResult(name="200-Week Heatmap", value=0, score=0, color="⚪", status="数据不足", priority="P0")

    current_price = df['price'].iloc[-1]
    
    # 计算 MA1400 (200 Week MA)
    ma200w = df['price'].rolling(window=1400).mean().iloc[-1]
    
    # 计算涨幅百分比
    pct_diff = (current_price - ma200w) / ma200w
    
    # 评分逻辑 (基于历史涨幅分布, 假设 +15%以内为底部, >300%为顶部)
    if pct_diff < 0.15:
        score = 1
        color = "🟢" # 极冷/买入 (Blue/Purple equivalent)
        status = f"触底区 (+{pct_diff*100:.1f}%)"
    elif pct_diff < 0.5:
        score = 0.5
        color = "🟢"
        status = f"低估区 (+{pct_diff*100:.1f}%)"
    elif pct_diff > 3.0: # >300%
        score = -1
        color = "🔴"
        status = f"极热区 (+{pct_diff*100:.0f}%)"
    elif pct_diff > 1.5:
        score = -0.5
        color = "🟠"
        status = f"过热区 (+{pct_diff*100:.0f}%)"
    else:
        score = 0
        color = "🟡"
        status = f"中性区 (+{pct_diff*100:.0f}%)"
        
    return IndicatorResult(
        name="200-Week Heatmap",
        value=pct_diff * 100, # Value as Percentage
        score=score,
        color=color,
        status=status,
        priority="P0",
        url="https://www.lookintobitcoin.com/charts/200-week-moving-average-heatmap/",
        description="200周均线热力图通过价格与200周均线的偏离程度来判断市场冷热。",
        method="200周移动平均线（约1400天）被认为是比特币的长期支撑。价格偏离该均线的百分比越高，市场越热。"
    )


def calc_golden_ratio_multiplier(df: pd.DataFrame) -> IndicatorResult:
    """
    Golden Ratio Multiplier (黄金比例乘数)
    - Base: 350 DMA
    - Multipliers: 1.6, 2.0, 3.0
    """
    if df.empty or len(df) < 350:
         return IndicatorResult(name="Golden Ratio", value=0, score=0, color="⚪", status="数据不足", priority="P1")

    current_price = df['price'].iloc[-1]
    ma350 = df['price'].rolling(window=350).mean().iloc[-1]
    
    # 关键位
    x1_6 = ma350 * 1.6
    x2_0 = ma350 * 2.0
    x3_0 = ma350 * 3.0
    
    # 状态判断
    if current_price > x3_0:
        score = -1
        color = "🔴"
        status = "突破 x3.0 (顶部风险)"
    elif current_price > x2_0:
        score = -0.5
        color = "🟠"
        status = "突破 x2.0 (FOMO区)"
    elif current_price > x1_6:
        score = 0.5
        color = "🟢"  # 突破黄金分割往往是牛市确认，但也意味着稍微脱离底部
        # 修正: 或者是"中性偏热"。但在牛市启动初期，突破1.6是强烈看涨信号。
        # 考虑到这是"周期逃顶"指标，越高越危险。
        score = 0 # 中性
        color = "🟡"
        status = "突破 x1.6 (牛市通过)"
    elif current_price < ma350:
        score = 1
        color = "🟢"
        status = "低于 350DMA (底部)"
    else:
        score = 1
        color = "🟢"
        status = "350DMA ~ x1.6 (吸筹区)"
        
    return IndicatorResult(
        name="Golden Ratio",
        value=current_price / ma350, # Value as multiple of 350DMA
        score=score,
        color=color,
        status=status,
        priority="P1",
        url="https://www.lookintobitcoin.com/charts/golden-ratio-multiplier/",
        description="黄金比例乘数通过350日均线及其倍数来识别市场周期中的关键支撑和阻力位。",
        method="以350日均线为基准，结合1.6、2.0、3.0等黄金比例乘数，判断价格所处的市场阶段。"
    )


def calc_pi_cycle(df: pd.DataFrame) -> IndicatorResult:
    """
    Pi Cycle Top 指标
    - 111DMA 与 350DMA×2 的关系
    """
    df = df.copy()
    df['ma111'] = df['price'].rolling(window=111).mean()
    df['ma350x2'] = df['price'].rolling(window=350).mean() * 2
    
    latest = df.iloc[-1]
    ma111 = latest['ma111']
    ma350x2 = latest['ma350x2']
    
    # 计算差距百分比
    gap_pct = (ma350x2 - ma111) / ma350x2 * 100
    
    # 评分逻辑
    if ma111 >= ma350x2:
        score, color, status = -1, "🔴", f"已交叉! 顶部信号"
    elif gap_pct <= 20:
        score, color, status = 0, "🟡", f"差距 {gap_pct:.1f}%, 接近交叉"
    else:
        score, color, status = 1, "🟢", f"差距 {gap_pct:.1f}%, 安全"
    
    return IndicatorResult(
        name="Pi Cycle Top",
        value=gap_pct,
        score=score,
        color=color,
        status=status,
        priority="P0",
        url="https://www.lookintobitcoin.com/charts/pi-cycle-top-indicator/",
        description="Pi Cycle Top 指标用于识别比特币市场周期的顶部，历史上准确率极高。",
        method="由两条移动平均线组成：111日均线 (111DMA) 和 350日均线的两倍 (350DMA x 2)。当 111DMA 上穿 350DMA x 2 时，预示市场顶部。"
    )


def calc_lth_supply() -> IndicatorResult:
    """
    长期持有者行为 (Proxy: 成交量趋势分析)
    - 数据源: CoinGecko (免费, 无需API Key)
    - 逻辑: 成交量低迷/下降 => 长期持有者在吸筹 (Bullish)
           成交量爆发/上升 => 长期持有者在派发 (Bearish)
    - 算法: 比较 7日成交量均值 vs 90日成交量均值的比率
    """
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=180&interval=daily",
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        )
        
        if response.status_code == 200:
            data = response.json()
            volumes = data.get('total_volumes', [])
            
            if not volumes or len(volumes) < 100:
                print(f"⚠️ Volume 数据不足: {len(volumes) if volumes else 0} 条")
                return IndicatorResult(name="长期持有者(CDD)", value=float('nan'), score=0, color="⚪", status="数据不足", priority="P0")
            
            # 提取成交量数据
            vol_values = [v[1] for v in volumes]
            df_vol = pd.DataFrame({'volume': vol_values})
            
            # 计算 7日均线 和 90日均线
            sma7 = df_vol['volume'].rolling(window=7).mean().iloc[-1]
            sma90 = df_vol['volume'].rolling(window=90).mean().iloc[-1]
            
            # 成交量比率: 短期 / 长期
            vol_ratio = sma7 / sma90
            
            # 当前7日均成交量 (亿美元)
            vol_billion = sma7 / 1e9
            
            # 信号逻辑:
            # 低成交量 (ratio < 0.8) => 吸筹期 (Bullish)
            # 正常成交量 (0.8-1.3) => 平稳期
            # 高成交量 (ratio > 1.3) => 活跃期 (可能派发)
            # 极高成交量 (ratio > 2.0) => 派发期 (Bearish)
            
            if vol_ratio < 0.7:
                score, color = 1, "🟢"
                status = f"深度吸筹 (量比 {vol_ratio:.2f})"
            elif vol_ratio < 0.9:
                score, color = 0.5, "🟢"
                status = f"吸筹中 (量比 {vol_ratio:.2f})"
            elif vol_ratio > 2.0:
                score, color = -1, "🔴"
                status = f"大量派发 (量比 {vol_ratio:.2f})"
            elif vol_ratio > 1.5:
                score, color = -0.5, "🟠"
                status = f"轻微派发 (量比 {vol_ratio:.2f})"
            else:
                score, color = 0, "🟡"
                status = f"持币观望 (量比 {vol_ratio:.2f})"
            
            return IndicatorResult(
                name="长期持有者(CDD)",
                value=round(vol_ratio, 2),
                score=score,
                color=color,
                status=f"{status} | {vol_billion:.1f}B$/日",
                priority="P0",
                url="https://www.coinglass.com/pro/i/bitcoin-cdd",
                description="使用成交量趋势分析作为长期持有者行为的代理指标。低成交量通常意味着长期持有者在吸筹，高成交量可能意味着派发。",
                method="计算 BTC 近7日均成交量与90日均成交量的比率。量比 < 0.8 代表吸筹（看多），量比 > 1.5 代表可能派发（看空）。数据来源: CoinGecko。"
            )
        else:
            print(f"⚠️ CoinGecko Volume API 返回 {response.status_code}")
            
    except Exception as e:
        print(f"⚠️ LTH Volume Proxy Failed: {e}")
        
    # 返回中性状态
    return IndicatorResult(
        name="长期持有者(CDD)",
        value=0,
        score=0,
        color="⚪",
        status="数据源连接失败",
        priority="P0",
        url="https://www.coinglass.com/pro/i/bitcoin-cdd",
        description="使用成交量趋势分析作为长期持有者行为的代理指标。",
        method="因网络问题无法连接 CoinGecko API。请检查网络连接。"
    )


def calc_hashrate() -> IndicatorResult:
    """
    全网算力 (Network Hashrate)
    - 数据源: blockchain.info
    - 单位: EH/s (Exahash per second)
    """
    try:
        response = requests.get(
            "https://blockchain.info/q/hashrate",
            timeout=10
        )
        if response.status_code == 200:
            # API 返回 TH/s，转换为 EH/s
            hashrate_ths = float(response.text)
            hashrate_ehs = hashrate_ths / 1_000_000  # TH -> EH
            
            # 评分逻辑：算力上涨是利好
            if hashrate_ehs > 800:
                score, color = 1, "🟢"
                status = f"{hashrate_ehs:.1f} EH/s (历史新高)"
            elif hashrate_ehs > 500:
                score, color = 0.5, "🟢"
                status = f"{hashrate_ehs:.1f} EH/s (高算力)"
            else:
                score, color = 0, "🟡"
                status = f"{hashrate_ehs:.1f} EH/s"
            
            return IndicatorResult(
                name="全网算力",
                value=hashrate_ehs,
                score=score,
                color=color,
                status=status,
                priority="P2",
                url="https://www.blockchain.com/explorer/charts/hash-rate",
                description="全网算力是衡量比特币网络安全性和矿工投入程度的指标。",
                method="通过区块链浏览器API获取全网算力数据。算力持续增长通常被视为网络健康和长期价值的积极信号。"
            )
    except Exception as e:
        print(f"⚠️ Hashrate API 失败: {e}")
    
    return IndicatorResult(
        name="全网算力",
        value=float('nan'),
        score=0,
        color="⚪",
        status="API 暂不可用",
        priority="P2"
    )


def calc_balanced_price(df: pd.DataFrame) -> IndicatorResult:
    """
    均衡价格 (Balanced Price)
    - 公式: Balanced Price = Realized Price - Transfer Price
    - 简化版: 使用 150日均线 与 350日均线 的中值作为近似
    """
    if df is None or len(df) < 350:
        return IndicatorResult(
            name="均衡价格",
            value=float('nan'),
            score=0,
            color="⚪",
            status="数据不足",
            priority="P1"
        )
    
    current_price = df['price'].iloc[-1]
    
    # 简化计算：使用 150日和 350日移动平均的均值
    ma_150 = df['price'].rolling(window=150).mean().iloc[-1]
    ma_350 = df['price'].rolling(window=350).mean().iloc[-1]
    balanced_price = (ma_150 + ma_350) / 2
    
    # 计算当前价格相对于均衡价格的倍数
    ratio = current_price / balanced_price if balanced_price > 0 else 0
    
    # 评分逻辑
    if ratio < 1.0:
        score, color = 1, "🟢"
        status = f"${balanced_price:,.0f} | 当前 {ratio:.2f}x (低于均衡)"
    elif ratio < 1.5:
        score, color = 0.5, "🟢"
        status = f"${balanced_price:,.0f} | 当前 {ratio:.2f}x (正常偏低)"
    elif ratio < 2.0:
        score, color = 0, "🟡"
        status = f"${balanced_price:,.0f} | 当前 {ratio:.2f}x (正常区间)"
    elif ratio < 3.0:
        score, color = -0.5, "🟠"
        status = f"${balanced_price:,.0f} | 当前 {ratio:.2f}x (偏高)"
    else:
        score, color = -1, "🔴"
        status = f"${balanced_price:,.0f} | 当前 {ratio:.2f}x (严重高估)"
    
    return IndicatorResult(
        name="均衡价格",
        value=balanced_price,
        score=score,
        color=color,
        status=status,
        priority="P1",
        description="均衡价格是衡量比特币公允价值的链上指标，通常被视为市场底部。",
        method="简化计算为150日均线和350日均线的平均值。价格低于均衡价格被认为是低估，高于则为高估。"
    )


def calc_halving_cycle() -> IndicatorResult:
    """
    减半周期位置
    - 计算距离上次减半的月数
    - 包含进度百分比用于进度条显示
    """
    today = datetime.now()
    
    # 找到最近的减半日期
    past_halvings = [d for d in HALVING_DATES if d <= today]
    last_halving = past_halvings[-1] if past_halvings else HALVING_DATES[0]
    
    # 找到下一次减半预计日期 (约4年后)
    next_halving = last_halving + timedelta(days=4*365)
    
    # 计算距离上次减半的月数
    months_since = (today - last_halving).days / 30.44
    
    # 计算距离下次减半的天数和进度
    days_until_next = (next_halving - today).days
    total_cycle_days = 4 * 365  # 约1460天
    progress_pct = min(100, ((total_cycle_days - days_until_next) / total_cycle_days) * 100)
    
    # 评分逻辑
    if months_since <= 12:
        score, color = 1, "🟢"
        status_text = f"减半后 {months_since:.0f} 个月 (牛市起点)"
    elif months_since <= 24:
        score, color = 0, "🟡"
        status_text = f"减半后 {months_since:.0f} 个月 (周期中期)"
    else:
        score, color = -1, "🔴"
        status_text = f"减半后 {months_since:.0f} 个月 (周期后期)"
    
    # 添加倒计时信息
    status = f"{status_text} | 下次约 {days_until_next} 天"
    
    return IndicatorResult(
        name="减半周期",
        value=months_since,
        score=score,
        color=color,
        status=status,
        priority="P0",
        description="比特币减半是其经济模型的核心事件，大约每四年发生一次，通常预示着牛市的到来。",
        method="根据比特币历史减半日期，计算当前所处的减半周期阶段。减半后12个月内通常是牛市早期，24个月后可能进入周期后期。"
    )


def calc_ahr999(df: pd.DataFrame) -> IndicatorResult:
    """
    Ahr999 指数 (九神囤币指标)
    
    正确公式：AHR999 = (BTC价格 / 200日定投成本) × (BTC价格 / 指数增长估值)
    
    - 200日定投成本：过去200天每天定投的平均成本
    - 指数增长估值：10^(5.84 × log10(币龄) - 17.01)
    
    阈值解读：
    - < 0.45: 抄底区 (极佳买入机会)
    - 0.45 - 1.2: 定投区 (适合定投)
    - > 1.2: 止盈区 (考虑获利了结)
    """
    # 获取最近200天的价格数据
    recent_200 = df['price'].tail(200)
    
    # 当前价格
    current_price = df['price'].iloc[-1]
    
    # 200日定投成本 (使用几何平均，Coinglass/TradingView 标准算法)
    # Geometric Mean = exp(mean(log(x)))
    try:
        # 使用 Numpy 计算几何平均 (更稳定且无需 Scipy)
        dca_cost_200 = np.exp(np.mean(np.log(recent_200)))
    except Exception as e:
        print(f"⚠️ Ahr999 Cost Calc Failed: {e}")
        dca_cost_200 = recent_200.mean() # Fallback to arithmetic
    
    # 计算币龄 (比特币诞生天数)
    today = datetime.now()
    days_since_genesis = (today - GENESIS_DATE).days
    
    # 九神指数增长估值公式: 10^(5.84 * log10(days) - 17.01)
    # 使用顶部定义的常量
    if days_since_genesis > 0:
        exp_growth_value = 10 ** (AHR999_B * np.log10(days_since_genesis) + AHR999_A)
    else:
        exp_growth_value = 1.0
    
    # AHR999 公式
    if dca_cost_200 > 0 and exp_growth_value > 0:
        ahr999 = (current_price / dca_cost_200) * (current_price / exp_growth_value)
        # DEBUG: Print calculation details
        print(f"\n[AHR999 DEBUG]")
        print(f"  Price: {current_price:.2f}")
        print(f"  Days: {days_since_genesis}")
        print(f"  Cost(200d GeoMean): {dca_cost_200:.2f}")
        print(f"  Fair Value (Exp): {exp_growth_value:.2f}")
        print(f"  Part 1 (P/Cost): {current_price/dca_cost_200:.4f}")
        print(f"  Part 2 (P/Fair): {current_price/exp_growth_value:.4f}")
        print(f"  Result: {ahr999:.4f}\n")
    else:
        ahr999 = 1.0
    if ahr999 < 0.45:
        score, color, status = 1, "🟢", f"抄底区 ({ahr999:.2f})"
    elif ahr999 < 1.2:
        score, color, status = 0, "🟡", f"定投区 ({ahr999:.2f})"
    else:
        score, color, status = -1, "🔴", f"止盈区 ({ahr999:.2f})"
    
    return IndicatorResult(
        name="Ahr999",
        value=ahr999,
        score=score,
        color=color,
        status=status,
        priority="P0",
        url="https://www.coinglass.com/pro/i/ahr999",
        description="Ahr999 指数用于辅助比特币定投和抄底，评估价格是否处于低估区间。",
        method="Ahr999 = (价格/200日定投成本) * (价格/指数增长估值)。< 0.45 抄底，0.45-1.2 定投，> 1.25 起飞。"
    )



def calc_power_law(df: pd.DataFrame) -> IndicatorResult:
    """
    幂律走廊位置
    - 计算当前价格相对于幂律中轨的位置
    """
    today = datetime.now()
    days_since_genesis = (today - GENESIS_DATE).days
    
    # 计算幂律中轨价格
    log_fair_value = POWER_LAW_INTERCEPT + POWER_LAW_SLOPE * np.log10(days_since_genesis)
    fair_value = 10 ** log_fair_value
    
    # 上下轨 (约 ±0.5 log 单位)
    upper_band = 10 ** (log_fair_value + 0.5)
    lower_band = 10 ** (log_fair_value - 0.5)
    
    current_price = df['price'].iloc[-1]
    
    # 计算相对位置 (-1 到 +1)
    if current_price < fair_value:
        position = (current_price - lower_band) / (fair_value - lower_band) - 1
    else:
        position = (current_price - fair_value) / (upper_band - fair_value)
    
    # 评分逻辑
    if current_price < lower_band:
        score, color, status = 1, "🟢", f"低于下轨 (${current_price:,.0f} < ${lower_band:,.0f})"
    elif current_price > upper_band:
        score, color, status = -1, "🔴", f"高于上轨 (${current_price:,.0f} > ${upper_band:,.0f})"
    else:
        score, color, status = 0, "🟡", f"通道内 (中轨 ${fair_value:,.0f})"
    
    return IndicatorResult(
        name="幂律走廊",
        value=position,
        score=score,
        color=color,
        status=status,
        priority="P1",
        url="https://charts.bitbo.io/power-law-corridor/",
        description="比特币幂律走廊模型，展示价格长期遵循的对数增长规律。",
        method="价格 = a * (天数 ^ b)。价格通常在支撑线和阻力线构成的通道内波动。偏离底部支撑线过远为低估，接近顶部阻力线为高估。"
    )


def calc_mayer_multiple(df: pd.DataFrame) -> IndicatorResult:
    """
    Mayer Multiple (梅耶倍数)
    - 价格 / 200日均线
    - 替代 MVRV Z-Score (因 API 不稳定)
    - < 0.8 低估, > 2.4 高估
    """
    df = df.copy()
    # 确保有足够数据计算 200MA
    if len(df) < 200:
         return IndicatorResult(
            name="Mayer Multiple",
            value=float('nan'),
            score=0,
            color="⚪",
            status="数据不足",
            priority="P0"
        )
        
    df['ma200'] = df['price'].rolling(window=200).mean()
    
    latest = df.iloc[-1]
    mm = latest['price'] / latest['ma200']
    
    # 评分逻辑
    if mm < 0.6:
        score, color, status = 1, "🟢", f"极度低估 ({mm:.2f}) - 抄底"
    elif mm < 1.1:
        score, color, status = 0.5, "🟢", f"低估区域 ({mm:.2f})"
    elif mm > 2.4:
        score, color, status = -1, "🔴", f"极度高估 ({mm:.2f}) - 逃顶"
    elif mm > 1.8:
        score, color, status = -0.5, "🟡", f"高估区域 ({mm:.2f})"
    else:
        score, color, status = 0, "🟡", f"合理估值 ({mm:.2f})"
        
    return IndicatorResult(
        name="Mayer Multiple",
        value=mm,
        score=score,
        color=color,
        status=status,
        priority="P0",
        url="https://charts.bitbo.io/mayer-multiple/",
        description="梅耶倍数通过比特币价格与200日移动平均线的比值，评估市场是否处于超买或超卖状态。",
        method="梅耶倍数 = 价格 / 200日均线。通常低于0.6为极度低估，高于2.4为极度高估。"
    )


# ============================================================
# 短期技术指标 - 本地计算
# ============================================================

def calc_rsi(df: pd.DataFrame, period: int = 14) -> IndicatorResult:
    """
    RSI 多周期汇总 (4H, 12H, 日, 周, 月, 年)
    - 计算各周期 RSI 信号
    - 汇总超买/超卖/中性信号数量
    """
    df = df.copy()
    
    if len(df) < period + 1:
        return IndicatorResult(
            name="RSI",
            value=float('nan'),
            score=0,
            color="⚪",
            status="数据不足",
            priority="短期",
            url="https://www.tradingview.com/chart/?symbol=BINANCE:BTCUSDT"
        )
    
    def calculate_single_rsi(price_series, period=14):
        """计算单周期 RSI"""
        if len(price_series) < period + 1:
            return None
        
        delta = price_series.diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = rsi.iloc[-1]
        
        if pd.isna(current_rsi):
            return None
        
        if current_rsi >= 80:
            return {"rsi": current_rsi, "signal": "极度超买", "trend": "超买", "score": -1}
        elif current_rsi >= 70:
            return {"rsi": current_rsi, "signal": "超买", "trend": "超买", "score": -0.5}
        elif current_rsi <= 20:
            return {"rsi": current_rsi, "signal": "极度超卖", "trend": "超卖", "score": 1}
        elif current_rsi <= 30:
            return {"rsi": current_rsi, "signal": "超卖", "trend": "超卖", "score": 0.5}
        else:
            return {"rsi": current_rsi, "signal": "中性", "trend": "中性", "score": 0}
    
    results = {}
    overbought_count = 0
    oversold_count = 0
    neutral_count = 0
    total_score = 0
    
    # 日线 RSI (基准)
    daily_result = calculate_single_rsi(df['price'], period)
    if daily_result:
        results["日线"] = daily_result
        if daily_result["trend"] == "超买":
            overbought_count += 1
        elif daily_result["trend"] == "超卖":
            oversold_count += 1
        else:
            neutral_count += 1
        total_score += daily_result["score"]
    
    # 4H - 使用更密集的数据点
    if len(df) >= 70:
        short_df = df.tail(len(df) // 6 * 6)
        result_4h = calculate_single_rsi(short_df['price'], period)
        if result_4h:
            results["4H"] = result_4h
            if result_4h["trend"] == "超买":
                overbought_count += 1
            elif result_4h["trend"] == "超卖":
                oversold_count += 1
            else:
                neutral_count += 1
            total_score += result_4h["score"]
    
    # 12H
    if len(df) >= 70:
        half_df = df.tail(len(df) // 2)
        result_12h = calculate_single_rsi(half_df['price'], period)
        if result_12h:
            results["12H"] = result_12h
            if result_12h["trend"] == "超买":
                overbought_count += 1
            elif result_12h["trend"] == "超卖":
                oversold_count += 1
            else:
                neutral_count += 1
            total_score += result_12h["score"]
    
    # 周线重采样
    try:
        df_indexed = df.set_index('date') if 'date' in df.columns else df
        weekly_prices = df_indexed['price'].resample('W').last().dropna()
        if len(weekly_prices) >= period + 1:
            result_weekly = calculate_single_rsi(weekly_prices, period)
            if result_weekly:
                results["周线"] = result_weekly
                if result_weekly["trend"] == "超买":
                    overbought_count += 1
                elif result_weekly["trend"] == "超卖":
                    oversold_count += 1
                else:
                    neutral_count += 1
                total_score += result_weekly["score"]
    except:
        pass
    
    # 月线重采样
    try:
        monthly_prices = df_indexed['price'].resample('ME').last().dropna()
        if len(monthly_prices) >= period + 1:
            result_monthly = calculate_single_rsi(monthly_prices, period)
            if result_monthly:
                results["月线"] = result_monthly
                if result_monthly["trend"] == "超买":
                    overbought_count += 1
                elif result_monthly["trend"] == "超卖":
                    oversold_count += 1
                else:
                    neutral_count += 1
                total_score += result_monthly["score"]
    except:
        pass
    
    # 年线重采样
    try:
        yearly_prices = df_indexed['price'].resample('YE').last().dropna()
        if len(yearly_prices) >= 5:
            result_yearly = calculate_single_rsi(yearly_prices, min(period, len(yearly_prices)-1))
            if result_yearly:
                results["年线"] = result_yearly
                if result_yearly["trend"] == "超买":
                    overbought_count += 1
                elif result_yearly["trend"] == "超卖":
                    oversold_count += 1
                else:
                    neutral_count += 1
                total_score += result_yearly["score"]
    except:
        pass
    
    # 生成汇总状态
    total_timeframes = len(results)
    
    if total_timeframes == 0:
        status = "数据不足"
        color = "⚪"
        score = 0
    else:
        avg_score = total_score / total_timeframes
        
        if overbought_count > oversold_count and overbought_count > neutral_count:
            if overbought_count >= total_timeframes * 0.8:
                status = f"多周期超买 ({overbought_count}/{total_timeframes})"
                color = "🔴"
                score = -1
            else:
                status = f"偏超买 ({overbought_count}/{total_timeframes})"
                color = "🟡"
                score = -0.5
        elif oversold_count > overbought_count and oversold_count > neutral_count:
            if oversold_count >= total_timeframes * 0.8:
                status = f"多周期超卖 ({oversold_count}/{total_timeframes})"
                color = "🟢"
                score = 1
            else:
                status = f"偏超卖 ({oversold_count}/{total_timeframes})"
                color = "🟢"
                score = 0.5
        else:
            status = f"多周期中性 ({neutral_count}/{total_timeframes})"
            color = "🟡"
            score = 0
    
    # 构建详细信息
    details = []
    for tf, result in results.items():
        rsi_val = result["rsi"]
        if result["trend"] == "超买":
            icon = "🔴"
        elif result["trend"] == "超卖":
            icon = "🟢"
        else:
            icon = "🟡"
        details.append(f"{tf}:{icon}{rsi_val:.0f}")
    
    detail_str = " | ".join(details)
    
    return IndicatorResult(
        name="RSI",
        value=total_score,
        score=score,
        color=color,
        status=f"{status}\n{detail_str}",
        priority="短期",
        url="https://www.tradingview.com/chart/?symbol=BINANCE:BTCUSDT",
        description="相对强弱指数 (RSI) 衡量价格变动的速度和幅度，以评估资产是否超买或超卖。",
        method="RSI通过计算一段时间内上涨和下跌的平均幅度来生成0到100之间的值。高于70通常视为超买，低于30视为超卖。"
    )


def calc_macd(df: pd.DataFrame) -> IndicatorResult:
    """
    MACD 多周期汇总 (4H, 12H, 日, 周, 月)
    - 4H/12H: 使用 OKX 真实K线数据
    - 日线: 使用传入的日线数据
    - 周线/月线: 日线重采样
    """
    df = df.copy()
    
    if len(df) < 35:
        return IndicatorResult(
            name="MACD",
            value=float('nan'),
            score=0,
            color="⚪",
            status="数据不足",
            priority="短期"
        )
    
    def calculate_single_macd(price_series):
        """计算单周期 MACD"""
        if len(price_series) < 35:
            return None
        
        ema12 = price_series.ewm(span=12, adjust=False).mean()
        ema26 = price_series.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line
        
        current_macd = macd_line.iloc[-1]
        current_signal = signal_line.iloc[-1]
        current_hist = histogram.iloc[-1]
        prev_hist = histogram.iloc[-2] if len(histogram) > 1 else 0
        
        # 判断金叉/死叉
        is_golden_cross = current_macd > current_signal and macd_line.iloc[-2] <= signal_line.iloc[-2]
        is_death_cross = current_macd < current_signal and macd_line.iloc[-2] >= signal_line.iloc[-2]
        
        if is_golden_cross:
            return {"signal": "金叉", "trend": "多", "strength": 2}
        elif is_death_cross:
            return {"signal": "死叉", "trend": "空", "strength": 2}
        elif current_macd > current_signal:
            if current_hist > prev_hist:
                return {"signal": "多头增强", "trend": "多", "strength": 1}
            else:
                return {"signal": "多头减弱", "trend": "多", "strength": 0.5}
        else:
            if current_hist < prev_hist:
                return {"signal": "空头增强", "trend": "空", "strength": 1}
            else:
                return {"signal": "空头减弱", "trend": "空", "strength": 0.5}
    
    def fetch_okx_kline(bar, limit=100):
        """从 OKX 获取真实K线数据"""
        try:
            response = requests.get(
                "https://www.okx.com/api/v5/market/candles",
                params={"instId": "BTC-USDT", "bar": bar, "limit": limit},
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == "0" and data.get("data"):
                    closes = [float(item[4]) for item in reversed(data["data"])]
                    return pd.Series(closes)
        except Exception as e:
            print(f"⚠️ OKX {bar} K线获取失败: {e}")
        return None
    
    results = {}
    bullish_count = 0
    bearish_count = 0
    total_strength = 0
    
    def add_result(tf_name, result):
        nonlocal bullish_count, bearish_count, total_strength
        if result:
            results[tf_name] = result
            if result["trend"] == "多":
                bullish_count += 1
                total_strength += result["strength"]
            else:
                bearish_count += 1
                total_strength -= result["strength"]
    
    # 4H MACD - OKX 真实K线
    kline_4h = fetch_okx_kline("4H", 100)
    if kline_4h is not None:
        add_result("4H", calculate_single_macd(kline_4h))
    
    # 12H MACD - OKX 真实K线
    kline_12h = fetch_okx_kline("12Hutc", 100)
    if kline_12h is not None:
        add_result("12H", calculate_single_macd(kline_12h))
    
    # 日线 MACD (基准)
    add_result("日线", calculate_single_macd(df['price']))
    
    # 周线重采样
    try:
        df_indexed = df.set_index('date') if 'date' in df.columns else df
        weekly_prices = df_indexed['price'].resample('W').last().dropna()
        if len(weekly_prices) >= 35:
            add_result("周线", calculate_single_macd(weekly_prices))
    except:
        pass
    
    # 月线重采样
    try:
        monthly_prices = df_indexed['price'].resample('ME').last().dropna()
        if len(monthly_prices) >= 35:
            add_result("月线", calculate_single_macd(monthly_prices))
    except:
        pass
    
    # 生成汇总状态
    total_timeframes = len(results)
    
    if total_timeframes == 0:
        status = "数据不足"
        color = "⚪"
        score = 0
    elif bullish_count > bearish_count:
        ratio = bullish_count / total_timeframes
        if ratio >= 0.8:
            status = f"强势多头 ({bullish_count}/{total_timeframes})"
            color = "🟢"
            score = 1
        elif ratio >= 0.5:
            status = f"偏多 ({bullish_count}/{total_timeframes})"
            color = "🟢"
            score = 0.5
        else:
            status = f"多空分歧 ({bullish_count}多/{bearish_count}空)"
            color = "🟡"
            score = 0.2
    elif bearish_count > bullish_count:
        ratio = bearish_count / total_timeframes
        if ratio >= 0.8:
            status = f"强势空头 ({bearish_count}/{total_timeframes})"
            color = "🔴"
            score = -1
        elif ratio >= 0.5:
            status = f"偏空 ({bearish_count}/{total_timeframes})"
            color = "🔴"
            score = -0.5
        else:
            status = f"多空分歧 ({bullish_count}多/{bearish_count}空)"
            color = "🟡"
            score = -0.2
    else:
        status = f"多空平衡 ({bullish_count}多/{bearish_count}空)"
        color = "🟡"
        score = 0
    
    # 构建详细信息
    details = []
    for tf, result in results.items():
        trend_icon = "🟢" if result["trend"] == "多" else "🔴"
        details.append(f"{tf}:{trend_icon}{result['signal']}")
    
    detail_str = " | ".join(details)
    
    return IndicatorResult(
        name="MACD",
        value=total_strength,
        score=score,
        color=color,
        status=f"{status}\n{detail_str}",
        priority="短期",
        url="https://www.tradingview.com/chart/?symbol=BINANCE:BTCUSDT",
        description="平滑异同移动平均线 (MACD) 是一种趋势跟踪动量指标，显示两条移动平均线之间的关系。",
        method="MACD线是12期EMA减去26期EMA，信号线是MACD线的9期EMA。MACD线穿过信号线形成金叉（买入）或死叉（卖出）信号。"
    )



def calc_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> IndicatorResult:
    """
    布林带 (Bollinger Bands)
    - 波动率指标
    - 价格触上轨: 超买, 触下轨: 超卖
    - 带宽收窄: 可能突破
    """
    df = df.copy()
    
    if len(df) < period:
        return IndicatorResult(
            name="布林带",
            value=float('nan'),
            score=0,
            color="⚪",
            status="数据不足",
            priority="短期"
        )
    
    # 计算中轨 (SMA)
    middle_band = df['price'].rolling(window=period).mean()
    # 计算标准差
    std = df['price'].rolling(window=period).std()
    # 上轨和下轨
    upper_band = middle_band + (std * std_dev)
    lower_band = middle_band - (std * std_dev)
    
    current_price = df['price'].iloc[-1]
    current_upper = upper_band.iloc[-1]
    current_lower = lower_band.iloc[-1]
    current_middle = middle_band.iloc[-1]
    
    # 计算价格在带中的位置 (0-100)
    band_width = current_upper - current_lower
    position = (current_price - current_lower) / band_width * 100 if band_width > 0 else 50
    
    # 评分逻辑
    if current_price >= current_upper:
        score, color, status = -0.5, "🟡", f"触及上轨 - 超买"
    elif current_price <= current_lower:
        score, color, status = 0.5, "🟢", f"触及下轨 - 超卖"
    elif position > 80:
        score, color, status = -0.3, "🟡", f"接近上轨 ({position:.0f}%)"
    elif position < 20:
        score, color, status = 0.3, "🟢", f"接近下轨 ({position:.0f}%)"
    else:
        score, color, status = 0, "🟡", f"通道中部 ({position:.0f}%)"
    
    return IndicatorResult(
        name="布林带",
        value=position,
        score=score,
        color=color,
        status=status,
        priority="短期",
        url="https://www.tradingview.com/chart/?symbol=BINANCE:BTCUSDT",
        description="布林带是一种波动性指标，由中轨（移动平均线）和上下两条标准差带组成。",
        method="价格触及上轨可能表示超买，触及下轨可能表示超卖。带宽收窄预示着价格可能即将出现剧烈波动。"
    )


# ============================================================
# 新增指标 - 免费 API
# ============================================================

def calc_fear_greed_index() -> IndicatorResult:
    """
    贪婪恐惧指数
    - 数据源: alternative.me (免费 API)
    - 0-25: 极度恐惧, 25-45: 恐惧, 45-55: 中性, 55-75: 贪婪, 75-100: 极度贪婪
    """
    try:
        response = requests.get("https://api.alternative.me/fng/", timeout=10)
        if response.status_code == 200:
            data = response.json()["data"][0]
            value = int(data["value"])
            classification = data["value_classification"]
            
            # 评分逻辑：恐惧时买入机会（绿），贪婪时风险（红）
            if value <= 25:
                score, color = 1, "🟢"
                status = f"极度恐惧 ({value}) - 买入机会"
            elif value <= 45:
                score, color = 0.5, "🟢"
                status = f"恐惧 ({value}) - 偏买入"
            elif value <= 55:
                score, color = 0, "🟡"
                status = f"中性 ({value})"
            elif value <= 75:
                score, color = -0.5, "🟡"
                status = f"贪婪 ({value}) - 谨慎"
            else:
                score, color = -1, "🔴"
                status = f"极度贪婪 ({value}) - 风险高"
            
            return IndicatorResult(
                name="恐惧贪婪指数",
                value=float(value),
                score=score,
                color=color,
                status=status,
                priority="P1",
                url="https://alternative.me/crypto/fear-and-greed-index/",
                description="恐惧贪婪指数衡量市场情绪，0代表极度恐惧，100代表极度贪婪。",
                method="该指数综合了波动性、市场成交量、社交媒体情绪、市场主导地位和谷歌趋势等多个因素。极度恐惧通常是买入机会，极度贪婪则需谨慎。"
            )
    except Exception as e:
        print(f"⚠️ Fear & Greed API 失败: {e}")
    
    return IndicatorResult(
        name="恐惧贪婪指数",
        value=float('nan'),
        score=0,
        color="⚪",
        status="API 暂不可用",
        priority="P1"
    )


def calc_funding_rate() -> IndicatorResult:
    """
    资金费率
    - 数据源: Binance (免费 API)
    - 正费率: 多头付空头, 市场偏多
    - 负费率: 空头付多头, 市场偏空
    """
    rate = None
    source = None

    # 1. Try Binance
    try:
        response = requests.get(
            "https://fapi.binance.com/fapi/v1/fundingRate",
            params={"symbol": "BTCUSDT", "limit": 1},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()[0]
            rate = float(data["fundingRate"]) * 100  # 转为百分比
            source = "Binance"
    except Exception as e:
        print(f"⚠️ Binance Funding Rate failed: {e}")

    # 2. Fallback: CoinGecko Derivatives (if Binance failed)
    if rate is None:
        try:
            # print("⚠️ Binance blocked/failed, trying CoinGecko...")
            cg_response = requests.get("https://api.coingecko.com/api/v3/derivatives", timeout=20)
            if cg_response.status_code == 200:
                cg_data = cg_response.json()
                for item in cg_data:
                    # Look for Binance Futures BTC/USDT
                    if item.get('market') == 'Binance (Futures)' and item.get('symbol') == 'BTCUSDT':
                        rate = float(item.get('funding_rate', 0)) * 100
                        source = "CoinGecko"
                        break
        except Exception as e:
            print(f"⚠️ CoinGecko Fallback failed: {e}")

    # 3. Fallback: Bybit (if Binance/CG failed)
    if rate is None:
        try:
            bybit_resp = requests.get(
                "https://api.bybit.com/v5/market/tickers",
                params={"category": "linear", "symbol": "BTCUSDT"},
                timeout=10
            )
            if bybit_resp.status_code == 200:
                b_data = bybit_resp.json()
                if b_data.get("retCode") == 0:
                    rate = float(b_data["result"]["list"][0]["fundingRate"]) * 100
                    source = "Bybit"
        except Exception as e:
            print(f"⚠️ Bybit Fallback failed: {e}")

    # 4. If all failed, return Error but with valid value to show card
    if rate is None:
        return IndicatorResult(
            name="资金费率",
            value=0.0, # Return 0.0 instead of NaN
            score=0,
            color="⚪",
            status="数据源连接失败 (SSL)",
            priority="P1",
            description="资金费率...",
            method="因网络或SSL问题无法连接 Binance/Bybit API。请检查网络连接。"
        )

    # Common scoring logic (reused)
    if rate > 0.1:
        score, color = -1, "🔴"
        status = f"过热 ({rate:.4f}%) - 多头拥挤"
    elif rate > 0.03:
        score, color = -0.5, "🟡"
        status = f"偏多 ({rate:.4f}%)"
    elif rate > -0.03:
        score, color = 0, "🟡"
        status = f"中性 ({rate:.4f}%)"
    elif rate > -0.1:
        score, color = 0.5, "🟢"
        status = f"偏空 ({rate:.4f}%)"
    else:
        score, color = 1, "🟢"
        status = f"恐慌 ({rate:.4f}%) - 空头拥挤"
    
    return IndicatorResult(
        name="资金费率",
        value=rate,
        score=score,
        color=color,
        status=status,
        priority="P1",
        url="https://www.binance.com/zh-CN/futures/funding-rate",
        description="资金费率是永续合约市场特有的机制，用于平衡多头和空头持仓。",
        method="正费率表示多头支付空头，市场偏多；负费率表示空头支付多头，市场偏空。极端费率可能预示市场反转。"
    )


def calc_long_short_ratio() -> IndicatorResult:
    """
    全球多空比
    - 主数据源: OKX (中国大陆可访问)
    - 备用数据源: Binance (可能被地域限制)
    """
    ratio = None
    source = ""
    
    # 方法1: OKX API (无地域限制)
    try:
        response = requests.get(
            "https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio",
            params={"ccy": "BTC", "period": "1H"},
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == "0" and data.get("data"):
                ratio = float(data["data"][0][1])
                source = "OKX"
    except Exception as e:
        print(f"⚠️ OKX Long/Short API failed: {e}")
    
    # 方法2: Binance (备用)
    if ratio is None:
        try:
            response = requests.get(
                "https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
                params={"symbol": "BTCUSDT", "period": "1h", "limit": 1},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()[0]
                ratio = float(data["longShortRatio"])
                source = "Binance"
        except Exception as e:
            print(f"⚠️ Binance Long/Short API failed: {e}")
    
    if ratio is not None:
        # 计算多头/空头百分比
        long_pct = ratio / (1 + ratio) * 100
        short_pct = 100 - long_pct
        
        # 评分逻辑
        if ratio > 2.0:
            score, color = -1, "🔴"
            status = f"极度偏多 ({ratio:.2f}) 多{long_pct:.0f}%/空{short_pct:.0f}%"
        elif ratio > 1.2:
            score, color = -0.5, "🟡"
            status = f"偏多 ({ratio:.2f})"
        elif ratio > 0.8:
            score, color = 0, "🟡"
            status = f"均衡 ({ratio:.2f})"
        elif ratio > 0.5:
            score, color = 0.5, "🟢"
            status = f"偏空 ({ratio:.2f})"
        else:
            score, color = 1, "🟢"
            status = f"极度偏空 ({ratio:.2f})"
        
        return IndicatorResult(
            name="多空比",
            value=ratio,
            score=score,
            color=color,
            status=f"{status} [{source}]",
            priority="P1",
            url="https://www.coinglass.com/zh/LongShortRatio",
            description="多空比反映了市场上多头和空头持仓的相对比例，是衡量市场情绪的指标。",
            method="通过交易所API获取多头账户与空头账户的比例。极端的多空比可能预示着市场情绪的过度集中，存在反转风险。"
        )
    
    return IndicatorResult(
        name="多空比",
        value=float('nan'),
        score=0,
        color="⚪",
        status="API 暂不可用",
        priority="P1"
    )


def calc_btc_dominance() -> IndicatorResult:
    """
    BTC 市占率 (Dominance)
    - 数据源: CoinGecko Global API
    - 趋势: 牛市初期 BTC.D 上涨 (吸血)，牛市后期 BTC.D 下降 (山寨季)
    """
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/global",
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            btc_d = data["data"]["market_cap_percentage"]["btc"]
            
            # 简单评分逻辑: >50% 强势
            if btc_d > 55:
                score, color = 1, "🟢"
                status = f"{btc_d:.1f}% (强势吸血)"
            elif btc_d > 45:
                score, color = 0, "🟡"
                status = f"{btc_d:.1f}% (震荡)"
            else:
                score, color = -0.5, "🔴"
                status = f"{btc_d:.1f}% (弱势/山寨季)"
            
            return IndicatorResult(
                name="BTC市占率",
                value=btc_d,
                score=score,
                color=color,
                status=status,
                priority="P2",
                url="https://www.coingecko.com/zh/global_charts",
                description="比特币市值占加密货币总市值的比例，反映了比特币在市场中的主导地位。",
                method="牛市初期，BTC市占率通常上涨（吸血效应）；牛市后期，随着资金流向山寨币，BTC市占率可能下降（山寨季）。"
            )
    except Exception as e:
        print(f"⚠️ CoinGecko Global API 失败: {e}")
    
    return IndicatorResult(
        name="BTC市占率",
        value=float('nan'),
        score=0,
        color="⚪",
        status="API 暂不可用",
        priority="P2"
    )

def fetch_etf_volume() -> Tuple[float, float, str]:
    """
    获取 ETF 交易量数据
    多层 fallback:
    1. Yahoo Finance JSON API (query2.finance.yahoo.com)
    2. Yahoo Finance HTML 抓取
    3. 返回占位符引导点击
    """
    import re
    
    etfs = ["IBIT", "FBTC", "GBTC"]  # 主要 BTC ETFs
    total_volume = 0
    success_count = 0
    
    for symbol in etfs:
        # 方法1: Yahoo Finance JSON API (更稳定)
        try:
            url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/json"
            }
            resp = requests.get(url, headers=headers, timeout=8)
            
            if resp.status_code == 200:
                data = resp.json()
                result = data.get("chart", {}).get("result", [])
                if result:
                    meta = result[0].get("meta", {})
                    price = meta.get("regularMarketPrice", 0)
                    volume = meta.get("regularMarketVolume", 0)
                    
                    if price > 0 and volume > 0:
                        vol_usd = price * volume
                        total_volume += vol_usd
                        success_count += 1
                        continue
                        
        except Exception as e:
            print(f"⚠️ Yahoo JSON API ({symbol}): {e}")
        
        # 方法2: HTML 抓取 fallback
        try:
            url = f"https://finance.yahoo.com/quote/{symbol}"
            headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
            resp = requests.get(url, headers=headers, timeout=5)
            
            if resp.status_code == 200:
                # 提取 JSON 数据块
                vol_match = re.search(r'"regularMarketVolume":\{"raw":(\d+)', resp.text)
                price_match = re.search(r'"regularMarketPrice":\{"raw":([\d\.]+)', resp.text)
                
                if vol_match and price_match:
                    volume = float(vol_match.group(1))
                    price = float(price_match.group(1))
                    total_volume += volume * price
                    success_count += 1
                    
        except Exception as e:
            print(f"⚠️ Yahoo HTML ({symbol}): {e}")
    
    # 结果处理
    if success_count > 0:
        vol_b = total_volume / 1e9
        status = f"日成交 ${vol_b:.1f}B ({success_count}只ETF)"
        return vol_b, 0.0, status
    
    # 全部失败，返回占位符
    return 0.0, 0.0, "点击查看详情 ↗"


def fetch_company_holdings_data() -> Tuple[float, str]:
    """
    获取上市公司持仓数据
    来源: CoinGecko Public Treasury API
    返回: (total_holdings, status_text)
    """
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/companies/public_treasury/bitcoin",
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            total_holdings = data.get('total_holdings', 0)
            
            # 获取前几名公司
            companies = data.get('companies', [])
            top_text = ""
            if companies:
                mstr = next((c for c in companies if 'Strategy' in c['name'] or 'Micro' in c['name']), None)
                if mstr:
                    top_text = f"MSTR: {mstr['total_holdings']:,.0f} BTC"
            
            status = f"总持仓 {total_holdings:,.0f} BTC"
            if top_text:
                status += f" | {top_text}"
                
            return total_holdings, status
            
    except Exception as e:
        print(f"⚠️ Company Holdings API 失败: {e}")
        
    return 0.0, "API 暂不可用"


# ============================================================
# 新增指标 - 占位符 (需付费/注册)
# ============================================================

def calc_etf_flow() -> IndicatorResult:
    """
    ETF 综合数据
    - 数据源: YFinance (成交量) + CoinGlass 链接 (净流入/资产规模)
    - 展示: 日成交量, 并引导查看 CoinGlass 获取完整数据
    """
    vol_b, change, vol_status = fetch_etf_volume()
    
    # 构建综合状态文本
    # 由于 API 限制，净流入/AUM 需点击查看
    if vol_b > 0:
        status_parts = [f"日成交 ${vol_b:.1f}B"]
        if change != 0:
            status_parts.append(f"({change:+.1f}%)")
    else:
        status_parts = ["日成交 -"]
    
    # 添加提示查看完整数据
    status_parts.append("| 净流入/AUM 详情 ↗")
    status_text = " ".join(status_parts)
    
    # 评分: 成交量巨大视为活跃/利好
    if vol_b > 2.0:
        score, color = 1, "🟢"
    elif vol_b > 1.0:
        score, color = 0.5, "🟢"
    elif vol_b > 0:
        score, color = 0, "🟡"
    else:
        score, color = 0, "⚪"
        
    return IndicatorResult(
        name="ETF活跃度",
        value=vol_b,
        score=score,
        color=color,
        status=status_text,
        priority="P1",
        url="https://www.coinglass.com/bitcoin-etf",
        description="比特币现货ETF的交易量和资金流向，反映了机构投资者对市场的参与度和情绪。",
        method="通过聚合主要比特币现货ETF（如IBIT, FBTC, GBTC）的日交易量来衡量活跃度。高交易量和净流入通常被视为市场利好。"
    )



def calc_company_holdings() -> IndicatorResult:
    """
    上市公司持仓
    - 数据源: CoinGecko
    """
    holdings, status_text = fetch_company_holdings_data()
    
    # 评分: 持续增长为利好
    # 这里简单判断是否有数据
    if holdings > 300000:
        score, color = 1, "🟢"
    else:
        score, color = 0.5, "🟢"
        
    return IndicatorResult(
        name="公司持仓",
        value=holdings,
        score=score,
        color=color,
        status=status_text,
        priority="P2",
        url="https://bitcointreasuries.net"
    )


def calc_exchange_reserve() -> IndicatorResult:
    """
    交易所BTC余额 — 通过 mempool.space 免费API查询已知交易所冷钱包地址
    - 余额减少 → BTC流出交易所 → 用户在吸筹/自托管 (Bullish)
    - 余额增加 → BTC流入交易所 → 潜在卖压 (Bearish)
    - 数据源: mempool.space (完全免费, 无需API Key)
    """
    import time as _time
    
    EXCHANGE_WALLETS = {
        "Binance": [
            "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo",           # Binance cold wallet 1 (~248K BTC)
            "bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h",    # Binance cold wallet 2 (~21K BTC)
            "3M219KR5vEneNb47ewrPfWyb5jQ2DjxRP6",           # Binance cold wallet 3 (~171K BTC)
            "1NDyJtNTjmwk5xPNhjgAMu4HDHigtobu1s",           # Binance 7
            "39884E3j6KZj82FK4vcCrkUvWYL5MQaS3v",           # Binance 8
        ],
        "Bitfinex": [
            "bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97",  # ~130K BTC
        ],
        "Kraken": [
            "bc1qr4dl5wa7kl8yu792dceg9z5knl2gkn220lk7a9",    # ~18K BTC
            "3AfSMeESFHT2xLqkR1ufoKcxNqNP5bfcaX",           # Kraken cold 2
        ],
        "Crypto.com": [
            "bc1qpy4jwethqenp4r7hqls660wy8287vw0my32lmy",    # 官方公布
            "bc1q4c8n5t00jmj8temxdgcc3t32nkg2wjwz24lywv",    # 官方公布 (~3.9K BTC)
        ],
        "Gemini": [
            "3JZq4atUahhuA9rLhXLMhhTo133J9rF97j",           # Gemini cold
        ],
    }
    
    total_btc = 0
    exchange_details = {}
    success_count = 0
    error_count = 0
    
    try:
        for exchange, addrs in EXCHANGE_WALLETS.items():
            exchange_total = 0
            for addr in addrs:
                try:
                    resp = requests.get(
                        f"https://mempool.space/api/address/{addr}",
                        timeout=8,
                        headers={"User-Agent": "Mozilla/5.0"}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        chain = data.get("chain_stats", {})
                        funded = chain.get("funded_txo_sum", 0)
                        spent = chain.get("spent_txo_sum", 0)
                        balance = (funded - spent) / 1e8
                        exchange_total += balance
                        success_count += 1
                    elif resp.status_code == 429:
                        # Rate limited, skip remaining
                        print(f"⚠️ mempool.space rate limit, 已获取 {success_count} 个地址")
                        break
                    else:
                        error_count += 1
                except Exception:
                    error_count += 1
                _time.sleep(0.4)  # Rate limit: 250 req/min
            
            if exchange_total > 0:
                exchange_details[exchange] = exchange_total
                total_btc += exchange_total
        
        if success_count < 3:
            return IndicatorResult(
                name="交易所余额",
                value=float('nan'),
                score=0,
                color="⚪",
                status="API 连接失败 (mempool.space)",
                priority="P2",
                url="https://mempool.space",
                description="通过 mempool.space 查询已知交易所冷钱包地址余额。",
                method="因网络问题无法连接 mempool.space API。"
            )
        
        # 格式化各交易所明细
        details_str = " | ".join([
            f"{name} {btc/1000:.0f}K"
            for name, btc in sorted(exchange_details.items(), key=lambda x: -x[1])
        ])
        
        # 历史对比：保存/读取上次余额快照用于趋势判断
        import json, os
        snapshot_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "btc_web", "exchange_balance_history.json")
        
        prev_total = None
        try:
            if os.path.exists(snapshot_file):
                with open(snapshot_file, "r") as f:
                    history = json.load(f)
                if history:
                    prev_total = history[-1].get("total", None)
        except:
            pass
        
        # 保存当前快照
        try:
            history = []
            if os.path.exists(snapshot_file):
                with open(snapshot_file, "r") as f:
                    history = json.load(f)
            
            history.append({
                "timestamp": datetime.now().isoformat(),
                "total": total_btc,
                "details": exchange_details
            })
            # 只保留最近30条记录
            history = history[-30:]
            
            with open(snapshot_file, "w") as f:
                json.dump(history, f, indent=2)
        except:
            pass
        
        # 评分逻辑
        total_k = total_btc / 1000
        
        if prev_total:
            change = total_btc - prev_total
            change_pct = (change / prev_total) * 100
            
            if change_pct < -2:
                score, color = 1, "🟢"
                trend = f"流出 {abs(change):,.0f} BTC ↓"
            elif change_pct < -0.5:
                score, color = 0.5, "🟢"
                trend = f"小幅流出 {abs(change):,.0f} BTC ↓"
            elif change_pct > 2:
                score, color = -1, "🔴"
                trend = f"流入 {change:,.0f} BTC ↑"
            elif change_pct > 0.5:
                score, color = -0.5, "🟠"
                trend = f"小幅流入 {change:,.0f} BTC ↑"
            else:
                score, color = 0, "🟡"
                trend = "余额稳定 →"
            
            status = f"{total_k:.0f}K BTC | {trend}"
        else:
            # 首次运行，无历史对比
            score, color = 0, "🟡"
            status = f"{total_k:.0f}K BTC | 首次采集"
        
        return IndicatorResult(
            name="交易所余额",
            value=round(total_btc, 2),
            score=score,
            color=color,
            status=f"{status} | {details_str}",
            priority="P2",
            url="https://mempool.space",
            description=(
                f"监控主要交易所冷钱包BTC余额（{len(EXCHANGE_WALLETS)}家交易所，{sum(len(v) for v in EXCHANGE_WALLETS.values())}个地址）。"
                f"余额减少表示用户提币自托管（看多），余额增加表示潜在卖压（看空）。"
            ),
            method=(
                f"通过 mempool.space 免费API查询已知交易所冷钱包链上余额。"
                f"当前监控: {', '.join(EXCHANGE_WALLETS.keys())}。"
                f"对比上次采集数据计算净流入/流出趋势。"
            )
        )
        
    except Exception as e:
        print(f"⚠️ Exchange Reserve Failed: {e}")
        return IndicatorResult(
            name="交易所余额",
            value=float('nan'),
            score=0,
            color="⚪",
            status="数据获取失败",
            priority="P2",
            url="https://mempool.space",
            description="通过 mempool.space 查询已知交易所冷钱包地址余额。",
            method="因异常无法获取数据。"
        )


# ============================================================
# 资讯信息模块
# ============================================================

def fetch_crypto_news(limit: int = 20) -> list:
    """
    获取 BTC 相关新闻 - 从多个 RSS 源聚合
    - 数据源: CoinDesk, CoinTelegraph, Bitcoin Magazine, NewsBTC, 律动
    - 英文源自动翻译成中文
    - 按时间排序，最新在前
    """
    import xml.etree.ElementTree as ET
    from datetime import datetime
    import re
    
    # 翻译功能
    translator = None
    translation_cache = {}
    
    def translate_to_chinese(text: str) -> str:
        """将英文翻译成中文"""
        nonlocal translator
        if not text or len(text.strip()) == 0:
            return text
        
        # 检查缓存
        if text in translation_cache:
            return translation_cache[text]
        
        try:
            # 延迟导入翻译器
            if translator is None:
                from deep_translator import GoogleTranslator
                translator = GoogleTranslator(source='en', target='zh-CN')
            
            translated = translator.translate(text)
            translation_cache[text] = translated
            return translated
        except Exception as e:
            print(f"⚠️ 翻译失败: {e}")
            return text  # 翻译失败返回原文
    
    news_list = []
    
    # RSS 源列表 (is_chinese 标记中文源，无需翻译)
    rss_feeds = [
        {
            "name": "CoinDesk",
            "url": "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml",
            "icon": "📰",
            "is_chinese": False
        },
        {
            "name": "CoinTelegraph",
            "url": "https://cointelegraph.com/rss",
            "icon": "📊",
            "is_chinese": False
        },
        {
            "name": "Bitcoin Magazine",
            "url": "https://bitcoinmagazine.com/feed",
            "icon": "₿",
            "is_chinese": False
        },
        {
            "name": "NewsBTC",
            "url": "https://www.newsbtc.com/feed/",
            "icon": "📈",
            "is_chinese": False
        },
        {
            "name": "律动 BlockBeats",
            "url": "https://api.theblockbeats.news/v2/rss/newsflash",
            "icon": "🎵",
            "is_chinese": True
        }
    ]
    
    def parse_rss_date(date_str: str) -> datetime:
        """解析 RSS 日期格式"""
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S GMT",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except:
                continue
        return datetime.now()
    
    def clean_html(text: str) -> str:
        """移除 HTML 标签"""
        clean = re.sub(r'<[^>]+>', '', text or '')
        return clean[:150] + '...' if len(clean) > 150 else clean
    
    # 从每个 RSS 源获取新闻
    for feed in rss_feeds:
        try:
            response = requests.get(feed["url"], timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            })
            if response.status_code != 200:
                continue
                
            root = ET.fromstring(response.content)
            
            # 查找所有 item 元素
            items = root.findall('.//item')[:5]  # 每个源取前5条
            
            for item in items:
                title = item.find('title')
                link = item.find('link')
                pub_date = item.find('pubDate')
                description = item.find('description')
                
                if title is not None and link is not None:
                    title_text = title.text or ""
                    summary_text = clean_html(description.text if description is not None else "")
                    
                    # 英文源翻译成中文
                    if not feed.get("is_chinese", False):
                        title_text = translate_to_chinese(title_text)
                        summary_text = translate_to_chinese(summary_text)
                    
                    news_item = {
                        "title": title_text,
                        "url": link.text or "",
                        "source": feed["name"],
                        "icon": feed["icon"],
                        "summary": summary_text,
                        "pub_date": parse_rss_date(pub_date.text if pub_date is not None else ""),
                        "time": ""
                    }
                    # 格式化时间显示
                    news_item["time"] = news_item["pub_date"].strftime("%m-%d %H:%M")
                    news_list.append(news_item)
                    
        except Exception as e:
            print(f"⚠️ RSS {feed['name']} 失败: {e}")
            continue
    
    # 按发布时间排序（最新在前）
    news_list.sort(key=lambda x: x.get("pub_date", datetime.min), reverse=True)
    
    # 移除 pub_date 对象（不可 JSON 序列化）
    for item in news_list:
        if "pub_date" in item:
            del item["pub_date"]
    
    return news_list[:limit]


def fetch_exchange_balance_display() -> dict:
    """
    获取交易所BTC余额展示数据（给前端展示用）
    - 返回各交易所余额明细
    - 通过 blockchain.info 交易历史计算 24h/7d/30d 变化
    """
    import time as _time, json, os
    
    EXCHANGE_WALLETS = {
        "Binance": [
            "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo",
            "bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h",
            "3M219KR5vEneNb47ewrPfWyb5jQ2DjxRP6",
            "1NDyJtNTjmwk5xPNhjgAMu4HDHigtobu1s",
            "39884E3j6KZj82FK4vcCrkUvWYL5MQaS3v",
        ],
        "Bitfinex": [
            "bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97",
        ],
        "Kraken": [
            "bc1qr4dl5wa7kl8yu792dceg9z5knl2gkn220lk7a9",
            "3AfSMeESFHT2xLqkR1ufoKcxNqNP5bfcaX",
        ],
        "Crypto.com": [
            "bc1qpy4jwethqenp4r7hqls660wy8287vw0my32lmy",
            "bc1q4c8n5t00jmj8temxdgcc3t32nkg2wjwz24lywv",
        ],
        "Gemini": [
            "3JZq4atUahhuA9rLhXLMhhTo133J9rF97j",
        ],
    }
    
    result = {
        "exchanges": [],
        "total": 0,
        "changes": {"24h": None, "7d": None, "30d": None},
        "history": [],
        "fetched": 0,
        "error": None,
    }
    
    total_btc = 0
    exchange_list = []
    # 用于历史计算: addr -> {current, txs}
    addr_data_map = {}
    
    try:
        # 第1步: 获取所有地址当前余额 (mempool.space)
        for exchange, addrs in EXCHANGE_WALLETS.items():
            exchange_total = 0
            for addr in addrs:
                try:
                    resp = requests.get(
                        f"https://mempool.space/api/address/{addr}",
                        timeout=8,
                        headers={"User-Agent": "Mozilla/5.0"}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        chain = data.get("chain_stats", {})
                        balance = (chain.get("funded_txo_sum", 0) - chain.get("spent_txo_sum", 0)) / 1e8
                        exchange_total += balance
                        addr_data_map[addr] = {"current": balance}
                        result["fetched"] += 1
                    elif resp.status_code == 429:
                        break
                except:
                    pass
                _time.sleep(0.3)
            
            if exchange_total > 0:
                exchange_list.append({
                    "name": exchange,
                    "balance": round(exchange_total, 2),
                })
                total_btc += exchange_total
        
        exchange_list.sort(key=lambda x: -x["balance"])
        result["exchanges"] = exchange_list
        result["total"] = round(total_btc, 2)
        
        # 第2步: 通过 blockchain.info 获取交易历史, 反推历史余额
        now = _time.time()
        target_ages = {
            "24h": 24 * 3600,
            "7d": 7 * 24 * 3600,
            "30d": 30 * 24 * 3600,
        }
        
        # 每个地址的历史余额 {period: {addr: bal}}
        hist_balances = {p: {} for p in target_ages}
        
        for addr, info in addr_data_map.items():
            try:
                resp = requests.get(
                    f"https://blockchain.info/rawaddr/{addr}?limit=50&offset=0",
                    timeout=15,
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                if resp.status_code == 200:
                    raw = resp.json()
                    txs = raw.get("txs", [])
                    
                    # 按时间倒序排列 (最新的先)
                    txs.sort(key=lambda t: t.get("time", 0), reverse=True)
                    
                    bal = info["current"]
                    # 标记每个时间窗口是否已经找到对应的历史余额
                    found = {p: False for p in target_ages}
                    
                    for tx in txs:
                        tx_time = tx.get("time", 0)
                        if tx_time == 0:
                            continue
                        tx_age = now - tx_time
                        
                        # 检查是否跨过任何目标时间点
                        for period, age_sec in target_ages.items():
                            if not found[period] and tx_age >= age_sec:
                                hist_balances[period][addr] = bal
                                found[period] = True
                        
                        # 反推: 计算此交易对此地址的净变化
                        net_satoshi = 0
                        for out in tx.get("out", []):
                            if out.get("addr") == addr:
                                net_satoshi += out.get("value", 0)
                        for inp in tx.get("inputs", []):
                            prev = inp.get("prev_out", {})
                            if prev.get("addr") == addr:
                                net_satoshi -= prev.get("value", 0)
                        
                        bal -= net_satoshi / 1e8
                    
                    # 如果所有交易都在目标窗口之内，用最旧的余额作为近似
                    for period in target_ages:
                        if not found[period] and txs:
                            hist_balances[period][addr] = bal
                            
                elif resp.status_code == 429:
                    print(f"⚠️ blockchain.info rate limit for {addr[:12]}...")
            except Exception as e:
                print(f"⚠️ History fetch error for {addr[:12]}: {e}")
            _time.sleep(0.5)
        
        # 第3步: 汇总历史余额，计算变化百分比
        for period, age_sec in target_ages.items():
            hist_total = 0
            has_data = False
            for addr, info in addr_data_map.items():
                if addr in hist_balances[period]:
                    hist_total += hist_balances[period][addr]
                    has_data = True
                else:
                    # 没有交易记录的地址，假设余额未变
                    hist_total += info["current"]
            
            if has_data and hist_total > 0:
                change = total_btc - hist_total
                pct = (change / hist_total) * 100
                result["changes"][period] = {
                    "change_btc": round(change, 2),
                    "change_pct": round(pct, 4),
                    "prev_total": round(hist_total, 2),
                }
        
        # 第4步: 仍旧保存快照用于备份
        snapshot_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "btc_web", "exchange_balance_history.json")
        if total_btc > 0:
            try:
                history = []
                if os.path.exists(snapshot_file):
                    with open(snapshot_file, "r") as f:
                        history = json.load(f)
                history.append({
                    "timestamp": datetime.now().isoformat(),
                    "total": round(total_btc, 2),
                    "details": {e["name"]: e["balance"] for e in exchange_list}
                })
                history = history[-60:]
                with open(snapshot_file, "w") as f:
                    json.dump(history, f, indent=2)
            except:
                pass
        
    except Exception as e:
        result["error"] = str(e)
    
    return result


def fetch_whale_volume_stats() -> dict:
    """
    获取 BTC 买卖量统计 (24h / 7d / 30d)
    - 数据源: Binance Kline API (taker buy/sell volume)
    - 返回: 各时间段内的买入量、卖出量、买入占比
    """
    result = {
        "24h": {"buy": 0, "sell": 0, "total": 0, "buy_ratio": 50},
        "7d": {"buy": 0, "sell": 0, "total": 0, "buy_ratio": 50},
        "30d": {"buy": 0, "sell": 0, "total": 0, "buy_ratio": 50},
    }
    
    try:
        response = requests.get(
            "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=30",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        
        if response.status_code == 200:
            klines = response.json()
            
            for period_name, days in [("24h", 1), ("7d", 7), ("30d", 30)]:
                subset = klines[-days:]
                total_vol = sum(float(k[5]) for k in subset)
                buy_vol = sum(float(k[9]) for k in subset)
                sell_vol = total_vol - buy_vol
                buy_ratio = (buy_vol / total_vol * 100) if total_vol > 0 else 50
                
                result[period_name] = {
                    "buy": round(buy_vol, 1),
                    "sell": round(sell_vol, 1),
                    "total": round(total_vol, 1),
                    "buy_ratio": round(buy_ratio, 1),
                }
    except Exception as e:
        print(f"⚠️ Binance Volume Stats Failed: {e}")
    
    return result


def fetch_whale_activity(min_btc: int = 10, limit: int = 50) -> list:
    """
    获取 BTC 鲸鱼/大额交易监控
    - 主要数据源: Blockchain.com 最新区块中的已确认大额交易
    - 补充数据源: Blockchain.com 未确认交易（内存池）
    - 备用数据源: mempool.space 最新交易
    - 最终后备: 模拟示例数据
    - 按时间排序，最新在前
    """
    whale_list = []
    
    # 获取当前 BTC 价格
    btc_price = 100000
    try:
        price_resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            timeout=5
        )
        if price_resp.status_code == 200:
            btc_price = price_resp.json().get("bitcoin", {}).get("usd", 100000)
    except:
        pass
    
    min_satoshi = min_btc * 100000000
    
    def classify_tx(btc_amount):
        """判断交易类型"""
        if btc_amount >= 1000:
            return "🐋 巨鲸", "🐋"
        elif btc_amount >= 500:
            return "🔥 超大额", "🔥"
        elif btc_amount >= 100:
            return "💰 大额", "💰"
        elif btc_amount >= 50:
            return "📊 中额", "📊"
        else:
            return "💵 交易", "💵"
    
    def parse_tx(tx, source_label=""):
        """解析交易数据并返回whale记录"""
        total_out = sum(out.get("value", 0) for out in tx.get("out", []))
        if total_out < min_satoshi:
            return None
        
        btc_amount = total_out / 100000000
        tx_time = tx.get("time", 0)
        tx_hash = tx.get("hash", "")
        
        if tx_time:
            tx_datetime = datetime.fromtimestamp(tx_time)
            time_str = tx_datetime.strftime("%m-%d %H:%M")
        else:
            tx_time = datetime.now().timestamp()
            time_str = "待确认"
        
        tx_type, icon = classify_tx(btc_amount)
        if source_label:
            tx_type = f"{tx_type}"
        
        return {
            "amount": f"{btc_amount:,.2f} BTC",
            "value_usd": f"${btc_amount * btc_price:,.0f}",
            "hash": tx_hash[:10] + "...",
            "full_hash": tx_hash,
            "time": time_str,
            "timestamp": tx_time,
            "type": tx_type,
            "icon": icon,
            "url": f"https://www.blockchain.com/explorer/transactions/btc/{tx_hash}"
        }
    
    seen_hashes = set()
    
    # 方法1: 从最新确认区块中获取大额交易（数据最丰富）
    try:
        # 获取最新区块信息
        latest_resp = requests.get(
            "https://blockchain.info/latestblock",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        )
        
        if latest_resp.status_code == 200:
            latest_block = latest_resp.json()
            block_hash = latest_block.get("hash", "")
            
            # 逐块扫描，最多扫描3个区块
            blocks_scanned = 0
            current_hash = block_hash
            
            while current_hash and blocks_scanned < 3 and len(whale_list) < limit:
                try:
                    block_resp = requests.get(
                        f"https://blockchain.info/rawblock/{current_hash}",
                        timeout=20,
                        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
                    )
                    
                    if block_resp.status_code == 200:
                        block_data = block_resp.json()
                        block_txs = block_data.get("tx", [])
                        prev_block = block_data.get("prev_block", "")
                        
                        for tx in block_txs:
                            tx_hash = tx.get("hash", "")
                            if tx_hash in seen_hashes:
                                continue
                            
                            record = parse_tx(tx)
                            if record:
                                seen_hashes.add(tx_hash)
                                whale_list.append(record)
                                
                                if len(whale_list) >= limit:
                                    break
                        
                        current_hash = prev_block
                        blocks_scanned += 1
                    else:
                        break
                        
                except Exception as e:
                    print(f"⚠️ 区块 {blocks_scanned + 1} 获取失败: {e}")
                    break
                    
    except Exception as e:
        print(f"⚠️ Blockchain.com 区块 API 失败: {e}")
    
    # 方法2: 补充未确认交易（内存池中的大额交易）
    if len(whale_list) < limit:
        try:
            response = requests.get(
                "https://blockchain.info/unconfirmed-transactions?format=json",
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
            )
            
            if response.status_code == 200:
                data = response.json()
                txs = data.get("txs", [])
                
                for tx in txs:
                    tx_hash = tx.get("hash", "")
                    if tx_hash in seen_hashes:
                        continue
                    
                    record = parse_tx(tx)
                    if record:
                        record["type"] = "⏳ " + record["type"].split(" ", 1)[-1]
                        record["icon"] = "⏳"
                        seen_hashes.add(tx_hash)
                        whale_list.append(record)
                        
                        if len(whale_list) >= limit:
                            break
                            
        except Exception as e:
            print(f"⚠️ Blockchain.com 未确认交易 API 失败: {e}")
    
    # 方法3: 如果获取不足，使用 mempool.space API
    if len(whale_list) < 3:
        try:
            response = requests.get(
                "https://mempool.space/api/mempool/recent",
                timeout=10
            )
            if response.status_code == 200:
                txs = response.json()
                for tx in txs[:200]:
                    btc_amount = tx.get("value", 0) / 100000000
                    if btc_amount >= min_btc:
                        tx_hash = tx.get("txid", "")
                        if tx_hash in seen_hashes:
                            continue
                        
                        tx_type, icon = classify_tx(btc_amount)
                        whale_list.append({
                            "amount": f"{btc_amount:,.2f} BTC",
                            "value_usd": f"${btc_amount * btc_price:,.0f}",
                            "hash": tx_hash[:10] + "...",
                            "full_hash": tx_hash,
                            "time": "待确认",
                            "timestamp": datetime.now().timestamp(),
                            "type": f"⏳ {tx_type.split(' ', 1)[-1]}",
                            "icon": "⏳",
                            "url": f"https://mempool.space/tx/{tx_hash}"
                        })
                        seen_hashes.add(tx_hash)
                        
                        if len(whale_list) >= limit:
                            break
        except Exception as e:
            print(f"⚠️ mempool.space API 失败: {e}")
    
    # 方法4: 如果仍然没有数据，显示示例/提示
    if len(whale_list) < 2:
        now = datetime.now()
        sample_transactions = [
            {"btc": 1250.50, "type": "🐋 巨鲸", "icon": "🐋", "mins_ago": 5},
            {"btc": 520.25, "type": "🔥 超大额", "icon": "🔥", "mins_ago": 12},
            {"btc": 180.80, "type": "💰 大额", "icon": "💰", "mins_ago": 18},
            {"btc": 95.50, "type": "📊 中额", "icon": "📊", "mins_ago": 25},
            {"btc": 45.20, "type": "💵 交易", "icon": "💵", "mins_ago": 32},
        ]
        
        for sample in sample_transactions[:limit]:
            tx_time = now - timedelta(minutes=sample["mins_ago"])
            whale_list.append({
                "amount": f"{sample['btc']:,.2f} BTC",
                "value_usd": f"${sample['btc'] * btc_price:,.0f}",
                "hash": "示例数据...",
                "full_hash": "",
                "time": tx_time.strftime("%m-%d %H:%M"),
                "timestamp": tx_time.timestamp(),
                "type": sample["type"],
                "icon": sample["icon"],
                "url": "https://whale-alert.io/"
            })
    
    # 按时间戳排序（最新在前）
    whale_list.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    
    # 移除 timestamp 字段
    for item in whale_list:
        if "timestamp" in item:
            del item["timestamp"]
    
    # 添加 Whale Alert 链接
    whale_list.append({
        "amount": "🔗 查看 Whale Alert",
        "value_usd": "更多鲸鱼动态",
        "hash": "",
        "time": "",
        "type": "链接",
        "icon": "🔗",
        "url": "https://whale-alert.io/"
    })
    
    return whale_list



def fetch_crypto_calendar() -> list:
    """
    获取加密货币日历 - 从律动 BlockBeats 获取
    - 代币解锁、空投、上线等事件
    - 使用关键词筛选相关快讯
    """
    crypto_events = []
    
    # 事件关键词分类
    event_keywords = {
        "解锁": ("🔓", "代币解锁", "高"),
        "空投": ("🪂", "空投", "高"),
        "上线": ("🚀", "上线", "中"),
        "升级": ("⚡", "升级", "中"),
        "主网": ("🌐", "主网", "中"),
        "测试网": ("🧪", "测试网", "低"),
        "发布": ("📢", "发布", "中"),
        "Unlock": ("🔓", "代币解锁", "高"),
        "Airdrop": ("🪂", "空投", "高"),
        "Launch": ("🚀", "上线", "中"),
    }
    
    try:
        # 从 BlockBeats Flash API 获取快讯
        response = requests.get(
            "https://api.theblockbeats.news/v1/open-api/open-flash",
            params={"size": 50, "page": 1, "type": "push", "lang": "cn"},
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        )
        
        if response.status_code == 200:
            data = response.json()
            items = data.get("data", {}).get("data", [])
            
            for item in items:
                title = item.get("title", "")
                content = item.get("content", "")
                full_text = title + content
                
                # 检查是否包含事件关键词
                for keyword, (icon, event_type, impact) in event_keywords.items():
                    if keyword in full_text:
                        # 提取时间信息
                        add_time = item.get("add_time", 0)
                        if add_time:
                            event_time = datetime.fromtimestamp(add_time)
                            time_str = event_time.strftime("%m-%d %H:%M")
                        else:
                            time_str = "即时"
                        
                        # 截取标题
                        display_title = title[:40] + "..." if len(title) > 40 else title
                        
                        crypto_events.append({
                            "event": display_title,
                            "date": time_str,
                            "status": event_type,
                            "impact": impact,
                            "type": "加密事件",
                            "icon": icon,
                            "url": f"https://www.theblockbeats.info/flash/{item.get('id', '')}"
                        })
                        break  # 只匹配第一个关键词
                
                if len(crypto_events) >= 8:
                    break
                    
    except Exception as e:
        print(f"⚠️ BlockBeats Calendar API 失败: {e}")
    
    # 如果没有获取到事件，添加一个提示
    if not crypto_events:
        crypto_events.append({
            "event": "暂无即时事件",
            "date": "",
            "status": "查看律动日历",
            "impact": "",
            "type": "提示",
            "icon": "📅",
            "url": "https://www.theblockbeats.info/calendar"
        })
    
    # 添加律动日历链接
    crypto_events.append({
        "event": "🔗 更多加密日历",
        "date": "",
        "status": "查看全部",
        "impact": "",
        "type": "链接",
        "icon": "🔗",
        "url": "https://www.theblockbeats.info/calendar"
    })
    
    return crypto_events


def fetch_macro_calendar() -> list:
    """
    获取宏观经济日历
    - 使用 faireconomy.media API (基于 Forex Factory)
    - 筛选美元相关的高影响事件：CPI、NFP、FOMC等
    - 中文翻译 + 实际/预期值显示
    """
    calendar = []
    
    # 英文 -> 中文名称映射
    name_translations = {
        # 通胀数据
        'CPI m/m': '📊 CPI 月率',
        'Core CPI m/m': '📊 核心CPI 月率',
        'CPI y/y': '📊 CPI 年率',
        'Core CPI y/y': '📊 核心CPI 年率',
        'PPI m/m': '📊 PPI 月率',
        'Core PPI m/m': '📊 核心PPI 月率',
        'PCE Price Index m/m': '📊 PCE物价指数 月率',
        'Core PCE Price Index m/m': '📊 核心PCE物价指数 月率',
        # 就业数据
        'Non-Farm Employment Change': '👷 非农就业人数',
        'Unemployment Rate': '👷 失业率',
        'Unemployment Claims': '👷 初请失业金人数',
        'Average Hourly Earnings m/m': '👷 平均时薪 月率',
        'Employment Cost Index q/q': '👷 就业成本指数 季率',
        'ADP Non-Farm Employment Change': '👷 ADP非农就业人数',
        'JOLTS Job Openings': '👷 职位空缺数',
        # 利率/美联储
        'Federal Funds Rate': '🏦 联邦基金利率',
        'FOMC Statement': '🏦 FOMC声明',
        'FOMC Meeting Minutes': '🏦 FOMC会议纪要',
        'Fed Chair Powell Speaks': '🏦 鲍威尔讲话',
        # GDP/经济增长
        'Advance GDP q/q': '📈 GDP初值 季率',
        'Prelim GDP q/q': '📈 GDP修正值 季率',
        'Final GDP q/q': '📈 GDP终值 季率',
        # 零售/消费
        'Retail Sales m/m': '🛒 零售销售 月率',
        'Core Retail Sales m/m': '🛒 核心零售销售 月率',
        'Consumer Confidence': '🛒 消费者信心指数',
        'CB Consumer Confidence': '🛒 谘商会消费者信心指数',
        # 制造业/服务业
        'ISM Manufacturing PMI': '🏭 ISM制造业PMI',
        'ISM Services PMI': '🏭 ISM服务业PMI',
        'Durable Goods Orders m/m': '🏭 耐用品订单 月率',
        'Core Durable Goods Orders m/m': '🏭 核心耐用品订单 月率',
        # 其他
        'Trade Balance': '📦 贸易差额',
        'Building Permits': '🏠 建筑许可',
        'Existing Home Sales': '🏠 成屋销售',
        'New Home Sales': '🏠 新屋销售',
    }
    
    # 影响等级映射
    impact_map = {
        'High': '高',
        'Medium': '中', 
        'Low': '低',
        'Holiday': '假日'
    }
    
    # 模块级缓存 (避免频繁请求导致429限流)
    global _macro_calendar_cache, _macro_calendar_cache_time
    
    now = datetime.now()
    if '_macro_calendar_cache' in dir(fetch_macro_calendar) and fetch_macro_calendar._cache_time:
        cache_age = (now - fetch_macro_calendar._cache_time).total_seconds()
        if cache_age < 1800 and fetch_macro_calendar._cache:  # 30分钟缓存
            return fetch_macro_calendar._cache
    
    try:
        # 获取本周经济日历 (带重试)
        import time as _time
        response = None
        for attempt in range(3):
            response = requests.get(
                "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
                timeout=15,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
            )
            if response.status_code == 200:
                break
            elif response.status_code == 429:
                wait_secs = 5 * (attempt + 1)
                print(f"⚠️ 经济日历 API 限流 (429)，{wait_secs}秒后重试...")
                _time.sleep(wait_secs)
            else:
                print(f"⚠️ 经济日历 API 返回 {response.status_code}")
                break
        
        if response is not None and response.status_code == 200:
            events = response.json()
            
            for event in events:
                country = event.get('country', '')
                title = event.get('title', '')
                impact = event.get('impact', '')
                date_str = event.get('date', '')
                actual = event.get('actual', '')
                forecast = event.get('forecast', '')
                previous = event.get('previous', '')
                
                # 只关注美元相关的高/中影响事件
                if country != 'USD':
                    continue
                if impact not in ['High', 'Medium']:
                    continue
                
                # 中文名称翻译
                chinese_name = name_translations.get(title, None)
                if chinese_name:
                    display_name = chinese_name
                else:
                    # 未翻译的事件添加默认图标
                    if 'CPI' in title or 'Inflation' in title or 'PPI' in title or 'PCE' in title:
                        display_name = f'📊 {title}'
                    elif 'Employ' in title or 'Unemployment' in title or 'Non-Farm' in title or 'NFP' in title:
                        display_name = f'👷 {title}'
                    elif 'Fed' in title or 'FOMC' in title or 'Rate' in title or 'Powell' in title:
                        display_name = f'🏦 {title}'
                    elif 'GDP' in title:
                        display_name = f'📈 {title}'
                    elif 'Retail' in title or 'Consumer' in title:
                        display_name = f'🛒 {title}'
                    elif 'ISM' in title or 'PMI' in title or 'Durable' in title:
                        display_name = f'🏭 {title}'
                    else:
                        display_name = f'📅 {title}'
                
                # 解析时间 (转换为北京时间 UTC+8)
                try:
                    event_time = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    beijing_tz = timezone(timedelta(hours=8))
                    event_time_beijing = event_time.astimezone(beijing_tz)
                    display_date = event_time_beijing.strftime("%m-%d %H:%M")
                except:
                    display_date = date_str[:16] if len(date_str) > 16 else date_str
                
                # 判断事件是否已经过去（已公布）
                is_past = False
                try:
                    event_dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    beijing_tz_check = timezone(timedelta(hours=8))
                    now_beijing = datetime.now(beijing_tz_check)
                    is_past = event_dt < now_beijing
                except:
                    pass
                
                # 构建数据结果字符串
                data_result = ""
                if actual:
                    data_result = f"公布: {actual}"
                    if forecast:
                        data_result += f" · 预期: {forecast}"
                    if previous:
                        data_result += f" · 前值: {previous}"
                elif is_past:
                    parts = []
                    if forecast:
                        parts.append(f"预期: {forecast}")
                    if previous:
                        parts.append(f"前值: {previous}")
                    data_result = " · ".join(parts) if parts else ""
                else:
                    parts = []
                    if forecast:
                        parts.append(f"预期: {forecast}")
                    if previous:
                        parts.append(f"前值: {previous}")
                    data_result = " · ".join(parts) if parts else ""
                
                # 事件状态
                if actual:
                    event_status = "已公布"
                elif is_past:
                    event_status = "已公布"
                else:
                    event_status = "待公布"
                
                calendar.append({
                    "event": display_name,
                    "date": display_date,
                    "data": data_result,
                    "impact": impact_map.get(impact, ''),
                    "type": "宏观经济",
                    "has_actual": bool(actual),
                    "is_past": is_past,
                    "event_status": event_status,
                    "forecast": forecast or "",
                    "previous": previous or "",
                    "actual": actual or ""
                })
            
            # 按时间排序
            calendar.sort(key=lambda x: x.get('date', ''))
            
            # 限制返回数量
            calendar = calendar[:15]
                    
    except Exception as e:
        print(f"⚠️ 经济日历 API 失败: {e}")
    
    # 如果没有获取到数据，返回备用信息
    if not calendar:
        calendar.append({
            "event": "📅 查看完整经济日历",
            "date": "",
            "data": "",
            "impact": "",
            "type": "链接",
            "url": "https://www.investing.com/economic-calendar/"
        })
    
    return calendar


def calc_max_pain() -> IndicatorResult:
    """
    BTC 期权最大痛点 (Max Pain)
    - 数据源: Deribit (Real-time Option Chain)
    - 逻辑: 选取持仓量(OI)最大的到期日，计算 Call/Put 归零最痛点位
    - 意义: 临近交割时，价格往往向痛点移动
    """
    try:
        # 1. 获取 Deribit 所有期权数据
        response = requests.get(
            "https://www.deribit.com/api/v2/public/get_book_summary_by_currency",
            params={"currency": "BTC", "kind": "option"},
            timeout=10
        )
        if response.status_code != 200:
            raise Exception(f"API Error {response.status_code}")
            
        data = response.json().get("result", [])
        if not data:
            raise Exception("No data returned")
            
        # 2. 整理数据，找到 active exps
        # 格式: BTC-29MAR24-60000-C
        options = []
        for item in data:
            parts = item["instrument_name"].split("-")
            if len(parts) == 4 and item.get("open_interest", 0) > 0:
                options.append({
                    "expiry": parts[1],
                    "strike": float(parts[2]),
                    "type": parts[3], # C or P
                    "oi": item["open_interest"]
                })
        
        if not options:
            raise Exception("No active options found")
            
        df = pd.DataFrame(options)
        
        # 3. 找到 OI 最大的到期日 (主力合约)
        top_expiry = df.groupby("expiry")["oi"].sum().idxmax()
        df_exp = df[df["expiry"] == top_expiry]
        
        # 4. 计算 Max Pain
        strikes = sorted(df_exp["strike"].unique())
        pain_data = []
        
        for price in strikes:
            total_pain = 0
            # Call Pain: if Price > Strike, Pain = (Price - Strike) * OI
            # Put Pain: if Price < Strike, Pain = (Strike - Price) * OI
            
            calls = df_exp[df_exp["type"] == "C"]
            puts = df_exp[df_exp["type"] == "P"]
            
            # 向量化计算加速
            # Call Pain
            itm_calls = calls[calls["strike"] < price]
            if not itm_calls.empty:
                total_pain += ((price - itm_calls["strike"]) * itm_calls["oi"]).sum()
                
            # Put Pain
            itm_puts = puts[puts["strike"] > price]
            if not itm_puts.empty:
                total_pain += ((itm_puts["strike"] - price) * itm_puts["oi"]).sum()
                
            pain_data.append((price, total_pain))
            
        best_strike, min_pain = min(pain_data, key=lambda x: x[1])
        
        # 状态描述
        # 简单给个中性评分，重点展示价格
        return IndicatorResult(
            name=f"最大痛点({top_expiry})",
            value=best_strike,
            score=0,
            color="🟡", # 中性颜色，作为参考位
            status=f"痛点价格 ${best_strike:,.0f}",
            priority="P1",
            url="https://www.deribit.com/statistics/BTC/options-open-interest"
        )

    except Exception as e:
        print(f"⚠️ Max Pain Calc Failed: {e}")
        return IndicatorResult(
            name="最大痛点",
            value=float('nan'),
            score=0,
            color="⚪",
            status="API 暂不可用",
            priority="P1"
        )


# ============================================================
# 历史数据获取函数
# ============================================================

def get_ahr999_history(df: pd.DataFrame, days: int = 90) -> dict:
    """获取 Ahr999 指标历史数据"""
    # 计算历史 Ahr999
    genesis = datetime(2009, 1, 3)
    
    # 取最近 N 天数据
    recent_df = df.tail(days).copy()
    
    dates = []
    values = []
    
    # 计算对数以求几何平均
    df['log_price'] = np.log(df['price'])
    # Rolling 200 Geometric Mean = exp(Rolling Mean(log_price))
    df['gmean200'] = np.exp(df['log_price'].rolling(200).mean())

    for date, row in recent_df.iterrows():
        days_since = (date - genesis).days
        if days_since > 0:
            log_fair = AHR999_A + AHR999_B * np.log10(days_since)
            fair_price = 10 ** log_fair
            
            # 使用预计算的几何平均 (Rolling Geometric Mean)
            if date in df.index:
                ma200 = df.loc[date, 'gmean200']
            else:
                ma200 = row['price'] # Fallback
            
            # Fallback calculation if rolling data missing (e.g. early days)
            if pd.isna(ma200):
                 # Try manual tail calculation if enough data
                 hist_slice = df.loc[:date, 'price'].tail(200)
                 if len(hist_slice) > 0:
                     ma200 = np.exp(np.mean(np.log(hist_slice)))

            if fair_price > 0 and ma200 > 0:
                # 标准 AHR999 公式: (Price/Cost) * (Price/Fair)
                ahr999 = (row['price'] / ma200) * (row['price'] / fair_price)
                dates.append(date.strftime('%Y-%m-%d'))
                values.append(round(ahr999, 3))
    
    # Clean up temporary columns
    df.drop(columns=['log_price', 'gmean200'], inplace=True, errors='ignore')
    
    return {
        "indicator": "Ahr999",
        "dates": dates,
        "values": values,
        "thresholds": {
            "buy": {"value": 0.45, "color": "#22c55e", "label": "抄底线"},
            "dca": {"value": 1.2, "color": "#eab308", "label": "定投上限"},
            "sell": {"value": 5.0, "color": "#ef4444", "label": "止盈线"}
        }
    }


def get_fear_greed_history(days: int = 30) -> dict:
    """获取恐惧贪婪指数历史数据"""
    try:
        response = requests.get(
            f"https://api.alternative.me/fng/?limit={days}",
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()["data"]
            dates = []
            values = []
            
            for item in reversed(data):  # API 返回的是倒序
                dates.append(datetime.fromtimestamp(int(item["timestamp"])).strftime('%Y-%m-%d'))
                values.append(int(item["value"]))
            
            return {
                "indicator": "恐惧贪婪指数",
                "dates": dates,
                "values": values,
                "thresholds": {
                    "extreme_fear": {"value": 25, "color": "#22c55e", "label": "极度恐惧"},
                    "neutral": {"value": 50, "color": "#eab308", "label": "中性"},
                    "extreme_greed": {"value": 75, "color": "#ef4444", "label": "极度贪婪"}
                }
            }
    except Exception as e:
        print(f"⚠️ Fear & Greed History API 失败: {e}")
    
    return {"indicator": "恐惧贪婪指数", "dates": [], "values": [], "thresholds": {}}


def get_funding_rate_history(days: int = 30) -> dict:
    """获取资金费率历史数据"""
    try:
        # Binance 资金费率每 8 小时一次，需要获取更多数据点
        limit = days * 3
        response = requests.get(
            "https://fapi.binance.com/fapi/v1/fundingRate",
            params={"symbol": "BTCUSDT", "limit": limit},
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            
            # 按日期分组，取每天最后一个费率
            daily_data = {}
            for item in data:
                date = datetime.fromtimestamp(item["fundingTime"] / 1000).strftime('%Y-%m-%d')
                rate = float(item["fundingRate"]) * 100
                daily_data[date] = rate
            
            # 排序并取最近 N 天
            sorted_dates = sorted(daily_data.keys())[-days:]
            dates = sorted_dates
            values = [round(daily_data[d], 4) for d in sorted_dates]
            
            return {
                "indicator": "资金费率",
                "dates": dates,
                "values": values,
                "thresholds": {
                    "negative": {"value": -0.03, "color": "#22c55e", "label": "偏空"},
                    "neutral": {"value": 0, "color": "#6b7280", "label": "中性"},
                    "positive": {"value": 0.03, "color": "#eab308", "label": "偏多"},
                    "extreme": {"value": 0.1, "color": "#ef4444", "label": "过热"}
                }
            }
    except Exception as e:
        print(f"⚠️ Funding Rate History API 失败: {e}")
    
    return {"indicator": "资金费率", "dates": [], "values": [], "thresholds": {}}


def get_long_short_history(days: int = 30) -> dict:
    """获取多空比历史数据 (OKX 主源 + Binance 备用)"""
    dates = []
    values = []
    
    # 方法1: OKX API
    try:
        response = requests.get(
            "https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio",
            params={"ccy": "BTC", "period": "1D"},
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == "0" and data.get("data"):
                # OKX 数据格式: [[timestamp_ms, ratio], ...]，按时间倒序
                for item in reversed(data["data"]):
                    ts = int(item[0]) / 1000
                    date = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                    dates.append(date)
                    values.append(round(float(item[1]), 2))
                
                # 只取最近 N 天
                dates = dates[-days:]
                values = values[-days:]
    except Exception as e:
        print(f"⚠️ OKX Long/Short History API 失败: {e}")
    
    # 方法2: Binance (备用)
    if not dates:
        try:
            response = requests.get(
                "https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
                params={"symbol": "BTCUSDT", "period": "1d", "limit": days},
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                for item in data:
                    date = datetime.fromtimestamp(item["timestamp"] / 1000).strftime('%Y-%m-%d')
                    dates.append(date)
                    values.append(round(float(item["longShortRatio"]), 2))
        except Exception as e:
            print(f"⚠️ Binance Long/Short History API 失败: {e}")
    
    if dates:
        return {
            "indicator": "多空比",
            "dates": dates,
            "values": values,
            "thresholds": {
                "short_squeeze": {"value": 0.5, "color": "#22c55e", "label": "空头拥挤"},
                "balanced": {"value": 1.0, "color": "#6b7280", "label": "均衡"},
                "long_heavy": {"value": 1.5, "color": "#eab308", "label": "偏多"},
                "extreme_long": {"value": 2.0, "color": "#ef4444", "label": "极度偏多"}
            }
        }
    
    return {"indicator": "多空比", "dates": [], "values": [], "thresholds": {}}


def get_pi_cycle_history(df: pd.DataFrame, days: int = 90) -> dict:
    """获取 Pi Cycle 历史数据（111MA vs 350MA*2 的差距百分比）"""
    recent_df = df.tail(days + 350).copy()  # 需要更多数据来计算 MA
    
    ma_111 = recent_df['price'].rolling(window=111).mean()
    ma_350 = recent_df['price'].rolling(window=350).mean() * 2
    
    # 计算差距百分比
    gap_pct = ((ma_350 - ma_111) / ma_350 * 100).dropna().tail(days)
    
    dates = [d.strftime('%Y-%m-%d') for d in gap_pct.index]
    values = [round(v, 2) for v in gap_pct.values]
    
    return {
        "indicator": "Pi Cycle Top",
        "dates": dates,
        "values": values,
        "thresholds": {
            "danger": {"value": 0, "color": "#ef4444", "label": "交叉危险"},
            "warning": {"value": 10, "color": "#eab308", "label": "接近"},
            "safe": {"value": 30, "color": "#22c55e", "label": "安全"}
        }
    }



def get_two_year_ma_history(df: pd.DataFrame, days: int = 365*4) -> dict:
    """获取 2-Year MA Multiplier 历史数据"""
    dates = []
    prices = []
    ma2y_vals = []
    ma2y_x5_vals = []
    
    # Pre-calculate rolling mean on FULL dataframe then slice
    # Use .copy() to avoid SettingWithCopyWarning
    work_df = df.copy()
    work_df['ma730'] = work_df['price'].rolling(window=730).mean()
    work_df['ma730_x5'] = work_df['ma730'] * 5
    
    sliced = work_df.tail(days)
    
    for date, row in sliced.iterrows():
        dates.append(date.strftime('%Y-%m-%d'))
        prices.append(round(row['price'], 2))
        ma2y_vals.append(round(row['ma730'], 2) if not pd.isna(row['ma730']) else None)
        ma2y_x5_vals.append(round(row['ma730_x5'], 2) if not pd.isna(row['ma730_x5']) else None)
        
    return {
        "indicator": "2-Year MA Mult",
        "dates": dates,
        "values": prices, # Main line is Price
        "lines": { # Additional lines
            "MA730 (Buy)": {"values": ma2y_vals, "color": "#22c55e"},
            "MA730 x5 (Sell)": {"values": ma2y_x5_vals, "color": "#ef4444"}
        },
        "thresholds": {}
    }

def get_200w_heatmap_history(df: pd.DataFrame, days: int = 365*4) -> dict:
    """获取 200-Week MA Heatmap 历史数据"""
    work_df = df.copy()
    work_df['ma200w'] = work_df['price'].rolling(window=1400).mean()
    sliced = work_df.tail(days)
    
    dates = []
    prices = []
    ma200w_vals = []
    
    for date, row in sliced.iterrows():
        dates.append(date.strftime('%Y-%m-%d'))
        prices.append(round(row['price'], 2))
        ma200w_vals.append(round(row['ma200w'], 2) if not pd.isna(row['ma200w']) else None)
        
    return {
        "indicator": "200-Week Heatmap",
        "dates": dates,
        "values": prices,
        "lines": {
            "200W MA (Bottom)": {"values": ma200w_vals, "color": "#3b82f6"} # Blue
        },
        "thresholds": {}
    }

def get_golden_ratio_history(df: pd.DataFrame, days: int = 365*2) -> dict:
    """获取 Golden Ratio Multiplier 历史数据"""
    work_df = df.copy()
    work_df['ma350'] = work_df['price'].rolling(window=350).mean()
    sliced = work_df.tail(days)
    
    dates = []
    prices = []
    x1_6 = []
    x2_0 = []
    x3_0 = []
    
    for date, row in sliced.iterrows():
        dates.append(date.strftime('%Y-%m-%d'))
        prices.append(round(row['price'], 2))
        if not pd.isna(row['ma350']):
            ma = row['ma350']
            x1_6.append(round(ma * 1.6, 2))
            x2_0.append(round(ma * 2.0, 2))
            x3_0.append(round(ma * 3.0, 2))
        else:
            x1_6.append(None)
            x2_0.append(None)
            x3_0.append(None)
            
    return {
        "indicator": "Golden Ratio",
        "dates": dates,
        "values": prices,
        "lines": {
            "x1.6 (Golden)": {"values": x1_6, "color": "#eab308"},
            "x2.0": {"values": x2_0, "color": "#f97316"},
            "x3.0 (Top)": {"values": x3_0, "color": "#ef4444"}
        },
        "thresholds": {}
    }


def get_indicator_history(indicator_name: str, df: pd.DataFrame = None, days: int = 30) -> dict:
    """统一的历史数据获取入口"""
    if indicator_name == "Ahr999" and df is not None:
        return get_ahr999_history(df, days)
    elif indicator_name == "恐惧贪婪指数":
        return get_fear_greed_history(days)
    elif indicator_name == "资金费率":
        return get_funding_rate_history(days)
    elif indicator_name == "多空比":
        return get_long_short_history(days)
    elif indicator_name == "Pi Cycle Top" and df is not None:
        return get_pi_cycle_history(df, days)
    # New Cycle Indicators
    elif indicator_name == "2-Year MA Mult" and df is not None:
        return get_two_year_ma_history(df, days)
    elif indicator_name == "200-Week Heatmap" and df is not None:
        return get_200w_heatmap_history(df, days)
    elif indicator_name == "Golden Ratio" and df is not None:
        return get_golden_ratio_history(df, days)
    else:
        return {"indicator": indicator_name, "dates": [], "values": [], "thresholds": {}}



# ============================================================

# 权重配置
WEIGHTS = {
    # ═══ 长期指标 55% (周期/定投参考) ═══
    "Mayer Multiple": 0.08,
    "Pi Cycle Top": 0.07,
    "减半周期": 0.07,
    "Ahr999": 0.07,
    "幂律走廊": 0.07,
    "2-Year MA Mult": 0.06,
    "200-Week Heatmap": 0.06,
    "Golden Ratio": 0.07,
    # ═══ 短期指标 30% (交易参考) ═══
    "RSI(14)": 0.05,
    "MACD": 0.05,
    "恐惧贪婪指数": 0.05,
    "布林带": 0.04,
    "资金费率": 0.04,
    "多空比": 0.04,
    "最大痛点": 0.03,
    # ═══ 辅助指标 15% ═══
    "长期持有者(CDD)": 0.06,
    "均衡价格": 0.03,
    "交易所余额": 0.02,
    "ETF资金流": 0.01,
    "BTC市占率": 0.01,
    "全网算力": 0.01,
    "公司持仓": 0.01,
}  # 总和 = 1.00 (100%)


def calculate_total_score(indicators: Dict[str, IndicatorResult]) -> Tuple[float, str]:
    """计算加权总分"""
    total = 0
    weight_sum = 0
    
    for name, result in indicators.items():
        # 这里需要注意名字匹配：Calculator returns "长期持有者(CDD)"
        if not np.isnan(result.value) and name in WEIGHTS:
            total += WEIGHTS[name] * result.score
            weight_sum += WEIGHTS[name]
    
    # 归一化
    if weight_sum > 0:
        normalized_score = total / weight_sum
    else:
        normalized_score = 0
            
    # 生成建议
    if normalized_score >= 0.8:
        recommendation = "强烈买入 (Strong Buy)"
    elif normalized_score >= 0.4:
        recommendation = "买入 (Buy)"
    elif normalized_score >= 0.1:
        recommendation = "增持 (Accumulate)"
    elif normalized_score >= -0.1:
        recommendation = "持有/观望 (Hold)"
    elif normalized_score >= -0.4:
        recommendation = "减仓 (Reduce)"
    elif normalized_score >= -0.8:
        recommendation = "卖出 (Sell)"
    else:
        recommendation = "清仓 (Strong Sell)"
        
    return normalized_score, recommendation


# ============================================================
# 仪表盘显示
# ============================================================

def print_dashboard(result: DashboardResult):
    """打印仪表盘"""
    print("\n" + "=" * 60)
    print("📊 BTC 长期指标仪表盘")
    print("=" * 60)
    print(f"更新时间: {result.timestamp.strftime('%Y-%m-%d %H:%M')}")
    print(f"当前价格: ${result.btc_price:,.2f}")
    print("-" * 60)
    
    # 综合评分条
    score = result.total_score
    bar_length = 30
    position = int((score + 1) / 2 * bar_length)
    bar = "━" * position + "●" + "━" * (bar_length - position - 1)
    print(f"\n综合评分: {score:.2f}  {result.recommendation}")
    print(f"  -1 [{bar}] +1")
    
    # 按优先级分组显示
    print("\n" + "-" * 60)
    print("🔴 P0 核心指标")
    print("-" * 60)
    for name, ind in result.indicators.items():
        if ind.priority == "P0":
            print(f"  {ind.color} {ind.name:15} | {ind.status}")
    
    print("\n" + "-" * 60)
    print("🟡 P1 参考指标")
    print("-" * 60)
    for name, ind in result.indicators.items():
        if ind.priority == "P1":
            print(f"  {ind.color} {ind.name:15} | {ind.status}")
    
    print("\n" + "=" * 60)


# ============================================================
# 主函数
# ============================================================

def run_dashboard() -> DashboardResult:
    """运行仪表盘分析"""
    # 获取历史数据（用于计算指标）
    df = fetch_btc_data()
    
    # 优先使用实时价格 API，失败则回退到历史数据最新价格
    realtime_price = fetch_realtime_btc_price()
    if realtime_price is not None:
        current_price = realtime_price
        # 更新 DataFrame 最新价格用于指标计算
        df.iloc[-1, df.columns.get_loc('price')] = current_price
    else:
        current_price = df['price'].iloc[-1]
        print("⚠️ 使用历史数据价格（非实时）")
    
    # 计算各指标
    indicators = {}
    
    # 长期指标 (周期/定投参考)
    indicators["Mayer Multiple"] = calc_mayer_multiple(df)
    indicators["Pi Cycle Top"] = calc_pi_cycle(df)
    indicators["减半周期"] = calc_halving_cycle()
    indicators["Ahr999"] = calc_ahr999(df)
    indicators["幂律走廊"] = calc_power_law(df)
    indicators["2-Year MA Mult"] = calc_two_year_ma_multiplier(df)
    indicators["200-Week Heatmap"] = calc_200w_ma_heatmap(df)
    indicators["Golden Ratio"] = calc_golden_ratio_multiplier(df)
    
    # 短期指标 (交易参考)
    indicators["RSI(14)"] = calc_rsi(df)
    indicators["MACD"] = calc_macd(df)
    indicators["布林带"] = calc_bollinger_bands(df)
    indicators["恐惧贪婪指数"] = calc_fear_greed_index()
    indicators["资金费率"] = calc_funding_rate()
    indicators["多空比"] = calc_long_short_ratio()
    indicators["最大痛点"] = calc_max_pain()
    
    # 辅助指标
    indicators["BTC市占率"] = calc_btc_dominance()
    indicators["ETF资金流"] = calc_etf_flow()
    indicators["公司持仓"] = calc_company_holdings()
    indicators["交易所余额"] = calc_exchange_reserve()
    indicators["全网算力"] = calc_hashrate()
    indicators["全网算力"] = calc_hashrate()
    indicators["均衡价格"] = calc_balanced_price(df)
    indicators["长期持有者(CDD)"] = calc_lth_supply()
    
    # 计算综合评分
    total_score, recommendation = calculate_total_score(indicators)
    
    # 构建结果
    result = DashboardResult(
        timestamp=datetime.now(),
        btc_price=current_price,
        indicators=indicators,
        total_score=total_score,
        recommendation=recommendation
    )
    
    return result


def main():
    """入口函数"""
    result = run_dashboard()
    print_dashboard(result)
    return result


if __name__ == "__main__":
    main()
