#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ahr999 比特币定投指标美化图表示例程序
功能：
  - 自动获取 BTC 历史数据
  - 计算 200 日定投成本与 Ahr999 指标
  - 绘制 BTC 价格、200 日移动均线、Ahr999 指标，并显示抄底线与定投线
  - 使用双坐标系展示数据，并采用 Seaborn 样式及字体美化图表
"""

import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
import time
import matplotlib.font_manager as fm

# -------------------------------
# 1. 全局样式和字体设置
# -------------------------------

# 启用 Seaborn 样式
plt.style.use("seaborn-whitegrid")
# 设置图形分辨率
plt.rcParams['figure.dpi'] = 130
# 保证负号正常显示
plt.rcParams['axes.unicode_minus'] = False

# 创建 FontProperties 对象，指定中文字体文件路径（请根据系统实际情况修改）
chinese_font = fm.FontProperties(fname='/System/Library/Fonts/STHeiti Medium.ttc')

# -------------------------------
# 2. 数据获取与指标计算
# -------------------------------
def get_btc_data(ticker="BTC-USD", start_date="2013-01-01", max_retries=3, pause=5):
    """通过 yfinance 获取 BTC 历史数据，并支持重试机制"""
    retries = 0
    while retries < max_retries:
        try:
            data = yf.download(ticker, start=start_date)
            if data.empty:
                raise ValueError("数据为空")
            return data
        except Exception as e:
            print(f"获取数据失败, 原因: {e}. 正在重试 {retries+1}/{max_retries} ...")
            retries += 1
            time.sleep(pause)
    return None

def main():
    # 获取数据
    btc = get_btc_data()
    if btc is None or btc.empty:
        print("未能获取BTC数据，请检查网络连接或数据源配置。")
        return

    # 取调整后的 'Close' 作为 BTC 价格
    btc['Price'] = btc['Close']
    # 计算 200 日移动平均线（定投成本）
    btc['MA200'] = btc['Price'].rolling(window=200).mean()
    # 计算 Ahr999 指标
    btc['Ahr999'] = btc['Price'] / btc['MA200']

    # 定义阈值：抄底线与定投线
    ratio_bottom = 0.6
    ratio_dingtou = 1.0

    # -------------------------------
    # 3. 绘制图形（美化版）
    # -------------------------------
    fig, ax1 = plt.subplots(figsize=(14, 8))
    # 使用双坐标系：ax1 显示价格相关指标；ax2 显示 Ahr999 指标
    ax2 = ax1.twinx()

    # 绘制 BTC 历史价格（蓝色实线）
    l1, = ax1.plot(btc.index, btc['Price'], label='BTC价格', color='blue', linewidth=2)
    # 绘制 200 日移动均线（橙色虚线）
    l2, = ax1.plot(btc.index, btc['MA200'], label='200日定投成本', color='orange', linestyle='--', linewidth=2)
    # 绘制 Ahr999 囤币指标（绿色实线）
    l3, = ax2.plot(btc.index, btc['Ahr999'], label='Ahr999囤币指标', color='green', linewidth=2)
    # 绘制阈值线：抄底线（红色水平虚线）和定投线（灰色水平虚线）
    l4 = ax2.axhline(ratio_bottom, color='red', linestyle=':', linewidth=2, label='抄底线 (0.6)')
    l5 = ax2.axhline(ratio_dingtou, color='gray', linestyle=':', linewidth=2, label='定投线 (1.0)')

    # 设置图表标题和坐标轴标签，并应用中文字体
    ax1.set_title("BTC价格 & 定投指标（Ahr999）", fontsize=18, fontproperties=chinese_font)
    ax1.set_xlabel("日期", fontsize=14, fontproperties=chinese_font)
    ax1.set_ylabel("价格 (USD)", fontsize=14, fontproperties=chinese_font)
    ax2.set_ylabel("Ahr999指标", fontsize=14, fontproperties=chinese_font)

    # 设置坐标轴刻度字体
    for label in ax1.get_xticklabels() + ax1.get_yticklabels() + ax2.get_yticklabels():
        label.set_fontproperties(chinese_font)

    # 合并图例，并设置图例样式（如阴影与边框）
    lines = [l1, l2, l3, l4, l5]
    labels = [line.get_label() for line in lines]
    legend = ax1.legend(lines, labels, loc='upper left', fontsize=12, prop=chinese_font, frameon=True, shadow=True)
    legend.get_frame().set_alpha(0.9)

    # 附加细节：可以对关键点添加标注（例如最新数据值）
    latest_date = btc.index[-1]
    latest_price = btc['Price'].iloc[-1]
    latest_ma200 = btc['MA200'].iloc[-1]
    latest_ahr999 = btc['Ahr999'].iloc[-1]
    annotation_text = (f"最新日期: {latest_date.date()}\n"
                       f"价格: {latest_price:.2f} USD\n"
                       f"MA200: {latest_ma200:.2f} USD\n"
                       f"Ahr999: {latest_ahr999:.2f}")
    ax1.annotate(annotation_text, xy=(latest_date, latest_price),
                 xytext=(latest_date, latest_price*1.1),
                 textcoords="data",
                 arrowprops=dict(arrowstyle="->", color="black"),
                 fontsize=12, fontproperties=chinese_font,
                 bbox=dict(boxstyle="round,pad=0.5", fc="yellow", ec="gray", alpha=0.5))

    # 调整网格、背景及整体布局
    ax1.grid(True, linestyle='--', alpha=0.6)
    fig.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
