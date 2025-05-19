# filepath: c:\Users\Nack\Documents\crypto-signal-app\app\simplified_backend.py
"""
Simplified Backend สำหรับ Crypto Signal App

ไฟล์นี้สร้างเซิร์ฟเวอร์ FastAPI แบบง่ายที่จำลองการทำงานของ WebSocket endpoints 
สำหรับข้อมูลเรียลไทม์ในแอปพลิเคชันสัญญาณการเทรดคริปโต:

WebSocket Endpoints:
- /ws/depth/{symbol}: ส่งข้อมูล orderbook (ความลึกของตลาด) ทุก 1 วินาที
- /ws/trades/{symbol}: ส่งข้อมูลการซื้อขายล่าสุด ทุก 2 วินาที
- /ws/kline/{symbol}: ส่งข้อมูลแท่งเทียน ทุก 5 วินาที
- /ws/signals/{symbol}: ส่งสัญญาณการเทรด ทุก 30-60 วินาที (สุ่ม)

API Endpoints:
- /api/history-signals: ส่งข้อมูลประวัติสัญญาณย้อนหลัง

ไฟล์นี้สร้างขึ้นเพื่อแก้ไขปัญหา WebSocket connection errors ในแอปพลิเคชัน
โดยเฉพาะอย่างยิ่งข้อผิดพลาด 403 ที่เกิดขึ้นเมื่อพยายามเชื่อมต่อกับ endpoint ที่ไม่มีอยู่
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import asyncio
import json
import random
from datetime import datetime
import os
import sys

# นำเข้าโมดูลจัดการตัวแปรสภาพแวดล้อม
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
import env_manager as env
import uvicorn

# สัญลักษณ์คริปโตที่เราติดตามจากตัวแปรสภาพแวดล้อม
SYMBOLS = env.get_available_symbols()

# ตั้งค่าแอพพลิเคชัน FastAPI
app = FastAPI(
    title="Simplified Crypto Signal API",
    description="Simple API for crypto WebSocket data simulation",
    version="0.1.0",
)

# ตั้งค่า CORS เพื่อให้ Frontend เรียกใช้ API ได้
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "Simplified Crypto API is running",
        "available_symbols": SYMBOLS,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/available-symbols")
async def get_available_symbols():
    """ดึงรายการสัญลักษณ์ที่มีให้บริการ"""
    return {"symbols": SYMBOLS}

# นำเข้า Pydantic models ที่ต้องใช้
class SymbolRequest(BaseModel):
    symbol: str

class SymbolResponse(BaseModel):
    success: bool
    message: str
    symbols: List[str]

# API endpoints สำหรับจัดการสัญลักษณ์คริปโต
@app.get("/api/symbols", response_model=SymbolResponse)
async def get_symbols():
    """
    ดึงรายการสัญลักษณ์ที่รองรับทั้งหมด
    
    Returns:
        รายการสัญลักษณ์คริปโตที่รองรับ
    """
    try:
        global SYMBOLS
        symbols = env.get_available_symbols()
        # อัปเดตตัวแปร SYMBOLS เพื่อให้ใช้ค่าล่าสุดเสมอ
        SYMBOLS = symbols
        
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
async def add_symbol(request: SymbolRequest):
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
        
        # ถ้าเพิ่มสำเร็จ ให้อัปเดตตัวแปร SYMBOLS
        if success:
            # อัปเดตตัวแปรในระดับแอปพลิเคชัน
            global SYMBOLS
            SYMBOLS = env.get_available_symbols()
            
            return SymbolResponse(
                success=True,
                message=f"เพิ่มสัญลักษณ์ {symbol} สำเร็จ",
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
async def remove_symbol(request: SymbolRequest):
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
        
        # ถ้าลบสำเร็จ ให้อัปเดตตัวแปร SYMBOLS
        if success:
            # อัปเดตตัวแปรในระดับแอปพลิเคชัน
            global SYMBOLS
            SYMBOLS = env.get_available_symbols()
            
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

@app.websocket("/ws/depth/{symbol}")
async def depth_websocket_endpoint(websocket: WebSocket, symbol: str):
    """
    WebSocket endpoint สำหรับข้อมูล orderbook depth ของสัญลักษณ์ที่ระบุ
    - ส่งข้อมูล mock ในอัตรา 1 ครั้ง/วินาที
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
        
        # กำหนดราคาพื้นฐาน
        base_price = 30000 if symbol.upper() == "BTCUSDT" else 2000
        
        try:
            # ส่งข้อมูลจำลองทุกวินาที
            while True:
                try:
                    # สุ่มการเปลี่ยนแปลงของราคา
                    price_change = random.uniform(-20, 20)
                    current_price = base_price + price_change
                    
                    # สร้างข้อมูลจำลอง
                    mock_data = {
                        "symbol": symbol.upper(),
                        "lastUpdateId": int(datetime.now().timestamp() * 1000),
                        "bids": [
                            [str(round(current_price - i * 10, 2)), str(round(1.0 / (i + 1), 3))] for i in range(10)
                        ],
                        "asks": [
                            [str(round(current_price + i * 10, 2)), str(round(1.0 / (i + 1), 3))] for i in range(10)
                        ],
                        "timestamp": int(datetime.now().timestamp() * 1000)
                    }
                    
                    # ส่งข้อมูลไปยัง client
                    await websocket.send_json(mock_data)
                    
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
    - ส่งข้อมูล mock ทุก 2 วินาที
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
        
        # กำหนดราคาพื้นฐาน
        base_price = 30000 if symbol.upper() == "BTCUSDT" else 2000
        
        try:
            # ส่งข้อมูลจำลองทุก 2 วินาที
            while True:
                try:
                    # กำหนดราคาสำหรับการซื้อขาย
                    price = base_price + random.uniform(-50, 50)
                    
                    # สร้างข้อมูลการซื้อขายจำลอง
                    is_buyer_maker = random.choice([True, False])
                    mock_trade = {
                        "e": "trade",
                        "E": int(datetime.now().timestamp() * 1000),
                        "s": symbol.upper(),
                        "t": int(datetime.now().timestamp() * 1000000),
                        "p": str(round(price, 2)),
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
    - ส่งข้อมูล mock ทุก 5 วินาที
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
        
        # กำหนดราคาพื้นฐาน
        base_price = 30000 if symbol.upper() == "BTCUSDT" else 2000
        
        # กำหนดเวลาเริ่มต้นและช่วงเวลา
        current_time = int(datetime.now().timestamp() * 1000) - (60 * 60 * 1000)  # 1 ชั่วโมงก่อน
        interval = 60 * 1000  # 1 นาที
        
        # สร้างข้อมูลประวัติย้อนหลัง 60 แท่ง
        historical_data = []
        current_price = base_price
        for i in range(60):
            price_change = random.uniform(-100, 100)
            open_price = current_price
            close_price = open_price + price_change
            high_price = max(open_price, close_price) + random.uniform(5, 20)
            low_price = min(open_price, close_price) - random.uniform(5, 20)
            volume = random.uniform(5, 20)
            
            candle = {
                "timestamp": current_time + (i * interval),
                "open": str(round(open_price, 2)),
                "high": str(round(high_price, 2)),
                "low": str(round(low_price, 2)),
                "close": str(round(close_price, 2)),
                "volume": str(round(volume, 2))
            }
            historical_data.append(candle)
            current_price = close_price
        
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
            # ส่งข้อมูลใหม่ทุก 5 วินาที
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
                        "open": str(round(open_price, 2)),
                        "high": str(round(high_price, 2)),
                        "low": str(round(low_price, 2)),
                        "close": str(round(close_price, 2)),
                        "volume": str(round(volume, 2))
                    }
                    
                    # ส่งข้อมูลไปยัง client
                    await websocket.send_json({
                        "type": "kline",
                        "symbol": symbol.upper(),
                        "data": new_candle
                    })
                    
                    # อัพเดทราคาล่าสุด
                    latest_price = close_price
                    
                    # รอ 5 วินาทีก่อนส่งข้อมูลถัดไป
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

@app.websocket("/ws/signals/{symbol}")
async def signals_websocket_endpoint(websocket: WebSocket, symbol: str):
    """
    WebSocket endpoint สำหรับข้อมูลสัญญาณการซื้อขายของสัญลักษณ์ที่ระบุ
    - ส่งข้อมูลสัญญาณจำลองทุก 30-60 วินาที
    """
    try:
        # ยอมรับการเชื่อมต่อ
        await websocket.accept()
        print(f"WebSocket connection accepted for signals/{symbol}")
        
        # ตรวจสอบว่าสัญลักษณ์นี้สนับสนุนหรือไม่
        if symbol.upper() not in SYMBOLS:
            await websocket.send_json({
                "error": f"Symbol {symbol} not supported. Available symbols are: {', '.join(SYMBOLS)}"
            })
            await websocket.close()
            return
        
        # กำหนดค่าพื้นฐานสำหรับสัญญาณ
        signal_types = ["buy", "sell", "strong_buy", "strong_sell", "neutral"]
        signal_confidences = [0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]
        timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]
        indicators = ["RSI", "MACD", "Bollinger Bands", "Moving Average", "Stochastic", "Ichimoku", "ADX", "OBV"]
        base_price = 30000 if symbol.upper() == "BTCUSDT" else 2000
        
        try:
            # ส่งข้อมูลสัญญาณย้อนหลัง 10 รายการ
            history_signals = []
            current_time = int(datetime.now().timestamp() * 1000) - (10 * 60 * 60 * 1000)  # 10 ชั่วโมงย้อนหลัง
            time_interval = 3600 * 1000  # 1 ชั่วโมงระหว่างสัญญาณ
            
            for i in range(10):
                signal_time = current_time + (i * time_interval)
                price = base_price + random.uniform(-500, 500)
                signal_type = random.choice(signal_types)
                
                history_signal = {
                    "id": f"sig_{str(int(signal_time))[-8:]}",
                    "type": signal_type,
                    "symbol": symbol.upper(),
                    "price": str(round(price, 2)),
                    "timestamp": signal_time,
                    "humanTime": datetime.fromtimestamp(signal_time/1000).strftime('%Y-%m-%d %H:%M:%S'),
                    "indicator": random.choice(indicators),
                    "timeframe": random.choice(timeframes),
                    "confidence": round(random.choice(signal_confidences), 2),
                    "message": f"{signal_type.replace('_', ' ').title()} signal detected for {symbol} at price {round(price, 2)}"
                }
                history_signals.append(history_signal)
            
            # ส่งข้อมูลประวัติไปยัง client
            await websocket.send_json({
                "type": "signal_history",
                "symbol": symbol.upper(),
                "data": history_signals
            })
            
            # ส่งสัญญาณใหม่ทุก 30-60 วินาที
            while True:
                try:
                    # สร้างระยะเวลารอที่สุ่ม
                    wait_time = random.uniform(30, 60)
                    await asyncio.sleep(wait_time)
                    
                    # สร้างสัญญาณใหม่
                    current_time = int(datetime.now().timestamp() * 1000)
                    price = base_price + random.uniform(-500, 500)
                    signal_type = random.choice(signal_types)
                    
                    new_signal = {
                        "id": f"sig_{str(current_time)[-8:]}",
                        "type": signal_type,
                        "symbol": symbol.upper(),
                        "price": str(round(price, 2)),
                        "timestamp": current_time,
                        "humanTime": datetime.fromtimestamp(current_time/1000).strftime('%Y-%m-%d %H:%M:%S'),
                        "indicator": random.choice(indicators),
                        "timeframe": random.choice(timeframes),
                        "confidence": round(random.choice(signal_confidences), 2),
                        "message": f"{signal_type.replace('_', ' ').title()} signal detected for {symbol} at price {round(price, 2)}"
                    }
                    
                    # ส่งสัญญาณใหม่ไปยัง client
                    await websocket.send_json({
                        "type": "signal",
                        "data": new_signal
                    })
                    
                except asyncio.CancelledError:
                    print(f"Task for signals/{symbol} was cancelled")
                    break
                
        except WebSocketDisconnect:
            print(f"WebSocket client for signals/{symbol} disconnected")
        except Exception as e:
            print(f"Error handling signals WebSocket for {symbol}: {e}")
            
    except Exception as e:
        print(f"Error in signals WebSocket endpoint for {symbol}: {e}")
        try:
            await websocket.close()
        except:
            pass

@app.get("/api/history-signals")
async def get_history_signals(symbol: str, limit: int = 20):
    """
    API endpoint สำหรับดึงข้อมูลประวัติสัญญาณย้อนหลังของสัญลักษณ์
    - รับพารามิเตอร์ symbol และ limit (จำนวนสัญญาณที่ต้องการ)
    """
    try:
        # ตรวจสอบว่าสัญลักษณ์นี้สนับสนุนหรือไม่
        if symbol.upper() not in SYMBOLS:
            return {"error": f"Symbol {symbol} not supported. Available symbols are: {', '.join(SYMBOLS)}"}

        # กำหนดค่าพื้นฐานสำหรับสัญญาณ
        signal_types = ["strong buy", "weak buy", "hold", "weak sell", "strong sell"]
        timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]
        indicators = ["RSI", "MACD", "Bollinger Bands", "Moving Average", "Stochastic", "Ichimoku", "ADX", "OBV"]
        base_price = 30000 if symbol.upper() == "BTCUSDT" else 2000
        
        # สร้างข้อมูลสัญญาณย้อนหลัง
        history_signals = []
        current_time = int(datetime.now().timestamp() * 1000) - (limit * 1800 * 1000)  # ย้อนหลังตามจำนวน limit (แต่ละสัญญาณห่างกัน 30 นาที)
        
        for i in range(limit):
            signal_time = current_time + (i * 1800 * 1000)  # เพิ่มขึ้นทุก 30 นาที
            price = base_price + random.uniform(-500, 500)
            category = random.choice(signal_types)
            confidence = random.uniform(0.6, 0.95)
            forecast_pct = random.uniform(-5, 10) if "buy" in category else random.uniform(-10, 2)
            
            history_signal = {
                "id": f"his_{str(int(signal_time))[-8:]}",
                "category": category,
                "symbol": symbol.upper(),
                "price": price,
                "timestamp": signal_time,
                "humanTime": datetime.fromtimestamp(signal_time/1000).strftime('%Y-%m-%d %H:%M:%S'),
                "indicator": random.choice(indicators),
                "timeframe": random.choice(timeframes),
                "confidence": round(confidence, 2),
                "forecast_pct": round(forecast_pct, 2),
                "message": f"{category.replace('_', ' ').title()} signal detected for {symbol} at price {round(price, 2)}"
            }
            history_signals.append(history_signal)
        
        return history_signals
            
    except Exception as e:
        print(f"Error in history-signals API endpoint: {e}")
        return {"error": "Failed to get signal history", "details": str(e)}

if __name__ == "__main__":
    uvicorn.run("simplified_backend:app", host="0.0.0.0", port=8000, reload=True)
