import asyncio
import websockets
import json
from datetime import datetime
import zlib
from typing import Dict, Set
from contextlib import asynccontextmanager

class WebSocketPool:
    def __init__(self, max_connections: int = 5):
        self.max_connections = max_connections
        self.active_connections: Set[websockets.WebSocketClientProtocol] = set()
        self.connection_semaphore = asyncio.Semaphore(max_connections)

    async def get_connection(self, uri: str):
        async with self.connection_semaphore:
            ws = await websockets.connect(
                uri,
                compression=None,  # Use None for raw connection, websockets handles compression
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
                max_size=2**23  # 8MB max message size
            )
            self.active_connections.add(ws)
            return ws

    async def release_connection(self, ws):
        if ws in self.active_connections:
            await ws.close()
            self.active_connections.remove(ws)

ws_pool = WebSocketPool()

async def test_binance_websocket():
    """Test direct connection to Binance WebSocket with detailed debugging and optimization"""
    print(f"\nDetailed Binance WebSocket Test - Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    stream_endpoint = "wss://stream.binance.com:9443/ws"
    symbols = ["btcusdt", "ethusdt"]
    message_buffer = []
    BUFFER_SIZE = 100
    
    try:
        ws = await ws_pool.get_connection(stream_endpoint)
        print("✅ Connected to Binance WebSocket")
        
        # Subscribe with compression
        subscribe_message = {
            "method": "SUBSCRIBE",
            "params": [f"{symbol}@kline_1m" for symbol in symbols],
            "id": 1
        }
        
        print(f"\nSending subscription request: {json.dumps(subscribe_message)}")
        await ws.send(json.dumps(subscribe_message))
        
        response = await ws.recv()
        print(f"Subscription response: {response}")
        
        print("\nMonitoring messages...")
        message_count = 0
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < 120:  # 2 minutes
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=5.0)
                message_count += 1
                
                # Efficient message processing with buffering
                data = json.loads(message)
                message_buffer.append(data)
                
                if len(message_buffer) >= BUFFER_SIZE:
                    await process_message_buffer(message_buffer)
                    message_buffer.clear()
                
            except asyncio.TimeoutError:
                print(".", end="", flush=True)
                continue
            except Exception as e:
                print(f"\n❌ Error receiving message: {e}")
                # Attempt to reconnect on failure
                await ws_pool.release_connection(ws)
                ws = await ws_pool.get_connection(stream_endpoint)
        
        if message_buffer:  # Process remaining messages
            await process_message_buffer(message_buffer)
        
        print(f"\n\nTotal messages processed: {message_count}")
        await ws_pool.release_connection(ws)
        
    except Exception as e:
        print(f"❌ Connection error: {e}")
    
    print(f"\nTest completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

async def process_message_buffer(messages: list):
    """Process a batch of messages efficiently"""
    for data in messages:
        if 'stream' in data:
            stream = data['stream']
            event_data = data.get('data', {})
            event_type = event_data.get('e')
            symbol = event_data.get('s')
            timestamp = datetime.fromtimestamp(event_data.get('E', 0)/1000)
            
            # Batch process kline events
            if event_type == 'kline':
                k = event_data.get('k', {})
                print(f"Processed {symbol} kline: {k.get('c')} at {timestamp}")

if __name__ == "__main__":
    asyncio.run(test_binance_websocket())
