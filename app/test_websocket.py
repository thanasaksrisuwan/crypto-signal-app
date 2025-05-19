import asyncio
from binance_ws_client import BinanceWebSocketClient

async def test_websocket():
    print("Starting WebSocket test...")
    client = BinanceWebSocketClient()
    
    try:
        connected = await client.connect()
        if connected:
            print("Successfully connected to Binance WebSocket")
            # Wait for some messages
            await asyncio.sleep(30)
        else:
            print("Failed to connect to Binance WebSocket")
    except Exception as e:
        print(f"Error during test: {e}")
    finally:
        await client.close()
        print("Test completed")

if __name__ == "__main__":
    asyncio.run(test_websocket())
