import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
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

// Optimized Signal Dashboard with React.memo and performance improvements
const SignalDashboard = React.memo(({ symbol, settings }) => {
  // Constants and configuration
  const MESSAGE_BUFFER_SIZE = 100;
  const CHART_UPDATE_INTERVAL = 1000; // 1 second
  const DATA_RETENTION_PERIOD = 24 * 60 * 60 * 1000; // 24 hours
  const WS_BASE = process.env.NODE_ENV === 'production'
    ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
    : 'ws://localhost:8000';
  const WS_RECONNECT_BASE_DELAY = 1000; // 1 second

  // Refs for managing WebSocket and update intervals
  const wsRef = useRef(null);
  const updateIntervalRef = useRef(null);
  const dataBufferRef = useRef([]);

  // Optimized state management with separate concerns
  const [chartData, setChartData] = useState({
    labels: [],
    datasets: []
  });

  // Memoized chart options for better performance
  const chartOptions = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 0 // Disable animations for better performance
    },
    interaction: {
      intersect: false,
      mode: 'index'
    },
    elements: {
      point: {
        radius: 0 // Hide points for better performance
      }
    },
    scales: {
      x: {
        type: 'time',
        time: {
          unit: 'minute',
          displayFormats: {
            minute: 'HH:mm'
          }
        },
        ticks: {
          maxTicksLimit: 8,
          source: 'auto',
          autoSkip: true
        }
      },
      y: {
        beginAtZero: false,
        ticks: {
          maxTicksLimit: 6
        }
      }
    }
  }), []);

  // Memoized WebSocket message handler
  const handleMessage = useCallback((message) => {
    try {
      const data = JSON.parse(message.data);
      dataBufferRef.current.push(data);

      // Trim old data to prevent memory issues
      const now = Date.now();
      dataBufferRef.current = dataBufferRef.current.filter(
        item => now - item.timestamp < DATA_RETENTION_PERIOD
      );

      // Keep buffer size in check
      if (dataBufferRef.current.length > MESSAGE_BUFFER_SIZE) {
        dataBufferRef.current = dataBufferRef.current.slice(-MESSAGE_BUFFER_SIZE);
      }
    } catch (error) {
      console.error('Error processing WebSocket message:', error);
    }
  }, []);

  // WebSocket connection manager with auto-reconnect
  const connectWebSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    wsRef.current = new WebSocket(`${WS_BASE}/ws/signals/${symbol}`);
    wsRef.current.onmessage = handleMessage;
    wsRef.current.onclose = () => {
      setTimeout(connectWebSocket, WS_RECONNECT_BASE_DELAY);
    };
  }, [symbol, handleMessage]);

  // Update chart data at fixed intervals
  const updateChartData = useCallback(() => {
    if (dataBufferRef.current.length === 0) return;

    const latestData = dataBufferRef.current;
    const processedData = {
      labels: latestData.map(d => new Date(d.timestamp)),
      datasets: [{
        label: 'Signal Strength',
        data: latestData.map(d => d.strength),
        borderColor: settings.theme === 'dark' ? '#4CAF50' : '#2196F3',
        fill: false,
        cubicInterpolationMode: 'monotone'
      }]
    };

    setChartData(processedData);
  }, [settings.theme]);

  // Initialize WebSocket and chart updates
  useEffect(() => {
    connectWebSocket();

    updateIntervalRef.current = setInterval(updateChartData, CHART_UPDATE_INTERVAL);

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (updateIntervalRef.current) {
        clearInterval(updateIntervalRef.current);
      }
    };
  }, [connectWebSocket, updateChartData]);

  // Render chart with React.lazy for better loading performance
  const Chart = useMemo(() => React.lazy(() => import('react-chartjs-2').then(module => ({ 
    default: module.Line 
  }))), []);

  return (
    <div className="signal-dashboard">
      <React.Suspense fallback={<div>Loading chart...</div>}>
        <Chart
          data={chartData}
          options={chartOptions}
          height={300}
        />
      </React.Suspense>
      {/* Add any additional dashboard components here */}
    </div>
  );
});

export default SignalDashboard;