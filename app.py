#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BTC Dashboard Web Server
========================
Flask 后端服务，提供 API 接口返回 BTC 指标数据
"""

import sys
import os

# 添加父目录到路径以导入 btc_dashboard
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, jsonify, request
from datetime import datetime
import numpy as np

# 导入 dashboard 运行函数和历史数据函数
from btc_dashboard import (
    run_dashboard, get_indicator_history, fetch_btc_data,
    get_sparklines,
    fetch_crypto_news, fetch_whale_activity, fetch_macro_calendar,
    fetch_crypto_calendar, fetch_whale_volume_stats, fetch_exchange_balance_display
)

app = Flask(__name__)

# 缓存 BTC 数据（避免每次请求都重新获取）
_btc_data_cache = None
_btc_data_timestamp = None


def get_cached_btc_data():
    """获取缓存的 BTC 数据"""
    global _btc_data_cache, _btc_data_timestamp
    
    # 缓存 5 分钟
    if _btc_data_cache is None or _btc_data_timestamp is None or \
       (datetime.now() - _btc_data_timestamp).seconds > 300:
        _btc_data_cache = fetch_btc_data()
        _btc_data_timestamp = datetime.now()
    
    return _btc_data_cache


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/dashboard')
def api_dashboard():
    """API 端点：返回仪表盘数据"""
    try:
        result = run_dashboard()
        
        indicators_json = {}
        for name, ind in result.indicators.items():
            indicators_json[name] = {
                "name": ind.name,
                "value": None if np.isnan(ind.value) else float(ind.value),
                "score": ind.score,
                "color": ind.color,
                "status": ind.status,
                "priority": ind.priority,
                "url": ind.url,
                "description": ind.description,
                "method": ind.method
            }
        
        # Get cached df for sparklines (reuses existing cache, zero extra API calls)
        df = get_cached_btc_data()
        sparklines = get_sparklines(df, result.indicators, days=7)

        return jsonify({
            "success": True,
            "timestamp": result.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            "btc_price": float(result.btc_price),
            "total_score": float(result.total_score),
            "recommendation": result.recommendation,
            "indicators": indicators_json,
            "sparklines": sparklines
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/history/<indicator_name>')
def api_history(indicator_name: str):
    """API 端点：返回指标历史数据"""
    try:
        days = request.args.get('days', 30, type=int)
        days = min(max(days, 7), 90)  # 限制 7-90 天
        
        # 获取缓存的 BTC 数据
        df = get_cached_btc_data()
        
        # 获取历史数据
        history = get_indicator_history(indicator_name, df, days)
        
        return jsonify({
            "success": True,
            **history
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/news')
def api_news():
    """API 端点：返回资讯信息"""
    try:
        news = fetch_crypto_news(limit=20)
        whales = fetch_whale_activity(min_btc=10, limit=50)
        whale_stats = fetch_whale_volume_stats()
        exchange_balance = fetch_exchange_balance_display()
        calendar = fetch_macro_calendar()
        crypto_calendar = fetch_crypto_calendar()
        
        return jsonify({
            "success": True,
            "news": news,
            "whales": whales,
            "whale_stats": whale_stats,
            "exchange_balance": exchange_balance,
            "calendar": calendar,
            "crypto_calendar": crypto_calendar
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5050))
    debug = os.environ.get('FLASK_ENV') != 'production'
    print(f"🚀 启动 BTC Dashboard Web 服务器 (port={port})...")
    print(f"📊 访问 http://localhost:{port} 查看仪表盘")
    app.run(debug=debug, use_reloader=False, host='0.0.0.0', port=port)


