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

from .logger import LoggerFactory, log_execution_time, error_logger, MetricsLogger
from .optimized_signal_processor import signal_processor
from .influxdb_storage import InfluxDBStorage

# Load environment variables
load_dotenv()

# Redis connection settings
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_CHANNEL_PREFIX = "crypto_signals:kline:"

# Default symbols to monitor
SYMBOLS = ["BTCUSDT", "ETHUSDT"]

# WebSocket endpoints
BINANCE_WS_API_ENDPOINT = "wss://ws-api.binance.com:443/ws-api/v3"
BINANCE_WS_STREAM_ENDPOINT = "wss://stream.binance.com:9443/ws"
BINANCE_WS_TESTNET_ENDPOINT = "wss://ws-api.testnet.binance.vision/ws-api/v3"

class EnhancedWebSocketClient:
    """Enhanced WebSocket Client with comprehensive error handling and logging"""
    
    def __init__(self, symbols: List[str], callback: Optional[Callable] = None):
        """Initialize WebSocket client with logging and metrics"""
        self.logger = LoggerFactory.get_logger('binance_ws')
        self.metrics = MetricsLogger('binance_ws')
        
        self.symbols = symbols
        self.callback = callback
        self.websocket = None
        self.processor = signal_processor
        
        # Initialize Redis connection
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
            self.logger.info("Redis connection established")
        except redis.RedisError as e:
            self.logger.error(f"Redis connection failed: {e}")
            error_logger.log_error(e, {'component': 'binance_ws', 'connection': 'redis'})
            raise
            
        # Initialize InfluxDB connection
        try:
            self.influxdb = InfluxDBStorage()
            self.logger.info("InfluxDB connection established")
        except Exception as e:
            self.logger.error(f"InfluxDB connection failed: {e}")
            error_logger.log_error(e, {'component': 'binance_ws', 'connection': 'influxdb'})
        
        # Reconnection settings
        self.reconnect_delay = 1.0
        self.max_reconnect_delay = 60.0
        self.reconnect_count = 0
        self.max_reconnect_attempts = 10
        
        # Message buffer settings
        self.message_buffer = []
        self.buffer_size = 100
        self.last_flush_time = time.time()
        self.flush_interval = 1.0
        
        # Connection ID for tracking
        self.connection_id = str(uuid.uuid4())
        
        # Initialize metrics
        self.metrics.record_metric('initialization', {
            'symbols': symbols,
            'connection_id': self.connection_id,
            'timestamp': datetime.now().isoformat()
        })
    
    @log_execution_time()
    async def connect(self):
        """Connect to WebSocket with enhanced error handling and metrics"""
        while True:
            try:
                # Create combined stream URL
                streams = [f"{symbol.lower()}@kline_1m" for symbol in self.symbols]
                url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(streams)}"
                
                self.logger.info(f"Connecting to WebSocket: {url}")
                connection_start = time.time()
                
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=20,
                    compression=None,
                    max_size=2**23,
                    close_timeout=10
                ) as websocket:
                    self.websocket = websocket
                    connection_time = time.time() - connection_start
                    
                    self.logger.info(f"WebSocket connected successfully in {connection_time:.2f}s")
                    self.metrics.record_metric('connection', {
                        'status': 'connected',
                        'connection_time': connection_time,
                        'connection_id': self.connection_id,
                        'timestamp': datetime.now().isoformat()
                    })
                    
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
                            'connection_id': self.connection_id,
                            'reconnect_count': self.reconnect_count
                        })
                        health_check_task.cancel()
                        raise
                        
            except Exception as e:
                self.logger.error(f"WebSocket error: {e}")
                error_logger.log_error(e, {
                    'component': 'binance_ws',
                    'event': 'connection_error',
                    'connection_id': self.connection_id,
                    'reconnect_count': self.reconnect_count
                })
                
                if self.reconnect_count >= self.max_reconnect_attempts:
                    self.logger.error("Maximum reconnection attempts reached")
                    self.metrics.record_metric('connection_failed', {
                        'reason': 'max_attempts_reached',
                        'connection_id': self.connection_id,
                        'timestamp': datetime.now().isoformat()
                    })
                    break
                    
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
                self.reconnect_count += 1
                
                self.metrics.record_metric('reconnection_attempt', {
                    'attempt_number': self.reconnect_count,
                    'delay': self.reconnect_delay,
                    'connection_id': self.connection_id,
                    'timestamp': datetime.now().isoformat()
                })
    
    @log_execution_time()
    async def _handle_message(self, message: str):
        """Handle incoming messages with comprehensive error tracking"""
        try:
            start_time = time.time()
            
            data = json.loads(message)
            self.message_buffer.append(data)
            
            # Record message processing metrics
            processing_time = time.time() - start_time
            self.metrics.record_metric('message_processing', {
                'processing_time': processing_time,
                'buffer_size': len(self.message_buffer),
                'connection_id': self.connection_id,
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
                'message_preview': message[:100],
                'connection_id': self.connection_id
            })
        except Exception as e:
            self.logger.error(f"Message handling error: {e}")
            error_logger.log_error(e, {
                'component': 'binance_ws',
                'event': 'message_handling_error',
                'connection_id': self.connection_id
            })
    
    @log_execution_time()
    async def _flush_buffer(self):
        """Process and store buffered messages with error handling"""
        if not self.message_buffer:
            return
            
        try:
            start_time = time.time()
            
            # Process messages in batch
            kline_data = []
            processing_errors = []
            
            for msg in self.message_buffer:
                try:
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
                except (KeyError, ValueError) as e:
                    processing_errors.append({
                        "error": str(e),
                        "message": str(msg)[:100]
                    })
            
            # Store in Redis
            if kline_data:
                try:
                    pipeline = self.redis_client.pipeline()
                    pipeline.xadd(
                        "market_data",
                        {"data": json.dumps(kline_data)},
                        maxlen=10000
                    )
                    pipeline.execute()
                except redis.RedisError as e:
                    self.logger.error(f"Redis storage error: {e}")
                    error_logger.log_error(e, {
                        'component': 'binance_ws',
                        'event': 'redis_storage_error',
                        'connection_id': self.connection_id
                    })
            
            # Store in InfluxDB
            if kline_data and hasattr(self, 'influxdb'):
                try:
                    for data in kline_data:
                        self.influxdb.store_kline_data(data["symbol"], [data])
                except Exception as e:
                    self.logger.error(f"InfluxDB storage error: {e}")
                    error_logger.log_error(e, {
                        'component': 'binance_ws',
                        'event': 'influxdb_storage_error',
                        'connection_id': self.connection_id
                    })
            
            # Call callback if exists
            if self.callback and kline_data:
                try:
                    await self.callback(kline_data)
                except Exception as e:
                    self.logger.error(f"Callback error: {e}")
                    error_logger.log_error(e, {
                        'component': 'binance_ws',
                        'event': 'callback_error',
                        'connection_id': self.connection_id
                    })
            
            # Record metrics
            processing_time = time.time() - start_time
            self.metrics.record_metric('buffer_flush', {
                'processing_time': processing_time,
                'messages_processed': len(self.message_buffer),
                'klines_processed': len(kline_data),
                'errors': len(processing_errors),
                'connection_id': self.connection_id,
                'timestamp': datetime.now().isoformat()
            })
            
            # Log processing errors if any
            if processing_errors:
                self.logger.warning(f"Message processing errors: {json.dumps(processing_errors)}")
            
        except Exception as e:
            self.logger.error(f"Buffer flush error: {e}")
            error_logger.log_error(e, {
                'component': 'binance_ws',
                'event': 'buffer_flush_error',
                'buffer_size': len(self.message_buffer),
                'connection_id': self.connection_id
            })
        finally:
            self.message_buffer.clear()
            self.last_flush_time = time.time()
    
    @log_execution_time()
    async def _health_check(self):
        """Monitor WebSocket health with metrics"""
        while True:
            try:
                if self.websocket and self.websocket.open:
                    await self.websocket.ping()
                    self.metrics.record_metric('health_check', {
                        'status': 'healthy',
                        'connection_id': self.connection_id,
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    self.logger.warning("WebSocket connection unhealthy")
                    self.metrics.record_metric('health_check', {
                        'status': 'unhealthy',
                        'connection_id': self.connection_id,
                        'timestamp': datetime.now().isoformat()
                    })
                await asyncio.sleep(30)
            except Exception as e:
                self.logger.error(f"Health check error: {e}")
                error_logger.log_error(e, {
                    'component': 'binance_ws',
                    'event': 'health_check_error',
                    'connection_id': self.connection_id
                })
                break
    
    async def close(self):
        """Close connections and cleanup resources with error handling"""
        try:
            self.logger.info("Closing WebSocket connection...")
            
            if self.websocket:
                await self.websocket.close()
            
            # Record final metrics
            self.metrics.record_metric('shutdown', {
                'total_reconnections': self.reconnect_count,
                'connection_id': self.connection_id,
                'timestamp': datetime.now().isoformat()
            })
            
            # Cleanup processor resources
            if hasattr(self, 'processor'):
                self.processor.cleanup()
            
            # Close Redis connection
            if hasattr(self, 'redis_client'):
                await self.redis_client.close()
            
            # Close InfluxDB connection
            if hasattr(self, 'influxdb'):
                self.influxdb.close()
            
            self.logger.info("All connections closed successfully")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            error_logger.log_error(e, {
                'component': 'binance_ws',
                'event': 'cleanup_error',
                'connection_id': self.connection_id
            })

async def main():
    """Main function with error handling"""
    logger = LoggerFactory.get_logger('main')
    client = None
    
    try:
        client = EnhancedWebSocketClient(SYMBOLS)
        await client.connect()
    except asyncio.CancelledError:
        logger.info("Program execution cancelled")
    except Exception as e:
        logger.error(f"Main execution error: {e}")
        error_logger.log_error(e, {
            'component': 'main',
            'event': 'main_error'
        })
    finally:
        if client:
            await client.close()

if __name__ == "__main__":
    # Set up asyncio error handling
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(lambda loop, context: error_logger.log_error(
        context.get('exception', Exception(context['message'])),
        {'component': 'asyncio', 'event': 'loop_error', 'context': context}
    ))
    
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Program terminated by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        error_logger.log_error(e, {
            'component': 'main',
            'event': 'fatal_error'
        })
    finally:
        loop.close()
