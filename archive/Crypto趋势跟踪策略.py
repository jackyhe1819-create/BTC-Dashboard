import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import warnings
import json
import os
from typing import Dict, List, Optional, Tuple
warnings.filterwarnings('ignore')

class EnhancedCryptoTrendStrategy:
    def __init__(self, symbol='BTCUSDT', initial_capital=10000):
        """
        增强版加密货币趋势跟踪策略
        
        Parameters:
        symbol: 交易对（默认BTC/USDT）
        initial_capital: 初始资金
        """
        self.symbol = symbol
        self.initial_capital = initial_capital
        self.data = None
        self.signals = None
        self.results = None
        self.strategy_params = {
            'ma_short': 20,
            'ma_long': 50,
            'rsi_period': 14,
            'rsi_overbought': 70,
            'rsi_oversold': 30,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'bb_period': 20,
            'bb_std': 2,
            'atr_period': 14
        }
        
    def fetch_data(self, days=365, use_demo_data=False):
        """获取历史数据 - 支持真实API和模拟数据"""
        if use_demo_data:
            return self.generate_demo_data(days)
        
        try:
            # 计算时间戳
            end_time = int(datetime.now().timestamp() * 1000)
            start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
            
            # Binance API URL
            url = f"https://api.binance.com/api/v3/klines"
            params = {
                'symbol': self.symbol,
                'interval': '1d',
                'startTime': start_time,
                'endTime': end_time,
                'limit': 1000
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            klines = response.json()
            
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            df.set_index('timestamp', inplace=True)
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            self.data = df
            print(f"✅ 成功获取 {len(df)} 天的 {self.symbol} 真实数据")
            return df
            
        except Exception as e:
            print(f"⚠️ 获取真实数据失败: {e}")
            print("🔄 自动切换到模拟数据模式...")
            return self.generate_demo_data(days)
    
    def generate_demo_data(self, days=365):
        """生成模拟的加密货币价格数据"""
        try:
            np.random.seed(42)
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            date_range = pd.date_range(start=start_date, end=end_date, freq='D')
            
            # 根据不同币种设置不同的初始价格
            price_map = {
                'BTCUSDT': 45000,
                'ETHUSDT': 2500,
                'ADAUSDT': 0.5,
                'BNBUSDT': 300,
                'XRPUSDT': 0.6,
                'SOLUSDT': 100,
                'DOGEUSDT': 0.08
            }
            initial_price = price_map.get(self.symbol, 45000)
            
            n_steps = len(date_range)
            dt = 1/365
            mu = 0.15    # 提高年化收益率
            sigma = 0.8  # 增加波动率
            
            # 添加趋势和周期性
            trend = np.linspace(0, 0.5, n_steps)  # 上升趋势
            cycle = 0.1 * np.sin(2 * np.pi * np.arange(n_steps) / 90)  # 90天周期
            
            random_returns = np.random.normal(
                (mu - 0.5 * sigma**2) * dt, 
                sigma * np.sqrt(dt), 
                n_steps
            )
            
            # 添加趋势和周期性影响
            random_returns += trend * dt + cycle * dt
            
            price_path = [initial_price]
            for i in range(1, n_steps):
                price_path.append(price_path[-1] * np.exp(random_returns[i]))
            
            closes = np.array(price_path)
            daily_ranges = np.random.uniform(0.02, 0.12, n_steps)
            highs = closes * (1 + daily_ranges)
            lows = closes * (1 - daily_ranges)
            
            opens = np.zeros_like(closes)
            opens[0] = closes[0]
            for i in range(1, n_steps):
                gap = np.random.uniform(-0.03, 0.03)
                opens[i] = closes[i-1] * (1 + gap)
            
            for i in range(n_steps):
                daily_high = max(opens[i], closes[i], highs[i])
                daily_low = min(opens[i], closes[i], lows[i])
                highs[i] = daily_high
                lows[i] = daily_low
            
            # 成交量与价格变化相关
            price_changes = np.abs(np.diff(closes, prepend=closes[0]))
            volumes = np.random.uniform(500000, 2000000, n_steps) * (1 + price_changes / closes)
            
            df = pd.DataFrame({
                'open': opens,
                'high': highs,
                'low': lows,
                'close': closes,
                'volume': volumes
            }, index=date_range)
            
            self.data = df
            print(f"✅ 成功生成 {len(df)} 天的模拟 {self.symbol} 数据")
            print(f"📊 价格范围: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
            
            return df
            
        except Exception as e:
            print(f"❌ 生成模拟数据失败: {e}")
            return None
    
    def calculate_indicators(self):
        """计算技术指标"""
        if self.data is None:
            print("请先获取数据")
            return
        
        df = self.data.copy()
        
        # 移动平均线
        df['MA_20'] = df['close'].rolling(window=self.strategy_params['ma_short']).mean()
        df['MA_50'] = df['close'].rolling(window=self.strategy_params['ma_long']).mean()
        df['MA_200'] = df['close'].rolling(window=200).mean()
        
        # 指数移动平均线
        df['EMA_12'] = df['close'].ewm(span=self.strategy_params['macd_fast']).mean()
        df['EMA_26'] = df['close'].ewm(span=self.strategy_params['macd_slow']).mean()
        
        # MACD
        df['MACD'] = df['EMA_12'] - df['EMA_26']
        df['MACD_signal'] = df['MACD'].ewm(span=self.strategy_params['macd_signal']).mean()
        df['MACD_histogram'] = df['MACD'] - df['MACD_signal']
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.strategy_params['rsi_period']).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.strategy_params['rsi_period']).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # 布林带
        df['BB_middle'] = df['close'].rolling(window=self.strategy_params['bb_period']).mean()
        bb_std = df['close'].rolling(window=self.strategy_params['bb_period']).std()
        df['BB_upper'] = df['BB_middle'] + (bb_std * self.strategy_params['bb_std'])
        df['BB_lower'] = df['BB_middle'] - (bb_std * self.strategy_params['bb_std'])
        
        # ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['ATR'] = true_range.rolling(self.strategy_params['atr_period']).mean()
        
        # 新增指标
        # 成交量移动平均
        df['Volume_MA'] = df['volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['volume'] / df['Volume_MA']
        
        # 价格动量
        df['Momentum'] = df['close'] / df['close'].shift(10) - 1
        
        # 威廉指标
        df['Williams_R'] = (df['high'].rolling(14).max() - df['close']) / (df['high'].rolling(14).max() - df['low'].rolling(14).min()) * -100
        
        # 随机指标
        lowest_low = df['low'].rolling(window=14).min()
        highest_high = df['high'].rolling(window=14).max()
        df['K_percent'] = 100 * (df['close'] - lowest_low) / (highest_high - lowest_low)
        df['D_percent'] = df['K_percent'].rolling(window=3).mean()
        
        self.data = df
        print("✅ 技术指标计算完成")
    
    def generate_signals(self, strategy_type='enhanced'):
        """
        生成交易信号
        
        Parameters:
        strategy_type: 策略类型 ('simple', 'enhanced', 'aggressive')
        """
        if self.data is None:
            print("请先计算技术指标")
            return
        
        df = self.data.copy()
        df['signal'] = 0
        df['position'] = 0
        df['signal_strength'] = 0  # 信号强度
        
        if strategy_type == 'simple':
            self._simple_signals(df)
        elif strategy_type == 'enhanced':
            self._enhanced_signals(df)
        elif strategy_type == 'aggressive':
            self._aggressive_signals(df)
        
        # 计算持仓
        df['position'] = df['signal'].replace(to_replace=0, method='ffill').fillna(0)
        
        self.signals = df
        signal_count = len(df[df['signal'] != 0])
        print(f"✅ 生成交易信号完成，共有 {signal_count} 个交易信号")
    
    def _simple_signals(self, df):
        """简单双均线策略"""
        for i in range(1, len(df)):
            if i < 50:
                continue
                
            # 金叉
            if (df['MA_20'].iloc[i] > df['MA_50'].iloc[i] and 
                df['MA_20'].iloc[i-1] <= df['MA_50'].iloc[i-1]):
                df.loc[df.index[i], 'signal'] = 1
                df.loc[df.index[i], 'signal_strength'] = 0.5
            
            # 死叉
            elif (df['MA_20'].iloc[i] < df['MA_50'].iloc[i] and 
                  df['MA_20'].iloc[i-1] >= df['MA_50'].iloc[i-1]):
                df.loc[df.index[i], 'signal'] = -1
                df.loc[df.index[i], 'signal_strength'] = 0.5
    
    def _enhanced_signals(self, df):
        """增强多指标策略"""
        for i in range(1, len(df)):
            if i < 50:
                continue
                
            # 多个条件评分
            bullish_score = 0
            bearish_score = 0
            
            # 均线条件
            if df['MA_20'].iloc[i] > df['MA_50'].iloc[i]:
                bullish_score += 1
            else:
                bearish_score += 1
            
            # MACD条件
            if df['MACD'].iloc[i] > df['MACD_signal'].iloc[i]:
                bullish_score += 1
            else:
                bearish_score += 1
            
            # RSI条件
            rsi = df['RSI'].iloc[i]
            if 30 < rsi < 70:
                if rsi > 50:
                    bullish_score += 0.5
                else:
                    bearish_score += 0.5
            
            # 布林带条件
            close_price = df['close'].iloc[i]
            if close_price > df['BB_middle'].iloc[i]:
                bullish_score += 0.5
            else:
                bearish_score += 0.5
            
            # 成交量条件
            if df['Volume_Ratio'].iloc[i] > 1.2:
                if bullish_score > bearish_score:
                    bullish_score += 0.5
                else:
                    bearish_score += 0.5
            
            # 动量条件
            if df['Momentum'].iloc[i] > 0.05:
                bullish_score += 0.5
            elif df['Momentum'].iloc[i] < -0.05:
                bearish_score += 0.5
            
            # 生成信号
            if bullish_score >= 3 and bullish_score > bearish_score:
                df.loc[df.index[i], 'signal'] = 1
                df.loc[df.index[i], 'signal_strength'] = min(bullish_score / 5, 1.0)
            elif bearish_score >= 3 and bearish_score > bullish_score:
                df.loc[df.index[i], 'signal'] = -1
                df.loc[df.index[i], 'signal_strength'] = min(bearish_score / 5, 1.0)
    
    def _aggressive_signals(self, df):
        """激进策略（更频繁交易）"""
        for i in range(1, len(df)):
            if i < 30:
                continue
                
            # 短期信号
            short_bullish = (df['MA_20'].iloc[i] > df['MA_20'].iloc[i-1] and
                           df['RSI'].iloc[i] > 50 and
                           df['MACD'].iloc[i] > df['MACD_signal'].iloc[i])
            
            short_bearish = (df['MA_20'].iloc[i] < df['MA_20'].iloc[i-1] and
                           df['RSI'].iloc[i] < 50 and
                           df['MACD'].iloc[i] < df['MACD_signal'].iloc[i])
            
            if short_bullish:
                df.loc[df.index[i], 'signal'] = 1
                df.loc[df.index[i], 'signal_strength'] = 0.7
            elif short_bearish:
                df.loc[df.index[i], 'signal'] = -1
                df.loc[df.index[i], 'signal_strength'] = 0.7
    
    def backtest(self, commission=0.001, stop_loss=0.05, take_profit=0.15, 
                 position_sizing='fixed', max_positions=1):
        """
        增强回测功能
        
        Parameters:
        commission: 手续费率
        stop_loss: 止损比例
        take_profit: 止盈比例
        position_sizing: 仓位管理方式 ('fixed', 'atr', 'signal_strength')
        max_positions: 最大同时持仓数
        """
        if self.signals is None:
            print("请先生成交易信号")
            return
        
        df = self.signals.copy()
        
        # 初始化回测变量
        df['returns'] = df['close'].pct_change()
        df['strategy_returns'] = 0.0
        df['portfolio_value'] = self.initial_capital
        df['cash'] = self.initial_capital
        df['holdings'] = 0.0
        df['position_size'] = 0.0
        df['trades'] = 0
        df['pnl'] = 0.0
        
        cash = self.initial_capital
        holdings = 0
        entry_price = 0
        current_position = 0
        position_size = 0
        
        trades_log = []
        
        for i in range(1, len(df)):
            current_price = df['close'].iloc[i]
            signal = df['signal'].iloc[i]
            signal_strength = df['signal_strength'].iloc[i]
            atr = df['ATR'].iloc[i] if 'ATR' in df.columns else current_price * 0.02
            
            # 计算仓位大小
            if position_sizing == 'fixed':
                target_position_size = 1.0
            elif position_sizing == 'atr':
                risk_per_trade = 0.02  # 每次交易风险2%
                target_position_size = min(cash * risk_per_trade / atr, 1.0)
            elif position_sizing == 'signal_strength':
                target_position_size = signal_strength
            else:
                target_position_size = 1.0
            
            # 检查止损止盈
            if current_position != 0:
                pnl_pct = (current_price - entry_price) / entry_price * current_position
                
                if (pnl_pct <= -stop_loss or pnl_pct >= take_profit):
                    # 平仓
                    pnl = (current_price - entry_price) * holdings * current_position
                    cash += holdings * current_price * (1 - commission)
                    
                    # 记录交易
                    trades_log.append({
                        'entry_date': entry_date,
                        'exit_date': df.index[i],
                        'entry_price': entry_price,
                        'exit_price': current_price,
                        'position': current_position,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'reason': 'stop_loss' if pnl_pct <= -stop_loss else 'take_profit'
                    })
                    
                    holdings = 0
                    current_position = 0
                    position_size = 0
                    df.loc[df.index[i], 'trades'] = 1
                    df.loc[df.index[i], 'pnl'] = pnl
            
            # 处理新信号
            if signal == 1 and current_position == 0:  # 做多
                position_size = target_position_size
                investment = cash * position_size
                holdings = investment / current_price * (1 - commission)
                cash -= investment
                entry_price = current_price
                entry_date = df.index[i]
                current_position = 1
                df.loc[df.index[i], 'trades'] = 1
                
            elif signal == -1 and current_position == 0:  # 做空
                position_size = target_position_size
                holdings = cash * position_size / current_price
                entry_price = current_price
                entry_date = df.index[i]
                current_position = -1
                df.loc[df.index[i], 'trades'] = 1
            
            # 更新投资组合价值
            if current_position > 0:
                portfolio_value = cash + holdings * current_price
            elif current_position < 0:
                portfolio_value = cash + holdings * (entry_price - current_price)
            else:
                portfolio_value = cash
            
            df.loc[df.index[i], 'cash'] = cash
            df.loc[df.index[i], 'holdings'] = holdings
            df.loc[df.index[i], 'position_size'] = position_size
            df.loc[df.index[i], 'portfolio_value'] = portfolio_value
        
        # 计算策略收益率
        df['strategy_returns'] = df['portfolio_value'].pct_change()
        
        self.results = df
        self.trades_log = trades_log
        print("✅ 回测完成")
    
    def analyze_performance(self):
        """分析策略表现"""
        if self.results is None:
            print("请先进行回测")
            return
        
        df = self.results
        
        # 基本指标
        total_return = (df['portfolio_value'].iloc[-1] / self.initial_capital - 1) * 100
        buy_hold_return = (df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100
        
        # 计算夏普比率
        strategy_std = df['strategy_returns'].std()
        if strategy_std > 0:
            strategy_sharpe = df['strategy_returns'].mean() / strategy_std * np.sqrt(365)
        else:
            strategy_sharpe = 0
        
        # 计算索提诺比率
        negative_returns = df['strategy_returns'][df['strategy_returns'] < 0]
        if len(negative_returns) > 0:
            downside_std = negative_returns.std()
            sortino_ratio = df['strategy_returns'].mean() / downside_std * np.sqrt(365)
        else:
            sortino_ratio = float('inf')
        
        # 计算最大回撤
        rolling_max = df['portfolio_value'].expanding().max()
        drawdown = (df['portfolio_value'] - rolling_max) / rolling_max
        max_drawdown = drawdown.min() * 100
        
        # 计算年化收益率
        days = len(df)
        years = days / 365
        annual_return = (df['portfolio_value'].iloc[-1] / self.initial_capital) ** (1/years) - 1
        annual_return_pct = annual_return * 100
        
        # 交易统计
        trades = df[df['trades'] == 1]
        total_trades = len(trades)
        
        # 胜率计算
        if hasattr(self, 'trades_log') and len(self.trades_log) > 0:
            winning_trades = len([t for t in self.trades_log if t['pnl'] > 0])
            win_rate = winning_trades / len(self.trades_log) * 100
            avg_win = np.mean([t['pnl'] for t in self.trades_log if t['pnl'] > 0]) if winning_trades > 0 else 0
            avg_loss = np.mean([t['pnl'] for t in self.trades_log if t['pnl'] < 0]) if len(self.trades_log) - winning_trades > 0 else 0
            profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
        else:
            win_rate = 0
            profit_factor = 0
        
        # 波动率
        annual_volatility = df['strategy_returns'].std() * np.sqrt(365) * 100
        
        # 输出结果
        print("\n" + "="*50)
        print("           📊 策略表现分析")
        print("="*50)
        print(f"💰 策略总收益率:     {total_return:.2f}%")
        print(f"📈 策略年化收益率:   {annual_return_pct:.2f}%")
        print(f"🏪 买入持有收益率:   {buy_hold_return:.2f}%")
        print(f"📊 年化波动率:       {annual_volatility:.2f}%")
        print(f"⚡ 夏普比率:         {strategy_sharpe:.2f}")
        print(f"🛡️ 索提诺比率:       {sortino_ratio:.2f}")
        print(f"📉 最大回撤:         {max_drawdown:.2f}%")
        print(f"🎯 交易次数:         {total_trades}")
        print(f"🏆 胜率:             {win_rate:.2f}%")
        print(f"💎 盈亏比:           {profit_factor:.2f}")
        print(f"📅 回测天数:         {days} 天")
        
        # 策略评估
        print("\n" + "="*50)
        print("           🎯 策略评估")
        print("="*50)
        
        score = 0
        if total_return > buy_hold_return:
            print("✅ 策略跑赢买入持有")
            score += 1
        else:
            print("❌ 策略跑输买入持有")
            
        if strategy_sharpe > 1.5:
            print("✅ 策略夏普比率优秀 (>1.5)")
            score += 1
        elif strategy_sharpe > 1:
            print("🟡 策略夏普比率良好 (1-1.5)")
            score += 0.5
        else:
            print("❌ 策略夏普比率较差 (<1)")
            
        if max_drawdown > -15:
            print("✅ 回撤控制良好 (<15%)")
            score += 1
        elif max_drawdown > -25:
            print("🟡 回撤控制一般 (15-25%)")
            score += 0.5
        else:
            print("❌ 回撤过大 (>25%)")
            
        if win_rate > 60:
            print("✅ 胜率优秀 (>60%)")
            score += 1
        elif win_rate > 50:
            print("🟡 胜率良好 (50-60%)")
            score += 0.5
        else:
            print("❌ 胜率较低 (<50%)")
        
        print(f"\n🌟 综合评分: {score}/4")
        
        if score >= 3:
            print("🎉 策略表现优秀！")
        elif score >= 2:
            print("👍 策略表现良好")
        else:
            print("💡 策略需要优化")
        
        return {
            'total_return': total_return,
            'annual_return': annual_return_pct,
            'buy_hold_return': buy_hold_return,
            'strategy_sharpe': strategy_sharpe,
            'sortino_ratio': sortino_ratio,
            'max_drawdown': max_drawdown,
            'annual_volatility': annual_volatility,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'days': days,
            'score': score
        }
    
    def plot_results(self, figsize=(16, 12)):
        """绘制回测结果"""
        if self.results is None:
            print("请先进行回测")
            return
        
        df = self.results
        plt.style.use('seaborn-v0_8')
        
        fig, axes = plt.subplots(2, 3, figsize=figsize)
        fig.suptitle(f'{self.symbol} 趋势跟踪策略回测结果', fontsize=16, fontweight='bold')
        
        # 1. 价格和信号
        ax1 = axes[0, 0]
        ax1.plot(df.index, df['close'], label='价格', alpha=0.7, color='black')
        ax1.plot(df.index, df['MA_20'], label='MA20', alpha=0.8, color='blue')
        ax1.plot(df.index, df['MA_50'], label='MA50', alpha=0.8, color='red')
        
        buy_signals = df[df['signal'] == 1]
        sell_signals = df[df['signal'] == -1]
        
        ax1.scatter(buy_signals.index, buy_signals['close'], 
                   color='green', marker='^', s=60, label='买入信号', zorder=5)
        ax1.scatter(sell_signals.index, sell_signals['close'], 
                   color='red', marker='v', s=60, label='卖出信号', zorder=5)
        
        ax1.set_title('价格走势与交易信号')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. 投资组合价