import json
import sys
import urllib.request

def main():
    print("Python version:", sys.version)
    print("Testing if server is running...")

    # Try simple HTTP connection to confirm server is running
    try:
        with urllib.request.urlopen("http://localhost:8000/") as response:
            data = response.read()
            print("Server is running. Response:", data.decode('utf-8'))
    except Exception as e:
        print("Error connecting to server:", e)
        return

    # Test API endpoints
    try:
        print("\nTesting history-signals API endpoint...")
        with urllib.request.urlopen("http://localhost:8000/api/history-signals?symbol=BTCUSDT&limit=5") as response:
            data = response.read()
            api_response = json.loads(data)
            if isinstance(api_response, list):
                print(f"API Success: Received {len(api_response)} signal history entries")
                print(f"First signal: {api_response[0]}")
            else:
                print(f"API Response: {api_response}")
    except Exception as e:
        print("Error connecting to API:", e)

    # This section would require websockets library
    print("\nWebSocket endpoints that should be working:")
    print("- ws://localhost:8000/ws/depth/BTCUSDT")
    print("- ws://localhost:8000/ws/trades/BTCUSDT")
    print("- ws://localhost:8000/ws/kline/BTCUSDT")
    print("- ws://localhost:8000/ws/signals/BTCUSDT")

if __name__ == "__main__":
    main()
    print("\nTest completed!")
