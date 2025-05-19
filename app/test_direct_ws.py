import asyncio
import websockets
import json

async def test_binance_websocket():
    """Test direct connection to Binance WebSocket"""
    print("\nTesting Binance WebSocket Connection...")
    
    stream_endpoint = "wss://stream.binance.com:9443/ws"
    symbols = ["btcusdt", "ethusdt"]
    
    try:
        async with websockets.connect(stream_endpoint) as ws:
            print("✅ Successfully connected to Binance WebSocket")
            
            # Create subscription message
            subscribe_message = {
                "method": "SUBSCRIBE",
                "params": [f"{symbol}@kline_1m" for symbol in symbols],
                "id": 1
            }
            
            # Send subscription request
            print(f"\nSubscribing to streams: {symbols}")
            await ws.send(json.dumps(subscribe_message))
            
            # Wait for subscription response
            response = await ws.recv()
            print(f"Subscription response: {response}")
            
            # Monitor messages for 30 seconds
            print("\nMonitoring messages for 30 seconds...")
            received_messages = {symbol: False for symbol in symbols}
            start_time = asyncio.get_event_loop().time()
            
            while asyncio.get_event_loop().time() - start_time < 30:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    data = json.loads(message)
                    
                    if 'stream' in data:
                        symbol = data['stream'].split('@')[0]
                        if not received_messages[symbol]:
                            received_messages[symbol] = True
                            print(f"✅ Received data for {symbol.upper()}")
                        
                        if all(received_messages.values()):
                            print("\n✅ Successfully received data for all symbols!")
                            break
                            
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    print(f"❌ Error receiving message: {e}")
            
            # Unsubscribe
            unsubscribe_message = {
                "method": "UNSUBSCRIBE",
                "params": [f"{symbol}@kline_1m" for symbol in symbols],
                "id": 2
            }
            await ws.send(json.dumps(unsubscribe_message))
            response = await ws.recv()
            print(f"\nUnsubscription response: {response}")
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
    
    print("\nTest completed")

if __name__ == "__main__":
    asyncio.run(test_binance_websocket())
