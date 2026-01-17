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
from btc_dashboard import run_dashboard, get_indicator_history, fetch_btc_data

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
                "url": ind.url
            }
        
        return jsonify({
            "success": True,
            "timestamp": result.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            "btc_price": float(result.btc_price),
            "total_score": float(result.total_score),
            "recommendation": result.recommendation,
            "indicators": indicators_json
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


if __name__ == '__main__':
    print("🚀 启动 BTC Dashboard Web 服务器...")
    print("📊 访问 http://localhost:5050 查看仪表盘")
    #使用 use_reloader=False 避免在后台运行时产生双进程问题
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5050)

