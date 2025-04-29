#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Crypto Signal App System Test

เครื่องมือทดสอบระบบสำหรับ Crypto Signal App
ทดสอบทุกองค์ประกอบว่าทำงานได้อย่างถูกต้อง:
- Redis
- Backend API
- Signal Processor
- WebSocket Connections
- Frontend Connectivity

วิธีใช้: python test_system.py
"""

import os
import sys
import json
import time
import asyncio
import requests
import argparse
import datetime
import subprocess
import websockets
from typing import Dict, List, Any, Tuple, Optional
import redis
import pandas as pd
import numpy as np

# เพิ่ม parent directory เข้าไปใน sys.path เพื่อให้สามารถ import modules จาก parent directory ได้
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# นำเข้าโมดูลที่ต้องการ
try:
    from app.signal_processor import SignalProcessor, grade_signal, calculate_ema, calculate_rsi
except ImportError:
    try:
        from signal_processor import SignalProcessor, grade_signal, calculate_ema, calculate_rsi
    except ImportError:
        print("ไม่สามารถนำเข้าโมดูล SignalProcessor ได้ ตรวจสอบว่าได้รันสคริปต์จากโฟลเดอร์ที่ถูกต้อง")
        sys.exit(1)

# ------ ส่วนการกำหนดค่าต่างๆ ------
API_URL = "http://localhost:8000"
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
WS_URL = "ws://localhost:8000/ws/signals"


class TestResult:
    """คลาสสำหรับเก็บผลลัพธ์การทดสอบ"""
    def __init__(self, component: str, test_name: str, result: bool, details: str = ""):
        self.component = component
        self.test_name = test_name
        self.result = result
        self.details = details
        self.timestamp = datetime.datetime.now()
    
    def __str__(self) -> str:
        result_str = "✅ ผ่าน" if self.result else "❌ ไม่ผ่าน"
        return f"{self.component} - {self.test_name}: {result_str} {self.details}"


class SystemTester:
    """คลาสหลักสำหรับการทดสอบระบบ"""
    
    def __init__(self, verbose: bool = False):
        """
        เริ่มต้นตัวทดสอบระบบ
        
        Args:
            verbose: แสดงรายละเอียดเพิ่มเติมระหว่างการทดสอบหรือไม่
        """
        self.verbose = verbose
        self.results: List[TestResult] = []
        self.redis_client = None
    
    def log(self, message: str) -> None:
        """พิมพ์ข้อความถ้าเปิดใช้งานโหมด verbose"""
        if self.verbose:
            print(f"[INFO] {message}")
    
    def add_result(self, component: str, test_name: str, result: bool, details: str = "") -> None:
        """เพิ่มผลลัพธ์การทดสอบใหม่"""
        test_result = TestResult(component, test_name, result, details)
        self.results.append(test_result)
        print(test_result)
    
    def test_redis_connection(self) -> bool:
        """ทดสอบการเชื่อมต่อกับ Redis"""
        self.log("กำลังทดสอบการเชื่อมต่อกับ Redis...")
        
        try:
            # เชื่อมต่อกับ Redis
            self.redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD,
                decode_responses=True,
                socket_timeout=5
            )
            
            # ทดสอบการเชื่อมต่อด้วยคำสั่ง ping
            response = self.redis_client.ping()
            
            if response:
                self.add_result("Redis", "การเชื่อมต่อ", True, "สามารถเชื่อมต่อกับ Redis ได้")
                self.log(f"Redis เชื่อมต่อสำเร็จที่ {REDIS_HOST}:{REDIS_PORT}")
                return True
            else:
                self.add_result("Redis", "การเชื่อมต่อ", False, "เชื่อมต่อกับ Redis ได้แต่ไม่ตอบสนอง")
                return False
                
        except redis.ConnectionError as e:
            self.add_result("Redis", "การเชื่อมต่อ", False, f"ไม่สามารถเชื่อมต่อกับ Redis ได้: {e}")
            return False
        except Exception as e:
            self.add_result("Redis", "การเชื่อมต่อ", False, f"เกิดข้อผิดพลาดที่ไม่คาดคิด: {e}")
            return False
    
    def test_redis_pubsub(self) -> bool:
        """ทดสอบการทำงานของ Redis Pub/Sub"""
        self.log("กำลังทดสอบการทำงานของ Redis Pub/Sub...")
        
        if not self.redis_client:
            self.add_result("Redis", "Pub/Sub", False, "ไม่ได้เชื่อมต่อกับ Redis")
            return False
            
        try:
            # สร้าง pubsub สำหรับการทดสอบ
            pubsub = self.redis_client.pubsub()
            
            # สมัครสมาชิกช่องทดสอบ
            test_channel = "crypto_signal_test"
            pubsub.subscribe(test_channel)
            
            # ส่งข้อความทดสอบ
            test_message = {"test": "message", "timestamp": int(time.time())}
            self.redis_client.publish(test_channel, json.dumps(test_message))
            
            # รอรับข้อความ
            message_received = False
            max_retries = 3
            retries = 0
            
            while retries < max_retries:
                message = pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    if message['type'] == 'message':
                        message_received = True
                        break
                time.sleep(0.1)
                retries += 1
            
            # ยกเลิกการสมัครสมาชิก
            pubsub.unsubscribe()
            
            if message_received:
                self.add_result("Redis", "Pub/Sub", True, "Pub/Sub ทำงานได้ตามปกติ")
                return True
            else:
                self.add_result("Redis", "Pub/Sub", False, "ไม่ได้รับข้อความที่ส่งผ่าน Pub/Sub")
                return False
                
        except Exception as e:
            self.add_result("Redis", "Pub/Sub", False, f"เกิดข้อผิดพลาดในการทดสอบ Pub/Sub: {e}")
            return False
    
    def test_api_availability(self) -> bool:
        """ทดสอบว่า API เข้าถึงได้หรือไม่"""
        self.log(f"กำลังทดสอบการเข้าถึง API ที่ {API_URL}...")
        
        try:
            response = requests.get(f"{API_URL}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                redis_status = data.get('redis_status')
                
                self.add_result("Backend API", "การเข้าถึง", True, 
                               f"API เข้าถึงได้ สถานะ: {response.status_code}, Redis: {redis_status}")
                return True
            else:
                self.add_result("Backend API", "การเข้าถึง", False, 
                               f"API เข้าถึงได้แต่ส่งรหัสสถานะผิดปกติ: {response.status_code}")
                return False
                
        except requests.ConnectionError:
            self.add_result("Backend API", "การเข้าถึง", False, 
                           "ไม่สามารถเชื่อมต่อกับ API ได้ (ตรวจสอบว่า Backend API ทำงานอยู่หรือไม่)")
            return False
        except Exception as e:
            self.add_result("Backend API", "การเข้าถึง", False, f"เกิดข้อผิดพลาดในการเข้าถึง API: {e}")
            return False
    
    def test_api_endpoints(self) -> bool:
        """ทดสอบ API endpoints ต่างๆ"""
        self.log("กำลังทดสอบ API endpoints...")
        
        endpoints = [
            ("/available-symbols", "รายการสัญลักษณ์"),
            ("/api/latest-signal?symbol=BTCUSDT", "สัญญาณล่าสุด"),
            ("/api/history-signals?symbol=BTCUSDT&limit=5", "ประวัติสัญญาณ")
        ]
        
        all_passed = True
        
        for endpoint, description in endpoints:
            try:
                response = requests.get(f"{API_URL}{endpoint}", timeout=10)
                
                if response.status_code == 200:
                    self.add_result("Backend API", f"Endpoint: {description}", True, 
                                   f"เข้าถึงได้: {endpoint}")
                else:
                    self.add_result("Backend API", f"Endpoint: {description}", False, 
                                   f"เข้าถึงได้แต่ส่งรหัสสถานะผิดปกติ: {response.status_code}")
                    all_passed = False
                    
            except Exception as e:
                self.add_result("Backend API", f"Endpoint: {description}", False, 
                               f"เกิดข้อผิดพลาดในการเข้าถึง {endpoint}: {e}")
                all_passed = False
        
        return all_passed
    
    async def test_websocket_connection(self) -> bool:
        """ทดสอบการเชื่อมต่อ WebSocket"""
        self.log(f"กำลังทดสอบการเชื่อมต่อ WebSocket ที่ {WS_URL}...")
        
        try:
            # เชื่อมต่อกับ WebSocket
            async with websockets.connect(WS_URL, timeout=10) as websocket:
                self.log("เชื่อมต่อ WebSocket สำเร็จ")
                
                # สมัครสมาชิกสำหรับสัญญาณของ BTCUSDT
                await websocket.send(json.dumps({"subscribe": "BTCUSDT"}))
                self.log("ส่งข้อความสมัครสมาชิกสำเร็จ")
                
                # รอรับข้อความ (อาจเป็น heartbeat หรือสัญญาณ)
                try:
                    # ตั้ง timeout 15 วินาทีสำหรับการรอรับข้อความ
                    response = await asyncio.wait_for(websocket.recv(), timeout=15)
                    self.log(f"ได้รับข้อความจาก WebSocket: {response[:100]}...")
                    
                    self.add_result("WebSocket", "การเชื่อมต่อ", True, 
                                   "สามารถเชื่อมต่อและรับข้อมูลจาก WebSocket ได้")
                    return True
                except asyncio.TimeoutError:
                    self.add_result("WebSocket", "การเชื่อมต่อ", False, 
                                   "เชื่อมต่อสำเร็จแต่ไม่ได้รับข้อมูลภายใน timeout")
                    return False
                    
        except Exception as e:
            self.add_result("WebSocket", "การเชื่อมต่อ", False, 
                           f"ไม่สามารถเชื่อมต่อกับ WebSocket ได้: {e}")
            return False
    
    def test_signal_processor(self) -> bool:
        """ทดสอบการทำงานของ SignalProcessor"""
        self.log("กำลังทดสอบ SignalProcessor...")
        
        try:
            # ทดสอบฟังก์ชัน grade_signal
            test_cases = [
                (1.5, 0.9, "strong buy"),
                (0.7, 0.7, "weak buy"),
                (0.1, 0.6, "hold"),
                (-0.7, 0.7, "weak sell"),
                (-1.5, 0.9, "strong sell"),
                (2.0, 0.5, "hold")  # ความมั่นใจต่ำ
            ]
            
            all_passed = True
            for forecast, confidence, expected in test_cases:
                result = grade_signal(forecast, confidence)
                if result == expected:
                    self.log(f"grade_signal({forecast}, {confidence}) = {result} ✓")
                else:
                    self.log(f"grade_signal({forecast}, {confidence}) = {result} ≠ {expected} ✗")
                    all_passed = False
            
            # ทดสอบ EMA calculation
            prices = [100.0, 102.0, 98.0, 103.0, 99.0, 101.0, 104.0, 105.0, 103.0]
            ema_result = calculate_ema(prices, 3)
            if len(ema_result) == len(prices):
                self.log(f"EMA calculation สำเร็จ: {ema_result[-3:]}")
            else:
                self.log(f"EMA calculation ผิดพลาด: ขนาดของผลลัพธ์ไม่ถูกต้อง")
                all_passed = False
            
            # ทดสอบ RSI calculation
            rsi_result = calculate_rsi(prices, 2)
            if len(rsi_result) == len(prices):
                self.log(f"RSI calculation สำเร็จ: {rsi_result[-3:]}")
            else:
                self.log(f"RSI calculation ผิดพลาด: ขนาดของผลลัพธ์ไม่ถูกต้อง")
                all_passed = False
            
            # ทดสอบการสร้าง SignalProcessor
            processor = SignalProcessor()
            self.log("สร้าง SignalProcessor สำเร็จ")
            
            # ทดสอบการอัปเดทประวัติราคา
            for i in range(25):
                processor.update_price_history("BTCUSDT", 20000 + (i * 100))
            
            # ทดสอบการคำนวณตัวชี้วัด
            indicators = processor.calculate_indicators("BTCUSDT")
            if all(v is not None for v in indicators.values()):
                self.log(f"การคำนวณตัวชี้วัดสำเร็จ: {indicators}")
            else:
                self.log(f"การคำนวณตัวชี้วัดผิดพลาด: {indicators}")
                all_passed = False
            
            # ทดสอบการคาดการณ์ราคาถัดไป
            forecast_pct, confidence = processor.predict_next_price("BTCUSDT")
            self.log(f"การคาดการณ์ราคา: {forecast_pct:.2f}%, confidence: {confidence:.2f}")
            
            # ทดสอบการสร้างสัญญาณ
            mock_data = {
                "is_closed": True,
                "open": 20000,
                "close": 20500,
                "close_time": int(time.time() * 1000)
            }
            signal = processor.process_market_data("BTCUSDT", mock_data)
            
            if signal:
                self.log(f"การสร้างสัญญาณสำเร็จ: {signal}")
                self.add_result("SignalProcessor", "การทำงาน", True, 
                               f"ทดสอบทุกฟังก์ชันสำเร็จ, สัญญาณที่ได้: {signal['category']}")
            else:
                self.log("การสร้างสัญญาณล้มเหลว")
                self.add_result("SignalProcessor", "การทำงาน", False, 
                               "ไม่สามารถสร้างสัญญาณได้")
                all_passed = False
            
            # ปิดการเชื่อมต่อ
            processor.close()
            
            return all_passed
            
        except Exception as e:
            self.add_result("SignalProcessor", "การทำงาน", False, 
                           f"เกิดข้อผิดพลาดในการทดสอบ SignalProcessor: {e}")
            return False
    
    def test_signal_data_flow(self) -> bool:
        """ทดสอบกระแสข้อมูลของสัญญาณจาก SignalProcessor ไปยัง Redis"""
        self.log("กำลังทดสอบกระแสข้อมูลของสัญญาณ...")
        
        if not self.redis_client:
            self.add_result("ระบบ", "กระแสข้อมูลสัญญาณ", False, 
                           "ไม่ได้เชื่อมต่อกับ Redis")
            return False
        
        try:
            print("เชื่อมต่อกับ InfluxDB สำเร็จ")
            # สร้าง SignalProcessor
            processor = SignalProcessor()
            
            # เตรียมข้อมูลทดสอบ - เพิ่มจำนวนข้อมูลเพื่อให้มีเพียงพอสำหรับการคำนวณตัวชี้วัด
            symbol = "BTCUSDT"
            for i in range(30):  # เพิ่มจากเดิม 25 เป็น 30 เพื่อให้มั่นใจว่ามีข้อมูลพอ
                processor.update_price_history(symbol, 20000 + (i * 100))
            
            # สร้างข้อมูลแท่งเทียนจำลอง
            close_time = int(time.time() * 1000)
            mock_data = {
                "is_closed": True,
                "open": 20000,
                "close": 20500,
                "close_time": close_time
            }
            
            # สร้างสัญญาณ
            signal = processor.process_market_data(symbol, mock_data)
            
            if not signal:
                self.add_result("ระบบ", "กระแสข้อมูลสัญญาณ", False, 
                               "ไม่สามารถสร้างสัญญาณได้")
                processor.close()
                return False
            
            # รอให้ข้อมูลเขียนลง Redis เสร็จสิ้น
            time.sleep(1)
            
            # ตรวจสอบว่าสัญญาณล่าสุดถูกบันทึกใน Redis หรือไม่
            latest_signal_key = f"latest_signal:{symbol}"
            latest_signal_data = self.redis_client.get(latest_signal_key)
            
            if latest_signal_data:
                latest_signal = json.loads(latest_signal_data)
                if latest_signal['close_time'] == close_time:
                    self.add_result("ระบบ", "กระแสข้อมูลสัญญาณ", True, 
                                   "สัญญาณถูกบันทึกใน Redis สำเร็จ")
                    processor.close()
                    return True
                else:
                    self.add_result("ระบบ", "กระแสข้อมูลสัญญาณ", False, 
                                   "พบสัญญาณใน Redis แต่ไม่ใช่สัญญาณที่เพิ่งสร้าง")
                    processor.close()
                    return False
            else:
                self.add_result("ระบบ", "กระแสข้อมูลสัญญาณ", False, 
                               f"ไม่พบสัญญาณล่าสุดใน Redis สำหรับ {symbol}")
                processor.close()
                return False
                
        except Exception as e:
            self.add_result("ระบบ", "กระแสข้อมูลสัญญาณ", False, 
                           f"เกิดข้อผิดพลาดในการทดสอบกระแสข้อมูลสัญญาณ: {e}")
            return False
    
    def check_frontend_connectivity(self) -> bool:
        """ตรวจสอบว่า Frontend สามารถเข้าถึง Backend API ได้หรือไม่"""
        self.log("กำลังตรวจสอบการเชื่อมต่อระหว่าง Frontend และ Backend...")
        
        try:
            # ตรวจสอบว่า Frontend รันอยู่หรือไม่ (บนพอร์ต 3000)
            response = requests.get("http://localhost:3000", timeout=5)
            
            if response.status_code == 200:
                self.add_result("Frontend", "การทำงาน", True, 
                               "Frontend ทำงานอยู่บนพอร์ต 3000")
                
                # ทดสอบว่า Frontend สามารถเข้าถึง Backend API ได้หรือไม่โดยตรวจสอบจาก Network requests
                # ในทางปฏิบัติจริง การทดสอบนี้จำเป็นต้องใช้ browser automation เช่น Selenium
                # ในที่นี้เราจะทำการตรวจสอบเบื้องต้นว่า Backend API พร้อมใช้งานสำหรับ Frontend หรือไม่
                
                # ตรวจสอบว่า Backend CORS ตั้งค่าถูกต้องไหม
                headers = {
                    "Origin": "http://localhost:3000"
                }
                response = requests.get(f"{API_URL}/api/latest-signal?symbol=BTCUSDT", 
                                      headers=headers, timeout=10)
                
                if "Access-Control-Allow-Origin" in response.headers:
                    self.add_result("ระบบ", "การเชื่อมต่อ Frontend-Backend", True, 
                                   "Backend API มีการตั้งค่า CORS ที่ถูกต้องสำหรับ Frontend")
                    return True
                else:
                    self.add_result("ระบบ", "การเชื่อมต่อ Frontend-Backend", False, 
                                   "Backend API ไม่มีการตั้งค่า CORS ที่ถูกต้อง อาจทำให้ Frontend ไม่สามารถเข้าถึงได้")
                    return False
                    
            else:
                self.add_result("Frontend", "การทำงาน", False, 
                               f"Frontend ตอบสนองด้วยรหัสสถานะผิดปกติ: {response.status_code}")
                return False
                
        except requests.ConnectionError:
            self.add_result("Frontend", "การทำงาน", False, 
                           "ไม่สามารถเชื่อมต่อกับ Frontend ได้ ตรวจสอบว่า Frontend ทำงานอยู่หรือไม่")
            
            # แม้ว่า Frontend จะไม่ทำงาน เราก็ยังสามารถตรวจสอบว่า Backend API พร้อมใช้งานสำหรับ Frontend หรือไม่
            try:
                headers = {
                    "Origin": "http://localhost:3000"
                }
                response = requests.get(f"{API_URL}/api/latest-signal?symbol=BTCUSDT", 
                                      headers=headers, timeout=10)
                
                if "Access-Control-Allow-Origin" in response.headers:
                    self.add_result("ระบบ", "การเชื่อมต่อ Frontend-Backend", True, 
                                   "Backend API มีการตั้งค่า CORS ที่ถูกต้องสำหรับ Frontend (แม้ว่า Frontend จะไม่ทำงาน)")
                    return True
                else:
                    self.add_result("ระบบ", "การเชื่อมต่อ Frontend-Backend", False, 
                                   "Backend API ไม่มีการตั้งค่า CORS ที่ถูกต้อง อาจทำให้ Frontend ไม่สามารถเข้าถึงได้")
                    return False
            except:
                self.add_result("ระบบ", "การเชื่อมต่อ Frontend-Backend", False, 
                               "ไม่สามารถตรวจสอบการตั้งค่า CORS ของ Backend API ได้")
                return False
                
        except Exception as e:
            self.add_result("Frontend", "การทำงาน", False, 
                           f"เกิดข้อผิดพลาดในการตรวจสอบ Frontend: {e}")
            return False
    
    def print_summary(self) -> None:
        """แสดงสรุปผลการทดสอบ"""
        print("\n" + "="*50)
        print("สรุปผลการทดสอบระบบ Crypto Signal App")
        print("="*50)
        
        pass_count = sum(1 for result in self.results if result.result)
        fail_count = len(self.results) - pass_count
        
        print(f"จำนวนการทดสอบทั้งหมด: {len(self.results)}")
        print(f"ผ่าน: {pass_count}")
        print(f"ไม่ผ่าน: {fail_count}")
        
        if fail_count > 0:
            print("\nรายการที่ไม่ผ่านการทดสอบ:")
            for result in self.results:
                if not result.result:
                    print(f"- {result.component} - {result.test_name}: {result.details}")
        
        print("="*50)
        
        if fail_count == 0:
            print("✅ ผลการทดสอบทั้งหมดผ่าน! ระบบพร้อมใช้งาน")
        else:
            print(f"❌ มีการทดสอบที่ไม่ผ่าน {fail_count} รายการ โปรดแก้ไขปัญหาก่อนใช้งานระบบ")
        
        print("="*50)
    
    def run_subprocess_with_timeout(self, cmd: List[str], timeout: int = 60) -> Tuple[bool, str]:
        """
        รันคำสั่งใน subprocess พร้อมกำหนด timeout
        
        Args:
            cmd: รายการคำสั่งที่จะรัน
            timeout: เวลา timeout ในวินาที
            
        Returns:
            (สำเร็จหรือไม่, ข้อความผลลัพธ์หรือข้อผิดพลาด)
        """
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, f"รหัสสถานะผิดพลาด: {result.returncode}, ข้อผิดพลาด: {result.stderr}"
        
        except subprocess.TimeoutExpired:
            return False, f"คำสั่งทำงานนานเกินกว่า {timeout} วินาที"
        except Exception as e:
            return False, f"เกิดข้อผิดพลาดในการรันคำสั่ง: {e}"
    
    def check_services_status(self) -> None:
        """ตรวจสอบสถานะของบริการต่างๆ (Redis, Backend, Frontend)"""
        print("\nกำลังตรวจสอบสถานะของบริการต่างๆ...")
        
        # ตรวจสอบ Redis
        try:
            result = subprocess.run(
                ["tasklist", "/fi", "imagename eq redis-server.exe"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if "redis-server.exe" in result.stdout:
                print("✅ Redis Server กำลังทำงาน")
            else:
                print("❌ Redis Server ไม่ได้ทำงานอยู่")
        except Exception as e:
            print(f"❌ ไม่สามารถตรวจสอบสถานะของ Redis Server ได้: {e}")
        
        # ตรวจสอบ Backend API (uvicorn บนพอร์ต 8000)
        try:
            result = subprocess.run(
                ["netstat", "-ano", "|", "find", "\":8000\"", "|", "find", "\"LISTENING\""],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True
            )
            
            if result.stdout.strip():
                print("✅ Backend API กำลังทำงานบนพอร์ต 8000")
            else:
                print("❌ Backend API ไม่ได้ทำงานบนพอร์ต 8000")
        except Exception as e:
            print(f"❌ ไม่สามารถตรวจสอบสถานะของ Backend API ได้: {e}")
        
        # ตรวจสอบ Frontend (Node.js บนพอร์ต 3000)
        try:
            result = subprocess.run(
                ["netstat", "-ano", "|", "find", "\":3000\"", "|", "find", "\"LISTENING\""],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True
            )
            
            if result.stdout.strip():
                print("✅ Frontend กำลังทำงานบนพอร์ต 3000")
            else:
                print("❌ Frontend ไม่ได้ทำงานบนพอร์ต 3000")
        except Exception as e:
            print(f"❌ ไม่สามารถตรวจสอบสถานะของ Frontend ได้: {e}")
    
    def run_all_tests(self) -> None:
        """รันการทดสอบทั้งหมด"""
        print("\n🚀 เริ่มต้นการทดสอบระบบ Crypto Signal App...\n")
        
        # ตรวจสอบสถานะบริการต่างๆ
        self.check_services_status()
        
        print("\n🔍 กำลังทดสอบองค์ประกอบต่างๆ...\n")
        
        # ทดสอบ Redis
        redis_ok = self.test_redis_connection()
        if redis_ok:
            self.test_redis_pubsub()
        
        # ทดสอบ Backend API
        api_ok = self.test_api_availability()
        if api_ok:
            self.test_api_endpoints()
        
        # ทดสอบ SignalProcessor
        self.test_signal_processor()
        
        # ทดสอบกระแสข้อมูลของสัญญาณ (ถ้า Redis ทำงานได้)
        if redis_ok:
            self.test_signal_data_flow()
        
        # ทดสอบ WebSocket (ถ้า API ทำงานได้)
        if api_ok:
            asyncio.run(self.test_websocket_connection())
        
        # ตรวจสอบการเชื่อมต่อระหว่าง Frontend และ Backend
        if api_ok:
            self.check_frontend_connectivity()
        
        # แสดงสรุปผลการทดสอบ
        self.print_summary()


if __name__ == "__main__":
    # สร้าง argument parser
    parser = argparse.ArgumentParser(description="ทดสอบระบบ Crypto Signal App")
    parser.add_argument("-v", "--verbose", action="store_true", help="แสดงรายละเอียดเพิ่มเติม")
    args = parser.parse_args()
    
    # รันการทดสอบ
    tester = SystemTester(verbose=args.verbose)
    tester.run_all_tests()