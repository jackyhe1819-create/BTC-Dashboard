import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm

# 下载比特币历史数据，auto_adjust默认为True
btc = yf.download("BTC-USD", start="2013-01-01", auto_adjust=True)

# 如果返回结果包含多重列索引，则扁平化（仅取第一层标签）
if isinstance(btc.columns, pd.MultiIndex):
    btc.columns = btc.columns.get_level_values(0)

# 仅保留收盘价，并确保其为Series
btc = btc[['Close']].squeeze().dropna()

# 计算200日移动平均线（此时Close为Series，rolling结果也是Series）
ma200 = btc.rolling(window=200).mean()

# 定义多个N值
n_values = [0.85, 0.90, 0.95, 1.0]
colors = ['red', 'orange', 'green', 'blue']

# 初始化图形
plt.figure(figsize=(14, 6))

# 动态分配颜色
cmap = cm.get_cmap('tab10', len(n_values))  # 使用 colormap 动态生成颜色

# 逐个计算并绘图
for i, n in enumerate(n_values):
    # 计算 Ahr999X 指数
    ahr_series = btc / (ma200 * n)
    plt.plot(
        ahr_series.index, 
        ahr_series, 
        label=f'N = {n}', 
        color=cmap(i),  # 动态分配颜色
        linewidth=1.5
    )

# 绘制参考线 Ahr999X = 1
plt.axhline(y=1, color='black', linestyle='--', label='参考线（Ahr999X = 1）')

# 设置标题、标签、图例和网格
plt.title("比特币 Ahr999X 指数（逃顶指标）", fontsize=14)
plt.xlabel("日期", fontsize=12)
plt.ylabel("Ahr999X 值", fontsize=12)
plt.legend(fontsize=10)
plt.grid(True, linestyle='--', alpha=0.6)
plt.tight_layout()

# 显示图形
plt.show()

