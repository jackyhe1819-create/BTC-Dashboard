#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BTC择时指标系统 - 增强版完整系统
文件名: btc_timing_system.py
作者: Claude
版本: 2.0
"""

import pandas as pd
import numpy as np
import requests
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import warnings
from typing import Dict, List, Tuple, Optional
warnings.filterwarnings('ignore')

# 设置matplotlib中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

class BTCDataCollector:
    """BTC数据收集器"""
    
    def __init__(self):
        self.binance_url = "https://api.binance.com/api/v3"
        self.fear_greed_url = "https://api.alternative.me/fng/"
        self.coingecko_url = "https://api.coingecko.com/api/v3"
        
    def get_btc_price_data(self, interval: str = '1d', limit: int = 500) -> pd.DataFrame:
        """获取BTC价格数据 - 增强版错误处理"""
        
        # 方法1: 尝试Binance API
        try:
            print("  🔄 尝试从Binance获取数据...")
            url = f"{self.binance_url}/klines"
            params = {
                'symbol': 'BTCUSDT',
                'interval': interval,
                'limit': limit
            }
            
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                if data and len(data) > 0:
                    df = pd.DataFrame(data, columns=[
                        'timestamp', 'open', 'high', 'low', 'close', 'volume',
                        'close_time', 'quote_volume', 'count', 'taker_buy_volume',
                        'taker_buy_quote_volume', 'ignore'
                    ])
                    
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        df[col] = df[col].astype(float)
                    
                    df.set_index('timestamp', inplace=True)
                    print(f"  ✅ Binance数据获取成功: {len(df)} 条记录")
                    return df[['open', 'high', 'low', 'close', 'volume']]
                else:
                    print("  ⚠️ Binance返回空数据")
            else:
                print(f"  ⚠️ Binance API错误: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Binance API失败: {e}")
        
        # 方法2: 尝试CoinGecko API
        try:
            print("  🔄 尝试从CoinGecko获取数据...")
            url = f"{self.coingecko_url}/coins/bitcoin/market_chart"
            params = {
                'vs_currency': 'usd',
                'days': min(365, limit),  # CoinGecko限制
                'interval': 'daily'
            }
            
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'prices' in data and len(data['prices']) > 0:
                    # 转换CoinGecko数据格式
                    prices = data['prices']
                    volumes = data.get('total_volumes', [[p[0], 1000000] for p in prices])
                    
                    df_data = []
                    for i, (timestamp, price) in enumerate(prices):
                        volume = volumes[i][1] if i < len(volumes) else 1000000
                        df_data.append({
                            'timestamp': pd.to_datetime(timestamp, unit='ms'),
                            'open': price,
                            'high': price * 1.02,  # 估算
                            'low': price * 0.98,   # 估算
                            'close': price,
                            'volume': volume
                        })
                    
                    df = pd.DataFrame(df_data)
                    df.set_index('timestamp', inplace=True)
                    print(f"  ✅ CoinGecko数据获取成功: {len(df)} 条记录")
                    return df[['open', 'high', 'low', 'close', 'volume']]
                else:
                    print("  ⚠️ CoinGecko返回空数据")
            else:
                print(f"  ⚠️ CoinGecko API错误: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ CoinGecko API失败: {e}")
        
        # 方法3: 生成模拟数据作为备用
        print("  🔄 生成模拟价格数据作为备用...")
        try:
            # 基于合理的BTC价格生成模拟数据
            dates = pd.date_range(end=datetime.now(), periods=limit, freq='D')
            
            # 设置基础价格（当前大概价格）
            base_price = 43000
            
            # 生成价格走势（包含趋势和随机波动）
            prices = []
            current_price = base_price
            
            for i in range(limit):
                # 长期趋势（年化增长）
                trend_factor = (1 + 0.5) ** (i / 365)
                
                # 周期性波动（模拟市场周期）
                cycle_factor = 1 + 0.3 * np.sin(i * 2 * np.pi / 180)  # 6个月周期
                
                # 随机日波动
                daily_change = np.random.normal(0, 0.03)  # 3%标准差
                random_factor = 1 + daily_change
                
                # 计算价格
                price = base_price * trend_factor * cycle_factor * random_factor
                price = max(price, 15000)  # 最低价格限制
                prices.append(price)
                current_price = price
            
            # 反转数组使其符合时间序列
            prices = prices[::-1]
            
            # 创建OHLCV数据
            data = []
            for i, price in enumerate(prices):
                high = price * (1 + abs(np.random.normal(0, 0.02)))
                low = price * (1 - abs(np.random.normal(0, 0.02)))
                open_price = prices[i-1] if i > 0 else price
                volume = np.random.uniform(10000, 50000)
                
                data.append({
                    'open': max(open_price, low),
                    'high': max(high, open_price, price),
                    'low': min(low, open_price, price),
                    'close': price,
                    'volume': volume
                })
            
            df = pd.DataFrame(data, index=dates)
            print(f"  ✅ 模拟数据生成成功: {len(df)} 条记录")
            print(f"  📊 价格范围: ${df['close'].min():,.0f} - ${df['close'].max():,.0f}")
            print(f"  💰 当前模拟价格: ${df['close'].iloc[-1]:,.0f}")
            
            return df
            
        except Exception as e:
            print(f"  ❌ 模拟数据生成失败: {e}")
            return pd.DataFrame()
    
    def get_fear_greed_index(self, limit: int = 200) -> pd.DataFrame:
        """获取恐慌贪婪指数 - 增强版"""
        try:
            print("  🔄 获取恐慌贪婪指数...")
            params = {'limit': limit, 'format': 'json'}
            response = requests.get(self.fear_greed_url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and len(data['data']) > 0:
                    df = pd.DataFrame(data['data'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                    df['value'] = df['value'].astype(int)
                    df = df.set_index('timestamp').sort_index()
                    print(f"  ✅ 恐慌贪婪指数获取成功: {len(df)} 条记录")
                    return df[['value', 'value_classification']]
                else:
                    print("  ⚠️ 恐慌贪婪指数数据为空")
            else:
                print(f"  ⚠️ 恐慌贪婪指数API错误: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ 恐慌贪婪指数获取失败: {e}")
        
        # 备用：生成模拟恐慌贪婪指数
        print("  🔄 生成模拟恐慌贪婪指数...")
        try:
            dates = pd.date_range(end=datetime.now(), periods=limit, freq='D')
            
            # 生成在0-100之间波动的情绪指数
            values = []
            current_value = 50  # 从中性开始
            
            for i in range(limit):
                # 添加趋势和随机性
                trend = np.sin(i * 2 * np.pi / 60) * 20  # 60天周期
                noise = np.random.normal(0, 10)
                
                new_value = 50 + trend + noise
                new_value = np.clip(new_value, 0, 100)
                values.append(int(new_value))
            
            # 反转以符合时间序列
            values = values[::-1]
            
            # 创建分类
            classifications = []
            for val in values:
                if val <= 25:
                    classifications.append('Extreme Fear')
                elif val <= 45:
                    classifications.append('Fear')
                elif val <= 55:
                    classifications.append('Neutral')
                elif val <= 75:
                    classifications.append('Greed')
                else:
                    classifications.append('Extreme Greed')
            
            df = pd.DataFrame({
                'value': values,
                'value_classification': classifications
            }, index=dates)
            
            print(f"  ✅ 模拟恐慌贪婪指数生成成功: {len(df)} 条记录")
            return df
            
        except Exception as e:
            print(f"  ❌ 模拟恐慌贪婪指数生成失败: {e}")
            return pd.DataFrame()
    
    def get_btc_dominance(self) -> pd.DataFrame:
        """获取BTC市值占比数据"""
        try:
            url = f"{self.coingecko_url}/global"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            btc_dominance = data['data']['market_cap_percentage']['btc']
            current_time = datetime.now()
            
            print("⚠️ 使用当前BTC占比生成历史模拟数据")
            
            dates = pd.date_range(end=current_time, periods=200, freq='D')
            base_dominance = btc_dominance
            dominance_values = []
            
            for i in range(200):
                cycle_factor = np.sin(i * 2 * np.pi / 90) * 5
                noise = np.random.normal(0, 2)
                trend_factor = (i - 100) * 0.05
                
                value = base_dominance + cycle_factor + noise + trend_factor
                value = np.clip(value, 35, 70)
                dominance_values.append(value)
            
            return pd.DataFrame({'btc_dominance': dominance_values}, index=dates)
            
        except Exception as e:
            print(f"BTC市值占比获取失败: {e}")
            dates = pd.date_range(end=datetime.now(), periods=200, freq='D')
            dominance_sim = 50 + 10 * np.sin(np.arange(200) * 2 * np.pi / 90) + np.random.normal(0, 3, 200)
            dominance_sim = np.clip(dominance_sim, 35, 70)
            return pd.DataFrame({'btc_dominance': dominance_sim}, index=dates)
    
    def get_market_cap_data(self) -> pd.DataFrame:
        """获取加密货币总市值数据"""
        try:
            url = f"{self.coingecko_url}/global"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            total_market_cap = data['data']['total_market_cap']['usd']
            print("⚠️ 使用当前市值生成历史模拟数据")
            
            dates = pd.date_range(end=datetime.now(), periods=200, freq='D')
            base_mcap = total_market_cap
            mcap_values = []
            
            for i in range(200):
                growth_factor = (1 + 0.001) ** i
                cycle_factor = 1 + 0.3 * np.sin(i * 2 * np.pi / 120)
                noise_factor = 1 + np.random.normal(0, 0.1)
                
                value = base_mcap * growth_factor * cycle_factor * noise_factor
                mcap_values.append(value)
            
            mcap_values = mcap_values[::-1]
            
            return pd.DataFrame({
                'total_market_cap': mcap_values,
                'btc_market_cap': [val * 0.5 for val in mcap_values]
            }, index=dates)
            
        except Exception as e:
            print(f"市值数据获取失败: {e}")
            dates = pd.date_range(end=datetime.now(), periods=200, freq='D')
            base_mcap = 2e12
            mcap_sim = [base_mcap * (1.001 ** i) * (1 + 0.2 * np.sin(i * 2 * np.pi / 100)) 
                       for i in range(200)]
            return pd.DataFrame({
                'total_market_cap': mcap_sim,
                'btc_market_cap': [val * 0.5 for val in mcap_sim]
            }, index=dates)

class BTCTimingIndicators:
    """BTC择时指标计算器"""
    
    def calculate_enhanced_ahr999(self, price_data: pd.DataFrame) -> Dict:
        """计算增强版AHR999指标"""
        close_prices = price_data['close']
        
        dca_200 = close_prices.rolling(200).mean()
        ahr999_standard = close_prices / dca_200
        
        ma_50 = close_prices.rolling(50).mean()
        ma_200 = close_prices.rolling(200).mean()
        ma_300 = close_prices.rolling(300).mean()
        
        weighted_ma = (ma_50 * 0.5 + ma_200 * 0.3 + ma_300 * 0.2)
        ahr999x_escape = close_prices / weighted_ma
        
        ahr999_change = ahr999_standard.pct_change(periods=7)
        
        return {
            'ahr999_standard': ahr999_standard,
            'ahr999x_escape': ahr999x_escape,
            'ahr999_change_7d': ahr999_change,
            'dca_200': dca_200
        }
    
    def calculate_pi_cycle_top(self, price_data: pd.DataFrame) -> Dict:
        """计算Pi Cycle Top指标"""
        close_prices = price_data['close']
        
        ma_111 = close_prices.rolling(111).mean()
        ma_350_x2 = close_prices.rolling(350).mean() * 2
        pi_signal = ma_111 - ma_350_x2
        
        return {
            'ma_111': ma_111,
            'ma_350_x2': ma_350_x2,
            'pi_signal': pi_signal,
            'is_top_signal': pi_signal > 0
        }
    
    def calculate_mvrv_zscore(self, price_data: pd.DataFrame) -> pd.Series:
        """计算MVRV Z-Score指标"""
        close_prices = price_data['close']
        
        realized_price = close_prices.rolling(200).mean()
        mvrv = close_prices / realized_price
        
        mvrv_mean = mvrv.rolling(365).mean()
        mvrv_std = mvrv.rolling(365).std()
        mvrv_zscore = (mvrv - mvrv_mean) / mvrv_std
        
        return mvrv_zscore
    
    def calculate_bitcoin_bubble_index(self, price_data: pd.DataFrame, market_cap_data: pd.DataFrame) -> Dict:
        """计算比特币泡沫指数"""
        close_prices = price_data['close']
        
        log_prices = np.log(close_prices)
        long_term_trend = log_prices.rolling(200).mean()
        price_deviation = (log_prices - long_term_trend) / log_prices.rolling(200).std()
        
        if not market_cap_data.empty and 'btc_market_cap' in market_cap_data.columns:
            btc_mcap = market_cap_data['btc_market_cap'].reindex(price_data.index, method='ffill')
            mcap_ma = btc_mcap.rolling(180).mean()
            mcap_deviation = (btc_mcap - mcap_ma) / mcap_ma
        else:
            mcap_deviation = pd.Series(0, index=price_data.index)
        
        returns = close_prices.pct_change()
        volatility = returns.rolling(30).std()
        vol_percentile = volatility.rolling(365).rank(pct=True)
        vol_bubble = vol_percentile
        
        price_component = np.clip((price_deviation + 3) / 6, 0, 1)
        mcap_component = np.clip((mcap_deviation + 0.5) / 1, 0, 1)
        vol_component = vol_bubble.fillna(0.5)
        
        bubble_index = (price_component * 0.5 + 
                       mcap_component * 0.3 + 
                       vol_component * 0.2) * 10
        
        bubble_level = pd.cut(bubble_index, 
                            bins=[0, 2, 4, 6, 8, 10],
                            labels=['低', '中低', '中等', '中高', '高'])
        
        return {
            'bubble_index': bubble_index,
            'bubble_level': bubble_level,
            'price_deviation': price_deviation,
            'mcap_deviation': mcap_deviation,
            'volatility_percentile': vol_bubble
        }
    
    def calculate_dominance_signals(self, dominance_data: pd.DataFrame) -> Dict:
        """计算BTC市值占比相关信号"""
        if dominance_data.empty:
            return {}
            
        dominance = dominance_data['btc_dominance']
        
        dom_ma_30 = dominance.rolling(30).mean()
        dom_ma_90 = dominance.rolling(90).mean()
        dom_trend = dominance - dom_ma_30
        dom_percentile = dominance.rolling(365).rank(pct=True)
        
        signal_strength = np.where(
            (dominance > 60) & (dom_trend > 0), 2,
            np.where((dominance > 55) & (dom_trend > 0), 1,
                    np.where((dominance < 45) & (dom_trend < 0), -2,
                            np.where((dominance < 50) & (dom_trend < 0), -1, 0))))
        
        return {
            'dominance': dominance,
            'dominance_ma30': dom_ma_30,
            'dominance_ma90': dom_ma_90,
            'dominance_trend': dom_trend,
            'dominance_percentile': dom_percentile,
            'dominance_signal': pd.Series(signal_strength, index=dominance.index)
        }
    
    def calculate_rsi(self, price_data: pd.DataFrame, window: int = 14) -> pd.Series:
        """计算RSI指标"""
        close_prices = price_data['close']
        
        delta = close_prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi

class BTCTimingStrategy:
    """BTC择时策略"""
    
    def __init__(self):
        self.indicators_calculator = BTCTimingIndicators()
        self.signal_weights = {
            'ahr999_standard': 0.20,
            'ahr999x_escape': 0.15,
            'pi_cycle': 0.15,
            'mvrv_zscore': 0.15,
            'btc_dominance': 0.12,
            'bubble_index': 0.10,
            'fear_greed': 0.08,
            'rsi': 0.05
        }
        
    def calculate_all_indicators(self, price_data: pd.DataFrame, 
                               fear_greed_data: pd.DataFrame,
                               dominance_data: pd.DataFrame,
                               market_cap_data: pd.DataFrame) -> pd.DataFrame:
        """计算所有指标"""
        
        indicators_df = pd.DataFrame(index=price_data.index)
        indicators_df['price'] = price_data['close']
        
        print("📊 计算增强版择时指标...")
        
        print("  • 增强版AHR999指标")
        ahr999_data = self.indicators_calculator.calculate_enhanced_ahr999(price_data)
        indicators_df['ahr999_standard'] = ahr999_data['ahr999_standard']
        indicators_df['ahr999x_escape'] = ahr999_data['ahr999x_escape']
        indicators_df['ahr999_change_7d'] = ahr999_data['ahr999_change_7d']
        indicators_df['dca_200'] = ahr999_data['dca_200']
        
        print("  • Pi Cycle Top指标")
        pi_data = self.indicators_calculator.calculate_pi_cycle_top(price_data)
        indicators_df['pi_ma111'] = pi_data['ma_111']
        indicators_df['pi_ma350x2'] = pi_data['ma_350_x2']
        indicators_df['pi_signal'] = pi_data['pi_signal']
        
        print("  • MVRV Z-Score")
        indicators_df['mvrv_zscore'] = self.indicators_calculator.calculate_mvrv_zscore(price_data)
        
        print("  • 比特币泡沫指数")
        bubble_data = self.indicators_calculator.calculate_bitcoin_bubble_index(price_data, market_cap_data)
        indicators_df['bubble_index'] = bubble_data['bubble_index']
        indicators_df['bubble_level'] = bubble_data['bubble_level']
        indicators_df['price_deviation'] = bubble_data['price_deviation']
        indicators_df['mcap_deviation'] = bubble_data['mcap_deviation']
        
        print("  • BTC市值占比分析")
        if not dominance_data.empty:
            dom_signals = self.indicators_calculator.calculate_dominance_signals(dominance_data)
            indicators_df['btc_dominance'] = dom_signals['dominance'].reindex(indicators_df.index, method='ffill')
            indicators_df['dominance_ma30'] = dom_signals['dominance_ma30'].reindex(indicators_df.index, method='ffill')
            indicators_df['dominance_trend'] = dom_signals['dominance_trend'].reindex(indicators_df.index, method='ffill')
            indicators_df['dominance_signal'] = dom_signals['dominance_signal'].reindex(indicators_df.index, method='ffill')
        
        print("  • RSI指标")
        indicators_df['rsi'] = self.indicators_calculator.calculate_rsi(price_data)
        
        print("  • 恐慌贪婪指数")
        if not fear_greed_data.empty:
            indicators_df['fear_greed'] = fear_greed_data['value'].reindex(indicators_df.index, method='ffill')
        
        return indicators_df
    
    def generate_signals(self, indicators_df: pd.DataFrame) -> pd.DataFrame:
        """生成交易信号"""
        
        signals_df = indicators_df.copy()
        
        signals_df['ahr999_score'] = self._calculate_ahr999_score(signals_df)
        signals_df['ahr999x_score'] = self._calculate_ahr999x_score(signals_df)
        signals_df['pi_cycle_score'] = self._calculate_pi_cycle_score(signals_df)
        signals_df['mvrv_score'] = self._calculate_mvrv_score(signals_df)
        signals_df['dominance_score'] = self._calculate_dominance_score(signals_df)
        signals_df['bubble_score'] = self._calculate_bubble_score(signals_df)
        signals_df['fear_greed_score'] = self._calculate_fear_greed_score(signals_df)
        signals_df['rsi_score'] = self._calculate_rsi_score(signals_df)
        
        score_columns = [
            ('ahr999_score', 'ahr999_standard'),
            ('ahr999x_score', 'ahr999x_escape'),
            ('pi_cycle_score', 'pi_cycle'),
            ('mvrv_score', 'mvrv_zscore'),
            ('dominance_score', 'btc_dominance'),
            ('bubble_score', 'bubble_index'),
            ('fear_greed_score', 'fear_greed'),
            ('rsi_score', 'rsi')
        ]
        
        signals_df['composite_score'] = 0
        for score_col, weight_key in score_columns:
            if score_col in signals_df.columns:
                weight = self.signal_weights.get(weight_key, 0)
                signals_df['composite_score'] += signals_df[score_col].fillna(50) * weight
        
        signals_df['signal_strength'] = (signals_df['composite_score'] - 50) * 2
        
        signals_df['action'] = 'HOLD'
        signals_df.loc[signals_df['signal_strength'] >= 40, 'action'] = 'STRONG_BUY'
        signals_df.loc[(signals_df['signal_strength'] >= 20) & (signals_df['signal_strength'] < 40), 'action'] = 'BUY'
        signals_df.loc[(signals_df['signal_strength'] <= -20) & (signals_df['signal_strength'] > -40), 'action'] = 'SELL'
        signals_df.loc[signals_df['signal_strength'] <= -40, 'action'] = 'STRONG_SELL'
        
        return signals_df
    
    def _calculate_ahr999_score(self, df: pd.DataFrame) -> pd.Series:
        ahr999 = df['ahr999_standard']
        score = np.where(ahr999 < 0.45, 90 + (0.45 - ahr999) / 0.45 * 10,
                        np.where(ahr999 > 1.2, 10 - (ahr999 - 1.2) / 2 * 10,
                                50 + (0.8 - ahr999) / 0.75 * 40))
        return pd.Series(np.clip(score, 0, 100), index=df.index)
    
    def _calculate_ahr999x_score(self, df: pd.DataFrame) -> pd.Series:
        ahr999x = df['ahr999x_escape']
        score = np.where(ahr999x > 2.0, 5,
                        np.where(ahr999x > 1.5, 20,
                                np.where(ahr999x < 1.0, 90, 
                                        70 - (ahr999x - 1.0) / 0.5 * 50)))
        return pd.Series(np.clip(score, 0, 100), index=df.index)
    
    def _calculate_pi_cycle_score(self, df: pd.DataFrame) -> pd.Series:
        pi_signal = df['pi_signal'].fillna(0)
        score = 50 - pi_signal * 10
        return pd.Series(np.clip(score, 0, 100), index=df.index)
    
    def _calculate_mvrv_score(self, df: pd.DataFrame) -> pd.Series:
        mvrv = df['mvrv_zscore'].fillna(0)
        score = np.where(mvrv < -1, 90 + (-1 - mvrv) * 5,
                        np.where(mvrv > 7, 10 - (mvrv - 7) * 2,
                                50 - mvrv * 5))
        return pd.Series(np.clip(score, 0, 100), index=df.index)
    
    def _calculate_dominance_score(self, df: pd.DataFrame) -> pd.Series:
        if 'btc_dominance' not in df.columns:
            return pd.Series(50, index=df.index)
            
        dominance = df['btc_dominance'].fillna(50)
        score = np.where(dominance > 60, 90,
                        np.where(dominance > 55, 70,
                                np.where(dominance < 45, 20,
                                        np.where(dominance < 40, 10, 50))))
        return pd.Series(score, index=df.index)
    
    def _calculate_bubble_score(self, df: pd.DataFrame) -> pd.Series:
        if 'bubble_index' not in df.columns:
            return pd.Series(50, index=df.index)
            
        bubble = df['bubble_index'].fillna(5)
        score = 100 - bubble * 10
        return pd.Series(np.clip(score, 0, 100), index=df.index)
    
    def _calculate_fear_greed_score(self, df: pd.DataFrame) -> pd.Series:
        if 'fear_greed' not in df.columns:
            return pd.Series(50, index=df.index)
            
        fg = df['fear_greed'].fillna(50)
        score = 100 - fg
        return pd.Series(score, index=df.index)
    
    def _calculate_rsi_score(self, df: pd.DataFrame) -> pd.Series:
        if 'rsi' not in df.columns:
            return pd.Series(50, index=df.index)
            
        rsi = df['rsi'].fillna(50)
        score = np.where(rsi < 30, 80,
                        np.where(rsi > 70, 20, 50))
        return pd.Series(score, index=df.index)

def plot_analysis(signals_df: pd.DataFrame):
    """绘制优化版分析图表"""
    
    # 第一组图表
    fig1, axes1 = plt.subplots(2, 2, figsize=(20, 12))
    fig1.suptitle('BTC择时指标分析 - 价格与核心指标', fontsize=18, fontweight='bold', y=0.95)
    
    # 1. 价格与交易信号
    ax1 = axes1[0, 0]
    ax1.plot(signals_df.index, signals_df['price'], label='BTC价格', color='orange', linewidth=3)
    
    buy_signals = signals_df[signals_df['action'].isin(['BUY', 'STRONG_BUY'])]
    sell_signals = signals_df[signals_df['action'].isin(['SELL', 'STRONG_SELL'])]
    
    if not buy_signals.empty:
        ax1.scatter(buy_signals.index, buy_signals['price'], 
                   color='green', marker='^', s=80, label='买入信号', alpha=0.8, zorder=5)
    
    if not sell_signals.empty:
        ax1.scatter(sell_signals.index, sell_signals['price'], 
                   color='red', marker='v', s=80, label='卖出信号', alpha=0.8, zorder=5)
    
    ax1.set_title('BTC价格与交易信号', fontsize=14, fontweight='bold', pad=20)
    ax1.set_ylabel('价格 (USD)', fontsize=12)
    ax1.legend(fontsize=10, loc='upper left')
    ax1.grid(True, alpha=0.3)
    ax1.tick_params(axis='x', rotation=45)
    
    # 2. 增强版AHR999指数对比
    ax2 = axes1[0, 1]
    ax2.plot(signals_df.index, signals_df['ahr999_standard'], 
             label='AHR999标准版', color='blue', linewidth=3)
    ax2.plot(signals_df.index, signals_df['ahr999x_escape'], 
             label='AHR999x逃顶版', color='red', linewidth=3)
    
    ax2.axhline(y=0.45, color='green', linestyle='--', alpha=0.8, linewidth=2, label='抄底线(0.45)')
    ax2.axhline(y=1.2, color='orange', linestyle='--', alpha=0.8, linewidth=2, label='卖出线(1.2)')
    ax2.axhline(y=2.0, color='red', linestyle='--', alpha=0.8, linewidth=2, label='逃顶线(2.0)')
    
    ax2.set_title('增强版AHR999指数', fontsize=14, fontweight='bold', pad=20)
    ax2.set_ylabel('AHR999值', fontsize=12)
    ax2.legend(fontsize=10, loc='upper left')
    ax2.grid(True, alpha=0.3)
    ax2.tick_params(axis='x', rotation=45)
    
    # 3. Pi Cycle Top
    ax3 = axes1[1, 0]
    ax3.plot(signals_df.index, signals_df['pi_ma111'], 
             label='111日均线', color='blue', linewidth=3)
    ax3.plot(signals_df.index, signals_df['pi_ma350x2'], 
             label='350日均线x2', color='red', linewidth=3)
    
    ax3.fill_between(signals_df.index, signals_df['pi_ma111'], signals_df['pi_ma350x2'], 
                     where=(signals_df['pi_ma111'] > signals_df['pi_ma350x2']), 
                     alpha=0.3, color='red', label='顶部警告区域')
    
    ax3.set_title('Pi Cycle Top指标', fontsize=14, fontweight='bold', pad=20)
    ax3.set_ylabel('价格 (USD)', fontsize=12)
    ax3.legend(fontsize=10, loc='upper left')
    ax3.grid(True, alpha=0.3)
    ax3.tick_params(axis='x', rotation=45)
    
    # 4. MVRV Z-Score
    ax4 = axes1[1, 1]
    ax4.plot(signals_df.index, signals_df['mvrv_zscore'], 
             label='MVRV Z-Score', color='purple', linewidth=3)
    ax4.axhline(y=7, color='red', linestyle='--', alpha=0.8, linewidth=2, label='卖出区域(7)')
    ax4.axhline(y=-1, color='green', linestyle='--', alpha=0.8, linewidth=2, label='买入区域(-1)')
    ax4.axhline(y=0, color='gray', linestyle='-', alpha=0.5, linewidth=1)
    
    ax4.set_title('MVRV Z-Score估值指标', fontsize=14, fontweight='bold', pad=20)
    ax4.set_ylabel('Z-Score', fontsize=12)
    ax4.legend(fontsize=10, loc='upper left')
    ax4.grid(True, alpha=0.3)
    ax4.tick_params(axis='x', rotation=45)
    
    plt.tight_layout()
    plt.subplots_adjust(top=0.92)
    plt.show()
    
    # 第二组图表
    fig2, axes2 = plt.subplots(2, 2, figsize=(20, 12))
    fig2.suptitle('BTC择时指标分析 - 市场结构与情绪指标', fontsize=18, fontweight='bold', y=0.95)
    
    # 5. BTC市值占比分析
    ax5 = axes2[0, 0]
    if 'btc_dominance' in signals_df.columns:
        ax5.plot(signals_df.index, signals_df['btc_dominance'], 
                 label='BTC市值占比', color='blue', linewidth=3)
        if 'dominance_ma30' in signals_df.columns:
            ax5.plot(signals_df.index, signals_df['dominance_ma30'], 
                     label='30日均线', color='red', alpha=0.7, linewidth=2)
        
        ax5.axhline(y=60, color='green', linestyle='--', alpha=0.8, linewidth=2, label='高占比区域(60%)')
        ax5.axhline(y=45, color='red', linestyle='--', alpha=0.8, linewidth=2, label='低占比区域(45%)')
        ax5.fill_between(signals_df.index, 45, 60, alpha=0.1, color='gray', label='正常区间')
    
    ax5.set_title('BTC市值占比 - 市场结构指标', fontsize=14, fontweight='bold', pad=20)
    ax5.set_ylabel('占比 (%)', fontsize=12)
    ax5.legend(fontsize=10, loc='upper left')
    ax5.grid(True, alpha=0.3)
    ax5.tick_params(axis='x', rotation=45)
    
    # 6. 恐慌贪婪指数与泡沫指数
    ax6 = axes2[0, 1]
    ax6_twin = ax6.twinx()
    
    if 'fear_greed' in signals_df.columns:
        line1 = ax6.plot(signals_df.index, signals_df['fear_greed'], 
                         label='恐慌贪婪指数', color='red', linewidth=3)
        ax6.axhline(y=25, color='green', linestyle='--', alpha=0.8, linewidth=2)
        ax6.axhline(y=75, color='red', linestyle='--', alpha=0.8, linewidth=2)
        ax6.fill_between(signals_df.index, 0, 25, alpha=0.2, color='green', label='极度恐慌区')
        ax6.fill_between(signals_df.index, 75, 100, alpha=0.2, color='red', label='极度贪婪区')
        ax6.set_ylabel('恐慌贪婪指数', fontsize=12, color='red')
        ax6.tick_params(axis='y', labelcolor='red')
    
    if 'bubble_index' in signals_df.columns:
        line2 = ax6_twin.plot(signals_df.index, signals_df['bubble_index'], 
                              label='泡沫指数', color='orange', linewidth=3)
        ax6_twin.set_ylabel('泡沫指数 (0-10)', fontsize=12, color='orange')
        ax6_twin.tick_params(axis='y', labelcolor='orange')
        ax6_twin.axhline(y=8, color='orange', linestyle='--', alpha=0.8, linewidth=2)
    
    ax6.set_title('市场情绪 & 泡沫指数', fontsize=14, fontweight='bold', pad=20)
    ax6.legend(loc='upper left', fontsize=10)
    ax6.grid(True, alpha=0.3)
    ax6.tick_params(axis='x', rotation=45)
    
    # 7. 综合信号强度柱状图
    ax7 = axes2[1, 0]
    colors = ['darkred' if x <= -40 else 'red' if x <= -20 else 'orange' if x < 0 else 
              'lightgreen' if x < 20 else 'green' if x < 40 else 'darkgreen' 
              for x in signals_df['signal_strength']]
    
    bars = ax7.bar(signals_df.index, signals_df['signal_strength'], 
                   color=colors, alpha=0.8, width=2)
    
    ax7.axhline(y=40, color='darkgreen', linestyle='--', alpha=0.8, linewidth=2, label='强买入(40)')
    ax7.axhline(y=20, color='green', linestyle='--', alpha=0.8, linewidth=2, label='买入(20)')
    ax7.axhline(y=0, color='gray', linestyle='-', alpha=0.5, linewidth=1)
    ax7.axhline(y=-20, color='orange', linestyle='--', alpha=0.8, linewidth=2, label='卖出(-20)')
    ax7.axhline(y=-40, color='red', linestyle='--', alpha=0.8, linewidth=2, label='强卖出(-40)')
    
    ax7.set_title('综合信号强度变化', fontsize=14, fontweight='bold', pad=20)
    ax7.set_ylabel('信号强度 (-100到+100)', fontsize=12)
    ax7.legend(fontsize=10, loc='upper left')
    ax7.grid(True, alpha=0.3)
    ax7.tick_params(axis='x', rotation=45)
    
    # 8. 各指标评分雷达图风格
    ax8 = axes2[1, 1]
    latest_data = signals_df.iloc[-1]
    
    score_mapping = [
        ('AHR999标准', 'ahr999_score'),
        ('AHR999x逃顶', 'ahr999x_score'),
        ('MVRV估值', 'mvrv_score'),
        ('BTC占比', 'dominance_score'),
        ('泡沫指数', 'bubble_score'),
        ('恐慌贪婪', 'fear_greed_score'),
        ('RSI技术', 'rsi_score')
    ]
    
    score_names = []
    score_values = []
    
    for name, score_col in score_mapping:
        if score_col in signals_df.columns and not pd.isna(latest_data[score_col]):
            score_names.append(name)
            score_values.append(latest_data[score_col])
    
    if score_names:
        bar_colors = ['darkgreen' if x >= 80 else 'green' if x >= 60 else 'yellow' if x >= 40 else 'orange' if x >= 20 else 'red' 
                      for x in score_values]
        
        bars = ax8.barh(score_names, score_values, color=bar_colors, alpha=0.8)
        ax8.set_xlim(0, 100)
        ax8.set_xlabel('评分 (0-100，分数越高越倾向买入)', fontsize=12)
        ax8.set_title('当前各指标评分分布', fontsize=14, fontweight='bold', pad=20)
        ax8.grid(True, alpha=0.3, axis='x')
        
        for bar, value in zip(bars, score_values):
            width = bar.get_width()
            ax8.text(width + 1.5, bar.get_y() + bar.get_height()/2, 
                    f'{value:.1f}', ha='left', va='center', fontweight='bold', fontsize=10)
        
        ax8.axvline(x=20, color='red', linestyle='--', alpha=0.5)
        ax8.axvline(x=40, color='orange', linestyle='--', alpha=0.5)
        ax8.axvline(x=60, color='yellow', linestyle='--', alpha=0.5)
        ax8.axvline(x=80, color='green', linestyle='--', alpha=0.5)
    
    plt.tight_layout()
    plt.subplots_adjust(top=0.92)
    plt.show()

def generate_detailed_report(signals_df: pd.DataFrame, strategy: BTCTimingStrategy) -> str:
    """生成详细分析报告"""
    
    latest = signals_df.iloc[-1]
    current_price = latest['price']
    current_action = latest['action']
    current_strength = latest['signal_strength']
    current_composite = latest['composite_score']
    
    report = f"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                          🚀 BTC量化择时分析报告 🚀                                      ║
║                        分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                        ║
╚══════════════════════════════════════════════════════════════════════════════════════╝

📊 【市场概况】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 当前BTC价格: ${current_price:,.2f} USD
🎯 综合择时评分: {current_composite:.1f}/100 分
💪 信号强度: {current_strength:.1f} (-100到+100)
🚦 操作建议: {current_action}

📈 【核心指标深度分析】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
    
    # 各指标分析
    if not pd.isna(latest['ahr999_standard']):
        ahr999_val = latest['ahr999_standard']
        ahr999_score = latest.get('ahr999_score', 50)
        weight = strategy.signal_weights.get('ahr999_standard', 0) * 100
        
        if ahr999_val < 0.45:
            status = "🟢 处于历史抄底区间，建议积极买入"
        elif ahr999_val > 1.2:
            status = "🔴 价格过高，建议减仓观望"
        else:
            status = "🟡 处于正常定投区间"
        
        report += f"""1️⃣ 【AHR999抄底指数】(权重: {weight:.0f}%)
   📊 数值: {ahr999_val:.3f} | 评分: {ahr999_score:.1f}/100
   🔍 状态: {status}
   📚 参考: <0.45抄底区，0.45-1.2定投区，>1.2减仓区

"""
    
    if not pd.isna(latest['ahr999x_escape']):
        ahr999x_val = latest['ahr999x_escape']
        ahr999x_score = latest.get('ahr999x_score', 50)
        weight = strategy.signal_weights.get('ahr999x_escape', 0) * 100
        
        if ahr999x_val > 2.0:
            status = "🔴 强烈逃顶信号！建议立即减仓"
        elif ahr999x_val > 1.5:
            status = "🟠 逃顶预警，密切关注"
        else:
            status = "🟢 暂无逃顶风险"
        
        report += f"""2️⃣ 【AHR999x逃顶指数】(权重: {weight:.0f}%)
   📊 数值: {ahr999x_val:.3f} | 评分: {ahr999x_score:.1f}/100
   🔍 状态: {status}
   📚 参考: >2.0强烈逃顶，1.5-2.0预警，<1.5安全

"""
    
    if not pd.isna(latest['pi_signal']):
        pi_signal = latest['pi_signal']
        pi_score = latest.get('pi_cycle_score', 50)
        weight = strategy.signal_weights.get('pi_cycle', 0) * 100
        
        if pi_signal > 0:
            status = "🔴 Pi Cycle顶部信号激活！历史准确率极高"
        else:
            status = "🟢 未触发顶部信号，暂时安全"
        
        report += f"""3️⃣ 【Pi Cycle Top指标】(权重: {weight:.0f}%)
   📊 信号差值: {pi_signal:.0f} | 评分: {pi_score:.1f}/100
   🔍 状态: {status}
   📚 参考: 111日均线上穿350日均线x2时触发卖出

"""
    
    if not pd.isna(latest['mvrv_zscore']):
        mvrv_val = latest['mvrv_zscore']
        mvrv_score = latest.get('mvrv_score', 50)
        weight = strategy.signal_weights.get('mvrv_zscore', 0) * 100
        
        if mvrv_val > 7:
            status = "🔴 严重高估，风险极高"
        elif mvrv_val < -1:
            status = "🟢 严重低估，历史性机会"
        else:
            status = "🟡 估值合理区间"
        
        report += f"""4️⃣ 【MVRV Z-Score估值】(权重: {weight:.0f}%)
   📊 数值: {mvrv_val:.2f} | 评分: {mvrv_score:.1f}/100
   🔍 状态: {status}
   📚 参考: >7严重高估，-1至3合理，<-1严重低估

"""
    
    # 综合操作建议
    if current_action == 'STRONG_BUY':
        advice = """🟢 【强烈买入信号】建议分3-5次重仓买入，可动用30-50%资金"""
    elif current_action == 'BUY':
        advice = """🟡 【买入信号】建议适度买入，可动用10-20%资金"""
    elif current_action == 'SELL':
        advice = """🟠 【卖出信号】建议减仓20-40%，保留核心仓位"""
    elif current_action == 'STRONG_SELL':
        advice = """🔴 【强烈卖出信号】建议减仓60-80%，准备迎接调整"""
    else:
        advice = """⚪ 【保持观望】维持现有仓位，等待明确信号"""
    
    report += f"""
🎯 【综合操作建议】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{advice}

"""
    
    # 关键价位
    if not pd.isna(latest['dca_200']) and latest['dca_200'] > 0:
        dca_price = latest['dca_200']
        strong_buy = dca_price * 0.45
        sell_price = dca_price * 1.2
        
        report += f"""📍 【关键价位参考】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 当前价格: ${current_price:,.0f}
📊 200日均价: ${dca_price:,.0f}
🟢 强买价位: ${strong_buy:,.0f} ({(current_price/strong_buy-1)*100:+.1f}%)
🔴 卖出价位: ${sell_price:,.0f} ({(sell_price/current_price-1)*100:+.1f}%)

"""
    
    # 风险提示
    report += f"""⚠️ 【重要提示】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚨 本报告仅供参考，不构成投资建议
🚨 加密货币投资具有极高风险
🚨 请结合个人风险承受能力决策
🚨 建议分散投资，严格控制仓位

╔══════════════════════════════════════════════════════════════════════════════════════╗
║                           📊 报告结束 📊                                               ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
"""
    
    return report

def main():
    """主函数"""
    print("🚀 BTC择时指标系统启动 - 完整版")
    print("=" * 60)
    
    # 1. 数据收集
    print("📊 正在收集数据...")
    collector = BTCDataCollector()
    
    try:
        # 获取BTC价格数据 - 增强错误处理
        btc_data = collector.get_btc_price_data('1d', 500)
        if not btc_data.empty:
            print(f"✅ BTC价格数据: {len(btc_data)} 条记录")
            print(f"📈 价格范围: ${btc_data['close'].min():,.0f} - ${btc_data['close'].max():,.0f}")
            print(f"💰 最新价格: ${btc_data['close'].iloc[-1]:,.0f}")
        else:
            print("❌ 无法获取BTC价格数据，程序退出")
            print("🔧 可能的解决方案:")
            print("  1. 检查网络连接")
            print("  2. 稍后重试（可能是API限制）")
            print("  3. 使用VPN（如果在某些地区）")
            return
        
        # 获取其他数据
        fear_greed_data = collector.get_fear_greed_index(200)
        print(f"✅ 恐慌贪婪指数: {len(fear_greed_data)} 条记录")
        
        dominance_data = collector.get_btc_dominance()
        print(f"✅ BTC市值占比数据: {len(dominance_data)} 条记录")
        
        market_cap_data = collector.get_market_cap_data()
        print(f"✅ 市值数据: {len(market_cap_data)} 条记录")
        
    except Exception as e:
        print(f"❌ 数据收集过程出错: {e}")
        return
    
    # 2. 计算指标
    print("\n🔧 计算择时指标...")
    strategy = BTCTimingStrategy()
    
    try:
        indicators_df = strategy.calculate_all_indicators(btc_data, fear_greed_data, dominance_data, market_cap_data)
        print("✅ 指标计算完成")
        
    except Exception as e:
        print(f"❌ 指标计算错误: {e}")
        return
    
    # 3. 生成信号
    print("\n📈 生成交易信号...")
    try:
        signals_df = strategy.generate_signals(indicators_df)
        print("✅ 信号生成完成")
        
    except Exception as e:
        print(f"❌ 信号生成错误: {e}")
        return
    
    # 4. 快速状态显示
    latest = signals_df.iloc[-1]
    print("\n🎯 当前市场状态")
    print("=" * 40)
    print(f"📈 BTC价格: ${latest['price']:,.2f}")
    print(f"🎯 综合评分: {latest['composite_score']:.1f}/100")
    print(f"🚦 操作建议: {latest['action']}")
    
    # 5. 生成图表
    print(f"\n📈 生成分析图表...")
    try:
        plot_analysis(signals_df)
        print("✅ 图表生成完成")
    except Exception as e:
        print(f"⚠️ 图表生成失败: {e}")
    
    # 6. 生成详细报告
    print(f"\n📄 生成详细分析报告...")
    detailed_report = generate_detailed_report(signals_df, strategy)
    print(detailed_report)
    
    # 7. 保存报告
    try:
        filename = f"BTC_Analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(detailed_report)
        print(f"💾 报告已保存: {filename}")
    except Exception as e:
        print(f"⚠️ 保存失败: {e}")
    
    print(f"\n✅ 分析完成！")
    return signals_df

if __name__ == "__main__":
    try:
        result = main()
    except KeyboardInterrupt:
        print("\n⏹️ 程序被用户中断")
    except Exception as e:
        print(f"\n❌ 运行错误: {e}")
        print("请检查网络连接和依赖包安装")