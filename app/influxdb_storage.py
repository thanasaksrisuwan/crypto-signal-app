import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
import pandas as pd
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

import os
import sys

# นำเข้าโมดูลจัดการตัวแปรสภาพแวดล้อม
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
import env_manager as env

# ตั้งค่าการเชื่อมต่อ InfluxDB
influxdb_config = env.get_influxdb_config()


class InfluxDBStorage:
    """คลาสสำหรับจัดการการเก็บข้อมูลใน InfluxDB พร้อม batch processing และ connection pooling"""

    def __init__(self, batch_size: int = 5000, flush_interval: int = 10000):
        """
        เริ่มต้นการเชื่อมต่อกับ InfluxDB พร้อมการตั้งค่า batch
        
        Args:
            batch_size: จำนวนข้อมูลสูงสุดต่อ batch
            flush_interval: ระยะเวลา (ms) ในการ flush batch อัตโนมัติ
        """
        try:            from influxdb_client.client.write_api import ASYNCHRONOUS
            
            self.client = InfluxDBClient(
                url=influxdb_config["url"],
                token=influxdb_config["token"],
                org=influxdb_config["org"],
                enable_gzip=True  # เปิดใช้การบีบอัดข้อมูล
            )
            
            # ใช้ ASYNCHRONOUS write API พร้อม batching
            self.write_api = self.client.write_api(
                write_options=ASYNCHRONOUS,
                batch_size=batch_size,
                flush_interval=flush_interval
            )
            
            self.query_api = self.client.query_api()
            self.delete_api = self.client.delete_api()
            
            # สร้าง connection pool
            self._setup_connection_pool()
            
            print(f"✅ เชื่อมต่อกับ InfluxDB สำเร็จที่ {INFLUXDB_URL}")
            self.connected = True
            
        except Exception as e:
            print(f"⚠️ ไม่สามารถเชื่อมต่อกับ InfluxDB ได้: {e}")
            self.client = None
            self.write_api = None
            self.query_api = None
            self.delete_api = None
            self.connected = False
            
    def _setup_connection_pool(self):
        """ตั้งค่า connection pool สำหรับ query"""
        self.query_clients = []
        MAX_POOL_SIZE = 5
        
        for _ in range(MAX_POOL_SIZE):
            client = InfluxDBClient(
                url=INFLUXDB_URL,
                token=INFLUXDB_TOKEN,
                org=INFLUXDB_ORG,
                enable_gzip=True
            )
            self.query_clients.append(client)
        
        self.current_client_index = 0
        
    def _get_next_client(self):
        """เลือก client ถัดไปจาก pool"""
        client = self.query_clients[self.current_client_index]
        self.current_client_index = (self.current_client_index + 1) % len(self.query_clients)
        return client
        
    def store_kline_data(self, symbol: str, data_points: List[Dict[str, Any]]) -> None:
        """
        บันทึกข้อมูล OHLCV (kline) แบบ batch ลงใน InfluxDB
        
        Args:
            symbol: สัญลักษณ์คู่เหรียญ
            data_points: รายการข้อมูล kline
        """
        if not self.connected:
            return
            
        points = []
        for data in data_points:
            point = Point("kline_data") \
                .tag("symbol", symbol) \
                .field("open", float(data["open"])) \
                .field("high", float(data["high"])) \
                .field("low", float(data["low"])) \
                .field("close", float(data["close"])) \
                .field("volume", float(data["volume"])) \
                .time(datetime.fromtimestamp(int(data["timestamp"]) / 1000))
            points.append(point)
            
        try:
            self.write_api.write(bucket=INFLUXDB_BUCKET, record=points)
        except Exception as e:
            print(f"⚠️ ไม่สามารถบันทึกข้อมูล kline ได้: {e}")
            
    def query_market_data(self, symbol: str, start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """
        ดึงข้อมูลตลาดโดยใช้ connection pool
        
        Args:
            symbol: สัญลักษณ์คู่เหรียญ
            start_time: เวลาเริ่มต้น
            end_time: เวลาสิ้นสุด
        """
        if not self.connected:
            return pd.DataFrame()
            
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: {start_time.isoformat()}Z, stop: {end_time.isoformat()}Z)
            |> filter(fn: (r) => r["symbol"] == "{symbol}")
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        
        try:
            client = self._get_next_client()
            result = client.query_api().query_data_frame(query, org=INFLUXDB_ORG)
            return result
        except Exception as e:
            print(f"⚠️ ไม่สามารถดึงข้อมูลตลาดได้: {e}")
            return pd.DataFrame()
            
    def close(self):
        """ปิดการเชื่อมต่อและ resource ทั้งหมด"""
        if self.write_api:
            self.write_api.close()
        if self.client:
            self.client.close()
        for client in self.query_clients:
            client.close()
            
            
# ตัวอย่างการใช้งาน
if __name__ == "__main__":
    # ตัวอย่างข้อมูล kline
    kline_data = [
        {
            "timestamp": 1619712000000,
            "open": 54000.0,
            "high": 54100.0,
            "low": 53900.0,
            "close": 54050.0,
            "volume": 15.5
        },
        {
            "timestamp": 1619712060000,
            "open": 54050.0,
            "high": 54150.0,
            "low": 54000.0,
            "close": 54100.0,
            "volume": 20.0
        }
    ]
    
    # ใช้งาน
    storage = InfluxDBStorage()
    
    # บันทึกข้อมูลตัวอย่าง
    try:
        storage.store_kline_data("BTCUSDT", kline_data)
        print("บันทึกข้อมูลตัวอย่างสำเร็จ")
        
        # ดึงข้อมูล
        start_time = datetime.fromtimestamp(1619712000)
        end_time = datetime.fromtimestamp(1619712120)
        market_data = storage.query_market_data("BTCUSDT", start_time, end_time)
        
        print("\nข้อมูลตลาด:")
        if not market_data.empty:
            print(market_data.head())
        else:
            print("ไม่พบข้อมูลตลาด")
            
    except Exception as e:
        print(f"เกิดข้อผิดพลาด: {e}")
    finally:
        storage.close()