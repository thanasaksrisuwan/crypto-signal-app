import asyncio
import json
import sys
import time

print("Python version:", sys.version)
print("Testing if websocket endpoint is running...")

# Try simple HTTP connection to confirm server is running
import urllib.request
try:
    with urllib.request.urlopen("http://localhost:8000/") as response:
        data = response.read()
        print("Server is running. Response:", data.decode('utf-8'))
except Exception as e:
    print("Error connecting to server:", e)

print("Note: Full WebSocket testing requires 'websockets' and 'aiohttp' packages.")
print("This script will only test if the server is running.")
        async with websockets.connect("ws://localhost:8000/ws/signals/BTCUSDT") as ws:
            print("Connected to signals WebSocket!")
            
            # รอรับข้อมูล signal_history
            print("Waiting for signal history...")
            history_response = await ws.recv()
            history_data = json.loads(history_response)
            print(f"Received signal history: {history_data['type']}, {len(history_data['data'])} entries")
            
            # รอรับข้อมูลสัญญาณใหม่
            print("Waiting for new signal...")
            signal_response = await ws.recv()
            signal_data = json.loads(signal_response)
            print(f"Received signal: {signal_data['type']}")
            print(f"Signal details: {signal_data['data']}")
            
            # ทดสอบจบแล้ว
            print("Test completed successfully!")
    except Exception as e:
        print(f"Error in test: {e}")

async def test_history_api():
    """
    ฟังก์ชันทดสอบการเรียก API สำหรับ history-signals endpoint
    """
    try:
        # ใช้ aiohttp เพื่อเรียก API
        import aiohttp
        
        print("Testing history-signals API endpoint...")
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8000/api/history-signals?symbol=BTCUSDT&limit=5") as response:
                data = await response.json()
                print(f"API Response status: {response.status}")
                if isinstance(data, list):
                    print(f"Received {len(data)} signal history entries")
                    print(f"First entry: {data[0]}")
                else:
                    print(f"Unexpected API response: {data}")
    except Exception as e:
        print(f"Error in API test: {e}")

async def main():
    """
    ฟังก์ชันหลักสำหรับการทดสอบ endpoints
    """
    print("Starting WebSocket endpoint tests...")
    
    # ทดสอบทั้ง WebSocket endpoint และ API endpoint
    await asyncio.gather(
        test_signals_websocket(),
        test_history_api()
    )
    
    print("All tests completed!")

if __name__ == "__main__":
    asyncio.run(main())
