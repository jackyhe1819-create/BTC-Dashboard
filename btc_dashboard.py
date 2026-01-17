#!/Users/jack/opt/anaconda3/bin/python
# -*- coding: utf-8 -*-
"""
BTC 长期指标仪表盘
==================
基于需求文档实现的 P0 + P1 指标监控系统

指标列表:
- P0: Pi Cycle Top, 减半周期
- P1: Ahr999, 幂律走廊
- (P0 MVRV 需 Glassnode API，暂用占位)

运行要求:
    pip install yfinance pandas matplotlib
"""

import pandas as pd
import numpy as np
import yfinance as yf
import requests
from datetime import datetime, timedelta
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

# Ahr999 参数 (复用幂律参数或使用特定拟合)
AHR999_A = -17.67
AHR999_B = 5.93


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
    """获取 BTC 历史价格数据（带重试机制）"""
    import time
    
    print("📥 正在获取 BTC 价格数据...")
    
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
            print(f"✅ 获取到 {len(btc)} 条数据，最新日期: {btc.index[-1].date()}")
            return btc
            
        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ 尝试 {attempt + 1}/{max_retries} 失败: {error_msg}")
            
            # 如果是限流错误，直接停止重试，使用示例数据
            if "Rate limited" in error_msg or "Too Many Requests" in error_msg:
                print("⛔️ 检测到 API 限流，立即切换到示例数据模式。")
                break
                
            if attempt < max_retries - 1:
                wait_time = 1 # 减少重试等待时间，提升用户体验
                print(f"   等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
    
    # 所有重试都失败，使用本地缓存或生成示例数据
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
        priority="P0"
    )


def calc_halving_cycle() -> IndicatorResult:
    """
    减半周期位置
    - 计算距离上次减半的月数
    """
    today = datetime.now()
    
    # 找到最近的减半日期
    past_halvings = [d for d in HALVING_DATES if d <= today]
    last_halving = past_halvings[-1] if past_halvings else HALVING_DATES[0]
    
    # 计算距离上次减半的月数
    months_since = (today - last_halving).days / 30.44
    
    # 评分逻辑
    if months_since <= 12:
        score, color, status = 1, "🟢", f"减半后 {months_since:.0f} 个月 (牛市起点)"
    elif months_since <= 24:
        score, color, status = 0, "🟡", f"减半后 {months_since:.0f} 个月 (周期中期)"
    else:
        score, color, status = -1, "🔴", f"减半后 {months_since:.0f} 个月 (周期后期)"
    
    return IndicatorResult(
        name="减半周期",
        value=months_since,
        score=score,
        color=color,
        status=status,
        priority="P0"
    )


def calc_ahr999(df: pd.DataFrame) -> IndicatorResult:
    """
    Ahr999 指数
    - 价格 / 200日均线
    """
    df = df.copy()
    df['ma200'] = df['price'].rolling(window=200).mean()
    
    latest = df.iloc[-1]
    ahr999 = latest['price'] / latest['ma200']
    
    # 评分逻辑
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
        priority="P1"
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
        priority="P1"
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
        url="https://charts.bitbo.io/mayer-multiple/"
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
                priority="P1"
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
    try:
        response = requests.get(
            "https://fapi.binance.com/fapi/v1/fundingRate",
            params={"symbol": "BTCUSDT", "limit": 1},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()[0]
            rate = float(data["fundingRate"]) * 100  # 转为百分比
            
            # 评分逻辑：极端费率是反向指标
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
                priority="P1"
            )
    except Exception as e:
        print(f"⚠️ Binance Funding Rate API 失败: {e}")
    
    return IndicatorResult(
        name="资金费率",
        value=float('nan'),
        score=0,
        color="⚪",
        status="API 暂不可用",
        priority="P1"
    )


def calc_long_short_ratio() -> IndicatorResult:
    """
    全球多空比
    - 数据源: Binance (免费 API)
    - >1: 多头占优, <1: 空头占优
    """
    try:
        response = requests.get(
            "https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
            params={"symbol": "BTCUSDT", "period": "1h", "limit": 1},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()[0]
            ratio = float(data["longShortRatio"])
            long_pct = float(data["longAccount"]) * 100
            short_pct = float(data["shortAccount"]) * 100
            
            # 评分逻辑：极端多空比是反向指标
            if ratio > 2.0:
                score, color = -1, "🔴"
                status = f"极度偏多 ({ratio:.2f}) 多{long_pct:.0f}%/空{short_pct:.0f}%"
            elif ratio > 1.2:
                score, color = -0.5, "🟡"
                status = f"偏多 ({ratio:.2f}) 多{long_pct:.0f}%/空{short_pct:.0f}%"
            elif ratio > 0.8:
                score, color = 0, "🟡"
                status = f"均衡 ({ratio:.2f}) 多{long_pct:.0f}%/空{short_pct:.0f}%"
            elif ratio > 0.5:
                score, color = 0.5, "🟢"
                status = f"偏空 ({ratio:.2f}) 多{long_pct:.0f}%/空{short_pct:.0f}%"
            else:
                score, color = 1, "🟢"
                status = f"极度偏空 ({ratio:.2f}) 多{long_pct:.0f}%/空{short_pct:.0f}%"
            
            return IndicatorResult(
                name="多空比",
                value=ratio,
                score=score,
                color=color,
                status=status,
                priority="P1"
            )
    except Exception as e:
        print(f"⚠️ Binance Long/Short API 失败: {e}")
    
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
                priority="P2"
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
        priority="P2",
        url="https://coinglass.com/bitcoin-etf"
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
    交易所余额 (占位符)
    - 需要 CryptoQuant API Key
    """
    return IndicatorResult(
        name="交易所余额",
        value=float('nan'),
        score=0,
        color="⚪",
        status="点击查看详情",
        priority="P2",
        url="https://cryptoquant.com/asset/btc/chart/exchange-flows/exchange-reserve"
    )


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
    
    for date, row in recent_df.iterrows():
        days_since = (date - genesis).days
        if days_since > 0:
            log_fair = AHR999_A + AHR999_B * np.log10(days_since)
            fair_price = 10 ** log_fair
            ma200 = df.loc[:date, 'price'].tail(200).mean()
            
            if fair_price > 0 and ma200 > 0:
                ahr999 = (row['price'] / fair_price) * (row['price'] / ma200) ** 0.5
                dates.append(date.strftime('%Y-%m-%d'))
                values.append(round(ahr999, 3))
    
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
    """获取多空比历史数据"""
    try:
        response = requests.get(
            "https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
            params={"symbol": "BTCUSDT", "period": "1d", "limit": days},
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            dates = []
            values = []
            
            for item in data:
                date = datetime.fromtimestamp(item["timestamp"] / 1000).strftime('%Y-%m-%d')
                dates.append(date)
                values.append(round(float(item["longShortRatio"]), 2))
            
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
    except Exception as e:
        print(f"⚠️ Long/Short History API 失败: {e}")
    
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
    else:
        return {"indicator": indicator_name, "dates": [], "values": [], "thresholds": {}}



# ============================================================

# 权重配置
WEIGHTS = {
    # P0 核心指标
    "Mayer Multiple": 0.15,
    "Pi Cycle Top": 0.12,
    "减半周期": 0.08,
    # P1 参考指标
    "Ahr999": 0.10,
    "幂律走廊": 0.10,
    "恐惧贪婪指数": 0.12,
    "资金费率": 0.10,
    "多空比": 0.08,
    "最大痛点": 0.05,
    # P2 辅助指标
    "BTC市占率": 0.05,
    "ETF资金流": 0.05,
    "公司持仓": 0.03,
    "交易所余额": 0.02,
}


def calculate_total_score(indicators: Dict[str, IndicatorResult]) -> Tuple[float, str]:
    """计算加权总分"""
    total = 0
    weight_sum = 0
    
    for name, result in indicators.items():
        if not np.isnan(result.value) and name in WEIGHTS:
            total += WEIGHTS[name] * result.score
            weight_sum += WEIGHTS[name]
    
    # 归一化
    if weight_sum > 0:
        total_score = total / weight_sum
    else:
        total_score = 0
    
    # 建议
    if total_score >= 0.5:
        recommendation = "🟢 积极加仓"
    elif total_score >= -0.3:
        recommendation = "🟡 持有观望"
    else:
        recommendation = "🔴 减仓止盈"
    
    return total_score, recommendation


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
    
    # P0 指标
    indicators["Mayer Multiple"] = calc_mayer_multiple(df)
    indicators["Pi Cycle Top"] = calc_pi_cycle(df)
    indicators["减半周期"] = calc_halving_cycle()
    
    # P1 指标
    indicators["Ahr999"] = calc_ahr999(df)
    indicators["幂律走廊"] = calc_power_law(df)
    indicators["恐惧贪婪指数"] = calc_fear_greed_index()
    indicators["资金费率"] = calc_funding_rate()
    indicators["多空比"] = calc_long_short_ratio()
    indicators["最大痛点"] = calc_max_pain()
    
    # P2 指标
    indicators["BTC市占率"] = calc_btc_dominance()
    indicators["ETF资金流"] = calc_etf_flow()
    indicators["公司持仓"] = calc_company_holdings()
    indicators["交易所余额"] = calc_exchange_reserve()
    
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
