import os
import sys
import argparse
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.gridspec import GridSpec
from typing import Dict, List, Tuple, Optional, Any
import statistics

# เพิ่มโฟลเดอร์แอปลงในพาธเพื่อสามารถนำเข้าโมดูลได้
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# นำเข้าโมดูลที่ต้องการ
from app.signal_processor import grade_signal, calculate_ema, calculate_sma, calculate_rsi
from app.influxdb_storage import InfluxDBStorage


class BacktestAnalyzer:
    """คลาสสำหรับทดสอบระบบสัญญาณย้อนหลังและวิเคราะห์ประสิทธิภาพ"""
    
    def __init__(self, symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
        """
        เริ่มต้นคลาสวิเคราะห์ backtest
        
        Args:
            symbol: สัญลักษณ์คู่เทรด เช่น BTCUSDT
            start_date: วันที่เริ่มต้นในรูปแบบ "YYYY-MM-DD" (ถ้าไม่ระบุจะเป็น 30 วันที่แล้ว)
            end_date: วันที่สิ้นสุดในรูปแบบ "YYYY-MM-DD" (ถ้าไม่ระบุจะเป็นวันปัจจุบัน)
        """
        self.symbol = symbol
        
        # ตั้งค่าช่วงเวลา
        now = datetime.now()
        if end_date:
            self.end_time = datetime.strptime(end_date, "%Y-%m-%d")
        else:
            self.end_time = now
        
        if start_date:
            self.start_time = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            self.start_time = now - timedelta(days=30)
        
        # แปลงเป็น timestamp มิลลิวินาที
        self.start_timestamp = int(self.start_time.timestamp() * 1000)
        self.end_timestamp = int(self.end_time.timestamp() * 1000)
        
        # เชื่อมต่อกับ InfluxDB
        self.influxdb_storage = InfluxDBStorage()
        
        # เก็บประวัติสัญญาณและข้อมูลแท่งเทียน
        self.klines_df = pd.DataFrame()
        self.signals_df = pd.DataFrame()
        self.backtest_results = pd.DataFrame()
        self.performance_metrics = {}
    
    def load_historical_data(self) -> bool:
        """
        โหลดข้อมูลประวัติแท่งเทียนและสัญญาณจาก InfluxDB
        
        Returns:
            True ถ้าโหลดข้อมูลสำเร็จ False ถ้าไม่สำเร็จ
        """
        try:
            # โหลดข้อมูลแท่งเทียน
            self.klines_df = self.influxdb_storage.get_historical_klines(
                symbol=self.symbol,
                interval='2m',
                start_time=self.start_timestamp,
                end_time=self.end_timestamp,
                limit=10000  # เพิ่มจำนวนแท่งเทียนสูงสุดเพื่อให้แน่ใจว่าจะได้ข้อมูลเพียงพอ
            )
            
            # โหลดข้อมูลสัญญาณ
            self.signals_df = self.influxdb_storage.get_historical_signals(
                symbol=self.symbol,
                start_time=self.start_timestamp,
                end_time=self.end_timestamp,
                limit=10000
            )
            
            # ถ้าไม่มีข้อมูลเพียงพอ
            if self.klines_df.empty or len(self.klines_df) < 10:
                print(f"ไม่มีข้อมูลแท่งเทียนเพียงพอสำหรับ {self.symbol} ในช่วงเวลาที่กำหนด")
                return False
                
            # จัดรูปแบบข้อมูล
            self.klines_df.sort_values('timestamp', inplace=True)
            
            if not self.signals_df.empty:
                self.signals_df.sort_values('timestamp', inplace=True)
            
            print(f"โหลดข้อมูลสำเร็จ: {len(self.klines_df)} แท่งเทียน และ {len(self.signals_df)} สัญญาณ")
            return True
            
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการโหลดข้อมูลประวัติ: {e}")
            return False
    
    def generate_signals(self, window_size: int = 50) -> None:
        """
        สร้างสัญญาณการเทรดจากข้อมูลประวัติแท่งเทียน
        
        Args:
            window_size: ขนาดหน้าต่างสำหรับคำนวณตัวชี้วัด (จำนวนแท่งเทียน)
        """
        if self.klines_df.empty:
            print("ไม่พบข้อมูลแท่งเทียนสำหรับสร้างสัญญาณ")
            return
        
        # สร้าง DataFrame ใหม่สำหรับผลลัพธ์การทดสอบย้อนหลัง
        results = []
        
        # ดึงข้อมูลราคาปิด
        prices = self.klines_df['close'].tolist()
        
        # คำนวณตัวชี้วัดทางเทคนิคอล
        for i in range(window_size, len(prices)):
            window = prices[i-window_size:i]
            current_price = prices[i]
            
            # คำนวณตัวชี้วัด
            ema9 = calculate_ema(window, 9)[-1]
            ema21 = calculate_ema(window, 21)[-1]
            sma20 = calculate_sma(window, 20)[-1]
            rsi14 = calculate_rsi(window, 14)[-1]
            
            # คำนวณสัญญาณ
            prev_price = prices[i-1]
            last_change_pct = ((current_price - prev_price) / prev_price) * 100
            
            # การสร้างสัญญาณแบบเดียวกับใน signal_processor.py
            ema_signal = 0.0
            rsi_signal = 0.0
            
            if ema9 > ema21:
                ema_signal = 1.0
            elif ema9 < ema21:
                ema_signal = -1.0
                
            if rsi14 < 30:
                rsi_signal = 1.0
            elif rsi14 > 70:
                rsi_signal = -1.0
                
            forecast_pct = (last_change_pct * 0.3) + (ema_signal * 0.4) + (rsi_signal * 0.3)
            signal_agreement = abs(ema_signal + rsi_signal + (1 if last_change_pct > 0 else -1)) / 3.0
            confidence = min(0.6 + (signal_agreement * 0.3), 0.9)
            
            # จัดเกรดสัญญาณ
            category = grade_signal(forecast_pct, confidence)
            
            # บันทึกผลลัพธ์
            record = {
                'timestamp': self.klines_df.iloc[i]['timestamp'],
                'price': current_price,
                'forecast_pct': forecast_pct,
                'confidence': confidence,
                'category': category,
                'ema9': ema9,
                'ema21': ema21,
                'sma20': sma20,
                'rsi14': rsi14
            }
            results.append(record)
        
        # สร้าง DataFrame สำหรับผลลัพธ์
        self.backtest_results = pd.DataFrame(results)
        print(f"สร้างสัญญาณสำหรับการทดสอบย้อนหลังสำเร็จ: {len(self.backtest_results)} สัญญาณ")
    
    def evaluate_performance(self, initial_balance: float = 10000.0, position_size_pct: float = 10.0) -> Dict[str, Any]:
        """
        ประเมินประสิทธิภาพของสัญญาณการเทรด
        
        Args:
            initial_balance: ยอดเงินเริ่มต้น
            position_size_pct: ขนาดของตำแหน่งเป็นเปอร์เซ็นต์ของยอดเงินทั้งหมด
            
        Returns:
            Dictionary ที่มีเมตริกประสิทธิภาพต่างๆ
        """
        if self.backtest_results.empty:
            print("ไม่พบข้อมูลสัญญาณสำหรับการประเมินประสิทธิภาพ")
            return {}
            
        # คัดกรองเฉพาะสัญญาณซื้อและขาย (ไม่รวม hold)
        trade_signals = self.backtest_results[self.backtest_results['category'] != 'hold'].copy()
        
        if trade_signals.empty or len(trade_signals) < 2:
            print("ไม่พบสัญญาณซื้อหรือขายเพียงพอสำหรับการประเมินประสิทธิภาพ")
            return {}
        
        # เตรียมข้อมูลสำหรับการจำลองการเทรด
        balance = initial_balance
        position = 0.0
        position_size = initial_balance * (position_size_pct / 100.0)
        trades = []
        equity_curve = []
        
        # จำลองการเทรด
        for idx, row in trade_signals.iterrows():
            timestamp = row['timestamp']
            price = row['price']
            category = row['category']
            
            # ดำเนินการซื้อ
            if 'buy' in category and position == 0:
                shares = position_size / price
                position = shares
                trade = {
                    'type': 'buy',
                    'timestamp': timestamp,
                    'price': price,
                    'shares': shares,
                    'amount': position_size,
                    'confidence': row['confidence'],
                    'category': category
                }
                trades.append(trade)
                equity = balance - position_size + (position * price)
                equity_curve.append({'timestamp': timestamp, 'equity': equity})
                
            # ดำเนินการขาย
            elif 'sell' in category and position > 0:
                sell_amount = position * price
                pnl = sell_amount - position_size
                balance += pnl
                
                trade = {
                    'type': 'sell',
                    'timestamp': timestamp,
                    'price': price,
                    'shares': position,
                    'amount': sell_amount,
                    'pnl': pnl,
                    'pnl_pct': (pnl / position_size) * 100,
                    'confidence': row['confidence'],
                    'category': category
                }
                trades.append(trade)
                position = 0
                equity = balance
                equity_curve.append({'timestamp': timestamp, 'equity': equity})
                
                # อัพเดทขนาดตำแหน่งสำหรับการเทรดครั้งต่อไป
                position_size = balance * (position_size_pct / 100.0)
        
        # ปิดตำแหน่งที่เปิดอยู่ด้วยราคาสุดท้าย
        if position > 0:
            last_price = self.backtest_results.iloc[-1]['price']
            sell_amount = position * last_price
            pnl = sell_amount - position_size
            balance += pnl
            
            trade = {
                'type': 'sell',
                'timestamp': self.backtest_results.iloc[-1]['timestamp'],
                'price': last_price,
                'shares': position,
                'amount': sell_amount,
                'pnl': pnl,
                'pnl_pct': (pnl / position_size) * 100,
                'confidence': None,
                'category': 'exit at end'
            }
            trades.append(trade)
            position = 0
            equity = balance
            equity_curve.append({'timestamp': self.backtest_results.iloc[-1]['timestamp'], 'equity': equity})
        
        # สร้าง DataFrame สำหรับการเทรดและเส้นกราฟความมั่งคั่ง
        trades_df = pd.DataFrame(trades)
        equity_curve_df = pd.DataFrame(equity_curve)
        
        # คำนวณเมตริกประสิทธิภาพ
        metrics = {}
        
        # จำนวนการเทรดทั้งหมด
        metrics['total_trades'] = len(trades_df[trades_df['type'] == 'sell'])
        
        # การเทรดที่กำไร vs ขาดทุน
        if not trades_df.empty and 'pnl' in trades_df.columns:
            profitable_trades = trades_df[trades_df['pnl'] > 0]
            loss_trades = trades_df[trades_df['pnl'] < 0]
            
            metrics['profitable_trades'] = len(profitable_trades)
            metrics['loss_trades'] = len(loss_trades)
            
            if metrics['total_trades'] > 0:
                metrics['win_rate'] = metrics['profitable_trades'] / metrics['total_trades']
            else:
                metrics['win_rate'] = 0.0
            
            # กำไร/ขาดทุนรวม
            metrics['total_pnl'] = trades_df['pnl'].sum() if 'pnl' in trades_df.columns else 0
            metrics['total_pnl_pct'] = (balance - initial_balance) / initial_balance * 100
            
            # อัตราส่วนกำไรต่อขาดทุน
            avg_profit = profitable_trades['pnl'].mean() if len(profitable_trades) > 0 else 0
            avg_loss = abs(loss_trades['pnl'].mean()) if len(loss_trades) > 0 else 0
            
            metrics['avg_profit'] = avg_profit
            metrics['avg_loss'] = avg_loss
            
            if avg_loss > 0:
                metrics['profit_loss_ratio'] = avg_profit / avg_loss
            else:
                metrics['profit_loss_ratio'] = float('inf') if avg_profit > 0 else 0.0
            
            # ความผันผวนของกำไรขาดทุน
            if len(equity_curve_df) > 2:
                pct_changes = equity_curve_df['equity'].pct_change().dropna()
                metrics['volatility'] = pct_changes.std() * (252 ** 0.5)  # ปรับเป็น annualized volatility
            else:
                metrics['volatility'] = 0.0
            
            # Sharpe Ratio (ใช้อัตราผลตอบแทนไม่มีความเสี่ยง 2% ต่อปี)
            risk_free_rate = 0.02
            if metrics['volatility'] > 0:
                excess_return = metrics['total_pnl_pct'] / 100 - risk_free_rate
                metrics['sharpe_ratio'] = excess_return / metrics['volatility']
            else:
                metrics['sharpe_ratio'] = 0.0
            
            # การลดลงสูงสุด (Maximum Drawdown)
            if len(equity_curve_df) > 0:
                equity_curve_df['peak'] = equity_curve_df['equity'].cummax()
                equity_curve_df['drawdown'] = (equity_curve_df['equity'] - equity_curve_df['peak']) / equity_curve_df['peak']
                metrics['max_drawdown'] = equity_curve_df['drawdown'].min() * 100  # เป็นเปอร์เซ็นต์
            else:
                metrics['max_drawdown'] = 0.0
        
        # เก็บผลลัพธ์
        self.performance_metrics = metrics
        
        print(f"การประเมินประสิทธิภาพเสร็จสิ้น:")
        print(f"- จำนวนการเทรดทั้งหมด: {metrics.get('total_trades', 0)}")
        print(f"- อัตราชนะ: {metrics.get('win_rate', 0)*100:.2f}%")
        print(f"- กำไร/ขาดทุนรวม: ${metrics.get('total_pnl', 0):.2f} ({metrics.get('total_pnl_pct', 0):.2f}%)")
        print(f"- อัตราส่วนกำไรต่อขาดทุน: {metrics.get('profit_loss_ratio', 0):.2f}")
        print(f"- Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
        print(f"- การลดลงสูงสุด: {abs(metrics.get('max_drawdown', 0)):.2f}%")
        
        return metrics
    
    def plot_results(self, output_file: Optional[str] = None) -> None:
        """
        แสดงผลการทดสอบย้อนหลังด้วยกราฟ
        
        Args:
            output_file: ชื่อไฟล์ที่ต้องการบันทึกกราฟ (ถ้าไม่ระบุจะแสดงกราฟแทน)
        """
        if self.backtest_results.empty:
            print("ไม่พบข้อมูลสัญญาณสำหรับการสร้างกราฟ")
            return
        
        # สร้างกราฟด้วย matplotlib
        plt.style.use('seaborn-v0_8-darkgrid')
        fig = plt.figure(figsize=(14, 10))
        gs = GridSpec(3, 1, height_ratios=[2, 1, 1])
        
        # กราฟราคา
        ax1 = plt.subplot(gs[0])
        ax1.plot(self.backtest_results['timestamp'], self.backtest_results['price'], color='blue', label='Price')
        ax1.set_title(f'{self.symbol} Backtest Results ({self.start_time.date()} to {self.end_time.date()})')
        ax1.set_ylabel('Price (USD)')
        ax1.legend(loc='upper left')
        
        # เพิ่มเส้น EMA
        ax1.plot(self.backtest_results['timestamp'], self.backtest_results['ema9'], color='red', linestyle='--', label='EMA9')
        ax1.plot(self.backtest_results['timestamp'], self.backtest_results['ema21'], color='green', linestyle='--', label='EMA21')
        
        # ทำเครื่องหมายสัญญาณซื้อ/ขาย
        buy_signals = self.backtest_results[self.backtest_results['category'].str.contains('buy')]
        sell_signals = self.backtest_results[self.backtest_results['category'].str.contains('sell')]
        
        ax1.scatter(buy_signals['timestamp'], buy_signals['price'], color='green', marker='^', s=100, label='Buy Signal')
        ax1.scatter(sell_signals['timestamp'], sell_signals['price'], color='red', marker='v', s=100, label='Sell Signal')
        
        ax1.legend()
        
        # กราฟ RSI
        ax2 = plt.subplot(gs[1], sharex=ax1)
        ax2.plot(self.backtest_results['timestamp'], self.backtest_results['rsi14'], color='purple', label='RSI(14)')
        ax2.axhline(y=30, color='green', linestyle='--')
        ax2.axhline(y=70, color='red', linestyle='--')
        ax2.set_ylabel('RSI')
        ax2.set_ylim(0, 100)
        ax2.legend(loc='upper left')
        
        # กราฟการคาดการณ์และความมั่นใจ
        ax3 = plt.subplot(gs[2], sharex=ax1)
        ax3.plot(self.backtest_results['timestamp'], self.backtest_results['forecast_pct'], color='blue', label='Forecast %')
        ax3.set_ylabel('Forecast %')
        ax3.axhline(y=0, color='gray', linestyle='-')
        ax3.legend(loc='upper left')
        
        # แสดงเมตริกประสิทธิภาพบนกราฟ
        if self.performance_metrics:
            metrics_text = (
                f"Total Trades: {self.performance_metrics.get('total_trades', 0)}\n"
                f"Win Rate: {self.performance_metrics.get('win_rate', 0)*100:.1f}%\n"
                f"Profit/Loss: {self.performance_metrics.get('total_pnl_pct', 0):.1f}%\n"
                f"Sharpe Ratio: {self.performance_metrics.get('sharpe_ratio', 0):.2f}\n"
                f"Max Drawdown: {abs(self.performance_metrics.get('max_drawdown', 0)):.1f}%"
            )
            
            # วางกล่องข้อความบนกราฟราคา
            props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
            ax1.text(0.02, 0.98, metrics_text, transform=ax1.transAxes, fontsize=10,
                    verticalalignment='top', bbox=props)
        
        # จัดรูปแบบแกน x
        plt.gcf().autofmt_xdate()
        date_formatter = mdates.DateFormatter('%Y-%m-%d')
        ax3.xaxis.set_major_formatter(date_formatter)
        
        plt.xlabel('Date')
        plt.tight_layout()
        
        # บันทึกหรือแสดงกราฟ
        if output_file:
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            print(f"บันทึกกราฟไปยัง: {output_file}")
        else:
            plt.show()
        
        plt.close()
    
    def save_results(self, output_file: str) -> None:
        """
        บันทึกผลการทดสอบย้อนหลังเป็นไฟล์ JSON
        
        Args:
            output_file: ชื่อไฟล์ที่ต้องการบันทึกผลลัพธ์
        """
        if self.backtest_results.empty:
            print("ไม่พบข้อมูลสัญญาณสำหรับการบันทึก")
            return
        
        # แปลง timestamp เป็นสตริง
        results_copy = self.backtest_results.copy()
        results_copy['timestamp'] = results_copy['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # สร้าง dictionary ผลลัพธ์
        output = {
            'symbol': self.symbol,
            'start_date': self.start_time.strftime('%Y-%m-%d'),
            'end_date': self.end_time.strftime('%Y-%m-%d'),
            'signals': results_copy.to_dict(orient='records'),
            'metrics': self.performance_metrics
        }
        
        # บันทึกเป็นไฟล์ JSON
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=4)
        
        print(f"บันทึกผลการทดสอบย้อนหลังไปยัง: {output_file}")
    
    def close(self):
        """ปิดการเชื่อมต่อทั้งหมด"""
        try:
            self.influxdb_storage.close()
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการปิดการเชื่อมต่อ: {e}")


# ฟังก์ชันหลักสำหรับรัน backtest
def run_backtest(symbol: str, start_date: Optional[str], end_date: Optional[str], 
                output_dir: str, initial_balance: float = 10000.0) -> None:
    """
    ฟังก์ชันหลักสำหรับรัน backtest
    
    Args:
        symbol: สัญลักษณ์คู่เทรด เช่น BTCUSDT
        start_date: วันที่เริ่มต้นในรูปแบบ "YYYY-MM-DD" (ถ้าไม่ระบุจะเป็น 30 วันที่แล้ว)
        end_date: วันที่สิ้นสุดในรูปแบบ "YYYY-MM-DD" (ถ้าไม่ระบุจะเป็นวันปัจจุบัน)
        output_dir: โฟลเดอร์สำหรับบันทึกผลลัพธ์
        initial_balance: ยอดเงินเริ่มต้นสำหรับการจำลองการเทรด
    """
    try:
        # สร้างโฟลเดอร์เก็บผลลัพธ์ถ้ายังไม่มี
        os.makedirs(output_dir, exist_ok=True)
        
        # สร้างอินสแตนซ์ BacktestAnalyzer
        backtest = BacktestAnalyzer(symbol, start_date, end_date)
        
        # โหลดข้อมูลประวัติ
        if not backtest.load_historical_data():
            print(f"ไม่สามารถโหลดข้อมูลประวัติสำหรับ {symbol} ได้")
            backtest.close()
            return
        
        # สร้างสัญญาณสำหรับการทดสอบย้อนหลัง
        backtest.generate_signals()
        
        # ประเมินประสิทธิภาพ
        backtest.evaluate_performance(initial_balance=initial_balance)
        
        # สร้างชื่อไฟล์สำหรับผลลัพธ์
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file_prefix = f"{symbol}_backtest_{timestamp}"
        
        # บันทึกผลลัพธ์
        backtest.save_results(os.path.join(output_dir, f"{output_file_prefix}.json"))
        
        # สร้างกราฟและบันทึก
        backtest.plot_results(os.path.join(output_dir, f"{output_file_prefix}.png"))
        
        print(f"การทดสอบย้อนหลังสำหรับ {symbol} เสร็จสิ้น")
        backtest.close()
        
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการทดสอบย้อนหลัง: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ทดสอบระบบสัญญาณการเทรดย้อนหลัง")
    
    parser.add_argument('--symbol', type=str, default="BTCUSDT", help="สัญลักษณ์คู่เทรด เช่น BTCUSDT")
    parser.add_argument('--start', type=str, help="วันที่เริ่มต้นในรูปแบบ YYYY-MM-DD")
    parser.add_argument('--end', type=str, help="วันที่สิ้นสุดในรูปแบบ YYYY-MM-DD")
    parser.add_argument('--balance', type=float, default=10000.0, help="ยอดเงินเริ่มต้นสำหรับการจำลองการเทรด")
    parser.add_argument('--output', type=str, default="../backtest_results", help="โฟลเดอร์สำหรับบันทึกผลลัพธ์")
    
    args = parser.parse_args()
    
    run_backtest(args.symbol, args.start, args.end, args.output, args.balance)