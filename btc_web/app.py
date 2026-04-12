#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BTC Dashboard Web Server
========================
Flask 后端服务，提供 API 接口返回 BTC 指标数据
"""

import sys
import os
import threading

# 添加当前目录到路径以导入 btc_dashboard（btc_dashboard.py 与 app.py 同级）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, jsonify, request
from datetime import datetime
import numpy as np

# 导入 dashboard 运行函数和历史数据函数
from btc_dashboard import (
    run_dashboard, get_indicator_history, fetch_btc_data,
    get_sparklines,
    fetch_crypto_news, fetch_whale_activity, fetch_macro_calendar,
    fetch_crypto_calendar, fetch_whale_volume_stats, fetch_exchange_balance_display,
    fetch_builders_feed
)

app = Flask(__name__)

# ── BTC 价格/指标缓存（5 分钟）──────────────────────────────────────
_btc_data_cache = None
_btc_data_timestamp = None

# ── 仪表盘缓存（stale-while-revalidate，5 分钟 TTL）─────────────────
_dashboard_cache = None
_dashboard_cache_timestamp = None
_dashboard_refreshing = False
_DASHBOARD_TTL = 300              # 5 分钟

# ── 资讯缓存（stale-while-revalidate，15 分钟 TTL）──────────────────
_news_cache = None
_news_cache_timestamp = None
_news_refreshing = False          # 防止并发重复刷新
_NEWS_TTL = 900                   # 15 分钟

# ── 开发者动态缓存（stale-while-revalidate，30 分钟 TTL）────────────
_builders_cache = None
_builders_cache_timestamp = None
_builders_refreshing = False
_BUILDERS_TTL = 1800              # 30 分钟


def _do_refresh_dashboard():
    """在后台线程中刷新仪表盘缓存。"""
    global _dashboard_cache, _dashboard_cache_timestamp, _dashboard_refreshing
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

        df = get_cached_btc_data()
        sparklines = get_sparklines(df, result.indicators, days=7)

        _dashboard_cache = {
            "timestamp": result.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            "btc_price": float(result.btc_price),
            "total_score": float(result.total_score),
            "recommendation": result.recommendation,
            "indicators": indicators_json,
            "sparklines": sparklines
        }
        _dashboard_cache_timestamp = datetime.now()
        print(f"✅ 仪表盘缓存刷新完成 {_dashboard_cache_timestamp.strftime('%H:%M:%S')}")
    except Exception as e:
        global _last_error
        import traceback
        traceback.print_exc()
        _last_error = f"{type(e).__name__}: {e}"
        print(f"⚠️ 仪表盘缓存刷新失败: {e}")
    finally:
        _dashboard_refreshing = False


def trigger_dashboard_refresh():
    """触发后台刷新仪表盘（若未在刷新中）。"""
    global _dashboard_refreshing
    if not _dashboard_refreshing:
        _dashboard_refreshing = True
        t = threading.Thread(target=_do_refresh_dashboard, daemon=True)
        t.start()


def _do_refresh_news():
    """在后台线程中刷新资讯缓存。"""
    global _news_cache, _news_cache_timestamp, _news_refreshing
    from concurrent.futures import ThreadPoolExecutor, as_completed
    try:
        tasks = {
            "news":             lambda: fetch_crypto_news(limit=100),
            "whales":           lambda: fetch_whale_activity(min_btc=10, limit=50),
            "whale_stats":      lambda: fetch_whale_volume_stats(),
            "exchange_balance": lambda: fetch_exchange_balance_display(),
            "calendar":         lambda: fetch_macro_calendar(),
            "crypto_calendar":  lambda: fetch_crypto_calendar(),
        }
        results = {}
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(fn): key for key, fn in tasks.items()}
            for future in as_completed(futures):
                key = futures[future]
                try:
                    results[key] = future.result(timeout=30)
                except Exception as e:
                    print(f"⚠️ {key} 获取失败: {e}")
                    results[key] = [] if key in ("news", "whales", "calendar", "crypto_calendar") else {}
        _news_cache = results
        _news_cache_timestamp = datetime.now()
        print(f"✅ 资讯缓存刷新完成 {_news_cache_timestamp.strftime('%H:%M:%S')}")
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        _news_refreshing = False


def trigger_news_refresh():
    """触发后台刷新（若未在刷新中）。"""
    global _news_refreshing
    if not _news_refreshing:
        _news_refreshing = True
        t = threading.Thread(target=_do_refresh_news, daemon=True)
        t.start()


def _do_refresh_builders():
    """在后台线程中刷新开发者动态缓存。"""
    global _builders_cache, _builders_cache_timestamp, _builders_refreshing
    try:
        data = fetch_builders_feed(limit=30)
        _builders_cache = data
        _builders_cache_timestamp = datetime.now()
        print(f"✅ 开发者动态缓存刷新完成 {_builders_cache_timestamp.strftime('%H:%M:%S')}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"⚠️ 开发者动态缓存刷新失败: {e}")
    finally:
        _builders_refreshing = False


def trigger_builders_refresh():
    """触发后台刷新开发者动态（若未在刷新中）。"""
    global _builders_refreshing
    if not _builders_refreshing:
        _builders_refreshing = True
        t = threading.Thread(target=_do_refresh_builders, daemon=True)
        t.start()


def get_cached_btc_data():
    """获取缓存的 BTC 数据"""
    global _btc_data_cache, _btc_data_timestamp

    # 缓存 5 分钟
    if _btc_data_cache is None or _btc_data_timestamp is None or \
       (datetime.now() - _btc_data_timestamp).seconds > 300:
        _btc_data_cache = fetch_btc_data()
        _btc_data_timestamp = datetime.now()

    return _btc_data_cache


# ── 启动时预热缓存（延迟 5s，避免启动瞬间内存峰值）──────────────────
def _delayed_warmup():
    import time as _t
    _t.sleep(5)
    trigger_dashboard_refresh()
    trigger_news_refresh()
    _t.sleep(15)
    trigger_builders_refresh()

threading.Thread(target=_delayed_warmup, daemon=True).start()


_last_error = None  # 记录最近一次后台错误

@app.route('/api/version')
def api_version():
    """部署版本检查"""
    import sys
    return jsonify({
        "version": "2026-04-12-v2",
        "server_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'),
        "python": sys.version,
        "dashboard_ready": _dashboard_cache is not None,
        "news_ready": _news_cache is not None,
        "refreshing": _dashboard_refreshing,
        "last_error": _last_error
    })


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/dashboard')
def api_dashboard():
    """
    API 端点：返回仪表盘数据
    策略：非阻塞 stale-while-revalidate
      - 有缓存 → 立即返回，若已过期则同时触发后台刷新
      - 无缓存 → 立即返回 computing=True，前端轮询直到就绪
        （避免 Render 等平台 30s 请求超时导致 504）
    """
    global _dashboard_cache, _dashboard_cache_timestamp

    now = datetime.now()
    cache_age = (now - _dashboard_cache_timestamp).seconds if _dashboard_cache_timestamp else None
    has_cache = _dashboard_cache is not None

    if has_cache:
        if cache_age is not None and cache_age >= _DASHBOARD_TTL:
            trigger_dashboard_refresh()
        return jsonify({
            "success": True,
            "cached": True,
            "cache_age_s": cache_age,
            **_dashboard_cache
        })

    # 无缓存（冷启动）：立即返回 computing 状态，前端负责轮询
    trigger_dashboard_refresh()
    return jsonify({
        "success": False,
        "computing": True,
        "error": "指标计算中，请稍候…"
    }), 202


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
    """
    API 端点：返回资讯信息
    策略：stale-while-revalidate
      - 有缓存 → 立即返回，若已过期则同时触发后台刷新
      - 无缓存 → 同步等待首次刷新完成（仅冷启动时）
    """
    global _news_cache, _news_cache_timestamp

    now = datetime.now()
    cache_age = (now - _news_cache_timestamp).seconds if _news_cache_timestamp else None
    has_cache = _news_cache is not None

    if has_cache:
        # 缓存过期 → 后台异步刷新，本次仍返回旧数据
        if cache_age is not None and cache_age >= _NEWS_TTL:
            trigger_news_refresh()
        return jsonify({
            "success": True,
            "cached": True,
            "cache_age_s": cache_age,
            **_news_cache
        })

    # 无缓存（冷启动场景）：等待后台刷新完成
    # 先触发（若未在刷新中），然后轮询最多 35 秒
    trigger_news_refresh()
    import time
    for _ in range(70):
        time.sleep(0.5)
        if _news_cache is not None:
            return jsonify({
                "success": True,
                "cached": False,
                "cache_age_s": 0,
                **_news_cache
            })
    return jsonify({"success": False, "error": "资讯加载超时，请稍后刷新"}), 504


@app.route('/api/builders')
def api_builders():
    """
    API 端点：返回 Bitcoin 开发者社区动态
    策略：stale-while-revalidate
      - 有缓存 → 立即返回，若已过期则同时触发后台刷新
      - 无缓存 → 同步等待首次刷新完成（仅冷启动时）
    """
    global _builders_cache, _builders_cache_timestamp

    now = datetime.now()
    cache_age = (now - _builders_cache_timestamp).seconds if _builders_cache_timestamp else None
    has_cache = _builders_cache is not None

    if has_cache:
        if cache_age is not None and cache_age >= _BUILDERS_TTL:
            trigger_builders_refresh()
        return jsonify({
            "success": True,
            "cached": True,
            "cache_age_s": cache_age,
            **_builders_cache
        })

    # 无缓存（冷启动）：触发刷新并轮询最多 60 秒
    trigger_builders_refresh()
    import time
    for _ in range(120):
        time.sleep(0.5)
        if _builders_cache is not None:
            return jsonify({
                "success": True,
                "cached": False,
                "cache_age_s": 0,
                **_builders_cache
            })
    return jsonify({"success": False, "error": "开发者动态加载超时，请稍后刷新"}), 504


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5050))
    debug = os.environ.get('FLASK_ENV') != 'production'
    print(f"🚀 启动 BTC Dashboard Web 服务器 (port={port})...")
    print(f"📊 访问 http://localhost:{port} 查看仪表盘")
    app.run(debug=debug, use_reloader=False, host='0.0.0.0', port=port)
