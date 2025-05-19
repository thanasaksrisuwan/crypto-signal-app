from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import json
import asyncio
from datetime import datetime
import sys

# Ensure the app directory is in the Python path
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# นำเข้าโมดูลจัดการตัวแปรสภาพแวดล้อม
import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
import env_manager as env

# ใช้ RedisManager แทนการสร้าง Redis client แยก
from redis_manager import get_redis_client, check_redis_connection

# นำเข้าคลาสและฟังก์ชันที่เราสร้างไว้
from binance_ws_client import BinanceWebSocketClient
from signal_processor import SignalProcessor, grade_signal
from notification_service import NotificationService
from enhanced_memory_monitor import enhanced_memory_monitor

# โหลดรายการสัญลักษณ์คริปโตที่รองรับจากตัวแปรสภาพแวดล้อม
SYMBOLS = env.get_available_symbols()

# ตั้งค่าการเชื่อมต่อกับ Redis
redis_config = env.get_redis_config()
REDIS_SIGNAL_CHANNEL = "crypto_signals:signals"
REDIS_KLINE_CHANNEL_PREFIX = "crypto_signals:kline:"

# ตั้งค่าแอพพลิเคชัน FastAPI
app = FastAPI(
    title="Crypto Signal API",
    description="API for crypto trading signals based on 2-minute OHLCV data",
    version="0.1.0",
)

# ตั้งค่า CORS เพื่อให้ Frontend เรียกใช้ API ได้
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ในการผลิตจริงควรระบุ origins ที่แน่นอน
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# โมเดลข้อมูลสำหรับสัญญาณ
class Signal(BaseModel):
    symbol: str
    timestamp: int
    forecast_pct: float
    confidence: float
    category: str  # strong buy, weak buy, hold, weak sell, strong sell
    price: Optional[float] = None
    indicators: Optional[Dict[str, Optional[float]]] = None

# นำเข้า Pydantic models ที่ต้องใช้
class SymbolRequest(BaseModel):
    symbol: str

class SymbolResponse(BaseModel):
    success: bool
    message: str
    symbols: List[str]

# ตัวแปรที่ใช้ตรวจสอบสถานะ Redis
redis_connected = False
redis_client = None

# ฟังก์ชันเชื่อมต่อกับ Redis พร้อมจัดการข้อผิดพลาด
def connect_to_redis():
    global redis_client, redis_connected
    try:
        # เชื่อมต่อกับ Redis โดยใช้ connection pool
        redis_client = get_redis_client(decode_responses=True)
        # ทดสอบการเชื่อมต่อ
        redis_connected = redis_client.ping()
        if redis_connected:
            print(f"✅ เชื่อมต่อกับ Redis สำเร็จที่ {REDIS_HOST}:{REDIS_PORT}")
        return redis_connected
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการเชื่อมต่อกับ Redis: {e}")
        redis_connected = False
        return False

# เชื่อมต่อกับ Redis
connect_to_redis()

# เริ่มการตรวจสอบหน่วยความจำ
enhanced_memory_monitor.start()

# ใช้ OptimizedSignalProcessor แทน SignalProcessor เพื่อประสิทธิภาพที่ดีขึ้น
from optimized_signal_processor import signal_processor

# สร้างข้อมูลว่างเปล่าเมื่อไม่มีข้อมูลจริง
def create_empty_signal(symbol: str) -> dict:
    return {
        "symbol": symbol,
        "timestamp": int(datetime.now().timestamp() * 1000),
        "forecast_pct": 0.0,
        "confidence": 0.0,
        "category": "no data",
        "price": 0.0,
        "indicators": {
            "ema9": None,
            "ema21": None,
            "sma20": None,
            "rsi14": None
        }
    }

# จัดการการเชื่อมต่อ WebSocket จาก clients
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.redis_pubsub = None
        self.task = None
        self.client_subscriptions = {}  # เก็บข้อมูลการสมัครสมาชิกของแต่ละ client
        self.heartbeat_task = None  # เพิ่ม task สำหรับ heartbeat

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.client_subscriptions[websocket] = set()  # เริ่มต้นด้วยเซ็ตว่าง
        print(f"📡 WebSocket client เชื่อมต่อแล้ว - จำนวนการเชื่อมต่อทั้งหมด: {len(self.active_connections)}")
        
        # เริ่ม Redis PubSub ถ้ายังไม่ได้เริ่มและ Redis เชื่อมต่อได้
        if self.redis_pubsub is None and redis_connected:
            try:
                self.redis_pubsub = redis_client.pubsub()
                self.redis_pubsub.subscribe(REDIS_SIGNAL_CHANNEL)
                # เริ่มตรวจสอบข้อความใหม่
                self.task = asyncio.create_task(self.listen_for_messages())
                print(f"📢 เริ่มต้น Redis PubSub listener สำหรับช่อง {REDIS_SIGNAL_CHANNEL}")
            except Exception as e:
                print(f"❌ ไม่สามารถเริ่ม Redis PubSub ได้: {e}")
        
        # เริ่ม heartbeat task ถ้ายังไม่มี
        if self.heartbeat_task is None:
            self.heartbeat_task = asyncio.create_task(self.send_heartbeats())
            print("💓 เริ่มต้น heartbeat system เพื่อรักษาการเชื่อมต่อ WebSocket")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            # ลบข้อมูลการสมัครสมาชิกของ client นี้
            if websocket in self.client_subscriptions:
                del self.client_subscriptions[websocket]
            print(f"🔌 WebSocket client ยกเลิกการเชื่อมต่อแล้ว - จำนวนการเชื่อมต่อที่เหลือ: {len(self.active_connections)}")
            
            # หากไม่มีการเชื่อมต่อเหลืออยู่ ให้หยุด PubSub
            if not self.active_connections:
                if self.task:
                    self.task.cancel()
                if self.redis_pubsub:
                    try:
                        self.redis_pubsub.unsubscribe()
                    except Exception as e:
                        print(f"⚠️ ไม่สามารถยกเลิกการสมัครสมาชิก Redis PubSub ได้: {e}")
                self.redis_pubsub = None
                self.task = None
                print("📢 ยกเลิก Redis PubSub listener แล้ว")
                
                # ยกเลิก heartbeat task
                if self.heartbeat_task:
                    self.heartbeat_task.cancel()
                    self.heartbeat_task = None
                    print("💓 ยกเลิก heartbeat system")

    async def broadcast(self, message: str):
        try:
            message_data = json.loads(message)
            # สร้างรายการของ WebSockets ที่ต้องลบเนื่องจากถูกปิด
            disconnected_websockets = []
            
            for connection in self.active_connections:
                try:
                    await connection.send_json(message_data)
                except RuntimeError as e:
                    if "Cannot call 'send' once a close message has been sent" in str(e):
                        print(f"⚠️ พบ WebSocket ที่ถูกปิดแล้วระหว่างการ broadcast - กำลังเพิ่มเข้าสู่รายการลบ")
                        disconnected_websockets.append(connection)
                    else:
                        raise
                except Exception as e:
                    print(f"❌ เกิดข้อผิดพลาดในการ broadcast ไปยัง client: {e}")
                    if "WebSocket is not connected" in str(e):
                        disconnected_websockets.append(connection)
            
            # ลบ WebSockets ที่ถูกปิดแล้วออกจากรายการ active_connections
            for ws in disconnected_websockets:
                if ws in self.active_connections:
                    self.disconnect(ws)
            
            if self.active_connections:  # ตรวจสอบว่ามี connections เหลืออยู่หรือไม่
                print(f"📢 ส่งข้อความไปยัง WebSocket clients ทั้งหมด {len(self.active_connections)} การเชื่อมต่อ")
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการส่งข้อความไปยัง clients: {e}")
    
    async def send_to_client(self, websocket: WebSocket, message: Dict):
        """ส่งข้อความไปยัง client เฉพาะราย"""
        try:
            # ตรวจสอบว่า websocket ยังเชื่อมต่ออยู่หรือไม่และอยู่ในรายการ active_connections
            if websocket in self.active_connections:
                try:
                    # ส่งข้อความไปยัง client
                    await websocket.send_json(message)
                    print(f"📨 ส่งข้อความไปยัง WebSocket client เฉพาะราย")
                except RuntimeError as e:
                    if "Cannot call 'send' once a close message has been sent" in str(e):
                        print(f"⚠️ WebSocket ถูกปิดระหว่างส่งข้อความ - กำลังลบออกจากรายการ")
                        # เอาออกจาก active_connections เพื่อป้องกันการส่งซ้ำ
                        if websocket in self.active_connections:
                            self.disconnect(websocket)
                    else:
                        raise
            else:
                print("⚠️ พยายามส่งข้อความไปยัง WebSocket ที่ไม่ได้เชื่อมต่อแล้ว - ข้ามการส่ง")
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการส่งข้อความไปยัง client: {e}")
            # ตรวจสอบว่าเป็นข้อผิดพลาดเกี่ยวกับการปิดการเชื่อมต่อหรือไม่
            if "WebSocket is not connected" in str(e) and websocket in self.active_connections:
                print("⚠️ พบ WebSocket ที่ไม่ได้เชื่อมต่อแล้วในรายการ active_connections - กำลังลบออก")
                self.disconnect(websocket)
    
    async def listen_for_messages(self):
        """ตรวจสอบข้อความใหม่จาก Redis PubSub และส่งไปยัง clients"""
        try:
            while True:
                if not redis_connected or self.redis_pubsub is None:
                    print("⚠️ Redis ไม่ได้เชื่อมต่อ - รอก่อนจะลองอีกครั้ง")
                    await asyncio.sleep(5)
                    # พยายามเชื่อมต่อกับ Redis อีกครั้ง
                    if connect_to_redis() and redis_connected:
                        try:
                            self.redis_pubsub = redis_client.pubsub()
                            self.redis_pubsub.subscribe(REDIS_SIGNAL_CHANNEL)
                            print(f"📢 เริ่มต้น Redis PubSub listener สำหรับช่อง {REDIS_SIGNAL_CHANNEL} อีกครั้ง")
                        except Exception as e:
                            print(f"❌ ไม่สามารถเริ่ม Redis PubSub ได้: {e}")
                    continue
                    
                try:
                    message = self.redis_pubsub.get_message(ignore_subscribe_messages=True)
                    if message and message['type'] == 'message':
                        print(f"📬 ได้รับข้อความใหม่จาก Redis ช่อง {message.get('channel')}")
                        await self.broadcast(message['data'])
                except redis.RedisError as e:
                    print(f"⚠️ เกิดข้อผิดพลาด Redis ในการรับข้อความ: {e}")
                    await asyncio.sleep(5)  # รอก่อนลองอีกครั้ง
                except Exception as e:
                    print(f"❌ เกิดข้อผิดพลาดไม่ทราบสาเหตุในการรับข้อความ: {e}")
                
                await asyncio.sleep(0.01)  # ลดการใช้ CPU
        except asyncio.CancelledError:
            # ถูกยกเลิกเมื่อไม่มีผู้ใช้เชื่อมต่อแล้ว
            print("🛑 Redis listener ถูกยกเลิก")
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดใน WebSocket listener: {e}")
            
    async def send_heartbeats(self):
        """ส่ง heartbeat ไปยัง clients เพื่อรักษาการเชื่อมต่อ"""
        try:
            while True:
                disconnected_websockets = []
                
                for connection in self.active_connections:
                    try:
                        # ส่ง heartbeat ทุก 30 วินาที
                        await connection.send_json({"type": "heartbeat", "timestamp": int(datetime.now().timestamp())})
                    except Exception as e:
                        # หากไม่สามารถส่งได้ แสดงว่า connection อาจถูกปิดไปแล้ว
                        print(f"⚠️ ไม่สามารถส่ง heartbeat ได้: {e}")
                        disconnected_websockets.append(connection)
                
                # ลบ connections ที่ไม่สามารถส่ง heartbeat ได้
                for ws in disconnected_websockets:
                    if ws in self.active_connections:
                        self.disconnect(ws)
                
                if self.active_connections and not disconnected_websockets:
                    print(f"💓 ส่ง heartbeat ไปยัง {len(self.active_connections)} connections")
                
                # รอ 30 วินาทีก่อนส่ง heartbeat ครั้งต่อไป
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            print("💓 ยกเลิก heartbeat task")
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดใน heartbeat system: {e}")
            # พยายามรีสตาร์ท heartbeat task
            await asyncio.sleep(10)
            if self.active_connections:
                self.heartbeat_task = asyncio.create_task(self.send_heartbeats())
                print("💓 รีสตาร์ท heartbeat system")

# สร้าง Connection Manager
manager = ConnectionManager()

@app.get("/")
async def root():
    """
    API endpoint สำหรับตรวจสอบว่า API ทำงานอยู่หรือไม่ และสถานะของ Redis
    """
    if not redis_connected:
        # ลองเชื่อมต่อกับ Redis อีกครั้ง
        connect_to_redis()
        
    return {
        "status": "online",
        "message": "Crypto Signal API is running",
        "redis_status": "connected" if redis_connected else "disconnected",
        "available_symbols": SYMBOLS,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/latest-signal")
async def get_latest_signal(symbol: str = "BTCUSDT"):
    if symbol not in SYMBOLS:
        raise HTTPException(status_code=404, detail=f"No data for symbol {symbol}")
    
    try:
        if not redis_connected:
            raise HTTPException(status_code=503, detail="Redis service unavailable")
            
        latest_signal = redis_client.get(f"latest_signal:{symbol}")
        
        if not latest_signal:
            return create_empty_signal(symbol)
        
        return json.loads(latest_signal)
    except redis.RedisError as e:
        print(f"⚠️ Redis error: {e}")
        raise HTTPException(status_code=503, detail="Redis service error")
    except Exception as e:
        print(f"❌ Error fetching latest signal: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching latest signal: {str(e)}")

@app.get("/api/history-signals")
async def get_history_signals(symbol: str = "BTCUSDT", limit: int = 10):
    if symbol not in SYMBOLS:
        raise HTTPException(status_code=404, detail=f"No data for symbol {symbol}")
    
    try:
        if not redis_connected:
            raise HTTPException(status_code=503, detail="Redis service unavailable")
            
        signals = redis_client.lrange(f"signal_history:{symbol}", 0, limit - 1)
        
        if not signals or len(signals) == 0:
            return []  # Return empty array if no signals found
        
        return [json.loads(signal) for signal in signals]
    except redis.RedisError as e:
        print(f"⚠️ Redis error: {e}")
        raise HTTPException(status_code=503, detail="Redis service error")
    except Exception as e:
        print(f"❌ Error fetching signal history: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching signal history: {str(e)}")

@app.get("/available-symbols")
async def get_available_symbols():
    """ดึงรายการสัญลักษณ์ที่มีให้บริการ"""
    return {"symbols": SYMBOLS}

@app.get("/latest-indicators")
async def get_latest_indicators(symbol: str = "BTCUSDT"):
    if symbol not in SYMBOLS:
        raise HTTPException(status_code=404, detail=f"No data for symbol {symbol}")
    
    try:
        if not redis_connected:
            raise HTTPException(status_code=503, detail="Redis service unavailable")
        
        latest_signal = redis_client.get(f"latest_signal:{symbol}")
        
        if not latest_signal:
            empty = create_empty_signal(symbol)
            return {"symbol": symbol, "indicators": empty["indicators"]}
        
        signal_data = json.loads(latest_signal)
        
        if 'indicators' in signal_data:
            return {"symbol": symbol, "indicators": signal_data['indicators']}
        else:
            empty = create_empty_signal(symbol)
            return {"symbol": symbol, "indicators": empty["indicators"]}
    except redis.RedisError as e:
        print(f"⚠️ Redis error: {e}")
        raise HTTPException(status_code=503, detail="Redis service error")
    except Exception as e:
        print(f"❌ Error fetching latest indicators: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching latest indicators: {str(e)}")

# API endpoints สำหรับจัดการสัญลักษณ์คริปโต
@app.get("/api/symbols", response_model=SymbolResponse)
async def get_symbols():
    """
    ดึงรายการสัญลักษณ์ที่รองรับทั้งหมด
    
    Returns:
        รายการสัญลักษณ์คริปโตที่รองรับ
    """
    try:
        symbols = env.get_available_symbols()
        return SymbolResponse(
            success=True,
            message=f"พบ {len(symbols)} สัญลักษณ์",
            symbols=symbols
        )
    except Exception as e:
        return SymbolResponse(
            success=False,
            message=f"เกิดข้อผิดพลาด: {str(e)}",
            symbols=[]
        )

@app.post("/api/symbols/add", response_model=SymbolResponse)
async def add_symbol(request: SymbolRequest, background_tasks: BackgroundTasks):
    """
    เพิ่มสัญลักษณ์คริปโตใหม่
    
    Args:
        request: ข้อมูลสัญลักษณ์ที่จะเพิ่ม
        
    Returns:
        สถานะการเพิ่มและรายการสัญลักษณ์ที่อัปเดตแล้ว
    """
    try:
        # ตรวจสอบรูปแบบของสัญลักษณ์
        symbol = request.symbol.strip().upper()
        if not symbol.endswith("USDT"):
            return SymbolResponse(
                success=False,
                message="สัญลักษณ์ต้องลงท้ายด้วย USDT",
                symbols=env.get_available_symbols()
            )
        
        # เพิ่มสัญลักษณ์ใหม่
        success = env.add_symbol(symbol)
        
        # ถ้าเพิ่มสำเร็จ ให้รีสตาร์ท Binance WebSocket client
        if success:
            # อัปเดตตัวแปรในระดับแอปพลิเคชัน
            global SYMBOLS
            SYMBOLS = env.get_available_symbols()
            
            # รีสตาร์ท WebSocket client ใน background task
            background_tasks.add_task(restart_websocket_client)
            
            return SymbolResponse(
                success=True,
                message=f"เพิ่มสัญลักษณ์ {symbol} สำเร็จ และกำลังเริ่มการติดตาม",
                symbols=SYMBOLS
            )
        else:
            return SymbolResponse(
                success=False,
                message=f"ไม่สามารถเพิ่มสัญลักษณ์ {symbol} ได้ (อาจมีอยู่แล้ว)",
                symbols=env.get_available_symbols()
            )
            
    except Exception as e:
        return SymbolResponse(
            success=False,
            message=f"เกิดข้อผิดพลาด: {str(e)}",
            symbols=env.get_available_symbols()
        )

@app.post("/api/symbols/remove", response_model=SymbolResponse)
async def remove_symbol(request: SymbolRequest, background_tasks: BackgroundTasks):
    """
    ลบสัญลักษณ์คริปโตที่มีอยู่
    
    Args:
        request: ข้อมูลสัญลักษณ์ที่จะลบ
        
    Returns:
        สถานะการลบและรายการสัญลักษณ์ที่อัปเดตแล้ว
    """
    try:
        symbol = request.symbol.strip().upper()
        success = env.remove_symbol(symbol)
        
        # ถ้าลบสำเร็จ ให้รีสตาร์ท Binance WebSocket client
        if success:
            # อัปเดตตัวแปรในระดับแอปพลิเคชัน
            global SYMBOLS
            SYMBOLS = env.get_available_symbols()
            
            # รีสตาร์ท WebSocket client ใน background task
            background_tasks.add_task(restart_websocket_client)
            
            return SymbolResponse(
                success=True,
                message=f"ลบสัญลักษณ์ {symbol} สำเร็จ",
                symbols=SYMBOLS
            )
        else:
            return SymbolResponse(
                success=False,
                message=f"ไม่สามารถลบสัญลักษณ์ {symbol} ได้ (อาจไม่พบหรือเป็นสัญลักษณ์สุดท้าย)",
                symbols=env.get_available_symbols()
            )
            
    except Exception as e:
        return SymbolResponse(
            success=False,
            message=f"เกิดข้อผิดพลาด: {str(e)}",
            symbols=env.get_available_symbols()
        )

# ฟังก์ชันสำหรับรีสตาร์ท WebSocket client
async def restart_websocket_client():
    """รีสตาร์ท Binance WebSocket client เพื่อปรับปรุงรายการสัญลักษณ์ที่ติดตาม"""
    try:
        # ปิดการเชื่อมต่อ WebSocket เดิม (ถ้ามี)
        if hasattr(app, 'ws_client') and app.ws_client:
            await app.ws_client.close()
        
        # สร้างอินสแตนซ์ใหม่ด้วยสัญลักษณ์ที่อัปเดตแล้ว
        app.ws_client = BinanceWebSocketClient(SYMBOLS)
        
        # เริ่มการติดตามราคาและข้อมูลอื่น ๆ
        asyncio.create_task(app.ws_client.start_kline_streams())
        
        # บันทึกการทำงาน
        logger.info(f"รีสตาร์ท WebSocket client สำเร็จ กับสัญลักษณ์: {', '.join(SYMBOLS)}")
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการรีสตาร์ท WebSocket client: {e}")

@app.websocket("/ws/signals")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint สำหรับสัญญาณการซื้อขายแบบเรียลไทม์
    """
    try:
        # ยอมรับการเชื่อมต่อ
        await manager.connect(websocket)
        
        # ตรวจสอบว่า WebSocket ยังคงเชื่อมต่ออยู่
        try:
            while True:
                try:
                    # รับข้อความจาก client ด้วย timeout
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                    
                    try:
                        client_message = json.loads(data)
                        print(f"📩 ได้รับข้อความจาก WebSocket client: {client_message}")
                        
                        # จัดการกับ pong จาก client
                        if client_message.get('type') == 'pong':
                            print(f"💓 ได้รับ pong จาก client เวลา {datetime.fromtimestamp(client_message.get('timestamp', 0)).strftime('%H:%M:%S')}")
                            continue
                        
                        # ตรวจสอบการสมัครสมาชิก
                        if 'subscribe' in client_message:
                            symbol = client_message['subscribe']
                            print(f"👂 Client ต้องการสมัครสมาชิกสำหรับ {symbol}")
                            
                            # บันทึกการสมัครสมาชิกของ client นี้
                            if websocket in manager.client_subscriptions:
                                manager.client_subscriptions[websocket].add(symbol)
                            
                            if symbol in SYMBOLS and websocket in manager.active_connections:
                                try:
                                    # ส่งข้อมูลล่าสุด
                                    latest_signal = redis_client.get(f"latest_signal:{symbol}")
                                    if latest_signal:
                                        await manager.send_to_client(websocket, json.loads(latest_signal))
                                    else:
                                        mock_data = create_empty_signal(symbol)
                                        await manager.send_to_client(websocket, mock_data)
                                except WebSocketDisconnect:
                                    raise
                                except Exception as e:
                                    print(f"⚠️ เกิดข้อผิดพลาดในการส่งข้อมูลสำหรับ {symbol}: {e}")

                    except json.JSONDecodeError:
                        print("⚠️ ได้รับข้อมูลที่ไม่ใช่ JSON ที่ถูกต้องจาก client")
                    except Exception as e:
                        print(f"❌ เกิดข้อผิดพลาดในการประมวลผลข้อความจาก client: {e}")
                        if "WebSocket is not connected" in str(e):
                            raise WebSocketDisconnect()

                except asyncio.TimeoutError:
                    # ส่ง ping เพื่อตรวจสอบการเชื่อมต่อ
                    try:
                        await websocket.send_json({"type": "ping", "timestamp": int(datetime.now().timestamp())})
                    except Exception:
                        raise WebSocketDisconnect()
                    continue

                except WebSocketDisconnect:
                    raise

        except WebSocketDisconnect:
            print("🔌 WebSocket client ยกเลิกการเชื่อมต่อ")
        finally:
            # ตรวจสอบว่า websocket ยังอยู่ในรายการ active_connections หรือไม่ก่อนเรียก disconnect
            if websocket in manager.active_connections:
                manager.disconnect(websocket)

    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดไม่ทราบสาเหตุใน WebSocket endpoint: {e}")
        # ตรวจสอบว่า websocket ยังอยู่ในรายการ active_connections หรือไม่ก่อนเรียก disconnect
        if websocket in manager.active_connections:
            manager.disconnect(websocket)

@app.websocket("/ws/depth/{symbol}")
async def depth_websocket_endpoint(websocket: WebSocket, symbol: str):
    """
    WebSocket endpoint สำหรับข้อมูล orderbook depth ของสัญลักษณ์ที่ระบุ
    - ส่งข้อมูล mock ในอัตรา 1 ครั้ง/วินาที เพื่อให้ frontend สามารถทำงานได้ระหว่างการแก้ไข
    """
    try:
        # ยอมรับการเชื่อมต่อ
        await websocket.accept()
        print(f"WebSocket connection accepted for depth/{symbol}")
        
        # ตรวจสอบว่าสัญลักษณ์นี้สนับสนุนหรือไม่
        if symbol.upper() not in SYMBOLS:
            await websocket.send_json({
                "error": f"Symbol {symbol} not supported. Available symbols are: {', '.join(SYMBOLS)}"
            })
            await websocket.close()
            return
        
        try:
            # ส่งข้อมูลจำลองทุกวินาที
            while True:
                try:
                    # สร้างข้อมูลจำลอง
                    mock_data = {
                        "symbol": symbol.upper(),
                        "lastUpdateId": int(datetime.now().timestamp() * 1000),
                        "bids": [
                            [str(30000 - i * 10), str(1.0 / (i + 1))] for i in range(5)
                        ],
                        "asks": [
                            [str(30000 + i * 10), str(1.0 / (i + 1))] for i in range(5)
                        ],
                        "timestamp": int(datetime.now().timestamp() * 1000)
                    }
                    
                    # ส่งข้อมูลไปยัง client
                    await websocket.send_json(mock_data)
                    
                    # รอดูว่ามีข้อความจาก client หรือไม่
                    try:
                        client_msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                        try:
                            client_data = json.loads(client_msg)
                            if client_data.get('type') == 'pong':
                                print(f"Received pong from client for depth/{symbol}")
                        except json.JSONDecodeError:
                            pass
                    except asyncio.TimeoutError:
                        pass
                    
                    # รอ 1 วินาทีก่อนส่งข้อมูลถัดไป
                    await asyncio.sleep(1.0)
                    
                except asyncio.CancelledError:
                    print(f"Task for depth/{symbol} was cancelled")
                    break
                    
        except WebSocketDisconnect:
            print(f"WebSocket client for depth/{symbol} disconnected")
        except Exception as e:
            print(f"Error handling depth WebSocket for {symbol}: {e}")
            
    except Exception as e:
        print(f"Error in depth WebSocket endpoint for {symbol}: {e}")
        try:
            await websocket.close()
        except:
            pass

@app.websocket("/ws/trades/{symbol}")
async def trades_websocket_endpoint(websocket: WebSocket, symbol: str):
    """
    WebSocket endpoint สำหรับข้อมูลการซื้อขายล่าสุดของสัญลักษณ์ที่ระบุ
    - ส่งข้อมูล mock ทุก 2 วินาทีเพื่อให้ frontend สามารถทำงานได้ระหว่างการแก้ไข
    """
    try:
        # ยอมรับการเชื่อมต่อ
        await websocket.accept()
        print(f"WebSocket connection accepted for trades/{symbol}")
        
        # ตรวจสอบว่าสัญลักษณ์นี้สนับสนุนหรือไม่
        if symbol.upper() not in SYMBOLS:
            await websocket.send_json({
                "error": f"Symbol {symbol} not supported. Available symbols are: {', '.join(SYMBOLS)}"
            })
            await websocket.close()
            return
        
        try:
            import random
            
            # ส่งข้อมูลจำลองทุก 2 วินาที
            while True:
                try:
                    # กำหนดราคาพื้นฐาน (สมมติว่าเป็นราคา Bitcoin)
                    base_price = 30000 + random.randint(-50, 50)
                    
                    # สร้างข้อมูลการซื้อขายจำลอง
                    is_buyer_maker = random.choice([True, False])
                    mock_trade = {
                        "e": "trade",
                        "E": int(datetime.now().timestamp() * 1000),
                        "s": symbol.upper(),
                        "t": int(datetime.now().timestamp() * 1000000),
                        "p": str(base_price),
                        "q": str(round(random.uniform(0.001, 0.1), 6)),
                        "b": 123456,
                        "a": 123457,
                        "T": int(datetime.now().timestamp() * 1000),
                        "m": is_buyer_maker,
                        "M": True
                    }
                    
                    # ส่งข้อมูลไปยัง client
                    await websocket.send_json(mock_trade)
                    
                    # รอ 2 วินาทีก่อนส่งข้อมูลถัดไป
                    await asyncio.sleep(2.0)
                    
                except asyncio.CancelledError:
                    print(f"Task for trades/{symbol} was cancelled")
                    break
                    
        except WebSocketDisconnect:
            print(f"WebSocket client for trades/{symbol} disconnected")
        except Exception as e:
            print(f"Error handling trades WebSocket for {symbol}: {e}")
            
    except Exception as e:
        print(f"Error in trades WebSocket endpoint for {symbol}: {e}")
        try:
            await websocket.close()
        except:
            pass

@app.websocket("/ws/kline/{symbol}")
async def kline_websocket_endpoint(websocket: WebSocket, symbol: str):
    """
    WebSocket endpoint สำหรับข้อมูล kline (แท่งเทียน) ของสัญลักษณ์ที่ระบุ
    - ส่งข้อมูล mock ทุก 1 นาทีเพื่อให้ frontend สามารถทำงานได้ระหว่างการแก้ไข
    """
    try:
        # ยอมรับการเชื่อมต่อ
        await websocket.accept()
        print(f"WebSocket connection accepted for kline/{symbol}")
        
        # ตรวจสอบว่าสัญลักษณ์นี้สนับสนุนหรือไม่
        if symbol.upper() not in SYMBOLS:
            await websocket.send_json({
                "error": f"Symbol {symbol} not supported. Available symbols are: {', '.join(SYMBOLS)}"
            })
            await websocket.close()
            return
        
        import random
        
        # กำหนดราคาเริ่มต้นและสร้างชุดข้อมูลประวัติ
        base_price = 30000
        current_time = int(datetime.now().timestamp() * 1000) - (60 * 60 * 1000)  # 1 ชั่วโมงก่อน
        interval = 60 * 1000  # 1 นาที
        
        # สร้างข้อมูลประวัติย้อนหลัง 60 แท่ง
        historical_data = []
        for i in range(60):
            price_change = random.uniform(-100, 100)
            open_price = base_price + price_change
            close_price = open_price + random.uniform(-50, 50)
            high_price = max(open_price, close_price) + random.uniform(5, 20)
            low_price = min(open_price, close_price) - random.uniform(5, 20)
            volume = random.uniform(5, 20)
            
            candle = {
                "timestamp": current_time + (i * interval),
                "open": str(open_price),
                "high": str(high_price),
                "low": str(low_price),
                "close": str(close_price),
                "volume": str(volume)
            }
            historical_data.append(candle)
            base_price = float(close_price)
        
        # ส่งข้อมูลประวัติไปยัง client
        await websocket.send_json({
            "type": "kline_history",
            "symbol": symbol.upper(),
            "data": historical_data
        })
        
        # สถานะล่าสุด
        latest_price = float(historical_data[-1]["close"])
        latest_timestamp = historical_data[-1]["timestamp"]
        
        try:
            # ส่งข้อมูลใหม่ทุก 1 นาที
            while True:
                try:
                    # อัพเดทเวลาและราคา
                    latest_timestamp += interval
                    price_change = random.uniform(-50, 50)
                    open_price = latest_price
                    close_price = open_price + price_change
                    high_price = max(open_price, close_price) + random.uniform(5, 20)
                    low_price = min(open_price, close_price) - random.uniform(5, 20)
                    volume = random.uniform(5, 20)
                    
                    # สร้างข้อมูล kline ใหม่
                    new_candle = {
                        "timestamp": latest_timestamp,
                        "open": str(open_price),
                        "high": str(high_price),
                        "low": str(low_price),
                        "close": str(close_price),
                        "volume": str(volume)
                    }
                    
                    # ส่งข้อมูลไปยัง client
                    await websocket.send_json({
                        "type": "kline",
                        "symbol": symbol.upper(),
                        "data": new_candle
                    })
                    
                    # อัพเดทราคาล่าสุด
                    latest_price = close_price
                    
                    # รอ 5 วินาทีในการพัฒนา (จริง ๆ ควรเป็น 1 นาที)
                    await asyncio.sleep(5.0)
                    
                except asyncio.CancelledError:
                    print(f"Task for kline/{symbol} was cancelled")
                    break
                    
        except WebSocketDisconnect:
            print(f"WebSocket client for kline/{symbol} disconnected")
        except Exception as e:
            print(f"Error handling kline WebSocket for {symbol}: {e}")
            
    except Exception as e:
        print(f"Error in kline WebSocket endpoint for {symbol}: {e}")
        try:
            await websocket.close()
        except:
            pass

# ฟังก์ชันเริ่มต้น Binance WebSocket Client ในพื้นหลัง
async def start_binance_client():
    """เริ่มต้น Binance WebSocket client และฟังการอัพเดตข้อมูล"""
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            print("🚀 กำลังเริ่มต้น Binance WebSocket client...")
            client = BinanceWebSocketClient()
            connected = await client.connect()
            
            if connected and client.is_running:
                print("✅ เชื่อมต่อกับ Binance WebSocket สำเร็จ")
                await client.start_kline_streams()
                
                # ทำงานต่อไปจนกว่าจะถูกยกเลิก
                while client.is_running:
                    await asyncio.sleep(60)
            else:
                print("⚠️ ไม่สามารถเชื่อมต่อกับ Binance WebSocket ได้")
                await asyncio.sleep(10)  # รอก่อนลองอีกครั้ง
                retry_count += 1
        except asyncio.CancelledError:
            print("🛑 ยกเลิกการทำงานของ Binance client")
            break
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดใน Binance client: {e}")
            await asyncio.sleep(10)  # รอก่อนลองอีกครั้ง
            retry_count += 1
        finally:
            try:
                if 'client' in locals() and client:
                    await client.close()
            except Exception as e:
                print(f"⚠️ เกิดข้อผิดพลาดในการปิด Binance client: {e}")
    
    print("⚠️ ไม่สามารถเริ่มต้น Binance client ได้หลังจากพยายามซ้ำหลายครั้ง")

# ฟังก์ชันที่ตรวจสอบข้อมูล kline ใหม่และสร้างสัญญาณ
async def process_kline_data():
    """รับข้อมูล kline จาก Redis PubSub และสร้างสัญญาณ"""
    if not redis_connected:
        print("⚠️ ไม่สามารถเริ่มกระบวนการประมวลผลข้อมูล kline ได้ - Redis ไม่ได้เชื่อมต่อ")
        return
    
    try:
        pubsub = redis_client.pubsub()
        
        # สมัครสมาชิกช่องสำหรับทุกสัญลักษณ์
        for symbol in SYMBOLS:
            channel = f"{REDIS_KLINE_CHANNEL_PREFIX}{symbol}:2m"
            pubsub.subscribe(channel)
            print(f"👂 สมัครสมาชิก Redis ช่อง {channel}")
        
        while True:
            if not redis_connected:
                print("⚠️ Redis ไม่ได้เชื่อมต่อ - หยุดประมวลผลข้อมูล kline ชั่วคราว")
                await asyncio.sleep(10)
                continue
                
            try:
                message = pubsub.get_message(ignore_subscribe_messages=True)
                
                if message and message['type'] == 'message':
                    try:
                        # แปลงข้อความเป็น JSON
                        data = json.loads(message['data'])
                        
                        # ดึงสัญลักษณ์จากชื่อช่อง
                        channel = message['channel']
                        channel_str = channel if isinstance(channel, str) else channel.decode()
                        parts = channel_str.split(':')
                        
                        # แก้ไขการดึงสัญลักษณ์จากชื่อช่อง
                        if len(parts) >= 3:
                            symbol = parts[2].split(":")[0]  # ดึงสัญลักษณ์จากชื่อช่อง
                            
                            # เพิ่มการตรวจสอบว่า symbol อยู่ใน SYMBOLS หรือไม่
                            if symbol in SYMBOLS:
                                # ประมวลผลข้อมูลและสร้างสัญญาณ
                                print(f"📊 ได้รับข้อมูล kline ใหม่สำหรับ {symbol}")
                                signal = signal_processor.process_market_data(symbol, data)
                                
                                if signal:
                                    print(f"📊 สร้างสัญญาณใหม่: {signal['category']} สำหรับ {symbol}")
                                    
                                    # ตรวจสอบว่าสัญญาณถูกบันทึกไปยัง Redis หรือไม่
                                    try:
                                        latest_signal = redis_client.get(f"latest_signal:{symbol}")
                                        if latest_signal:
                                            print(f"✅ บันทึกสัญญาณล่าสุดสำหรับ {symbol} สำเร็จ")
                                        else:
                                            print(f"⚠️ ไม่พบการบันทึกสัญญาณล่าสุดสำหรับ {symbol}")
                                    except Exception as e:
                                        print(f"⚠️ ไม่สามารถตรวจสอบสัญลักษณ์ล่าสุดได้: {e}")
                            else:
                                print(f"⚠️ ได้รับข้อมูลสำหรับสัญลักษณ์ที่ไม่รู้จัก: {symbol}")
                        else:
                            print(f"⚠️ รูปแบบช่อง Redis ไม่ถูกต้อง: {channel_str}")
                            
                    except json.JSONDecodeError as e:
                        print(f"⚠️ ไม่สามารถแปลงข้อความเป็น JSON ได้: {e}")
                    except Exception as e:
                        print(f"❌ เกิดข้อผิดพลาดในการประมวลผลข้อความ: {e}")
            except redis.RedisError as e:
                print(f"⚠️ เกิดข้อผิดพลาด Redis ในการรับข้อความ: {e}")
                await asyncio.sleep(5)  # รอก่อนลองอีกครั้ง
            except Exception as e:
                print(f"❌ เกิดข้อผิดพลาดในการรับข้อความ: {e}")
                await asyncio.sleep(5)  # รอก่อนลองอีกครั้ง
            
            await asyncio.sleep(0.01)  # ลดการใช้ CPU
    except asyncio.CancelledError:
        # หยุดการทำงานเมื่อแอปถูกปิด
        try:
            pubsub.unsubscribe()
        except Exception as e:
            print(f"⚠️ เกิดข้อผิดพลาดในการยกเลิกการสมัครสมาชิก: {e}")
        print("🛑 กระบวนการประมวลผลข้อมูล kline ถูกยกเลิก")
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในตัวประมวลผลข้อมูล: {e}")
        try:
            pubsub.unsubscribe()
        except Exception as unsub_err:
            print(f"⚠️ เกิดข้อผิดพลาดในการยกเลิกการสมัครสมาชิก: {unsub_err}")

# ฟังก์ชันเริ่มต้น Notification Service ในพื้นหลัง
async def start_notification_service():
    """เริ่มต้นบริการแจ้งเตือนในพื้นหลัง"""
    if not redis_connected:
        print("⚠️ ไม่สามารถเริ่มบริการแจ้งเตือนได้ - Redis ไม่ได้เชื่อมต่อ")
        return
        
    try:
        print("📱 กำลังเริ่มต้นบริการแจ้งเตือน...")
        notification_service = NotificationService()
        
        try:
            pubsub = notification_service.pubsub
            print("👂 บริการแจ้งเตือนกำลังฟังข้อความ...")
            
            while True:
                if not redis_connected:
                    print("⚠️ Redis ไม่ได้เชื่อมต่อ - หยุดบริการแจ้งเตือนชั่วคราว")
                    await asyncio.sleep(10)
                    continue
                    
                try:
                    message = pubsub.get_message(ignore_subscribe_messages=True)
                    if message:
                        print(f"📣 ได้รับข้อความใหม่สำหรับการแจ้งเตือน")
                        notification_service.process_message(message)
                except redis.RedisError as e:
                    print(f"⚠️ เกิดข้อผิดพลาด Redis ในบริการแจ้งเตือน: {e}")
                    await asyncio.sleep(5)
                    
                await asyncio.sleep(0.01)  # ลดการใช้ CPU
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในบริการแจ้งเตือน: {e}")
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการเริ่มบริการแจ้งเตือน: {e}")
    finally:
        try:
            if 'pubsub' in locals():
                pubsub.unsubscribe()
        except Exception as e:
            print(f"⚠️ เกิดข้อผิดพลาดในการยกเลิกการสมัครสมาชิกของบริการแจ้งเตือน: {e}")

@app.on_event("startup")
async def startup_event():
    """เริ่มต้นงานพื้นหลังเมื่อแอปเริ่มต้น"""
    global redis_connected
    
    print("🚀 กำลังเริ่มต้น API server...")
    
    # ตรวจสอบการเชื่อมต่อ Redis อีกครั้ง
    if not redis_connected:
        redis_connected = connect_to_redis()
    
    # เริ่มเก็บข้อมูลจาก Binance WebSocket
    asyncio.create_task(start_binance_client())
    print("✅ เริ่มต้น task Binance WebSocket client แล้ว")
    
    # เริ่มประมวลผลข้อมูลเพื่อสร้างสัญญาณ
    asyncio.create_task(process_kline_data())
    print("✅ เริ่มต้น task ประมวลผลข้อมูล kline แล้ว")
    
    # เริ่มบริการแจ้งเตือน
    asyncio.create_task(start_notification_service())
    print("✅ เริ่มต้น task บริการแจ้งเตือนแล้ว")
    
    print("🌟 API server เริ่มต้นเสร็จสมบูรณ์")

@app.on_event("shutdown")
async def shutdown_event():
    """จัดการการปิดแอปอย่างสะอาด"""
    # ทาสคงจะถูกยกเลิกโดยอัตโนมัติเมื่อแอปถูกปิด
    print("⏹️ กำลังปิดแอป...")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)