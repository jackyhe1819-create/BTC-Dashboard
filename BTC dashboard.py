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
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Tuple, Dict
import warnings
warnings.filterwarnings('ignore')


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
            print(f"⚠️ 尝试 {attempt + 1}/{max_retries} 失败: {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
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


def calc_mvrv_placeholder() -> IndicatorResult:
    """
    MVRV Z-Score (占位符)
    - 需要 Glassnode API，暂时返回中性
    """
    return IndicatorResult(
        name="MVRV Z-Score",
        value=float('nan'),
        score=0,
        color="⚪",
        status="需要 Glassnode API",
        priority="P0"
    )


# ============================================================
# 综合评分计算
# ============================================================

# 权重配置
WEIGHTS = {
    "MVRV Z-Score": 0.20,
    "Pi Cycle Top": 0.15,
    "减半周期": 0.10,
    "Ahr999": 0.15,
    "幂律走廊": 0.15,
    "NUPL": 0.15,
    "MPI": 0.10,
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
    # 获取数据
    df = fetch_btc_data()
    current_price = df['price'].iloc[-1]
    
    # 计算各指标
    indicators = {}
    
    # P0 指标
    indicators["MVRV Z-Score"] = calc_mvrv_placeholder()
    indicators["Pi Cycle Top"] = calc_pi_cycle(df)
    indicators["减半周期"] = calc_halving_cycle()
    
    # P1 指标
    indicators["Ahr999"] = calc_ahr999(df)
    indicators["幂律走廊"] = calc_power_law(df)
    
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
