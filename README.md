# ₿ BTC 长期指标仪表盘

> 基于 P0/P1 核心指标的比特币市场实时监控系统，帮助投资者识别趋势、量化风险、捕捉周期拐点。

## ✨ 功能概览

### 📊 核心指标体系

| 分类 | 指标 | 说明 |
|------|------|------|
| **周期指标 (P0)** | Pi Cycle Top | 350MA 与 111MA×2 交叉检测牛市顶部 |
| | 减半周期 | 距上次/下次减半的时间位置分析 |
| | Ahr999 | 定投参考指标 (<0.45 抄底区 / >1.2 过热区) |
| | 幂律走廊 | 基于幂律模型的价格通道上下轨 |
| | 均衡价格 | 基于 CVDD 的公允价值评估 |
| **短期指标 (P1)** | MACD 多周期 | 4H/12H/日/周/月 五周期真实 MACD 信号汇总 |
| | 布林带 | 波动率分析 + 超买超卖判断 |
| | RSI | 相对强弱指标 |
| | 资金费率 | 永续合约资金费率情绪 |
| | 多空比 | 多交易所多空账户比例 (OKX) |
| | 恐惧贪婪指数 | Alternative.me 恐惧与贪婪指数 |
| **辅助指标 (P2)** | MVRV Z-Score | 链上估值偏离度 |
| | NUPL | 网络未实现盈亏占比 |
| | 全网算力 | 挖矿安全性与矿工信心 |

### 📰 资讯中心

- **BTC 资讯聚合** — CoinDesk / CoinTelegraph / Bitcoin Magazine / NewsBTC / 律动
- **宏观经济日历** — CPI / 非农 / 利率决议 (自动标注已公布/待公布状态)
- **巨鲸动态** — Blockchain.com 实时大额交易监控 (≥10 BTC)

### 📈 价格走势图

- TradingView K线图 (`INDEX:BTCUSD` 多交易所综合指数)
- 汇总 Binance、Coinbase、Bitstamp、Kraken 等主要交易所交易量加权价格

## 🏗️ 技术架构

```
btc_dashboard.py          # 核心指标计算引擎 (3000+ 行)
btc_web/
├── app.py                # Flask Web 服务器 (API 路由)
├── templates/
│   └── index.html        # 前端页面模板
└── static/
    ├── script.js         # 前端渲染逻辑
    └── style.css         # 暗色主题样式
```

### 数据源

| 数据 | 来源 | 说明 |
|------|------|------|
| BTC 历史价格 | Yahoo Finance | 日线数据 (2014年至今) |
| 实时价格 | CoinGecko / Coinbase | 多源备用 |
| 4H/12H K线 | OKX API | MACD 多周期真实数据 |
| 多空比 | OKX API | 无地域限制，Binance 备用 |
| 资金费率 | Binance API | 永续合约费率 |
| 恐惧贪婪指数 | Alternative.me | 市场情绪 |
| 链上数据 | Blockchain.com | MVRV / 大额交易 |
| 宏观日历 | faireconomy.media | 经济事件 |
| 新闻资讯 | 多源 RSS | 加密货币新闻 |
| K线图 | TradingView Widget | INDEX:BTCUSD 综合指数 |

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install flask requests pandas numpy yfinance
```

### 2. 启动服务

```bash
cd btc_web
python3 app.py
```

### 3. 访问面板

浏览器打开 **http://localhost:5050**

## 📐 评分系统

每个指标输出 **-1 ~ +1** 的评分:

| 评分范围 | 信号 | 含义 |
|---------|------|------|
| +0.8 ~ +1.0 | 🟢 强烈看多 | 历史性买入机会 |
| +0.3 ~ +0.8 | 🟢 偏多 | 适合逐步建仓 |
| -0.3 ~ +0.3 | 🟡 中立 | 观望或小仓位 |
| -0.8 ~ -0.3 | 🔴 偏空 | 注意风险控制 |
| -1.0 ~ -0.8 | 🔴 强烈看空 | 考虑减仓避险 |

加权汇总所有指标评分后生成 **综合建议**：定投买入 / 持有观望 / 注意风险 / 减仓避险。

## 🔄 V2.0 更新日志

- ✅ K线图升级为多交易所综合指数 (`INDEX:BTCUSD`)
- ✅ 多空比改用 OKX API (解决中国大陆 Binance 地域限制)
- ✅ MACD 4H/12H 使用 OKX 真实K线数据 (修复假模拟 bug)
- ✅ 宏观经济日历增加已公布/待公布状态标识
- ✅ 巨鲸动态支持 50 条大额交易滚动浏览
- ✅ UI 优化: 自适应布局 + 自定义滚动条

## ⚠️ 免责声明

本项目仅供学习和研究使用，不构成任何投资建议。加密货币市场风险极高，请独立判断、谨慎决策。

## 📄 License

MIT License
