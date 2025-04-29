import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
import pandas as pd
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from dotenv import load_dotenv

# โหลด environment variables
load_dotenv()

# ตั้งค่าการเชื่อมต่อ InfluxDB
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "crypto_signals")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "crypto_data")


class InfluxDBStorage:
    """คลาสสำหรับจัดการการเก็บข้อมูลใน InfluxDB"""

    def __init__(self):
        """เริ่มต้นการเชื่อมต่อกับ InfluxDB"""
        try:
            self.client = InfluxDBClient(
                url=INFLUXDB_URL,
                token=INFLUXDB_TOKEN,
                org=INFLUXDB_ORG
            )
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            self.query_api = self.client.query_api()
            self.delete_api = self.client.delete_api()
            # เช็คการเชื่อมต่อด้วยการทดสอบ query
            self.query_api.query(f'from(bucket:"{INFLUXDB_BUCKET}") |> range(start: -1m) |> limit(n:1)')
            print(f"✅ เชื่อมต่อกับ InfluxDB สำเร็จที่ {INFLUXDB_URL}")
            self.connected = True
        except Exception as e:
            print(f"⚠️ ไม่สามารถเชื่อมต่อกับ InfluxDB ได้: {e}")
            # ยังคงเก็บคลาสไว้แต่ตั้งค่า flag ว่าไม่ได้เชื่อมต่อ
            self.client = None
            self.write_api = None
            self.query_api = None
            self.delete_api = None
            self.connected = False

    def store_kline_data(self, symbol: str, data: Dict[str, Any]) -> None:
        """
        บันทึกข้อมูล OHLCV (kline) ลงใน InfluxDB
        
        Args:
            symbol: สัญลักษณ์คู่เทรด เช่น BTCUSDT
            data: ข้อมูล kline ที่ต้องการบันทึก
        """
        # สร้าง point สำหรับ InfluxDB
        point = Point("klines") \
            .tag("symbol", symbol) \
            .tag("interval", data.get("interval", "2m")) \
            .field("open", float(data.get("open", 0))) \
            .field("high", float(data.get("high", 0))) \
            .field("low", float(data.get("low", 0))) \
            .field("close", float(data.get("close", 0))) \
            .field("volume", float(data.get("volume", 0))) \
            .field("trades", int(data.get("number_of_trades", 0))) \
            .time(int(data.get("close_time", datetime.now().timestamp() * 1000)))

        # บันทึกลง InfluxDB
        try:
            self.write_api.write(bucket=INFLUXDB_BUCKET, record=point)
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการบันทึกข้อมูล kline: {e}")
            raise

    def store_signal(self, signal: Dict[str, Any]) -> None:
        """
        บันทึกข้อมูลสัญญาณการเทรดลงใน InfluxDB
        
        Args:
            signal: ข้อมูลสัญญาณการเทรดที่ต้องการบันทึก
        """
        # ตรวจสอบว่ามีการเชื่อมต่อกับ InfluxDB หรือไม่
        if not hasattr(self, 'connected') or not self.connected:
            print("⚠️ ไม่มีการเชื่อมต่อกับ InfluxDB - ข้ามการบันทึกสัญญาณ")
            return

        # สร้าง point สำหรับ InfluxDB
        point = Point("signals") \
            .tag("symbol", signal.get("symbol", "unknown")) \
            .tag("category", signal.get("category", "unknown")) \
            .field("price", float(signal.get("price", 0))) \
            .field("forecast_pct", float(signal.get("forecast_pct", 0))) \
            .field("confidence", float(signal.get("confidence", 0)))

        # เพิ่มตัวชี้วัดถ้ามี
        if "indicators" in signal and isinstance(signal["indicators"], dict):
            indicators = signal["indicators"]
            for key, value in indicators.items():
                if value is not None:
                    point = point.field(key, float(value))

        # ตั้งค่าเวลา
        timestamp = signal.get("timestamp")
        if timestamp:
            point = point.time(int(timestamp))

        # บันทึกลง InfluxDB
        try:
            self.write_api.write(bucket=INFLUXDB_BUCKET, record=point)
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการบันทึกข้อมูลสัญญาณ: {e}")
            # ตั้งค่า flag เพื่อหลีกเลี่ยงการพยายามบันทึกในอนาคต
            self.connected = False

    def get_historical_klines(self, symbol: str, interval: str = "2m", 
                             start_time: Optional[int] = None, 
                             end_time: Optional[int] = None,
                             limit: int = 1000) -> pd.DataFrame:
        """
        ดึงข้อมูลประวัติ kline จาก InfluxDB
        
        Args:
            symbol: สัญลักษณ์คู่เทรด เช่น BTCUSDT
            interval: ช่วงเวลาของแท่งเทียน (2m, 1h, 1d, ฯลฯ)
            start_time: timestamp เริ่มต้น (มิลลิวินาที)
            end_time: timestamp สิ้นสุด (มิลลิวินาที)
            limit: จำนวนแท่งเทียนสูงสุดที่ต้องการ
            
        Returns:
            DataFrame ที่มีข้อมูลประวัติ OHLCV
        """
        # สร้าง query
        query_start = ""
        if start_time:
            start_time_str = datetime.fromtimestamp(start_time / 1000).strftime('%Y-%m-%dT%H:%M:%SZ')
            query_start = f'|> range(start: {start_time_str}'
        else:
            query_start = f'|> range(start: -30d'
            
        if end_time:
            end_time_str = datetime.fromtimestamp(end_time / 1000).strftime('%Y-%m-%dT%H:%M:%SZ')
            query_start += f', stop: {end_time_str})'
        else:
            query_start += ')'
            
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
          {query_start}
          |> filter(fn: (r) => r._measurement == "klines")
          |> filter(fn: (r) => r.symbol == "{symbol}")
          |> filter(fn: (r) => r.interval == "{interval}")
          |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"], desc: false)
          |> limit(n: {limit})
        '''
        
        # ทำ query
        try:
            result = self.query_api.query_data_frame(query)
            
            # ถ้าไม่พบข้อมูล
            if result is None or (isinstance(result, list) and len(result) == 0) or result.empty:
                return pd.DataFrame()
            
            # จัดรูปแบบผลลัพธ์
            if isinstance(result, list):
                result = pd.concat(result)
                
            # ลบคอลัมน์ที่ไม่จำเป็น
            if '_measurement' in result.columns:
                result = result.drop(columns=['_measurement', 'result', 'table', '_start', '_stop'])
                
            # เปลี่ยนชื่อคอลัมน์
            result = result.rename(columns={'_time': 'timestamp'})
            
            return result
            
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการดึงข้อมูลประวัติ kline: {e}")
            return pd.DataFrame()

    def get_historical_signals(self, symbol: str, 
                              start_time: Optional[int] = None, 
                              end_time: Optional[int] = None,
                              limit: int = 1000) -> pd.DataFrame:
        """
        ดึงข้อมูลประวัติสัญญาณจาก InfluxDB
        
        Args:
            symbol: สัญลักษณ์คู่เทรด เช่น BTCUSDT
            start_time: timestamp เริ่มต้น (มิลลิวินาที)
            end_time: timestamp สิ้นสุด (มิลลิวินาที)
            limit: จำนวนสัญญาณสูงสุดที่ต้องการ
            
        Returns:
            DataFrame ที่มีข้อมูลประวัติสัญญาณ
        """
        # สร้าง query
        query_start = ""
        if start_time:
            start_time_str = datetime.fromtimestamp(start_time / 1000).strftime('%Y-%m-%dT%H:%M:%SZ')
            query_start = f'|> range(start: {start_time_str}'
        else:
            query_start = f'|> range(start: -30d'
            
        if end_time:
            end_time_str = datetime.fromtimestamp(end_time / 1000).strftime('%Y-%m-%dT%H:%M:%SZ')
            query_start += f', stop: {end_time_str})'
        else:
            query_start += ')'
            
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
          {query_start}
          |> filter(fn: (r) => r._measurement == "signals")
          |> filter(fn: (r) => r.symbol == "{symbol}")
          |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"], desc: false)
          |> limit(n: {limit})
        '''
        
        # ทำ query
        try:
            result = self.query_api.query_data_frame(query)
            
            # ถ้าไม่พบข้อมูล
            if result is None or (isinstance(result, list) and len(result) == 0) or result.empty:
                return pd.DataFrame()
            
            # จัดรูปแบบผลลัพธ์
            if isinstance(result, list):
                result = pd.concat(result)
                
            # ลบคอลัมน์ที่ไม่จำเป็น
            if '_measurement' in result.columns:
                result = result.drop(columns=['_measurement', 'result', 'table', '_start', '_stop'])
                
            # เปลี่ยนชื่อคอลัมน์
            result = result.rename(columns={'_time': 'timestamp'})
            
            return result
            
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการดึงข้อมูลประวัติสัญญาณ: {e}")
            return pd.DataFrame()

    def delete_old_data(self, retention_days: int = 30) -> None:
        """
        ลบข้อมูลเก่าที่เกินระยะเวลาที่กำหนด
        
        Args:
            retention_days: จำนวนวันที่ต้องการเก็บข้อมูล
        """
        try:
            start = datetime.utcfromtimestamp(0).strftime('%Y-%m-%dT%H:%M:%SZ')
            stop = (datetime.now() - pd.Timedelta(days=retention_days)).strftime('%Y-%m-%dT%H:%M:%SZ')
            
            # ลบข้อมูล kline เก่า
            self.delete_api.delete(
                start=start,
                stop=stop,
                predicate='_measurement="klines"',
                bucket=INFLUXDB_BUCKET
            )
            
            # ลบข้อมูลสัญญาณเก่า
            self.delete_api.delete(
                start=start,
                stop=stop,
                predicate='_measurement="signals"',
                bucket=INFLUXDB_BUCKET
            )
            
            print(f"ลบข้อมูลเก่าเกิน {retention_days} วันเรียบร้อยแล้ว")
            
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการลบข้อมูลเก่า: {e}")

    def close(self) -> None:
        """ปิดการเชื่อมต่อกับ InfluxDB"""
        if self.client:
            self.client.close()
            
            
# ตัวอย่างการใช้งาน
if __name__ == "__main__":
    # ตัวอย่างข้อมูล kline
    kline_data = {
        "symbol": "BTCUSDT",
        "interval": "2m",
        "start_time": 1619712000000,
        "close_time": 1619712120000,
        "open": 54000.0,
        "high": 54100.0,
        "low": 53900.0,
        "close": 54050.0,
        "volume": 15.5,
        "number_of_trades": 125,
        "is_closed": True
    }
    
    # ตัวอย่างข้อมูลสัญญาณ
    signal_data = {
        "symbol": "BTCUSDT",
        "timestamp": 1619712120000,
        "forecast_pct": 0.75,
        "confidence": 0.82,
        "category": "weak buy",
        "price": 54050.0,
        "indicators": {
            "ema9": 53980.5,
            "ema21": 53750.2,
            "sma20": 53800.1,
            "rsi14": 62.5
        }
    }
    
    # ใช้งาน
    storage = InfluxDBStorage()
    
    # บันทึกข้อมูลตัวอย่าง
    try:
        storage.store_kline_data("BTCUSDT", kline_data)
        storage.store_signal(signal_data)
        print("บันทึกข้อมูลตัวอย่างสำเร็จ")
        
        # ดึงข้อมูล
        klines = storage.get_historical_klines("BTCUSDT", "2m", limit=10)
        signals = storage.get_historical_signals("BTCUSDT", limit=5)
        
        print("\nข้อมูล kline ล่าสุด:")
        if not klines.empty:
            print(klines.head())
        else:
            print("ไม่พบข้อมูล kline")
            
        print("\nข้อมูลสัญญาณล่าสุด:")
        if not signals.empty:
            print(signals.head())
        else:
            print("ไม่พบข้อมูลสัญญาณ")
            
    except Exception as e:
        print(f"เกิดข้อผิดพลาด: {e}")
    finally:
        storage.close()