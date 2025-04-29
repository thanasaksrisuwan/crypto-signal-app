import numpy as np
from enum import Enum
from typing import Tuple, Dict, Any, List, Optional
import pandas as pd
import redis
import json
import os
from dotenv import load_dotenv

# นำเข้าคลาส InfluxDBStorage ด้วยการลองหลายวิธี
try:
    # เมื่อรันเป็น module โดยตรง
    from .influxdb_storage import InfluxDBStorage
except (ImportError, ModuleNotFoundError):
    try:
        # เมื่อรันจาก app directory โดยตรง
        from app.influxdb_storage import InfluxDBStorage
    except (ImportError, ModuleNotFoundError):
        try:
            # เมื่อรันเป็น script โดยตรง
            from influxdb_storage import InfluxDBStorage
        except (ImportError, ModuleNotFoundError):
            print("ไม่สามารถนำเข้า InfluxDBStorage ได้ - จะทำงานโดยไม่มีการบันทึกข้อมูลลง InfluxDB")
            # สร้างคลาสจำลองเพื่อหลีกเลี่ยงข้อผิดพลาด
            class InfluxDBStorage:
                def __init__(self):
                    print("คลาส InfluxDBStorage จำลอง - ไม่มีการเชื่อมต่อกับ InfluxDB จริง")
                
                def store_signal(self, signal):
                    pass
                
                def close(self):
                    pass

# โหลด environment variables
load_dotenv()

# ตั้งค่าการเชื่อมต่อ Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_SIGNAL_CHANNEL = "crypto_signals:signals"

# คลาส Enum สำหรับประเภทสัญญาณ
class SignalCategory(str, Enum):
    STRONG_BUY = "strong buy"
    WEAK_BUY = "weak buy"
    HOLD = "hold"
    WEAK_SELL = "weak sell"
    STRONG_SELL = "strong sell"

def calculate_ema(prices: List[float], period: int) -> List[float]:
    """
    คำนวณ Exponential Moving Average (EMA)
    
    Args:
        prices: รายการราคาปิด
        period: ระยะเวลาของ EMA (จำนวนแท่งเทียน)
        
    Returns:
        List ของค่า EMA
    """
    return pd.Series(prices).ewm(span=period, adjust=False).mean().tolist()

def calculate_sma(prices: List[float], period: int) -> List[float]:
    """
    คำนวณ Simple Moving Average (SMA)
    
    Args:
        prices: รายการราคาปิด
        period: ระยะเวลาของ SMA (จำนวนแท่งเทียน)
        
    Returns:
        List ของค่า SMA
    """
    return pd.Series(prices).rolling(window=period).mean().tolist()

def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
    """
    คำนวณ Relative Strength Index (RSI)
    
    Args:
        prices: รายการราคาปิด
        period: ระยะเวลาของ RSI (โดยปกติคือ 14)
        
    Returns:
        List ของค่า RSI
    """
    # ถ้ามีข้อมูลไม่เพียงพอ ให้ส่งคืนลิสต์ที่มีค่า None
    if len(prices) < period + 1:
        return [None] * len(prices)
        
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    # วิธีการคำนวณแบบปลอดภัยกว่า โดยใช้การคำนวณเริ่มต้นที่ถูกต้อง
    avg_gain = np.zeros_like(prices, dtype=float)
    avg_loss = np.zeros_like(prices, dtype=float)
    
    # คำนวณค่าเฉลี่ยของ gain และ loss ช่วงแรก
    if len(gains) >= period:
        avg_gain[period] = np.mean(gains[:period])
        avg_loss[period] = np.mean(losses[:period])
    
        # คำนวณค่าเฉลี่ยแบบถ่วงน้ำหนักสำหรับวันที่เหลือ
        for i in range(period + 1, len(prices)):
            if i - 1 < len(gains):
                avg_gain[i] = (avg_gain[i-1] * (period-1) + gains[i-1]) / period
                avg_loss[i] = (avg_loss[i-1] * (period-1) + losses[i-1]) / period
    
    # คำนวณ RS และ RSI
    rs = np.where(avg_loss != 0, avg_gain / avg_loss, 100)
    rsi = 100 - (100 / (1 + rs))
    
    # แทนที่ค่า NaN ด้วย None
    rsi = np.where(np.isnan(rsi), None, rsi)
    
    return rsi.tolist()

def grade_signal(forecast_pct: float, confidence: float) -> str:
    """
    วิเคราะห์ข้อมูลการคาดการณ์เปอร์เซ็นต์การเปลี่ยนแปลงและความมั่นใจ เพื่อจัดประเภทสัญญาณการซื้อขาย
    
    Args:
        forecast_pct: เปอร์เซ็นต์การเปลี่ยนแปลงราคาที่คาดการณ์ (+ คือขึ้น, - คือลง)
        confidence: ค่าความมั่นใจของการคาดการณ์ (0.0-1.0)
        
    Returns:
        ประเภทของสัญญาณ: strong buy, weak buy, hold, weak sell, หรือ strong sell
    """
    if not (0 <= confidence <= 1.0):
        raise ValueError("ค่าความมั่นใจต้องอยู่ระหว่าง 0 และ 1")
    if confidence < 0.6:
        return SignalCategory.HOLD
    if forecast_pct > 0:
        if forecast_pct >= 1.0 and confidence >= 0.8:
            return SignalCategory.STRONG_BUY
        elif forecast_pct >= 0.5 or confidence >= 0.7:
            return SignalCategory.WEAK_BUY
        else:
            return SignalCategory.HOLD
    elif forecast_pct < 0:
        if forecast_pct <= -1.0 and confidence >= 0.8:
            return SignalCategory.STRONG_SELL
        elif forecast_pct <= -0.5 or confidence >= 0.7:
            return SignalCategory.WEAK_SELL
        else:
            return SignalCategory.HOLD
    else:
        return SignalCategory.HOLD

class SignalProcessor:
    def __init__(self):
        """เริ่มต้นตัวประมวลผลสัญญาณด้วยการเชื่อมต่อกับ Redis และ InfluxDB"""
        self.redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        
        # สร้างอินสแตนซ์ของ InfluxDBStorage
        self.influxdb_storage = InfluxDBStorage()
        
        self.price_history = {}
        
    def update_price_history(self, symbol: str, price: float):
        """
        อัพเดทประวัติราคาสำหรับการคำนวณตัวชี้วัดเทคนิคอล
        
        Args:
            symbol: สัญลักษณ์คู่สกุลเงิน
            price: ราคาปิดล่าสุด
        """
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        self.price_history[symbol].append(price)
        if len(self.price_history[symbol]) > 50:
            self.price_history[symbol] = self.price_history[symbol][-50:]
    
    def calculate_indicators(self, symbol: str) -> Dict[str, Any]:
        """
        คำนวณตัวชี้วัดทางเทคนิคอลสำหรับสัญลักษณ์ที่กำหนด
        
        Args:
            symbol: สัญลักษณ์คู่สกุลเงิน
            
        Returns:
            Dictionary ที่มีค่าตัวชี้วัดต่างๆ (EMA9, EMA21, SMA20, RSI14)
        """
        if symbol not in self.price_history or len(self.price_history[symbol]) < 22:
            return {
                'ema9': None,
                'ema21': None,
                'sma20': None,
                'rsi14': None
            }
        prices = self.price_history[symbol]
        ema9_values = calculate_ema(prices, 9)
        ema21_values = calculate_ema(prices, 21)
        sma20_values = calculate_sma(prices, 20)
        rsi14_values = calculate_rsi(prices, 14)
        return {
            'ema9': ema9_values[-1] if ema9_values and len(ema9_values) > 0 else None,
            'ema21': ema21_values[-1] if ema21_values and len(ema21_values) > 0 else None,
            'sma20': sma20_values[-1] if sma20_values and len(sma20_values) > 0 else None,
            'rsi14': rsi14_values[-1] if rsi14_values and len(rsi14_values) > 0 else None
        }
    
    def predict_next_price(self, symbol: str) -> Tuple[float, float]:
        """
        คาดการณ์การเปลี่ยนแปลงราคาในช่วงเวลาถัดไปพร้อมความมั่นใจ
        
        Args:
            symbol: สัญลักษณ์คู่สกุลเงิน
            
        Returns:
            Tuple ของ (forecast_pct, confidence)
        """
        if symbol not in self.price_history or len(self.price_history[symbol]) < 22:
            return 0.0, 0.0
        prices = self.price_history[symbol]
        indicators = self.calculate_indicators(symbol)
        if not all(indicators.values()):
            return 0.0, 0.0
        current_price = prices[-1]
        prev_price = prices[-2] if len(prices) >= 2 else current_price
        last_change_pct = ((current_price - prev_price) / prev_price) * 100
        ema_signal = 0.0
        rsi_signal = 0.0
        if indicators['ema9'] > indicators['ema21']:
            ema_signal = 1.0
        elif indicators['ema9'] < indicators['ema21']:
            ema_signal = -1.0
        rsi = indicators['rsi14']
        if rsi < 30:
            rsi_signal = 1.0
        elif rsi > 70:
            rsi_signal = -1.0
        forecast_pct = (last_change_pct * 0.3) + (ema_signal * 0.4) + (rsi_signal * 0.3)
        signal_agreement = abs(ema_signal + rsi_signal + (1 if last_change_pct > 0 else -1)) / 3.0
        confidence = 0.6 + (signal_agreement * 0.3)
        return forecast_pct, min(confidence, 0.9)
    
    def process_market_data(self, symbol: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        ประมวลผลข้อมูลตลาดเพื่อสร้างการคาดการณ์และสัญญาณ
        
        Args:
            symbol: สัญลักษณ์คู่สกุลเงินที่กำลังวิเคราะห์
            data: ข้อมูลแท่งเทียนล่าสุด
            
        Returns:
            สัญญาณที่สร้างขึ้น หรือ None ถ้าไม่มีสัญญาณใหม่
        """
        try:
            if data.get('is_closed', False):
                open_price = float(data.get('open', 0))
                close_price = float(data.get('close', 0))
                if open_price > 0:
                    self.update_price_history(symbol, close_price)
                    indicators = self.calculate_indicators(symbol)
                    forecast_pct, confidence = self.predict_next_price(symbol)
                    category = grade_signal(forecast_pct, confidence)
                    signal = {
                        'symbol': symbol,
                        'timestamp': data.get('close_time'),
                        'forecast_pct': forecast_pct,
                        'confidence': confidence,
                        'category': category,
                        'price': close_price,
                        'indicators': indicators
                    }
                    
                    try:
                        # เผยแพร่สัญญาณผ่าน Redis Pub/Sub
                        self.redis_client.publish(
                            REDIS_SIGNAL_CHANNEL, 
                            json.dumps(signal)
                        )
                        
                        # เก็บสัญญาณล่าสุดใน Redis
                        self.redis_client.set(
                            f"latest_signal:{symbol}", 
                            json.dumps(signal)
                        )
                        
                        # เก็บประวัติสัญญาณใน Redis
                        self.redis_client.lpush(
                            f"signal_history:{symbol}", 
                            json.dumps(signal)
                        )
                        self.redis_client.ltrim(f"signal_history:{symbol}", 0, 99)
                    except redis.RedisError as e:
                        print(f"⚠️ เกิดข้อผิดพลาด Redis ในการบันทึกสัญญาณ: {e}")
                    
                    # บันทึกสัญญาณลงใน InfluxDB
                    try:
                        self.influxdb_storage.store_signal(signal)
                        print(f"บันทึกสัญญาณลง InfluxDB สำเร็จ: {symbol} {category}")
                    except Exception as e:
                        print(f"เกิดข้อผิดพลาดในการบันทึกสัญญาณลง InfluxDB: {e}")
                        # ไม่ควรล้มเหลวเนื่องจาก InfluxDB ไม่พร้อมใช้งาน
                    
                    return signal
            return None
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการประมวลผลข้อมูลตลาด: {e}")
            return None
    
    def close(self):
        """ปิดการเชื่อมต่อกับ InfluxDB"""
        try:
            self.influxdb_storage.close()
            print("ปิดการเชื่อมต่อกับ InfluxDB")
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการปิดการเชื่อมต่อกับ InfluxDB: {e}")

# ตัวอย่างการใช้งาน
if __name__ == "__main__":
    print("Strong Buy:", grade_signal(1.5, 0.9))
    print("Weak Buy:", grade_signal(0.7, 0.7))
    print("Hold:", grade_signal(0.1, 0.6))
    print("Weak Sell:", grade_signal(-0.7, 0.7))
    print("Strong Sell:", grade_signal(-1.5, 0.9))
    print("Low Confidence:", grade_signal(2.0, 0.5))
    processor = SignalProcessor()
    for i in range(25):
        processor.update_price_history("BTCUSDT", 20000 + (i * 100))
    print("Indicators:", processor.calculate_indicators("BTCUSDT"))
    print("Prediction:", processor.predict_next_price("BTCUSDT"))
    processor.close()  # ปิดการเชื่อมต่อกับ InfluxDB