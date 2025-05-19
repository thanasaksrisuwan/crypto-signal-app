import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { createChart, LineStyle, CrosshairMode } from 'lightweight-charts';
import IndicatorHelperModal from './IndicatorHelperModal';
import { calculateRSI, calculateEMA } from '../utils/indicatorCalculations';
import debounce from 'lodash.debounce';
import './MarketData.css';

// WebSocket connection manager with enhanced reliability and memory optimization
const useWebSocketManager = (url, onMessage, options = {}) => {
  const wsRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimeoutRef = useRef(null);
  const messageQueue = useRef([]);
  const isProcessing = useRef(false);
  const maxQueueSize = options.maxQueueSize || 100;
  const heartbeatIntervalRef = useRef(null);
  const lastMessageTimeRef = useRef(Date.now());

  // ประมวลผลข้อความที่เข้าคิว
  const processQueue = useCallback(() => {
    if (isProcessing.current || messageQueue.current.length === 0) return;

    isProcessing.current = true;
    const nextMessage = messageQueue.current.shift();
    
    // ส่งข้อความไปยังคอลแบ็ค
    try {
      onMessage(nextMessage);
    } catch (e) {
      console.error('Error processing WebSocket message:', e);
    } finally {
      isProcessing.current = false;
      
      // ใช้ requestAnimationFrame สำหรับการประมวลผลข้อความถัดไป
      // เพื่อป้องกันไม่ให้ UI เกิดการค้าง (jank)
      if (messageQueue.current.length > 0) {
        requestAnimationFrame(processQueue);
      }
    }
  }, [onMessage]);

  // ส่งสัญญาณ heartbeat เพื่อรักษาการเชื่อมต่อ
  const sendHeartbeat = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      // ตรวจสอบว่าเราไม่ได้รับข้อความเป็นเวลานาน
      const timeSinceLastMessage = Date.now() - lastMessageTimeRef.current;
      
      // หากไม่มีข้อความนานเกิน 30 วินาที ให้ส่ง ping
      if (timeSinceLastMessage > 30000) {
        try {
          wsRef.current.send(JSON.stringify({ type: 'ping' }));
        } catch (e) {
          console.warn('Failed to send heartbeat:', e);
        }
      }
    }
  }, []);

  const connect = useCallback(() => {
    try {
      console.log(`Connecting to WebSocket: ${url}`);
      wsRef.current = new WebSocket(url);

      wsRef.current.onopen = () => {
        console.log('WebSocket connected');
        reconnectAttempts.current = 0;
        
        // เริ่มการตรวจสอบ heartbeat ทุก 30 วินาที
        if (heartbeatIntervalRef.current) {
          clearInterval(heartbeatIntervalRef.current);
        }
        heartbeatIntervalRef.current = setInterval(sendHeartbeat, 30000);
        
        if (options.onOpen) options.onOpen();
      };

      wsRef.current.onmessage = (event) => {
        lastMessageTimeRef.current = Date.now();
        
        try {
          // ตรวจสอบว่าเป็นข้อความ pong จาก heartbeat
          if (event.data === '{"type":"pong"}') {
            return; // ข้ามข้อความ pong
          }
          
          const data = JSON.parse(event.data);
          
          // จำกัดขนาดคิว เพื่อป้องกัน memory leak
          if (messageQueue.current.length >= maxQueueSize) {
            // ลบข้อความเกี่ยวกับราคาที่เก่าที่สุด แต่รักษาสัญญาณสำคัญ
            const importantMessages = messageQueue.current.filter(
              msg => msg.type === 'signal' || msg.category === 'strong buy' || msg.category === 'strong sell'
            );
            const otherMessages = messageQueue.current.filter(
              msg => msg.type !== 'signal' && msg.category !== 'strong buy' && msg.category !== 'strong sell'
            );
            
            // ตัดข้อมูลที่ไม่สำคัญออกครึ่งหนึ่ง
            otherMessages.splice(0, Math.ceil(otherMessages.length / 2));
            messageQueue.current = [...importantMessages, ...otherMessages];
          }
          
          // เพิ่มข้อความใหม่เข้าคิว
          messageQueue.current.push(data);
          
          // เริ่มประมวลผลคิวถ้ายังไม่ได้ดำเนินการ
          if (!isProcessing.current) {
            requestAnimationFrame(processQueue);
          }
        } catch (e) {
          console.error('WebSocket message parse error:', e);
        }
      };

      wsRef.current.onclose = (event) => {
        console.log(`WebSocket closed. Code: ${event.code}, Reason: ${event.reason}`);
        
        // ล้างช่วงเวลา heartbeat
        if (heartbeatIntervalRef.current) {
          clearInterval(heartbeatIntervalRef.current);
        }
        
        // ยุติการเชื่อมต่อใหม่หลังจากเกิดข้อผิดพลาดรุนแรง (เช่น authen ล้มเหลว)
        if ([1008, 1011].includes(event.code)) {
          console.error('WebSocket connection terminated due to policy violation or server error');
          return;
        }
        
        // ลองเชื่อมต่อใหม่ด้วยการเลื่อนเวลาออกไปเรื่อยๆ
        if (reconnectAttempts.current < 10) {
          const delay = Math.min(1000 * Math.pow(1.5, reconnectAttempts.current), 60000);
          console.log(`Attempting to reconnect in ${delay/1000} seconds`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttempts.current++;
            connect();
          }, delay);
        } else {
          console.error('Maximum reconnection attempts reached');
          if (options.onMaxReconnectAttempts) {
            options.onMaxReconnectAttempts();
          }
        }
      };

      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

    } catch (error) {
      console.error('WebSocket connection error:', error);
    }
  }, [url, onMessage, options, processQueue, sendHeartbeat, maxQueueSize]);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current);
      }
      // ล้างคิว
      messageQueue.current = [];
    };
  }, [connect]);

  // ให้ interface เพิ่มเติมสำหรับการจัดการ WebSocket
  return {
    webSocket: wsRef,
    // ล้างคิว
    clearQueue: () => {
      messageQueue.current = [];
    },
    // สถานะการเชื่อมต่อ
    status: () => wsRef.current ? wsRef.current.readyState : WebSocket.CLOSED
  };
};

// Optimized chart data processor with Web Worker
const chartWorker = new Worker(new URL('../workers/chartWorker.js', import.meta.url));

// Memoized chart options
const useChartOptions = (theme) => {
  return useMemo(() => ({
    layout: {
      background: { color: theme === 'dark' ? '#1e222d' : '#ffffff' },
      textColor: theme === 'dark' ? '#d1d4dc' : '#131722',
    },
    grid: {
      vertLines: { color: theme === 'dark' ? '#334158' : '#f0f3fa' },
      horzLines: { color: theme === 'dark' ? '#334158' : '#f0f3fa' },
    },
    crosshair: {
      mode: CrosshairMode.Normal,
      vertLine: { labelBackgroundColor: theme === 'dark' ? '#334158' : '#f0f3fa' },
      horzLine: { labelBackgroundColor: theme === 'dark' ? '#334158' : '#f0f3fa' },
    },
    timeScale: {
      timeVisible: true,
      secondsVisible: false,
      borderColor: theme === 'dark' ? '#334158' : '#f0f3fa',
    },
  }), [theme]);
};

// Optimized MarketData component with React.memo
const MarketData = React.memo(({ symbol, settings }) => {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const candlestickSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);

  const [timeframe, setTimeframe] = useState('1h');
  const [candleData, setCandleData] = useState([]);
  const [orderbookData, setOrderbookData] = useState([]);
  const [recentTrades, setRecentTrades] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  const API_BASE = process.env.NODE_ENV === 'production' 
    ? window.location.origin 
    : 'http://localhost:8000';

  const WS_BASE = process.env.NODE_ENV === 'production'
    ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
    : 'ws://localhost:8000';

  // Memoized chart options
  const chartOptions = useChartOptions(settings.theme);

  // Memoized data processors
  const processCandle = useCallback((data) => {
    chartWorker.postMessage({ type: 'processCandle', data });
  }, []);

  const processVolume = useCallback((data) => {
    chartWorker.postMessage({ type: 'processVolume', data });
  }, []);

  // WebSocket connections using custom hook
  const candleWs = useWebSocketManager(
    `${WS_BASE}/ws/kline/${symbol}`,
    processCandle,
    { onOpen: () => setIsLoading(false) }
  );

  const depthWs = useWebSocketManager(
    `${WS_BASE}/ws/depth/${symbol}`,
    (data) => setOrderbookData(data)
  );

  const tradesWs = useWebSocketManager(
    `${WS_BASE}/ws/trades/${symbol}`,
    (data) => setRecentTrades(prev => [data, ...prev].slice(0, 50))
  );

  // Use IntersectionObserver for lazy loading
  const containerRef = useRef(null);
  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          chartRef.current?.resize();
        }
      },
      { threshold: 0.1 }
    );

    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    return () => observer.disconnect();
  }, []);

  // Debounced chart resize handler
  const debouncedResize = useCallback(
    debounce(() => {
      if (chartRef.current) {
        chartRef.current.resize();
      }
    }, 100),
    []
  );

  useEffect(() => {
    window.addEventListener('resize', debouncedResize);
    return () => window.removeEventListener('resize', debouncedResize);
  }, [debouncedResize]);

  // Memoized indicator calculations
  const indicators = useMemo(() => ({
    ema9: calculateEMA(candleData, 9),
    ema21: calculateEMA(candleData, 21),
    rsi: calculateRSI(candleData),
  }), [candleData]);

  // Render optimization with virtualized lists
  const renderOrderbook = useCallback(() => {
    return (
      <VirtualizedList
        data={orderbookData}
        rowHeight={20}
        windowSize={10}
        renderRow={row => (
          <div className="orderbook-row">
            <span>{row.price}</span>
            <span>{row.amount}</span>
          </div>
        )}
      />
    );
  }, [orderbookData]);

  return (
    <div className="market-data-container">
      <div className="chart-panel" ref={chartContainerRef}></div>
      <div className="orderbook-panel">
        {renderOrderbook()}
      </div>
    </div>
  );
});

// Virtualized List component for better performance
const VirtualizedList = React.memo(({ data, rowHeight, windowSize, renderRow }) => {
  const [scrollTop, setScrollTop] = useState(0);
  const containerRef = useRef(null);

  const visibleItems = useMemo(() => {
    const start = Math.floor(scrollTop / rowHeight);
    const end = Math.min(start + windowSize, data.length);
    return data.slice(start, end).map((item, index) => ({
      ...item,
      index: start + index,
    }));
  }, [data, rowHeight, windowSize, scrollTop]);

  const handleScroll = useCallback((e) => {
    setScrollTop(e.target.scrollTop);
  }, []);

  return (
    <div
      ref={containerRef}
      style={{ height: windowSize * rowHeight, overflow: 'auto' }}
      onScroll={handleScroll}
    >
      <div style={{ height: data.length * rowHeight, position: 'relative' }}>
        {visibleItems.map((item) => (
          <div
            key={item.index}
            style={{
              position: 'absolute',
              top: item.index * rowHeight,
              height: rowHeight,
            }}
          >
            {renderRow(item)}
          </div>
        ))}
      </div>
    </div>
  );
});

export default MarketData;
