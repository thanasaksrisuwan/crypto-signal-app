import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './SignalHistory.css';

const SignalHistory = ({ symbol, settings }) => {
  // สถานะสำหรับประวัติสัญญาณ
  const [signalHistory, setSignalHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // กำหนด API Base URL
  const API_BASE = process.env.NODE_ENV === 'production' 
    ? window.location.origin 
    : 'http://localhost:8000';
  
  // โหลดประวัติสัญญาณเมื่อคอมโพเนนต์เริ่มต้นหรือเมื่อสัญลักษณ์เปลี่ยน
  useEffect(() => {
    const fetchHistory = async () => {
      setLoading(true);
      try {
        const response = await axios.get(`${API_BASE}/api/history-signals?symbol=${symbol}&limit=20`);
        if (Array.isArray(response.data)) {
          setSignalHistory(response.data);
        } else {
          setSignalHistory([]);
        }
      } catch (error) {
        console.error('ไม่สามารถโหลดประวัติสัญญาณได้:', error);
        setSignalHistory([]);
      } finally {
        setLoading(false);
      }
    };
    
    fetchHistory();
    
    // ตั้งเวลาดึงข้อมูลซ้ำทุก 1 นาที
    const intervalId = setInterval(fetchHistory, 60000);
    
    // ยกเลิกตัวตั้งเวลาเมื่อคอมโพเนนต์ถูกยกเลิก
    return () => clearInterval(intervalId);
  }, [symbol]);
  
  // ฟังก์ชันกรองสัญญาณตามการตั้งค่า
  const filterSignals = (signals) => {
    return signals.filter(signal => {
      // กรองตามเกณฑ์ความมั่นใจ
      if (signal.confidence < settings.confidenceThreshold) {
        return false;
      }
      
      // กรองสัญญาณอ่อนถ้าตั้งค่าไว้
      if (!settings.showWeakSignals && signal.category.toLowerCase().includes('weak')) {
        return false;
      }
      
      return true;
    });
  };
  
  // ฟังก์ชันแสดงอีโมจิตามประเภทสัญญาณ
  const getSignalEmoji = (category) => {
    switch (category.toLowerCase()) {
      case 'strong buy':
        return '🚀';
      case 'weak buy':
        return '📈';
      case 'hold':
        return '⏸️';
      case 'weak sell':
        return '📉';
      case 'strong sell':
        return '⚠️';
      default:
        return '🔔';
    }
  };
  
  // ฟังก์ชันแสดงคลาส CSS ตามประเภทสัญญาณ
  const getSignalClass = (category) => {
    switch (category.toLowerCase()) {
      case 'strong buy':
        return 'signal-item strong-buy';
      case 'weak buy':
        return 'signal-item weak-buy';
      case 'hold':
        return 'signal-item hold';
      case 'weak sell':
        return 'signal-item weak-sell';
      case 'strong sell':
        return 'signal-item strong-sell';
      default:
        return 'signal-item';
    }
  };
  
  // กรองสัญญาณตามการตั้งค่า
  const filteredSignals = filterSignals(signalHistory);
  
  return (
    <div className="signal-history-container">
      <h3>ประวัติสัญญาณล่าสุด</h3>
      
      {loading ? (
        <div className="loading-message">กำลังโหลดประวัติสัญญาณ...</div>
      ) : filteredSignals.length > 0 ? (
        <ul className="signal-list">
          {filteredSignals.map((signal, index) => (
            <li key={index} className={getSignalClass(signal.category)}>
              <div className="signal-header">
                <span className="signal-emoji">{getSignalEmoji(signal.category)}</span>
                <span className="signal-type">{signal.category.toUpperCase()}</span>
                <span className="signal-confidence">{(signal.confidence * 100).toFixed(1)}%</span>
              </div>
              
              <div className="signal-body">
                <div className="signal-details">
                  <span className="signal-price">${signal.price.toFixed(2)}</span>
                  <span className="signal-forecast">คาดการณ์: {signal.forecast_pct.toFixed(2)}%</span>
                </div>
                
                <div className="signal-time">
                  {new Date(signal.timestamp).toLocaleString()}
                </div>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="empty-message">ไม่มีประวัติสัญญาณที่ตรงกับเกณฑ์ที่กำหนด</div>
      )}
    </div>
  );
};

export default SignalHistory;