import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
} from 'chart.js';
import 'chartjs-adapter-date-fns';
import axios from 'axios';
import './SignalDashboard.css';

// ลงทะเบียนคอมโพเนนต์ของ Chart.js
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale
);

const SignalDashboard = ({ symbol, settings }) => {
  // สถานะสำหรับข้อมูลแท่งเทียน (candlestick data)
  const [candleData, setCandleData] = useState([]);
  
  // สถานะสำหรับสัญญาณล่าสุด
  const [latestSignal, setLatestSignal] = useState(null);
  
  // อ้างอิงถึงการเชื่อมต่อ WebSocket
  const wsRef = useRef(null);
  const reconnectAttempts = useRef(0);
  
  // เพิ่มสถานะสำหรับติดตามการเชื่อมต่อ
  const [isConnected, setIsConnected] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const reconnectTimeout = useRef(null);

  // ฟังก์ชันสำหรับเชื่อมต่อกับ WebSocket API
  const connectWebSocket = useCallback(() => {
    if (isReconnecting) return;

    // ปิดการเชื่อมต่อเดิมก่อน (ถ้ามี)
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }

    setIsReconnecting(true);
    
    // ปรับใช้กับทั้ง HTTP และ HTTPS
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    
    // สร้าง URL ที่เหมาะสมตาม environment
    let wsUrl;
    if (process.env.NODE_ENV === 'production') {
      wsUrl = `${protocol}//${window.location.host}/ws/signals`;
    } else {
      wsUrl = `ws://localhost:8000/ws/signals`;
    }
    
    console.log(`กำลังเชื่อมต่อไปยัง WebSocket: ${wsUrl}`);
    
    try {
      const ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        console.log('เชื่อมต่อ WebSocket สำเร็จ');
        setIsConnected(true);
        setIsReconnecting(false);
        reconnectAttempts.current = 0;
        
        // ส่งข้อความสมัครสมาชิกสำหรับสัญลักษณ์ที่เลือก
        if (symbol) {
          ws.send(JSON.stringify({ subscribe: symbol }));
        }
      };
      
      ws.onmessage = (event) => {
        try {
          const signalData = JSON.parse(event.data);
          
          // จัดการกับข้อความ heartbeat
          if (signalData.type === 'heartbeat' || signalData.type === 'ping') {
            console.log(`💓 ได้รับ ${signalData.type} จาก server เวลา ${new Date(signalData.timestamp * 1000).toLocaleTimeString()}`);
            // ส่ง pong กลับเพื่อยืนยันว่า client ยังทำงานอยู่
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: 'pong', timestamp: Math.floor(Date.now() / 1000) }));
            }
            return;
          }
          
          if (signalData.symbol === symbol) {
            setLatestSignal(signalData);
            
            if (signalData.price) {
              const newCandle = {
                timestamp: signalData.timestamp,
                price: signalData.price,
                category: signalData.category,
                forecast_pct: signalData.forecast_pct,
                confidence: signalData.confidence
              };
              
              setCandleData(prevData => {
                const exists = prevData.some(candle => candle.timestamp === newCandle.timestamp);
                if (!exists) {
                  return [...prevData, newCandle].sort((a, b) => a.timestamp - b.timestamp);
                }
                return prevData;
              });
            }
          }
        } catch (err) {
          console.error('เกิดข้อผิดพลาดในการแปลงข้อมูล WebSocket:', err);
        }
      };
      
      ws.onclose = (event) => {
        console.log(`การเชื่อมต่อ WebSocket ถูกปิด: รหัส=${event.code}, เหตุผล=${event.reason || 'ไม่ระบุ'}`);
        setIsConnected(false);
        
        // ลองเชื่อมต่อใหม่แบบมี exponential backoff
        const maxDelay = 30000; // 30 วินาที
        const baseDelay = 1000; // 1 วินาที
        const delay = Math.min(
          maxDelay,
          baseDelay * Math.pow(1.5, Math.min(10, reconnectAttempts.current))
        );
        
        console.log(`จะลองเชื่อมต่อใหม่ในอีก ${delay / 1000} วินาที...`);
        
        if (reconnectTimeout.current) {
          clearTimeout(reconnectTimeout.current);
        }
        
        reconnectTimeout.current = setTimeout(() => {
          reconnectAttempts.current++;
          setIsReconnecting(false);
          connectWebSocket();
        }, delay);
      };
      
      ws.onerror = (error) => {
        console.error('เกิดข้อผิดพลาด WebSocket:', error);
      };
      
      wsRef.current = ws;
      
    } catch (error) {
      console.error('เกิดข้อผิดพลาดในการสร้าง WebSocket:', error);
      setIsReconnecting(false);
    }
  }, [symbol, isReconnecting]);

  // โหลดข้อมูลสัญญาณล่าสุดและประวัติเมื่อเริ่มต้น
  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        // เพิ่ม API base URL
        const API_BASE_URL = process.env.NODE_ENV === 'production' 
          ? window.location.origin
          : 'http://localhost:8000';

        const [latestRes, historyRes] = await Promise.all([
          axios.get(`${API_BASE_URL}/api/latest-signal?symbol=${symbol}`),
          axios.get(`${API_BASE_URL}/api/history-signals?symbol=${symbol}&limit=50`)
        ]);

        if (latestRes.data && !latestRes.data.message) {
          setLatestSignal(latestRes.data);
        }

        if (Array.isArray(historyRes.data)) {
          const candles = historyRes.data.map(signal => ({
            timestamp: signal.timestamp,
            price: signal.price,
            category: signal.category,
            forecast_pct: signal.forecast_pct,
            confidence: signal.confidence
          }));
          candles.sort((a, b) => a.timestamp - b.timestamp);
          setCandleData(candles);
        }
      } catch (error) {
        console.error('ไม่สามารถโหลดข้อมูลเริ่มต้นได้:', error);
        // เพิ่มการแสดงข้อความผิดพลาดให้ผู้ใช้เห็น
        setLatestSignal({ error: 'ไม่สามารถโหลดข้อมูลได้' });
      }
    };

    if (symbol) {
      fetchInitialData();
      connectWebSocket();
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
    };
  }, [symbol, connectWebSocket]);
  
  // ฟังก์ชันสำหรับแปลงข้อมูลสำหรับกราฟ
  const prepareChartData = () => {
    if (candleData.length === 0) {
      return {
        labels: [],
        datasets: []
      };
    }
    
    // แปลงข้อมูลเป็นรูปแบบที่ Chart.js ต้องการ
    return {
      labels: candleData.map(candle => new Date(candle.timestamp)),
      datasets: [
        {
          label: `${symbol} Price`,
          data: candleData.map(candle => candle.price),
          borderColor: 'rgba(75, 192, 192, 1)',
          backgroundColor: 'rgba(75, 192, 192, 0.2)',
          tension: 0.1,
          fill: false,
          pointRadius: 3,
          pointHoverRadius: 5,
          pointBackgroundColor: candleData.map(candle => {
            // สีของจุดตามประเภทของสัญญาณ
            switch (candle.category) {
              case 'strong buy':
                return 'rgba(0, 179, 60, 1)';
              case 'weak buy':
                return 'rgba(102, 204, 102, 1)';
              case 'hold':
                return 'rgba(179, 179, 179, 1)';
              case 'weak sell':
                return 'rgba(255, 153, 128, 1)';
              case 'strong sell':
                return 'rgba(255, 51, 0, 1)';
              default:
                return 'rgba(75, 192, 192, 1)';
            }
          })
        }
      ]
    };
  };
  
  // ตัวเลือกสำหรับกราฟ
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
      },
      title: {
        display: true,
        text: `${symbol} Price Chart with Signals`,
      },
      tooltip: {
        callbacks: {
          label: (context) => {
            const pointIndex = context.dataIndex;
            const candle = candleData[pointIndex];
            if (candle) {
              return [
                `Price: $${candle.price.toFixed(2)}`,
                `Signal: ${candle.category}`,
                `Forecast: ${candle.forecast_pct.toFixed(2)}%`,
                `Confidence: ${(candle.confidence * 100).toFixed(1)}%`
              ];
            }
            return '';
          }
        }
      }
    },
    scales: {
      x: {
        type: 'time',
        time: {
          unit: 'minute',
          tooltipFormat: 'PPpp', // การแสดงผลใน tooltip
          displayFormats: {
            minute: 'HH:mm'
          }
        },
        title: {
          display: true,
          text: 'Time'
        }
      },
      y: {
        title: {
          display: true,
          text: 'Price (USD)'
        }
      }
    }
  };
  
  // ฟังก์ชันแสดงปุ่มสัญญาณ
  const renderSignalBadge = (category, confidence) => {
    if (!category) return null;
    
    // กำหนดสีและข้อความตามประเภทสัญญาณ
    let badgeClass = 'signal-badge';
    
    switch (category.toLowerCase()) {
      case 'strong buy':
        badgeClass += ' strong-buy';
        break;
      case 'weak buy':
        badgeClass += ' weak-buy';
        break;
      case 'hold':
        badgeClass += ' hold';
        break;
      case 'weak sell':
        badgeClass += ' weak-sell';
        break;
      case 'strong sell':
        badgeClass += ' strong-sell';
        break;
      default:
        badgeClass += ' hold';
    }
    
    // แสดงสัญญาณเฉพาะที่ผ่านเกณฑ์ความมั่นใจ
    if (confidence < settings.confidenceThreshold) {
      return null;
    }
    
    // กรองสัญญาณอ่อนถ้าตั้งค่าไว้
    if (!settings.showWeakSignals) {
      if (category.toLowerCase().includes('weak')) {
        return null;
      }
    }
    
    return (
      <div className={badgeClass}>
        <span className="signal-emoji">
          {category.toLowerCase() === 'strong buy' ? '🚀' : 
           category.toLowerCase() === 'weak buy' ? '📈' : 
           category.toLowerCase() === 'hold' ? '⏸️' : 
           category.toLowerCase() === 'weak sell' ? '📉' : 
           category.toLowerCase() === 'strong sell' ? '⚠️' : '🔔'}
        </span>
        <span className="signal-text">{category.toUpperCase()}</span>
        <span className="signal-confidence">{(confidence * 100).toFixed(1)}% confident</span>
      </div>
    );
  };
  
  // แสดงกราฟและสัญญาณล่าสุด
  return (
    <div className="signal-dashboard">
      <div className="chart-container">
        {candleData.length > 0 ? (
          <Line data={prepareChartData()} options={chartOptions} />
        ) : (
          <div className="loading-chart">กำลังโหลดข้อมูล...</div>
        )}
      </div>
      
      <div className="latest-signal-container">
        <h3>สัญญาณล่าสุด</h3>
        {latestSignal ? (
          <div className="signal-details">
            {renderSignalBadge(latestSignal.category, latestSignal.confidence)}
            <div className="price-info">
              <span className="current-price">${latestSignal.price ? latestSignal.price.toFixed(2) : 'N/A'}</span>
              <span className="forecast">คาดการณ์: {latestSignal.forecast_pct ? latestSignal.forecast_pct.toFixed(2) : 'N/A'}%</span>
            </div>
            <div className="indicator-info">
              {latestSignal.indicators && (
                <>
                  <div className="indicator">
                    <span className="indicator-label">EMA9:</span>
                    <span className="indicator-value">{latestSignal.indicators.ema9 ? latestSignal.indicators.ema9.toFixed(2) : 'N/A'}</span>
                  </div>
                  <div className="indicator">
                    <span className="indicator-label">EMA21:</span>
                    <span className="indicator-value">{latestSignal.indicators.ema21 ? latestSignal.indicators.ema21.toFixed(2) : 'N/A'}</span>
                  </div>
                  <div className="indicator">
                    <span className="indicator-label">RSI14:</span>
                    <span className="indicator-value">{latestSignal.indicators.rsi14 ? latestSignal.indicators.rsi14.toFixed(2) : 'N/A'}</span>
                  </div>
                </>
              )}
            </div>
            <div className="timestamp">
              {latestSignal.timestamp ? new Date(latestSignal.timestamp).toLocaleString() : 'N/A'}
            </div>
          </div>
        ) : (
          <div className="no-signal">ไม่มีสัญญาณล่าสุด</div>
        )}
      </div>
    </div>
  );
};

export default SignalDashboard;