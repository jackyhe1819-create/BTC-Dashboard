# BTC-Dashboard（用户原版）

本目录是**用户的原版** BTC 指标仪表盘 —— 单一综合评分体系（runner.py 的 WEIGHTS 加权）。

- 本地端口：**5050**（`python3 btc_web/app.py`）
- GitHub：https://github.com/jackyhe1819-create/BTC-Dashboard
- Render 服务名：`btc-dashboard`

## 与实验分叉版的关系

Claude 重构的双评分实验版 **BTC Compass** 在 `../btc_compass`：
- 仓库 https://github.com/jackyhe1819-create/btc-compass，本地端口 **5070**
- 两个版本**刻意保留评分体系差异**做 A/B 对比

## 修改归属规则

- 在本目录会话中的修改 = 改**用户的原版**
- 要改 Compass → 去 `../btc_compass` 操作（或明确说明后用绝对路径）
- **评分公式/权重/指标体系的改动不要在两个版本间互相同步**（A/B 对比的前提）
- 数据底盘类修复（数据源失效、缓存 bug 等）经用户同意后可双向移植
