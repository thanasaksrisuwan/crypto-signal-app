import asyncio
import json
import os
import time
import websockets
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Union, Callable, Any

import redis
from dotenv import load_dotenv

# นำเข้าคลาส InfluxDBStorage
try:
    # เมื่อรันเป็น module โดยตรง
    from .influxdb_storage import InfluxDBStorage
    has_influxdb = True
except (ImportError, ModuleNotFoundError):
    try:
        # เมื่อรันจาก parent directory
        from app.influxdb_storage import InfluxDBStorage
        has_influxdb = True
    except (ImportError, ModuleNotFoundError):
        try:
            # เมื่อรันเป็น script โดยตรง
            from influxdb_storage import InfluxDBStorage
            has_influxdb = True
        except (ImportError, ModuleNotFoundError):
            # กรณีที่ไม่สามารถนำเข้า InfluxDBStorage ได้
            print("ไม่สามารถนำเข้า InfluxDBStorage ได้ - จะข้ามการบันทึกข้อมูลลง InfluxDB")
            has_influxdb = False
            # สร้างคลาสจำลองเพื่อหลีกเลี่ยงข้อผิดพลาด
            class InfluxDBStorage:
                def __init__(self):
                    print("คลาส InfluxDBStorage จำลอง - ไม่มีการเชื่อมต่อกับ InfluxDB จริง")
                
                def store_kline_data(self, symbol, data):
                    pass
                
                def close(self):
                    pass

# โหลด environment variables
load_dotenv()

# ค่าตัวแปรสำหรับการเชื่อมต่อ
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_CHANNEL_PREFIX = "crypto_signals:kline:"

# สัญลักษณ์คริปโตที่จะติดตาม
SYMBOLS = ["BTCUSDT", "ETHUSDT"]

# Binance WebSocket endpoints
BINANCE_WS_API_ENDPOINT = "wss://ws-api.binance.com:443/ws-api/v3"  # API endpoint
BINANCE_WS_STREAM_ENDPOINT = "wss://stream.binance.com:9443/ws"     # Stream endpoint
BINANCE_WS_TESTNET_ENDPOINT = "wss://ws-api.testnet.binance.vision/ws-api/v3"


class BinanceWebSocketClient:
    def __init__(self, use_testnet=False):
        # เชื่อมต่อกับ Redis
        self.redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        
        # สร้างอินสแตนซ์ของ InfluxDBStorage ถ้ามี
        if has_influxdb:
            try:
                self.influxdb_storage = InfluxDBStorage()
            except Exception as e:
                print(f"ไม่สามารถเชื่อมต่อกับ InfluxDB ได้: {e}")
                self.influxdb_storage = None
        else:
            self.influxdb_storage = None
        
        # ตั้งค่า WebSocket endpoints
        self.use_testnet = use_testnet
        self.ws_api_endpoint = BINANCE_WS_TESTNET_ENDPOINT if use_testnet else BINANCE_WS_API_ENDPOINT
        self.ws_stream_endpoint = BINANCE_WS_STREAM_ENDPOINT
        
        # WebSocket connections
        self.api_ws = None       # For API requests
        self.stream_ws = None    # For data streams
        self.is_running = False
        self.pending_requests = {}  # Store callbacks for API requests
        self.active_streams = {}    # Track active stream subscriptions

    async def connect(self):
        """เชื่อมต่อกับ Binance WebSocket API และ Stream"""
        # ทดสอบการเชื่อมต่อกับ Redis
        try:
            self.redis_client.ping()
            print("เชื่อมต่อกับ Redis สำเร็จ")
        except redis.ConnectionError:
            print("ไม่สามารถเชื่อมต่อกับ Redis ได้")
            return False
        
        # เชื่อมต่อกับ WebSocket API
        try:
            self.api_ws = await websockets.connect(self.ws_api_endpoint)
            print(f"เชื่อมต่อกับ Binance WebSocket API สำเร็จ: {self.ws_api_endpoint}")
            
            # เริ่ม task สำหรับการรับข้อความจาก API WebSocket
            asyncio.create_task(self._handle_api_messages())
            
            # เชื่อมต่อกับ WebSocket Stream
            self.stream_ws = await websockets.connect(self.ws_stream_endpoint)
            print(f"เชื่อมต่อกับ Binance WebSocket Stream สำเร็จ: {self.ws_stream_endpoint}")
            
            # เริ่ม task สำหรับการรับข้อความจาก Stream WebSocket
            asyncio.create_task(self._handle_stream_messages())
            
            self.is_running = True
            return True
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการเชื่อมต่อกับ Binance WebSocket: {e}")
            await self.close()
            return False

    async def _handle_api_messages(self):
        """จัดการกับข้อความที่ได้รับจาก API WebSocket"""
        try:
            while self.is_running and self.api_ws:
                try:
                    message = await self.api_ws.recv()
                    data = json.loads(message)
                    
                    # ตรวจสอบว่าเป็น ping แล้วตอบกลับด้วย pong
                    if isinstance(data, dict) and "id" in data:
                        request_id = data.get("id")
                        if request_id in self.pending_requests:
                            callback = self.pending_requests.pop(request_id)
                            if callable(callback):
                                await callback(data)
                except websockets.ConnectionClosed:
                    print("การเชื่อมต่อ API WebSocket ถูกปิด กำลังเชื่อมต่อใหม่...")
                    await asyncio.sleep(5)  # รอก่อนเชื่อมต่อใหม่
                    try:
                        self.api_ws = await websockets.connect(self.ws_api_endpoint)
                    except Exception as reconnect_error:
                        print(f"ไม่สามารถเชื่อมต่อกับ API WebSocket ใหม่ได้: {reconnect_error}")
                        await asyncio.sleep(10)  # รอนานขึ้นก่อนลองอีกครั้ง
                except Exception as e:
                    print(f"เกิดข้อผิดพลาดในการประมวลผลข้อความจาก API WebSocket: {e}")
                    await asyncio.sleep(1)
        except Exception as e:
            print(f"เกิดข้อผิดพลาดใน _handle_api_messages: {e}")
            self.is_running = False

    async def _handle_stream_messages(self):
        """จัดการกับข้อความที่ได้รับจาก Stream WebSocket"""
        try:
            while self.is_running and self.stream_ws:
                try:
                    message = await self.stream_ws.recv()
                    data = json.loads(message)
                    
                    # ตรวจสอบว่าเป็น stream event หรือไม่
                    if isinstance(data, dict):
                        if "stream" in data and "data" in data:  # Combined stream format
                            await self._process_stream_message(data["stream"], data["data"])
                        elif "e" in data:  # Single stream format (has event type)
                            stream_name = data.get("s", "").lower()  # Symbol
                            event_type = data.get("e", "")  # Event type
                            
                            if stream_name and event_type:
                                stream_id = f"{stream_name}@{event_type}"
                                await self._process_stream_message(stream_id, data)
                except websockets.ConnectionClosed:
                    print("การเชื่อมต่อ Stream WebSocket ถูกปิด กำลังเชื่อมต่อใหม่...")
                    await asyncio.sleep(5)  # รอก่อนเชื่อมต่อใหม่
                    try:
                        self.stream_ws = await websockets.connect(self.ws_stream_endpoint)
                        # เมื่อเชื่อมต่อใหม่ ต้องสมัครสมาชิก stream อีกครั้ง
                        if self.active_streams:
                            await self._resubscribe_streams()
                    except Exception as reconnect_error:
                        print(f"ไม่สามารถเชื่อมต่อกับ Stream WebSocket ใหม่ได้: {reconnect_error}")
                        await asyncio.sleep(10)  # รอนานขึ้นก่อนลองอีกครั้ง
                except Exception as e:
                    print(f"เกิดข้อผิดพลาดในการประมวลผลข้อความจาก Stream WebSocket: {e}")
                    await asyncio.sleep(1)
        except Exception as e:
            print(f"เกิดข้อผิดพลาดใน _handle_stream_messages: {e}")
            self.is_running = False

    async def _resubscribe_streams(self):
        """สมัครสมาชิก stream ทั้งหมดอีกครั้งหลังจากการเชื่อมต่อใหม่"""
        if not self.active_streams:
            return
            
        try:
            streams = list(self.active_streams.keys())
            request_id = str(uuid.uuid4())
            
            subscription_message = {
                "method": "SUBSCRIBE",
                "params": streams,
                "id": request_id
            }
            
            await self.stream_ws.send(json.dumps(subscription_message))
            print(f"สมัครสมาชิก stream อีกครั้ง: {streams}")
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการสมัครสมาชิก stream อีกครั้ง: {e}")
            # ไม่ควรล้มเหลวทั้งหมด เพราะจะทำให้ไม่ได้รับข้อมูลเลย
            await asyncio.sleep(5)  # รอสักครู่แล้วลองอีกครั้งใน loop หลัก

    async def _process_stream_message(self, stream_id: str, data: Dict):
        """ประมวลผลข้อความจาก stream"""
        # ตรวจสอบประเภทของข้อมูล
        if "e" in data:
            event_type = data["e"]
            
            # ประมวลผลตามประเภทของเหตุการณ์
            if event_type == "kline":
                await self.process_kline_message(data)
            elif event_type == "aggTrade":
                await self.process_aggtrade_message(data)
            elif event_type == "24hrTicker":
                await self.process_ticker_message(data)
            elif event_type == "depthUpdate":
                await self.process_depth_message(data)
            else:
                # ประเภทเหตุการณ์อื่นๆ
                redis_channel = f"crypto_signals:{event_type}:{data.get('s', 'unknown')}"
                self.redis_client.publish(redis_channel, json.dumps(data))

    async def process_kline_message(self, message: Dict):
        """แปลงและเผยแพร่ข้อมูล kline ไปยัง Redis และบันทึกลง InfluxDB"""
        if message.get('e') == 'kline':
            kline = message['k']
            
            # แปลงข้อมูลให้อยู่ในรูปแบบที่เหมาะสม
            data = {
                'symbol': message['s'],
                'interval': kline['i'],
                'start_time': kline['t'],
                'close_time': kline['T'],
                'open': float(kline['o']),
                'high': float(kline['h']),
                'low': float(kline['l']),
                'close': float(kline['c']),
                'volume': float(kline['v']),
                'number_of_trades': kline['n'],
                'is_closed': kline['x']  # แสดงว่า candle นี้ปิดแล้วหรือไม่
            }
            
            # สร้างชื่อ channel สำหรับ symbol และ interval นี้
            channel = f"{REDIS_CHANNEL_PREFIX}{message['s']}:{kline['i']}"
            
            # เผยแพร่ข้อมูลเฉพาะเมื่อ candle ปิดแล้ว
            if data['is_closed']:
                print(f"เผยแพร่ candle ที่ปิดแล้ว: {message['s']} {kline['i']} ที่ {datetime.fromtimestamp(kline['T']/1000)}")
                self.redis_client.publish(channel, json.dumps(data))
                
                # บันทึกข้อมูล kline ลงใน InfluxDB
                if self.influxdb_storage:
                    try:
                        self.influxdb_storage.store_kline_data(message['s'], data)
                        print(f"บันทึกข้อมูล kline ลง InfluxDB สำเร็จ: {message['s']} ที่ {datetime.fromtimestamp(kline['T']/1000)}")
                    except Exception as e:
                        print(f"เกิดข้อผิดพลาดในการบันทึกข้อมูลลง InfluxDB: {e}")
            
            # เก็บ candle ล่าสุดเสมอ (ไม่ว่าจะปิดหรือไม่) ในกรณีที่ต้องการดูข้อมูลปัจจุบัน
            self.redis_client.set(f"latest_kline:{message['s']}:{kline['i']}", json.dumps(data))

    async def process_aggtrade_message(self, message: Dict):
        """ประมวลผลข้อมูล aggregate trade"""
        if message.get('e') == 'aggTrade':
            # แปลงข้อมูลให้อยู่ในรูปแบบที่เหมาะสม
            data = {
                'symbol': message['s'],
                'trade_id': message['a'],
                'price': float(message['p']),
                'quantity': float(message['q']),
                'first_trade_id': message['f'],
                'last_trade_id': message['l'],
                'timestamp': message['T'],
                'is_buyer_maker': message['m'],
                'event_time': message['E']
            }
            
            # สร้างชื่อ channel สำหรับ symbol
            channel = f"crypto_signals:aggtrade:{message['s']}"
            
            # เผยแพร่ข้อมูล
            self.redis_client.publish(channel, json.dumps(data))
            
            # เก็บ trade ล่าสุด
            self.redis_client.set(f"latest_trade:{message['s']}", json.dumps(data))

    async def process_ticker_message(self, message: Dict):
        """ประมวลผลข้อมูล ticker"""
        if message.get('e') == '24hrTicker':
            # แปลงข้อมูลให้อยู่ในรูปแบบที่เหมาะสม
            data = {
                'symbol': message['s'],
                'price_change': float(message['p']),
                'price_change_percent': float(message['P']),
                'weighted_avg_price': float(message['w']),
                'last_price': float(message['c']),
                'last_qty': float(message['Q']),
                'open_price': float(message['o']),
                'high_price': float(message['h']),
                'low_price': float(message['l']),
                'volume': float(message['v']),
                'quote_volume': float(message['q']),
                'event_time': message['E'],
                'close_time': message['C']
            }
            
            # สร้างชื่อ channel สำหรับ symbol
            channel = f"crypto_signals:ticker:{message['s']}"
            
            # เผยแพร่ข้อมูล
            self.redis_client.publish(channel, json.dumps(data))
            
            # เก็บ ticker ล่าสุด
            self.redis_client.set(f"latest_ticker:{message['s']}", json.dumps(data))

    async def process_depth_message(self, message: Dict):
        """ประมวลผลข้อมูล order book depth"""
        if message.get('e') == 'depthUpdate':
            # แปลงข้อมูลให้อยู่ในรูปแบบที่เหมาะสม
            data = {
                'symbol': message['s'],
                'first_update_id': message['U'],
                'final_update_id': message['u'],
                'bids': message['b'],
                'asks': message['a'],
                'event_time': message['E']
            }
            
            # สร้างชื่อ channel สำหรับ symbol
            channel = f"crypto_signals:depth:{message['s']}"
            
            # เผยแพร่ข้อมูล
            self.redis_client.publish(channel, json.dumps(data))
            
            # เก็บ depth ล่าสุด
            self.redis_client.set(f"latest_depth:{message['s']}", json.dumps(data))

    async def subscribe_kline_stream(self, symbol: str, interval: str = '1m'):
        """สมัครสมาชิก kline stream"""
        stream_id = f"{symbol.lower()}@kline_{interval}"
        
        if stream_id in self.active_streams:
            print(f"มีการสมัครสมาชิก {stream_id} อยู่แล้ว")
            return True
            
        request_id = str(uuid.uuid4())
        
        subscription_message = {
            "method": "SUBSCRIBE",
            "params": [stream_id],
            "id": request_id
        }
        
        try:
            await self.stream_ws.send(json.dumps(subscription_message))
            
            # บันทึกสถานะการสมัครสมาชิก
            self.active_streams[stream_id] = True
            print(f"สมัครสมาชิก {stream_id} สำเร็จ")
            return True
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการสมัครสมาชิก {stream_id}: {e}")
            return False

    async def subscribe_aggtrade_stream(self, symbol: str):
        """สมัครสมาชิก aggregate trade stream"""
        stream_id = f"{symbol.lower()}@aggTrade"
        
        if stream_id in self.active_streams:
            print(f"มีการสมัครสมาชิก {stream_id} อยู่แล้ว")
            return True
            
        request_id = str(uuid.uuid4())
        
        subscription_message = {
            "method": "SUBSCRIBE",
            "params": [stream_id],
            "id": request_id
        }
        
        try:
            await self.stream_ws.send(json.dumps(subscription_message))
            
            # บันทึกสถานะการสมัครสมาชิก
            self.active_streams[stream_id] = True
            print(f"สมัครสมาชิก {stream_id} สำเร็จ")
            return True
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการสมัครสมาชิก {stream_id}: {e}")
            return False

    async def subscribe_ticker_stream(self, symbol: str):
        """สมัครสมาชิก ticker stream"""
        stream_id = f"{symbol.lower()}@ticker"
        
        if stream_id in self.active_streams:
            print(f"มีการสมัครสมาชิก {stream_id} อยู่แล้ว")
            return True
            
        request_id = str(uuid.uuid4())
        
        subscription_message = {
            "method": "SUBSCRIBE",
            "params": [stream_id],
            "id": request_id
        }
        
        try:
            await self.stream_ws.send(json.dumps(subscription_message))
            
            # บันทึกสถานะการสมัครสมาชิก
            self.active_streams[stream_id] = True
            print(f"สมัครสมาชิก {stream_id} สำเร็จ")
            return True
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการสมัครสมาชิก {stream_id}: {e}")
            return False

    async def subscribe_depth_stream(self, symbol: str, level: str = ''):
        """สมัครสมาชิก order book depth stream
        
        level: ความละเอียดของ order book ('5', '10', '20' หรือว่างไว้เพื่อรับการอัปเดตเต็มรูปแบบ)
        """
        stream_id = f"{symbol.lower()}@depth{level}"
        
        if stream_id in self.active_streams:
            print(f"มีการสมัครสมาชิก {stream_id} อยู่แล้ว")
            return True
            
        request_id = str(uuid.uuid4())
        
        subscription_message = {
            "method": "SUBSCRIBE",
            "params": [stream_id],
            "id": request_id
        }
        
        try:
            await self.stream_ws.send(json.dumps(subscription_message))
            
            # บันทึกสถานะการสมัครสมาชิก
            self.active_streams[stream_id] = True
            print(f"สมัครสมาชิก {stream_id} สำเร็จ")
            return True
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการสมัครสมาชิก {stream_id}: {e}")
            return False

    async def unsubscribe_stream(self, stream_id: str):
        """ยกเลิกการสมัครสมาชิก stream"""
        if stream_id not in self.active_streams:
            print(f"ไม่มีการสมัครสมาชิก {stream_id} อยู่")
            return True
            
        request_id = str(uuid.uuid4())
        
        unsubscription_message = {
            "method": "UNSUBSCRIBE",
            "params": [stream_id],
            "id": request_id
        }
        
        try:
            await self.stream_ws.send(json.dumps(unsubscription_message))
            
            # ลบออกจากรายการสมัครสมาชิก
            if stream_id in self.active_streams:
                del self.active_streams[stream_id]
                
            print(f"ยกเลิกการสมัครสมาชิก {stream_id} สำเร็จ")
            return True
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการยกเลิกการสมัครสมาชิก {stream_id}: {e}")
            return False

    async def list_subscriptions(self):
        """แสดงรายการ stream ที่สมัครสมาชิกอยู่"""
        request_id = str(uuid.uuid4())
        
        message = {
            "method": "LIST_SUBSCRIPTIONS",
            "id": request_id
        }
        
        try:
            await self.stream_ws.send(json.dumps(message))
            print(f"ส่งคำขอรายการสมัครสมาชิกด้วย ID: {request_id}")
            return True
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการขอรายการสมัครสมาชิก: {e}")
            return False

    # WebSocket API methods
    async def get_depth(self, symbol: str, limit: int = 10) -> Optional[Dict]:
        """ขอข้อมูล order book"""
        if not self.is_running or not self.api_ws:
            print("ยังไม่ได้เชื่อมต่อกับ WebSocket API")
            return None
            
        request_id = str(uuid.uuid4())
        
        message = {
            "id": request_id,
            "method": "depth",
            "params": {
                "symbol": symbol.upper(),
                "limit": limit
            }
        }
        
        response = await self._send_api_request(message)
        return response

    async def get_recent_trades(self, symbol: str, limit: int = 10) -> Optional[Dict]:
        """ขอข้อมูลการซื้อขายล่าสุด"""
        if not self.is_running or not self.api_ws:
            print("ยังไม่ได้เชื่อมต่อกับ WebSocket API")
            return None
            
        request_id = str(uuid.uuid4())
        
        message = {
            "id": request_id,
            "method": "trades",
            "params": {
                "symbol": symbol.upper(),
                "limit": limit
            }
        }
        
        response = await self._send_api_request(message)
        return response

    async def get_ticker(self, symbol: Optional[str] = None) -> Optional[Dict]:
        """ขอข้อมูล ticker สำหรับหนึ่งหรือทุก symbol"""
        if not self.is_running or not self.api_ws:
            print("ยังไม่ได้เชื่อมต่อกับ WebSocket API")
            return None
            
        request_id = str(uuid.uuid4())
        params = {}
        
        if symbol:
            params["symbol"] = symbol.upper()
            
        message = {
            "id": request_id,
            "method": "ticker.24hr",
            "params": params
        }
        
        response = await self._send_api_request(message)
        return response

    async def get_klines(self, symbol: str, interval: str = '1m', limit: int = 10) -> Optional[Dict]:
        """ขอข้อมูล klines (candlesticks)"""
        if not self.is_running or not self.api_ws:
            print("ยังไม่ได้เชื่อมต่อกับ WebSocket API")
            return None
            
        request_id = str(uuid.uuid4())
        
        message = {
            "id": request_id,
            "method": "klines",
            "params": {
                "symbol": symbol.upper(),
                "interval": interval,
                "limit": limit
            }
        }
        
        response = await self._send_api_request(message)
        return response

    async def _send_api_request(self, message: Dict) -> Optional[Dict]:
        """ส่งคำขอไปยัง WebSocket API และรอผลลัพธ์"""
        request_id = message["id"]
        future = asyncio.get_event_loop().create_future()
        
        # ลงทะเบียนคอลแบ็คสำหรับคำขอนี้
        self.pending_requests[request_id] = lambda data: future.set_result(data)
        
        try:
            # ส่งคำขอผ่าน WebSocket
            await self.api_ws.send(json.dumps(message))
            
            # รอผลลัพธ์ด้วยไทม์เอาต์
            response = await asyncio.wait_for(future, timeout=10.0)
            return response
        except asyncio.TimeoutError:
            print(f"คำขอ {request_id} หมดเวลา")
            self.pending_requests.pop(request_id, None)
            return None
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการส่งคำขอ {request_id}: {e}")
            self.pending_requests.pop(request_id, None)
            return None

    async def start_kline_streams(self):
        """เริ่ม streams สำหรับ kline ของทุกสัญลักษณ์"""
        for symbol in SYMBOLS:
            await self.subscribe_kline_stream(symbol, '2m')

    async def close(self):
        """ปิดการเชื่อมต่อทั้งหมด"""
        self.is_running = False
        
        # ปิดการเชื่อมต่อ WebSocket
        try:
            if self.api_ws:
                await self.api_ws.close()
                print("ปิดการเชื่อมต่อกับ Binance WebSocket API")
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการปิดการเชื่อมต่อกับ Binance WebSocket API: {e}")
        
        try:
            if self.stream_ws:
                await self.stream_ws.close()
                print("ปิดการเชื่อมต่อกับ Binance WebSocket Stream")
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการปิดการเชื่อมต่อกับ Binance WebSocket Stream: {e}")
        
        # ปิดการเชื่อมต่อกับ InfluxDB
        if self.influxdb_storage:
            try:
                self.influxdb_storage.close()
                print("ปิดการเชื่อมต่อกับ InfluxDB")
            except Exception as e:
                print(f"เกิดข้อผิดพลาดในการปิดการเชื่อมต่อกับ InfluxDB: {e}")

async def main():
    """ฟังก์ชันหลักสำหรับเริ่มต้นโปรแกรม"""
    client = BinanceWebSocketClient()
    
    try:
        is_connected = await client.connect()
        if is_connected and client.is_running:
            # เริ่ม kline streams
            await client.start_kline_streams()
            
            # ทดสอบ API requests
            symbol = "BTCUSDT"
            print(f"ขอข้อมูลราคาล่าสุดของ {symbol}...")
            ticker_data = await client.get_ticker(symbol)
            if ticker_data:
                print(f"ข้อมูล ticker: {json.dumps(ticker_data, indent=2)}")
            
            # รอไว้เพื่อให้โปรแกรมทำงานต่อไป
            while client.is_running:
                await asyncio.sleep(60)
                print("โปรแกรมยังทำงานอยู่...")
                
    except asyncio.CancelledError:
        print("ยกเลิกการทำงานของโปรแกรม")
    except Exception as e:
        print(f"เกิดข้อผิดพลาดหลัก: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    # รันโปรแกรมหลัก
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("ได้รับสัญญาณการหยุดโปรแกรม")
    finally:
        loop.close()