import asyncio
import json
import os
import time
import websockets
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Union, Callable, Any

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
                    print("Mock InfluxDBStorage - No actual InfluxDB connection")
                
                def store_candle(self, data):
                    pass
                
                def store_trade(self, data):
                    pass
                
                def store_ticker(self, data):
                    pass
                
                def store_depth(self, data):
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

from .optimized_signal_processor import signal_processor
from .logger import LoggerFactory, log_execution_time, error_logger, MetricsLogger

class BinanceWebSocketClient:
    def __init__(self, symbols: List[str], callback: Optional[Callable] = None):
        """Initialize WebSocket client with logging"""
        self.logger = LoggerFactory.get_logger('binance_ws')
        self.metrics = MetricsLogger('binance_ws')
        
        self.symbols = symbols
        self.callback = callback
        self.websocket = None
        try:
            # ใช้ redis client จาก redis_manager แทนการสร้างใหม่
            from .redis_manager import get_redis_client
            self.redis_client = get_redis_client(decode_responses=True)
            self.logger.info("Redis connection established via connection pool")
        except Exception as e:
            self.logger.error(f"Redis connection failed: {e}")
            error_logger.log_error(e, {'component': 'binance_ws', 'connection': 'redis'})
            raise
        
        # Initialize metrics
        self.metrics.record_metric('initialization', {
            'symbols': symbols,
            'timestamp': datetime.now().isoformat()
        })
        
        # Reconnection settings
        self.reconnect_delay = 1.0
        self.max_reconnect_delay = 60.0
        self.reconnect_count = 0
        self.max_reconnect_attempts = 10
        
        # Message buffer
        self.message_buffer = []
        self.buffer_size = 100
        self.last_flush_time = time.time()
        self.flush_interval = 1.0
        
    @log_execution_time()
    async def connect(self):
        """Connect to WebSocket with enhanced error handling"""
        while True:
            try:
                streams = [f"{symbol.lower()}@kline_1m" for symbol in self.symbols]
                url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(streams)}"
                
                self.logger.info(f"Connecting to Binance WebSocket: {url}")
                
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=20,
                    compression=None,
                    max_size=2**23,
                    close_timeout=10
                ) as websocket:
                    self.websocket = websocket
                    self.logger.info(f"WebSocket connected successfully")
                    
                    # Reset reconnection parameters
                    self.reconnect_delay = 1.0
                    self.reconnect_count = 0
                    
                    # Start health check
                    health_check_task = asyncio.create_task(self._health_check())
                    
                    try:
                        while True:
                            message = await websocket.recv()
                            await self._handle_message(message)
                    except websockets.ConnectionClosed as e:
                        self.logger.warning(f"WebSocket connection closed: {e}")
                        error_logger.log_error(e, {
                            'component': 'binance_ws',
                            'event': 'connection_closed',
                            'reconnect_count': self.reconnect_count
                        })
                        health_check_task.cancel()
                        raise
                        
            except Exception as e:
                self.logger.error(f"WebSocket error: {e}")
                error_logger.log_error(e, {
                    'component': 'binance_ws',
                    'event': 'connection_error',
                    'reconnect_count': self.reconnect_count
                })
                
                if self.reconnect_count >= self.max_reconnect_attempts:
                    self.logger.error("Maximum reconnection attempts reached")
                    break
                    
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
                self.reconnect_count += 1
                
                # Record metrics for reconnection
                self.metrics.record_metric('reconnection_attempt', {
                    'attempt_number': self.reconnect_count,
                    'delay': self.reconnect_delay,
                    'timestamp': datetime.now().isoformat()
                })

    @log_execution_time()
    async def _handle_message(self, message: str):
        """Handle incoming messages with error tracking"""
        try:
            start_time = time.time()
            
            data = json.loads(message)
            self.message_buffer.append(data)
            
            # Record message processing metrics
            processing_time = time.time() - start_time
            self.metrics.record_metric('message_processing', {
                'processing_time': processing_time,
                'buffer_size': len(self.message_buffer),
                'timestamp': datetime.now().isoformat()
            })
            
            # Check if buffer should be flushed
            current_time = time.time()
            should_flush = (
                len(self.message_buffer) >= self.buffer_size or
                current_time - self.last_flush_time >= self.flush_interval
            )
            
            if should_flush:
                await self._flush_buffer()
                
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error: {message[:100]}...")
            error_logger.log_error(e, {
                'component': 'binance_ws',
                'event': 'message_decode_error',
                'message_preview': message[:100]
            })
        except Exception as e:
            self.logger.error(f"Message handling error: {e}")
            error_logger.log_error(e, {
                'component': 'binance_ws',
                'event': 'message_handling_error'
            })

    @log_execution_time()
    async def _flush_buffer(self):
        """Flush message buffer with error handling"""
        if not self.message_buffer:
            return
            
        try:
            start_time = time.time()
            
            # Process messages in batch
            kline_data = []
            for msg in self.message_buffer:
                if "data" in msg and "k" in msg["data"]:
                    kline = msg["data"]["k"]
                    kline_data.append({
                        "symbol": kline["s"],
                        "timestamp": kline["t"],
                        "open": float(kline["o"]),
                        "high": float(kline["h"]),
                        "low": float(kline["l"]),
                        "close": float(kline["c"]),
                        "volume": float(kline["v"])
                    })
            
            # Store in Redis
            if kline_data:
                try:
                    self.redis_client.xadd(
                        "market_data",
                        {"data": json.dumps(kline_data)},
                        maxlen=10000
                    )
                except redis.RedisError as e:
                    self.logger.error(f"Redis storage error: {e}")
                    error_logger.log_error(e, {
                        'component': 'binance_ws',
                        'event': 'redis_storage_error'
                    })
            
            # Call callback if exists
            if self.callback and kline_data:
                try:
                    await self.callback(kline_data)
                except Exception as e:
                    self.logger.error(f"Callback error: {e}")
                    error_logger.log_error(e, {
                        'component': 'binance_ws',
                        'event': 'callback_error'
                    })
            
            # Record metrics
            processing_time = time.time() - start_time
            self.metrics.record_metric('buffer_flush', {
                'processing_time': processing_time,
                'messages_processed': len(self.message_buffer),
                'klines_processed': len(kline_data),
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            self.logger.error(f"Buffer flush error: {e}")
            error_logger.log_error(e, {
                'component': 'binance_ws',
                'event': 'buffer_flush_error',
                'buffer_size': len(self.message_buffer)
            })
        finally:
            self.message_buffer.clear()
            self.last_flush_time = time.time()

    @log_execution_time()
    async def _health_check(self):
        """Monitor WebSocket health"""
        while True:
            try:
                if self.websocket and self.websocket.open:
                    await self.websocket.ping()
                    self.metrics.record_metric('health_check', {
                        'status': 'healthy',
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    self.logger.warning("WebSocket connection unhealthy")
                    self.metrics.record_metric('health_check', {
                        'status': 'unhealthy',
                        'timestamp': datetime.now().isoformat()
                    })
                await asyncio.sleep(30)
            except Exception as e:
                self.logger.error(f"Health check error: {e}")
                error_logger.log_error(e, {
                    'component': 'binance_ws',
                    'event': 'health_check_error'
                })
                break
                
    async def close(self):
        """Close connections and cleanup resources"""
        try:
            self.logger.info("Closing WebSocket connection...")
            
            if self.websocket:
                await self.websocket.close()
            
            # Record final metrics
            self.metrics.record_metric('shutdown', {
                'total_reconnections': self.reconnect_count,
                'timestamp': datetime.now().isoformat()
            })
            
            if hasattr(self, 'processor'):
                self.processor.cleanup()
                
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            error_logger.log_error(e, {
                'component': 'binance_ws',
                'event': 'cleanup_error'
            })
        finally:            try:
                await self.redis_client.close()
            except Exception as e:
                self.logger.error(f"Error closing Redis connection: {e}")
                
    @log_execution_time()
    async def start_kline_streams(self):
        """
        เริ่มต้นการสมัครสมาชิก Binance WebSocket streams ทั้งหมดที่จำเป็น
        - kline streams สำหรับการวิเคราะห์ราคา
        - depth streams สำหรับข้อมูล orderbook
        - trades streams สำหรับข้อมูลการซื้อขายล่าสุด
        """
        self.logger.info("Starting Binance WebSocket streams...")
        
        # เริ่มการเชื่อมต่อใหม่ถ้ายังไม่ได้เชื่อมต่อ
        if not hasattr(self, 'websocket') or not self.websocket or not self.websocket.open:
            await self.connect()
            
        try:
            # เริ่ม depth และ trades streams สำหรับแต่ละสัญลักษณ์
            for symbol in self.symbols:
                # เริ่ม depth stream
                asyncio.create_task(self.start_depth_stream(symbol))
                self.logger.info(f"Started depth stream for {symbol}")
                
                # เริ่ม trades stream
                asyncio.create_task(self.start_trades_stream(symbol))
                self.logger.info(f"Started trades stream for {symbol}")
                
            return True
        except Exception as e:
            self.logger.error(f"Failed to start streams: {e}")
            error_logger.log_error(e, {
                'component': 'binance_ws',
                'event': 'start_streams_error'
            })
            return False
            
    @log_execution_time()
    async def start_depth_stream(self, symbol: str):
        """
        เริ่มต้นการสมัครสมาชิก depth stream สำหรับสัญลักษณ์ที่ระบุ
        
        Args:
            symbol: สัญลักษณ์คริปโตที่ต้องการข้อมูล depth
        """
        stream_name = f"{symbol.lower()}@depth20@100ms"
        url = f"wss://stream.binance.com:9443/ws/{stream_name}"
        
        self.logger.info(f"Connecting to depth stream: {url}")
        
        reconnect_delay = 1.0
        max_reconnect_delay = 60.0
        reconnect_count = 0
        
        while True:
            try:
                async with websockets.connect(url, ping_interval=30) as ws:
                    self.logger.info(f"Connected to depth stream for {symbol}")
                    
                    # รีเซ็ตค่าสำหรับการเชื่อมต่อใหม่
                    reconnect_delay = 1.0
                    reconnect_count = 0
                    
                    while True:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=60)
                            
                            # แปลงข้อความเป็น JSON และประมวลผล
                            data = json.loads(message)
                            
                            # เก็บข้อมูลล่าสุดใน Redis
                            redis_key = f"latest_depth:{symbol}"
                            self.redis_client.set(redis_key, message, ex=60)  # หมดอายุใน 60 วินาที
                            
                            # เผยแพร่ข้อมูลไปยัง channel
                            redis_channel = f"crypto_signals:depth:{symbol}"
                            self.redis_client.publish(redis_channel, message)
                            
                        except asyncio.TimeoutError:
                            # ส่ง ping เพื่อตรวจสอบการเชื่อมต่อ
                            try:
                                pong = await ws.ping()
                                await asyncio.wait_for(pong, timeout=10)
                            except Exception:
                                # การเชื่อมต่อมีปัญหา เชื่อมต่อใหม่
                                raise ConnectionError("Ping failed")
                                
                        except json.JSONDecodeError as e:
                            self.logger.error(f"JSON decode error in depth stream: {message[:100]}...")
                            error_logger.log_error(e, {
                                'component': 'binance_ws',
                                'event': 'depth_decode_error',
                                'symbol': symbol
                            })
                            
                        except Exception as e:
                            self.logger.error(f"Error processing depth message: {e}")
                            error_logger.log_error(e, {
                                'component': 'binance_ws',
                                'event': 'depth_processing_error',
                                'symbol': symbol
                            })
                            # หากเป็นข้อผิดพลาดการเชื่อมต่อ ให้เชื่อมต่อใหม่
                            if "connection" in str(e).lower() or "socket" in str(e).lower():
                                raise ConnectionError(str(e))
                            
            except (websockets.exceptions.ConnectionClosed, ConnectionError) as e:
                if reconnect_count >= 10:
                    self.logger.error(f"Maximum reconnection attempts reached for depth stream {symbol}")
                    break
                
                self.logger.warning(f"Depth stream for {symbol} disconnected: {e}. Reconnecting in {reconnect_delay}s...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
                reconnect_count += 1
                
            except Exception as e:
                self.logger.error(f"Unexpected error in depth stream for {symbol}: {e}")
                error_logger.log_error(e, {
                    'component': 'binance_ws',
                    'event': 'depth_stream_error',
                    'symbol': symbol
                })
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
                reconnect_count += 1

    @log_execution_time()
    async def start_trades_stream(self, symbol: str):
        """
        เริ่มต้นการสมัครสมาชิก trades stream สำหรับสัญลักษณ์ที่ระบุ
        
        Args:
            symbol: สัญลักษณ์คริปโตที่ต้องการข้อมูลการซื้อขาย
        """
        stream_name = f"{symbol.lower()}@trade"
        url = f"wss://stream.binance.com:9443/ws/{stream_name}"
        
        self.logger.info(f"Connecting to trades stream: {url}")
        
        reconnect_delay = 1.0
        max_reconnect_delay = 60.0
        reconnect_count = 0
        
        while True:
            try:
                async with websockets.connect(url, ping_interval=30) as ws:
                    self.logger.info(f"Connected to trades stream for {symbol}")
                    
                    # รีเซ็ตค่าสำหรับการเชื่อมต่อใหม่
                    reconnect_delay = 1.0
                    reconnect_count = 0
                    
                    while True:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=60)
                            
                            # แปลงข้อความเป็น JSON และประมวลผล
                            data = json.loads(message)
                            
                            # เก็บข้อมูลล่าสุดใน Redis (เฉพาะรายการซื้อขายล่าสุด 100 รายการ)
                            redis_key = f"latest_trades:{symbol}"
                            trade_list_key = f"trades_list:{symbol}"
                            
                            # เก็บข้อมูลซื้อขายล่าสุดใน Redis
                            self.redis_client.set(redis_key, message, ex=60)  # หมดอายุใน 60 วินาที
                            
                            # เก็บรายการซื้อขายล่าสุด 100 รายการใน Redis List
                            self.redis_client.lpush(trade_list_key, message)
                            self.redis_client.ltrim(trade_list_key, 0, 99)  # เก็บเฉพาะ 100 รายการล่าสุด
                            
                            # เผยแพร่ข้อมูลไปยัง channel
                            redis_channel = f"crypto_signals:trades:{symbol}"
                            self.redis_client.publish(redis_channel, message)
                            
                        except asyncio.TimeoutError:
                            # ส่ง ping เพื่อตรวจสอบการเชื่อมต่อ
                            try:
                                pong = await ws.ping()
                                await asyncio.wait_for(pong, timeout=10)
                            except Exception:
                                # การเชื่อมต่อมีปัญหา เชื่อมต่อใหม่
                                raise ConnectionError("Ping failed")
                                
                        except json.JSONDecodeError as e:
                            self.logger.error(f"JSON decode error in trades stream: {message[:100]}...")
                            error_logger.log_error(e, {
                                'component': 'binance_ws',
                                'event': 'trades_decode_error',
                                'symbol': symbol
                            })
                            
                        except Exception as e:
                            self.logger.error(f"Error processing trades message: {e}")
                            error_logger.log_error(e, {
                                'component': 'binance_ws',
                                'event': 'trades_processing_error',
                                'symbol': symbol
                            })
                            # หากเป็นข้อผิดพลาดการเชื่อมต่อ ให้เชื่อมต่อใหม่
                            if "connection" in str(e).lower() or "socket" in str(e).lower():
                                raise ConnectionError(str(e))
                            
            except (websockets.exceptions.ConnectionClosed, ConnectionError) as e:
                if reconnect_count >= 10:
                    self.logger.error(f"Maximum reconnection attempts reached for trades stream {symbol}")
                    break
                
                self.logger.warning(f"Trades stream for {symbol} disconnected: {e}. Reconnecting in {reconnect_delay}s...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
                reconnect_count += 1
                
            except Exception as e:
                self.logger.error(f"Unexpected error in trades stream for {symbol}: {e}")
                error_logger.log_error(e, {
                    'component': 'binance_ws',
                    'event': 'trades_stream_error',
                    'symbol': symbol
                })
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
                reconnect_count += 1

async def main():
    """ฟังก์ชันหลักสำหรับเริ่มต้นโปรแกรม"""
    client = BinanceWebSocketClient(SYMBOLS)
    
    try:
        await client.connect()
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