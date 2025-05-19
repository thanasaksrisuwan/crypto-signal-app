import asyncio
import redis
from datetime import datetime

# Import the WebSocket client
try:
    from binance_ws_client import BinanceWebSocketClient, SYMBOLS
except ImportError:
    from app.binance_ws_client import BinanceWebSocketClient, SYMBOLS

async def test_binance_websocket():
    """Test the Binance WebSocket functionality"""
    print(f"\n{'='*50}")
    print("Starting Binance WebSocket Test")
    print(f"{'='*50}\n")
    
    print(f"Testing connection for symbols: {SYMBOLS}")
    client = BinanceWebSocketClient()
    
    try:
        # Step 1: Connect to WebSocket
        print("\n1. Establishing connection...")
        connected = await client.connect()
        if not connected:
            print("❌ Failed to connect to Binance WebSocket")
            return
        print("✅ Successfully connected to Binance WebSocket")
        
        # Step 2: Subscribe to kline streams
        print("\n2. Subscribing to kline streams...")
        await client.start_kline_streams()
        print("✅ Subscribed to kline streams")
        
        # Step 3: Monitor data for 30 seconds
        print("\n3. Monitoring data for 30 seconds...")
        received_data = {symbol: False for symbol in SYMBOLS}
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < 30:
            await asyncio.sleep(1)
            for symbol in SYMBOLS:
                try:
                    key = f"latest_signal:{symbol}"
                    data = client.redis_client.get(key)
                    if data and not received_data[symbol]:
                        received_data[symbol] = True
                        print(f"✅ Received data for {symbol}")
                        
                except redis.RedisError as e:
                    print(f"❌ Redis error for {symbol}: {e}")
                
            if all(received_data.values()):
                print("\n✅ Successfully received data for all symbols!")
                break
        
        # Step 4: Final status report
        print("\n4. Test Results:")
        all_success = True
        for symbol, received in received_data.items():
            status = "✅" if received else "❌"
            result = "Data received" if received else "No data received"
            print(f"{status} {symbol}: {result}")
            if not received:
                all_success = False
        
        if all_success:
            print("\n🎉 All tests passed successfully!")
        else:
            print("\n⚠️ Some tests failed. Check the results above.")
            
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
    finally:
        print("\nClosing connections...")
        await client.close()
        print("Test completed")

if __name__ == "__main__":
    try:
        asyncio.run(test_binance_websocket())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
