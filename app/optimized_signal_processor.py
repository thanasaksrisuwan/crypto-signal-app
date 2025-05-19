import numpy as np
from enum import Enum
from typing import Tuple, Dict, Any, List, Optional
import pandas as pd
import redis
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from .cache_manager import cache_manager
from .influxdb_storage import InfluxDBStorage
from .logger import LoggerFactory, log_execution_time, error_logger, MetricsLogger

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

class OptimizedSignalProcessor:
    """คลาสประมวลผลสัญญาณที่มีการเพิ่มประสิทธิภาพด้วย Redis caching และการจัดการข้อผิดพลาดที่สมบูรณ์"""
    
    def __init__(self):
        """เริ่มต้นตัวประมวลผลสัญญาณพร้อมการตั้งค่า logging"""
        self.logger = LoggerFactory.get_logger('signal_processor')
        self.metrics = MetricsLogger('signal_processor')
        
        try:
            self.redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30
            )
            self.logger.info("เชื่อมต่อ Redis สำเร็จ")
        except redis.RedisError as e:
            self.logger.error(f"ไม่สามารถเชื่อมต่อ Redis ได้: {e}")
            error_logger.log_error(e, {'component': 'signal_processor', 'connection': 'redis'})
            raise
            
        try:
            self.influxdb_storage = InfluxDBStorage()
            self.logger.info("เชื่อมต่อ InfluxDB สำเร็จ")
        except Exception as e:
            self.logger.error(f"ไม่สามารถเชื่อมต่อ InfluxDB ได้: {e}")
            error_logger.log_error(e, {'component': 'signal_processor', 'connection': 'influxdb'})
            raise
            
        self.cache = cache_manager
        self.price_history = {}
        self.max_history_length = 500
        self.max_symbols = 100
        
        # เริ่มต้นเมตริก
        self.metrics.record_metric('initialization', {
            'max_history_length': self.max_history_length,
            'max_symbols': self.max_symbols,
            'timestamp': datetime.now().isoformat()
        })

    @log_execution_time()
    def update_price_history(self, symbol: str, price: float) -> None:
        """อัพเดทประวัติราคาพร้อม memory management และ logging"""
        try:
            if len(self.price_history) >= self.max_symbols and symbol not in self.price_history:
                oldest_symbol = next(iter(self.price_history))
                del self.price_history[oldest_symbol]
                self.logger.info(f"ลบประวัติราคาของ {oldest_symbol} เพื่อประหยัดหน่วยความจำ")
            
            if symbol not in self.price_history:
                self.price_history[symbol] = []
                self.logger.debug(f"เริ่มเก็บประวัติราคาสำหรับ {symbol}")
            
            self.price_history[symbol].append(price)
            
            if len(self.price_history[symbol]) > self.max_history_length:
                self.price_history[symbol] = self.price_history[symbol][-self.max_history_length:]
                self.logger.debug(f"ตัดประวัติราคาของ {symbol} เหลือ {self.max_history_length} รายการ")
                
            # บันทึกเมตริก
            self.metrics.record_metric(f'price_history_{symbol}', {
                'length': len(self.price_history[symbol]),
                'latest_price': price,
                'timestamp': datetime.now().isoformat()
            })
                
        except Exception as e:
            self.logger.error(f"ข้อผิดพลาดในการอัพเดทประวัติราคา: {e}")
            error_logger.log_error(e, {
                'component': 'signal_processor',
                'method': 'update_price_history',
                'symbol': symbol,
                'price': price
            })
            raise

    @log_execution_time()
    def calculate_indicators_batch(self, symbol: str, prices: List[float]) -> Dict[str, Any]:
        """คำนวณตัวบ่งชี้ทางเทคนิคทั้งหมดพร้อมการจัดการข้อผิดพลาด"""
        try:
            start_time = datetime.now()
            
            if len(prices) < 22:
                self.logger.warning(f"ข้อมูลราคาไม่เพียงพอสำหรับ {symbol} ({len(prices)} < 22)")
                return {
                    'ema9': None,
                    'ema21': None,
                    'sma20': None,
                    'rsi14': None
                }
            
            # คำนวณตัวบ่งชี้
            prices_series = pd.Series(prices)
            
            ema9 = prices_series.ewm(span=9, adjust=False).mean().iloc[-1]
            ema21 = prices_series.ewm(span=21, adjust=False).mean().iloc[-1]
            sma20 = prices_series.rolling(window=20).mean().iloc[-1]
            
            deltas = np.diff(prices)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            
            avg_gain = np.mean(gains[:14])
            avg_loss = np.mean(losses[:14])
            
            for i in range(14, len(deltas)):
                avg_gain = (avg_gain * 13 + gains[i]) / 14
                avg_loss = (avg_loss * 13 + losses[i]) / 14
            
            rs = avg_gain / (avg_loss + 1e-10)
            rsi = 100 - (100 / (1 + rs))
            
            result = {
                'ema9': float(ema9),
                'ema21': float(ema21),
                'sma20': float(sma20),
                'rsi14': float(rsi)
            }
            
            # บันทึกเมตริก
            execution_time = (datetime.now() - start_time).total_seconds()
            self.metrics.record_metric(f'indicators_calculation_{symbol}', {
                'execution_time': execution_time,
                'indicators': result,
                'timestamp': datetime.now().isoformat()
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"ข้อผิดพลาดในการคำนวณตัวบ่งชี้: {e}")
            error_logger.log_error(e, {
                'component': 'signal_processor',
                'method': 'calculate_indicators_batch',
                'symbol': symbol,
                'prices_length': len(prices)
            })
            return {
                'ema9': None,
                'ema21': None,
                'sma20': None,
                'rsi14': None
            }

    @log_execution_time()
    def process_market_data(self, symbol: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """ประมวลผลข้อมูลตลาดพร้อมการจัดการข้อผิดพลาดที่สมบูรณ์"""
        try:
            start_time = datetime.now()
            
            # ตรวจสอบแคช
            cache_key = f"market_data:{symbol}"
            cached_result = self.cache.get_market_data(symbol, "processed")
            
            if cached_result:
                if cached_result.get('timestamp', 0) >= data.get('close_time', 0):
                    self.logger.debug(f"ใช้ข้อมูลจากแคชสำหรับ {symbol}")
                    return cached_result
            
            if not data.get('is_closed', False):
                return None
                
            # ประมวลผลข้อมูล
            close_price = float(data.get('close', 0))
            if close_price <= 0:
                self.logger.warning(f"ราคาปิดไม่ถูกต้องสำหรับ {symbol}: {close_price}")
                return None
                
            self.update_price_history(symbol, close_price)
            
            indicators = self.calculate_indicators_batch(symbol, self.price_history[symbol])
            forecast_pct, confidence = self.predict_next_price(symbol)
            category = self.grade_signal(forecast_pct, confidence)
            
            signal = {
                'symbol': symbol,
                'timestamp': data.get('close_time'),
                'forecast_pct': forecast_pct,
                'confidence': confidence,
                'category': category,
                'price': close_price,
                'indicators': indicators
            }
            
            # บันทึกข้อมูลแบบ batch
            try:
                pipeline = self.redis_client.pipeline()
                pipeline.publish(REDIS_SIGNAL_CHANNEL, json.dumps(signal))
                pipeline.set(f"latest_signal:{symbol}", json.dumps(signal))
                pipeline.lpush(f"signal_history:{symbol}", json.dumps(signal))
                pipeline.ltrim(f"signal_history:{symbol}", 0, 99)
                pipeline.execute()
            except redis.RedisError as e:
                self.logger.error(f"ข้อผิดพลาดในการบันทึกข้อมูลใน Redis: {e}")
                error_logger.log_error(e, {
                    'component': 'signal_processor',
                    'method': 'process_market_data',
                    'operation': 'redis_batch_write',
                    'symbol': symbol
                })
            
            # บันทึกลง InfluxDB
            try:
                self.influxdb_storage.store_signal(signal)
            except Exception as e:
                self.logger.error(f"ข้อผิดพลาดในการบันทึกข้อมูลใน InfluxDB: {e}")
                error_logger.log_error(e, {
                    'component': 'signal_processor',
                    'method': 'process_market_data',
                    'operation': 'influxdb_write',
                    'symbol': symbol
                })
            
            # บันทึกลงแคช
            self.cache.set_market_data(cache_key, "processed", signal, ttl=300)
            
            # บันทึกเมตริก
            execution_time = (datetime.now() - start_time).total_seconds()
            self.metrics.record_metric(f'market_data_processing_{symbol}', {
                'execution_time': execution_time,
                'signal_category': category,
                'timestamp': datetime.now().isoformat()
            })
            
            return signal
            
        except Exception as e:
            self.logger.error(f"ข้อผิดพลาดในการประมวลผลข้อมูลตลาด: {e}")
            error_logger.log_error(e, {
                'component': 'signal_processor',
                'method': 'process_market_data',
                'symbol': symbol,
                'data': data
            })
            return None

    def predict_next_price(self, symbol: str) -> Tuple[float, float]:
        """คาดการณ์ราคาถัดไปพร้อม caching"""
        try:
            cache_key = f"prediction:{symbol}"
            cached_prediction = self.cache.get_market_data(cache_key, "")
            
            if cached_prediction:
                return cached_prediction['forecast_pct'], cached_prediction['confidence']
            
            if symbol not in self.price_history or len(self.price_history[symbol]) < 22:
                return 0.0, 0.0
                
            prices = self.price_history[symbol]
            indicators = self.calculate_indicators_batch(symbol, prices)
            
            if not all(indicators.values()):
                return 0.0, 0.0
                
            current_price = prices[-1]
            prev_price = prices[-2]
            last_change_pct = ((current_price - prev_price) / prev_price) * 100
            
            # คำนวณสัญญาณจากตัวบ่งชี้
            ema_signal = 1.0 if indicators['ema9'] > indicators['ema21'] else -1.0 if indicators['ema9'] < indicators['ema21'] else 0.0
            rsi_signal = 1.0 if indicators['rsi14'] < 30 else -1.0 if indicators['rsi14'] > 70 else 0.0
            
            # คำนวณการคาดการณ์
            forecast_pct = (last_change_pct * 0.3) + (ema_signal * 0.4) + (rsi_signal * 0.3)
            signal_agreement = abs(ema_signal + rsi_signal + (1 if last_change_pct > 0 else -1)) / 3.0
            confidence = min(0.6 + (signal_agreement * 0.3), 0.9)
            
            # บันทึกผลลัพธ์ลงแคช
            self.cache.set_market_data(cache_key, "", {
                'forecast_pct': forecast_pct,
                'confidence': confidence
            }, ttl=300)  # แคช 5 นาที
            
            return forecast_pct, confidence
            
        except Exception as e:
            self.logger.error(f"ข้อผิดพลาดในการคาดการณ์ราคา: {e}")
            error_logger.log_error(e, {
                'component': 'signal_processor',
                'method': 'predict_next_price',
                'symbol': symbol
            })
            return 0.0, 0.0

    @staticmethod
    def grade_signal(forecast_pct: float, confidence: float) -> str:
        """จัดเกรดสัญญาณการซื้อขาย"""
        if not (0 <= confidence <= 1.0):
            return SignalCategory.HOLD
            
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
    
    def cleanup(self):
        """ทำความสะอาด resources พร้อมการจัดการข้อผิดพลาด"""
        try:
            # บันทึกเมตริกสุดท้าย
            self.metrics.record_metric('cleanup', {
                'price_history_size': len(self.price_history),
                'timestamp': datetime.now().isoformat()
            })
            
            # ล้างแคชเก่า
            self.cache.cleanup_old_keys("market:*")
            self.cache.cleanup_old_keys("prediction:*")
            
            # ปิดการเชื่อมต่อ
            self.influxdb_storage.close()
            self.redis_client.close()
            
            self.logger.info("ทำความสะอาด resources เสร็จสมบูรณ์")
            
        except Exception as e:
            self.logger.error(f"ข้อผิดพลาดในการ cleanup: {e}")
            error_logger.log_error(e, {
                'component': 'signal_processor',
                'method': 'cleanup'
            })
            raise

# สร้าง singleton instance
signal_processor = OptimizedSignalProcessor()
