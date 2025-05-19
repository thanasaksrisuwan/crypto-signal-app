import asyncio
import json
from binance_ws_client import BinanceWebSocketClient, SYMBOLS

async def test_kline_streams():
    print("Starting Kline Streams Test...")
    client = BinanceWebSocketClient()
    
    try:
        # Connect to WebSocket
        connected = await client.connect()
        if not connected:
            print("❌ Failed to connect to Binance WebSocket")
            return
            
        print("✅ Successfully connected to Binance WebSocket")
        print(f"🔄 Starting kline streams for symbols: {SYMBOLS}")
        
        # Start kline streams
        await client.start_kline_streams()
        
        # Monitor for 60 seconds
        print("📊 Monitoring kline data for 60 seconds...")
        start_time = asyncio.get_event_loop().time()
        received_data = {symbol: False for symbol in SYMBOLS}
        
        while asyncio.get_event_loop().time() - start_time < 60:
            await asyncio.sleep(1)
            # Check Redis for received data
            try:
                for symbol in SYMBOLS:
                    key = f"latest_signal:{symbol}"
                    data = client.redis_client.get(key)
                    if data and not received_data[symbol]:
                        received_data[symbol] = True
                        print(f"✅ Received data for {symbol}")
                
                # Check if we've received data for all symbols
                if all(received_data.values()):
                    print("✅ Successfully received data for all symbols!")
                    break
                    
            except Exception as e:
                print(f"❌ Error checking Redis: {e}")
        
        # Final status report
        print("\nTest Results:")
        for symbol, received in received_data.items():
            status = "✅" if received else "❌"
            print(f"{status} {symbol}: {'Data received' if received else 'No data received'}")
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
    finally:
        print("\nClosing connections...")
        await client.close()
        print("Test completed")

if __name__ == "__main__":
    asyncio.run(test_kline_streams())
