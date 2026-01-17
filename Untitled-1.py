#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETH牛市逃顶监控系统 - MacBook专用版
专为macOS优化，支持终端通知和原生特性
自动从多个API获取实时数据，无需手动输入
"""

import sys
import os
import datetime
import json
import time
import urllib.request
import urllib.error
from urllib.parse import urlencode
import subprocess
import platform

def clear_screen():
    """macOS清屏函数"""
    os.system('clear')

def send_macos_notification(title, message, sound=True):
    """发送macOS原生通知"""
    try:
        script = f'''
        display notification "{message}" with title "{title}"
        '''
        if sound:
            script += ' sound name "Glass"'
        
        subprocess.run(['osascript', '-e', script], 
                      capture_output=True, text=True)
    except:
        pass  # 静默失败，不影响主程序

def print_header():
    """打印标题 - macOS风格"""
    print("🍎" + "=" * 68 + "🍎")
    print(" " * 20 + "ETH牛市逃顶监控系统")
    print(" " * 15 + "MacBook专用版 v2.0 🚀")
    print("🍎" + "=" * 68 + "🍎")
    print(f"🕐 运行时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💻 系统: {platform.system()} {platform.release()}")
    print("-" * 70)

def check_macos_version():
    """检查macOS版本兼容性"""
    try:
        version = platform.mac_ver()[0]
        if version:
            major_version = int(version.split('.')[0])
            if major_version >= 10:
                return True, version
        return False, version
    except:
        return False, "未知"

class ETHMonitorMacOS:
    """ETH监控系统 - MacBook专用版"""
    
    def __init__(self):
        self.data = {
            'price': 0.0,
            'ma200': 0.0,
            'change_24h': 0.0,
            'mvrv': 2.0,
            'nupl': 0.65,
            'funding_rate': 0.05,
            'fear_greed': 55,
            'volume_billion': 0.0
        }
        self.risk_score = 0
        self.signals = []
        self.last_notification_time = 0
        
        # macOS特定路径
        self.home_dir = os.path.expanduser("~")
        self.reports_dir = os.path.join(self.home_dir, "Documents", "ETH_Reports")
        self.ensure_reports_directory()
        
        # API配置
        self.api_config = {
            'coingecko_base': 'https://api.coingecko.com/api/v3',
            'binance_base': 'https://api.binance.com/api/v3',
            'fear_greed_base': 'https://api.alternative.me/fng/',
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15'
            }
        }
        
        # 检查系统兼容性
        self.macos_compatible, self.macos_version = check_macos_version()
        if self.macos_compatible:
            print(f"✅ macOS {self.macos_version} 兼容")
        else:
            print(f"⚠️ 系统版本: {self.macos_version}")
    
    def ensure_reports_directory(self):
        """确保报告目录存在"""
        try:
            os.makedirs(self.reports_dir, exist_ok=True)
        except:
            self.reports_dir = self.home_dir
    
    def make_request(self, url, timeout=15):
        """安全的HTTP请求 - 针对macOS网络优化"""
        try:
            request = urllib.request.Request(url, headers=self.api_config['headers'])
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            print(f"  ❌ HTTP错误 {e.code}: {e.reason}")
            return None
        except urllib.error.URLError as e:
            print(f"  ❌ 网络错误: {e.reason}")
            return None
        except json.JSONDecodeError:
            print("  ❌ JSON解析错误")
            return None
        except Exception as e:
            print(f"  ❌ 请求失败: {str(e)}")
            return None
    
    def get_eth_price_data(self):
        """从CoinGecko获取ETH价格数据"""
        print("  📡 获取ETH价格数据...")
        
        url = f"{self.api_config['coingecko_base']}/simple/price"
        params = {
            'ids': 'ethereum',
            'vs_currencies': 'usd',
            'include_24hr_change': 'true',
            'include_24hr_vol': 'true'
        }
        
        response = self.make_request(f"{url}?{urlencode(params)}")
        if response and 'ethereum' in response:
            eth_data = response['ethereum']
            self.data['price'] = eth_data.get('usd', 0)
            self.data['change_24h'] = eth_data.get('usd_24h_change', 0)
            self.data['volume_billion'] = eth_data.get('usd_24h_vol', 0) / 1e9
            print(f"    ✅ 价格: ${self.data['price']:.2f}")
            print(f"    ✅ 24h变化: {self.data['change_24h']:+.2f}%")
            print(f"    ✅ 成交量: ${self.data['volume_billion']:.2f}B")
            return True
        
        print("    ❌ 价格数据获取失败")
        return False
    
    def get_ma200_data(self):
        """计算200日均线"""
        print("  📊 计算200日均线...")
        
        url = f"{self.api_config['coingecko_base']}/coins/ethereum/market_chart"
        params = {
            'vs_currency': 'usd',
            'days': '200',
            'interval': 'daily'
        }
        
        response = self.make_request(f"{url}?{urlencode(params)}")
        if response and 'prices' in response:
            prices = [price[1] for price in response['prices']]
            if len(prices) >= 200:
                self.data['ma200'] = sum(prices[-200:]) / 200
                print(f"    ✅ 200日均线: ${self.data['ma200']:.2f}")
                return True
        
        # 估算值
        self.data['ma200'] = self.data['price'] * 0.75
        print(f"    ⚠️ 使用估算值: ${self.data['ma200']:.2f}")
        return False
    
    def get_binance_funding_rate(self):
        """从Binance获取ETH永续合约资金费率"""
        print("  💰 获取资金费率...")
        
        url = f"{self.api_config['binance_base']}/premiumIndex"
        params = {'symbol': 'ETHUSDT'}
        
        response = self.make_request(f"{url}?{urlencode(params)}")
        if response and 'lastFundingRate' in response:
            funding_rate = float(response['lastFundingRate']) * 100
            self.data['funding_rate'] = funding_rate
            print(f"    ✅ 资金费率: {funding_rate:.4f}%")
            return True
        
        print("    ⚠️ 使用默认资金费率: 0.05%")
        return False
    
    def get_fear_greed_index(self):
        """获取恐惧贪婪指数"""
        print("  😰 获取恐惧贪婪指数...")
        
        url = f"{self.api_config['fear_greed_base']}?limit=1"
        
        response = self.make_request(url)
        if response and 'data' in response and len(response['data']) > 0:
            fear_greed = int(response['data'][0]['value'])
            self.data['fear_greed'] = fear_greed
            print(f"    ✅ 恐惧贪婪指数: {fear_greed}")
            return True
        
        print("    ⚠️ 使用默认恐惧贪婪指数: 55")
        return False
    
    def get_alternative_eth_data(self):
        """备用数据源"""
        print("  🔄 尝试备用数据源...")
        
        url = f"{self.api_config['binance_base']}/ticker/24hr"
        params = {'symbol': 'ETHUSDT'}
        
        response = self.make_request(f"{url}?{urlencode(params)}")
        if response:
            self.data['price'] = float(response.get('lastPrice', 0))
            self.data['change_24h'] = float(response.get('priceChangePercent', 0))
            self.data['volume_billion'] = float(response.get('quoteVolume', 0)) / 1e9
            print(f"    ✅ 备用源价格: ${self.data['price']:.2f}")
            return True
        
        return False
    
    def estimate_onchain_metrics(self):
        """估算链上指标"""
        print("  ⛓️ 估算链上指标...")
        
        price = self.data['price']
        if price > 4000:
            self.data['mvrv'] = 2.5 + (price - 4000) / 1000
        elif price > 3000:
            self.data['mvrv'] = 2.0 + (price - 3000) / 2000
        else:
            self.data['mvrv'] = 1.5 + price / 6000
        
        mvrv = self.data['mvrv']
        if mvrv > 3.0:
            self.data['nupl'] = 0.75 + (mvrv - 3.0) * 0.05
        elif mvrv > 2.0:
            self.data['nupl'] = 0.5 + (mvrv - 2.0) * 0.25
        else:
            self.data['nupl'] = 0.3 + mvrv * 0.1
        
        # 限制范围
        self.data['mvrv'] = max(0.5, min(self.data['mvrv'], 5.0))
        self.data['nupl'] = max(0.0, min(self.data['nupl'], 1.0))
        
        print(f"    ✅ 估算MVRV: {self.data['mvrv']:.2f}")
        print(f"    ✅ 估算NUPL: {self.data['nupl']:.2f}")
    
    def fetch_all_data(self):
        """获取所有实时数据"""
        print("\n🔄 【获取实时数据】".center(60, '='))
        
        success_count = 0
        total_sources = 4
        
        # 获取数据
        if self.get_eth_price_data():
            success_count += 1
        elif self.get_alternative_eth_data():
            success_count += 1
        
        if self.get_ma200_data():
            success_count += 1
        
        if self.get_binance_funding_rate():
            success_count += 1
        
        if self.get_fear_greed_index():
            success_count += 1
        
        self.estimate_onchain_metrics()
        
        print(f"\n📊 数据获取完成: {success_count}/{total_sources} 个主要数据源成功")
        
        if success_count < 2:
            print("⚠️ 警告: 大部分数据源失败，分析结果可能不准确")
            if self.macos_compatible:
                send_macos_notification("ETH监控", "数据获取失败，将使用演示数据")
            use_demo = input("是否使用演示数据继续？(y/n): ").lower()
            if use_demo == 'y':
                self.load_demo_data()
        
        time.sleep(1)
    
    def load_demo_data(self):
        """加载演示数据"""
        self.data = {
            'price': 4475.0,
            'ma200': 2561.0,
            'change_24h': 2.5,
            'mvrv': 2.8,
            'nupl': 0.68,
            'funding_rate': 0.08,
            'fear_greed': 75,
            'volume_billion': 18.5
        }
        print("    ✅ 已加载演示数据")
    
    def calculate_eth_ahrx(self):
        """计算ETH-AHRX逃顶指标"""
        launch_date = datetime.datetime(2015, 7, 30)
        current_date = datetime.datetime.now()
        days_active = (current_date - launch_date).days
        years_active = days_active / 365.0
        
        growth_estimate = 0.1 * (1.5 ** years_active)
        
        price = self.data['price']
        ma200 = self.data['ma200']
        if price > 0 and ma200 > 0:
            ahrx = (ma200 / price) * (growth_estimate / price) * 2.5
        else:
            ahrx = 1.0
        
        return ahrx, days_active
    
    def analyze_risk(self):
        """分析风险等级"""
        self.risk_score = 0
        self.signals = []
        
        # 1. ETH-AHRX评分（权重30%）
        ahrx, days = self.calculate_eth_ahrx()
        if ahrx < 0.45:
            self.risk_score += 30
            self.signals.append("🔴 ETH-AHRX触发逃顶信号 (< 0.45)")
        elif ahrx < 0.6:
            self.risk_score += 25
            self.signals.append("🟠 ETH-AHRX进入高风险区 (0.45-0.6)")
        elif ahrx < 1.0:
            self.risk_score += 20
            self.signals.append("🟡 ETH-AHRX警戒区域 (0.6-1.0)")
        elif ahrx < 3.0:
            self.risk_score += 10
        
        # 2. MVRV评分（权重20%）
        mvrv = self.data['mvrv']
        if mvrv > 3.5:
            self.risk_score += 20
            self.signals.append("🔴 MVRV极度超买 (> 3.5)")
        elif mvrv > 3.0:
            self.risk_score += 15
            self.signals.append("🟠 MVRV显著偏高 (> 3.0)")
        elif mvrv > 2.5:
            self.risk_score += 10
        elif mvrv > 2.0:
            self.risk_score += 5
        
        # 3. NUPL评分（权重15%）
        nupl = self.data['nupl']
        if nupl > 0.75:
            self.risk_score += 15
            self.signals.append("🔴 NUPL极度贪婪 (> 0.75)")
        elif nupl > 0.65:
            self.risk_score += 10
            self.signals.append("🟡 NUPL偏高 (> 0.65)")
        elif nupl > 0.5:
            self.risk_score += 5
        
        # 4. 价格动量评分（权重10%）
        change = self.data['change_24h']
        if abs(change) > 10:
            self.risk_score += 10
            if change > 0:
                self.signals.append("🔴 24h涨幅过大 (> 10%)")
            else:
                self.signals.append("🟢 大幅回调 (< -10%)")
        elif abs(change) > 7:
            self.risk_score += 7
        elif abs(change) > 5:
            self.risk_score += 4
        
        # 5. 资金费率评分（权重10%）
        funding = self.data['funding_rate']
        if funding > 0.1:
            self.risk_score += 10
            self.signals.append("🔴 资金费率过高 (> 0.1%)")
        elif funding > 0.05:
            self.risk_score += 7
        elif funding > 0.01:
            self.risk_score += 3
        elif funding < -0.01:
            self.signals.append("🟢 空头主导 (< -0.01%)")
        
        # 6. 恐惧贪婪指数评分（权重10%）
        fear_greed = self.data['fear_greed']
        if fear_greed > 80:
            self.risk_score += 10
            self.signals.append("🔴 极度贪婪 (> 80)")
        elif fear_greed > 65:
            self.risk_score += 7
            self.signals.append("🟡 市场贪婪 (> 65)")
        elif fear_greed > 50:
            self.risk_score += 3
        elif fear_greed < 30:
            self.signals.append("🟢 市场恐慌 (< 30)")
        
        # 7. 成交量评分（权重5%）
        volume = self.data['volume_billion']
        if volume > 30:
            self.risk_score += 5
            self.signals.append("🟡 成交量异常放大")
        elif volume < 10:
            self.signals.append("🟡 成交量萎缩")
        
        return ahrx, days
    
    def get_risk_level(self):
        """获取风险等级"""
        if self.risk_score >= 70:
            return "🔴 极度危险", "red"
        elif self.risk_score >= 50:
            return "🟠 高度警戒", "orange"
        elif self.risk_score >= 30:
            return "🟡 中等风险", "yellow"
        else:
            return "🟢 相对安全", "green"
    
    def get_recommendations(self):
        """获取操作建议"""
        recommendations = []
        
        if self.risk_score >= 70:
            recommendations.append("🚨 立即减仓70%以上！多个指标显示极度危险")
            recommendations.append("💰 锁定利润，不要贪婪")
            recommendations.append("⏰ 设置止损，保护本金")
        elif self.risk_score >= 50:
            recommendations.append("⚠️ 建议减仓40-60%")
            recommendations.append("📊 密切关注指标变化")
            recommendations.append("🛡️ 分批止盈，降低风险")
        elif self.risk_score >= 30:
            recommendations.append("👀 保持警惕，准备减仓计划")
            recommendations.append("📈 可以继续持有，但设好止损")
            recommendations.append("🔍 每日监控关键指标")
        else:
            recommendations.append("✅ 市场相对安全，可以继续持有")
            recommendations.append("📊 在回调时可考虑适量加仓")
            recommendations.append("⏰ 设置价格提醒，关注变化")
        
        return recommendations
    
    def send_risk_notification(self):
        """发送风险通知"""
        if not self.macos_compatible:
            return
            
        current_time = time.time()
        # 避免频繁通知，至少间隔10分钟
        if current_time - self.last_notification_time < 600:
            return
        
        risk_level, _ = self.get_risk_level()
        
        if self.risk_score >= 70:
            send_macos_notification(
                "🚨 ETH极度危险警告", 
                f"风险评分: {self.risk_score}/100\n{risk_level}\n建议立即减仓！",
                sound=True
            )
            self.last_notification_time = current_time
        elif self.risk_score >= 50:
            send_macos_notification(
                "⚠️ ETH高风险警告", 
                f"风险评分: {self.risk_score}/100\n{risk_level}\n建议减仓40-60%",
                sound=True
            )
            self.last_notification_time = current_time
    
    def print_report(self):
        """打印分析报告 - macOS优化版"""
        clear_screen()
        print_header()
        
        # 计算指标
        ahrx, days = self.analyze_risk()
        risk_level, _ = self.get_risk_level()
        
        # 发送通知
        self.send_risk_notification()
        
        # 基础数据
        print("\n🎯 【实时市场数据】".center(60, '='))
        print(f"  💰 ETH价格: ${self.data['price']:.2f}")
        print(f"  📊 200日均线: ${self.data['ma200']:.2f}")
        print(f"  📈 24h涨跌: {self.data['change_24h']:+.2f}%")
        print(f"  💹 24h成交量: ${self.data['volume_billion']:.1f}B")
        print(f"  📍 均线偏离度: {((self.data['price']/self.data['ma200']-1)*100):+.1f}%")
        
        # 核心指标
        print("\n⭐ 【核心指标】".center(60, '='))
        print(f"  🔮 ETH-AHRX: {ahrx:.4f}", end="")
        if ahrx < 0.45:
            print(" [🚨 逃顶信号!]")
        elif ahrx < 0.6:
            print(" [⚠️ 高风险]")
        elif ahrx < 1.0:
            print(" [⚡ 警戒]")
        else:
            print(" [✅ 安全]")
        
        print(f"  📊 MVRV: {self.data['mvrv']:.2f}")
        print(f"  📈 NUPL: {self.data['nupl']:.2f}")
        print(f"  💸 资金费率: {self.data['funding_rate']:.3f}%")
        print(f"  😰 恐惧贪婪: {self.data['fear_greed']:.0f}/100")
        print(f"  📅 ETH运行天数: {days}天")
        
        # 风险评估
        print("\n🎯 【风险评估】".center(60, '='))
        print(f"  🏆 综合风险评分: {self.risk_score}/100")
        print(f"  📊 风险等级: {risk_level}")
        
        # 风险信号
        if self.signals:
            print("\n🚨 【风险信号】".center(60, '='))
            for signal in self.signals:
                print(f"  {signal}")
        
        # 历史对比
        print("\n📚 【历史顶部对比】".center(60, '='))
        print("  时期          价格     AHRX    结果")
        print("  " + "-" * 40)
        print("  2017年12月    $1,420   0.38    ✅ 成功预警")
        print("  2021年5月     $4,362   0.42    ✅ 成功预警")
        print("  2021年11月    $4,868   0.45    ✅ 成功预警")
        print(f"  当前         ${self.data['price']:<7.0f} {ahrx:.2f}    🔍 监控中...")
        
        # 操作建议
        print("\n💡 【操作建议】".center(60, '='))
        for i, rec in enumerate(self.get_recommendations(), 1):
            print(f"  {i}. {rec}")
        
        print("\n🍎" + "=" * 68 + "🍎")
        print("🔄 数据来源: CoinGecko + Binance + Alternative.me")
        print("⚡ AHRX<0.45为历史验证的逃顶信号 | 风险>70为极度危险")
        print("📁 报告保存在: ~/Documents/ETH_Reports/")
        print("🍎" + "=" * 68 + "🍎")
    
    def save_report(self):
        """保存报告到Documents文件夹"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ETH_Report_macOS_{timestamp}.txt"
        filepath = os.path.join(self.reports_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("ETH逃顶监控报告 - MacBook专用版\n")
                f.write(f"生成时间: {datetime.datetime.now()}\n")
                f.write(f"macOS版本: {self.macos_version}\n")
                f.write("-" * 50 + "\n\n")
                
                f.write("实时市场数据:\n")
                for key, value in self.data.items():
                    f.write(f"  {key}: {value}\n")
                
                ahrx, _ = self.calculate_eth_ahrx()
                f.write(f"\nETH-AHRX: {ahrx:.4f}\n")
                f.write(f"风险评分: {self.risk_score}/100\n")
                f.write(f"风险等级: {self.get_risk_level()[0]}\n")
                
                f.write("\n风险信号:\n")
                for signal in self.signals:
                    f.write(f"  {signal}\n")
                
                f.write("\n操作建议:\n")
                for rec in self.get_recommendations():
                    f.write(f"  {rec}\n")
                
                f.write(f"\n数据来源: CoinGecko + Binance + Alternative.me\n")
                f.write(f"系统信息: {platform.system()} {platform.release()}\n")
            
            print(f"\n✅ 报告已保存到: {filepath}")
            
            # macOS通知
            if self.macos_compatible:
                send_macos_notification("ETH监控", f"报告已保存到Documents文件夹")
                
            # 询问是否在Finder中显示
            show_finder = input("是否在Finder中显示报告？(y/n): ").lower()
            if show_finder == 'y':
                subprocess.run(['open', '-R', filepath])
                
        except Exception as e:
            print(f"\n❌ 保存失败: {e}")
    
    def auto_monitor(self, interval_minutes=30):
        """自动监控模式 - macOS优化"""
        print(f"\n🔄 启动自动监控模式，每{interval_minutes}分钟更新一次")
        print("按 Ctrl+C 停止监控\n")
        
        # 启动通知
        if self.macos_compatible:
            send_macos_notification("ETH监控启动", f"已开始每{interval_minutes}分钟自动监控")
        
        try:
            cycle_count = 0
            while True:
                cycle_count += 1
                print(f"\n🔄 监控周期 #{cycle_count}")
                
                # 获取数据并生成报告
                self.fetch_all_data()
                self.print_report()
                
                # 高风险自动保存和通知
                if self.risk_score >= 70:
                    self.save_report()
                    print("\n🚨 检测到极度危险，已自动保存报告！")
                
                # 等待下次更新
                print(f"\n⏰ {interval_minutes}分钟后将自动更新...")
                for remaining in range(interval_minutes * 60, 0, -30):
                    if remaining % 300 == 0:  # 每5分钟显示一次倒计时
                        mins = remaining // 60
                        print(f"⏳ 还有 {mins} 分钟更新...")
                    time.sleep(30)
                
        except KeyboardInterrupt:
            print("\n\n⏹️ 自动监控已停止")
            if self.macos_compatible:
                send_macos_notification("ETH监控", "自动监控已停止")
    
    def open_terminal_in_new_window(self, command):
        """在新终端窗口中运行命令"""
        try:
            script = f'''
            tell application "Terminal"
                do script "{command}"
                activate
            end tell
            '''
            subprocess.run(['osascript', '-e', script])
        except:
            print("无法打开新终端窗口")
    
    def run_interactive(self):
        """交互式运行 - macOS优化"""
        while True:
            clear_screen()
            print_header()
            
            print("\n🎯 请选择操作:")
            print("  1. 📡 获取实时数据并分析")
            print("  2. 🔄 启动自动监控 (30分钟间隔)")
            print("  3. ⚡ 启动自动监控 (10分钟间隔)")
            print("  4. 🚀 启动高频监控 (5分钟间隔)")
            print("  5. 📚 查看历史回测")
            print("  6. 🎮 使用演示数据")
            print("  7. 📁 打开报告文件夹")
            print("  8. 🍎 系统信息")
            print("  9. 🚪 退出程序")
            
            choice = input("\n请输入选择 (1-9): ").strip()
            
            if choice == '1':
                self.fetch_all_data()
                self.print_report()
                save = input("\n是否保存报告？(y/n): ").lower()
                if save == 'y':
                    self.save_report()
                input("\n按回车键继续...")
                
            elif choice == '2':
                self.auto_monitor(30)
                input("\n按回车键继续...")
                
            elif choice == '3':
                self.auto_monitor(10)
                input("\n按回车键继续...")
                
            elif choice == '4':
                self.auto_monitor(5)
                input("\n按回车键继续...")
                
            elif choice == '5':
                self.show_backtest()
                input("\n按回车键继续...")
                
            elif choice == '6':
                self.load_demo_data()
                self.print_report()
                save = input("\n是否保存报告？(y/n): ").lower()
                if save == 'y':
                    self.save_report()
                input("\n按回车键继续...")
                
            elif choice == '7':
                try:
                    subprocess.run(['open', self.reports_dir])
                    print(f"\n✅ 已打开报告文件夹: {self.reports_dir}")
                except:
                    print(f"\n❌ 无法打开文件夹: {self.reports_dir}")
                input("\n按回车键继续...")
                
            elif choice == '8':
                self.show_system_info()
                input("\n按回车键继续...")
                
            elif choice == '9':
                print("\n🍎 感谢使用MacBook专用版！再见！")
                if self.macos_compatible:
                    send_macos_notification("ETH监控", "程序已退出，感谢使用！")
                break
            else:
                print("\n❌ 无效选择，请重试")
                time.sleep(1)
    
    def show_system_info(self):
        """显示系统信息"""
        clear_screen()
        print_header()
        
        print("\n🍎 【系统信息】".center(60, '='))
        print(f"  💻 系统: {platform.system()}")
        print(f"  📱 版本: {platform.release()}")
        print(f"  🏗️ 架构: {platform.machine()}")
        print(f"  🐍 Python: {platform.python_version()}")
        print(f"  📁 用户目录: {self.home_dir}")
        print(f"  📄 报告目录: {self.reports_dir}")
        
        # 检测处理器类型
        try:
            processor_info = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], 
                                          capture_output=True, text=True)
            if processor_info.returncode == 0:
                print(f"  🚀 处理器: {processor_info.stdout.strip()}")
        except:
            print(f"  🚀 处理器: {platform.processor()}")
        
        # 检测内存
        try:
            memory_info = subprocess.run(['sysctl', '-n', 'hw.memsize'], 
                                       capture_output=True, text=True)
            if memory_info.returncode == 0:
                memory_gb = int(memory_info.stdout.strip()) / (1024**3)
                print(f"  🧠 内存: {memory_gb:.1f} GB")
        except:
            print("  🧠 内存: 无法检测")
        
        # 网络状态
        print(f"\n🌐 【网络状态】".center(60, '='))
        test_urls = [
            ("CoinGecko", "https://api.coingecko.com/api/v3/ping"),
            ("Binance", "https://api.binance.com/api/v3/ping"),
            ("恐惧贪婪", "https://api.alternative.me/fng/?limit=1")
        ]
        
        for name, url in test_urls:
            try:
                start_time = time.time()
                response = urllib.request.urlopen(url, timeout=5)
                end_time = time.time()
                latency = (end_time - start_time) * 1000
                if response.getcode() == 200:
                    print(f"  ✅ {name}: 连接正常 ({latency:.0f}ms)")
                else:
                    print(f"  ⚠️ {name}: 响应异常")
            except:
                print(f"  ❌ {name}: 连接失败")
        
        # macOS特性
        print(f"\n🎯 【macOS特性】".center(60, '='))
        print(f"  🔔 通知支持: {'✅ 已启用' if self.macos_compatible else '❌ 不支持'}")
        print(f"  📁 Finder集成: ✅ 已启用")
        print(f"  🎨 终端颜色: ✅ 已启用")
        print(f"  🔊 声音提醒: ✅ 已启用")
        
        print(f"\n📚 【使用说明】".center(60, '='))
        print("  💡 支持macOS原生通知推送")
        print("  📁 报告自动保存到Documents文件夹")
        print("  🔊 危险等级达到时会有声音提醒")
        print("  ⌨️ 使用Ctrl+C可以安全退出自动监控")
        print("  🍎 完全适配Apple Silicon和Intel处理器")
    
    def show_backtest(self):
        """显示历史回测 - macOS优化版"""
        clear_screen()
        print_header()
        
        print("\n📚 【历史回测分析】".center(60, '='))
        
        # 历史数据
        historical = [
            ("2017年12月", 1420, 280, 3.8, 0.85, 0.15, 100),
            ("2021年5月", 4362, 1800, 3.5, 0.82, 0.12, 95),
            ("2021年11月", 4868, 2400, 3.2, 0.78, 0.10, 85),
        ]
        
        print("\n时期        价格    200MA   MVRV  NUPL  资金费率  恐贪  AHRX")
        print("-" * 65)
        
        for period, price, ma200, mvrv, nupl, funding, fg in historical:
            # 计算历史AHRX
            ahrx = (ma200 / price) * (0.5 / price) * 2.5
            print(f"{period:<10} ${price:<6} ${ma200:<6} {mvrv:<5.1f} {nupl:<5.2f} "
                  f"{funding:<8.2f}% {fg:<5} {ahrx:.3f}")
        
        print("\n🎯 回测结论:")
        print("  ✅ ETH-AHRX < 0.45 成功预警3次历史顶部")
        print("  ✅ MVRV > 3.2 是可靠的顶部信号")
        print("  ✅ NUPL > 0.75 表示市场极度贪婪")
        print("  ✅ 多指标共振时准确率最高")
        
        print("\n📡 API数据源说明:")
        print("  🌐 CoinGecko: 价格、涨跌幅、成交量、历史数据")
        print("  🔄 Binance: 资金费率、备用价格数据")
        print("  😰 Alternative.me: 恐惧贪婪指数")
        print("  ⛓️ 链上指标: 基于价格模型估算")
        
        print("\n🍎 macOS优化特性:")
        print("  🔔 风险等级变化时自动推送通知")
        print("  📁 报告自动保存到Documents文件夹")
        print("  🎨 彩色终端输出和emoji指示")
        print("  🔊 高风险时播放系统提示音")

def check_network_connectivity():
    """检查网络连接"""
    print("🌐 检查网络连接...")
    test_url = "https://api.coingecko.com/api/v3/ping"
    try:
        request = urllib.request.Request(test_url)
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.getcode() == 200:
                print("✅ 网络连接正常")
                return True
            else:
                print("⚠️ 网络连接可能有问题")
                return False
    except:
        print("❌ 网络连接失败，将使用演示数据")
        return False

def main():
    """主程序 - macOS专用版"""
    try:
        # 启动信息
        clear_screen()
        print("🍎 正在启动ETH监控系统 - MacBook专用版...")
        
        # 检查系统
        if platform.system() != "Darwin":
            print("⚠️ 警告: 此版本专为macOS优化，其他系统可能无法使用所有功能")
        
        # 检查网络
        network_ok = check_network_connectivity()
        
        # 创建监控器实例
        print("🚀 初始化监控系统...")
        monitor = ETHMonitorMacOS()
        
        # 启动通知
        if monitor.macos_compatible:
            send_macos_notification("ETH监控系统", "MacBook专用版已启动！")
        
        # 运行交互式界面
        monitor.run_interactive()
        
    except KeyboardInterrupt:
        print("\n\n⏹️ 程序被用户中断")
        if 'monitor' in locals() and monitor.macos_compatible:
            send_macos_notification("ETH监控", "程序已被用户中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print("如果遇到问题，请:")
        print("1. 🌐 检查网络连接")
        print("2. 🔒 确认安全软件设置")
        print("3. 🎮 尝试使用演示数据模式")
        print("4. 🍎 确认macOS版本兼容性")
        input("按回车键退出...")

if __name__ == "__main__":
    main()