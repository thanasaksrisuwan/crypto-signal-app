import React, { useRef, useEffect } from 'react';
import './TechnicalIndicatorView.css';

/**
 * คอมโพเนนต์สำหรับแสดงมุมมองเฉพาะสำหรับตัวบ่งชี้ทางเทคนิค
 * @param {Object} props - พารามิเตอร์ของคอมโพเนนต์
 * @param {Array} props.rsiData - ข้อมูล RSI
 * @param {Object} props.macdData - ข้อมูล MACD
 */
const TechnicalIndicatorView = ({ rsiData, macdData }) => {
  const rsiCanvasRef = useRef(null);
  const macdCanvasRef = useRef(null);

  useEffect(() => {
    if (rsiCanvasRef.current && rsiData && rsiData.length > 0) {
      drawRSIChart(rsiCanvasRef.current, rsiData);
    }
  }, [rsiData]);

  useEffect(() => {
    if (macdCanvasRef.current && macdData && 
        macdData.macdLine && macdData.macdLine.length > 0 &&
        macdData.signalLine && macdData.signalLine.length > 0 &&
        macdData.histogram && macdData.histogram.length > 0) {
      drawMACDChart(macdCanvasRef.current, macdData);
    }
  }, [macdData]);

  /**
   * วาดกราฟ RSI ลงบนแคนวาส
   * @param {HTMLCanvasElement} canvas - แคนวาสที่จะวาด
   * @param {Array} data - ข้อมูล RSI
   */
  const drawRSIChart = (canvas, data) => {
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    // เคลียร์แคนวาส
    ctx.clearRect(0, 0, width, height);
    
    // กำหนดค่า RSI ที่จะแสดง (30 ข้อมูลล่าสุด หรือทั้งหมดถ้าน้อยกว่า)
    const dataToDisplay = data.slice(-30);
    
    // ค้นหาค่าสูงสุดและต่ำสุด
    const minValue = 0;
    const maxValue = 100;
    
    // กำหนดสัดส่วนเพื่อการวาดกราฟ
    const xScale = width / (dataToDisplay.length - 1);
    const yScale = height / (maxValue - minValue);
    
    // วาดเส้นระดับซื้อมากเกินไป (70) และขายมากเกินไป (30)
    ctx.strokeStyle = 'rgba(255, 100, 100, 0.5)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, height - (70 - minValue) * yScale);
    ctx.lineTo(width, height - (70 - minValue) * yScale);
    ctx.stroke();
    
    ctx.strokeStyle = 'rgba(100, 255, 100, 0.5)';
    ctx.beginPath();
    ctx.moveTo(0, height - (30 - minValue) * yScale);
    ctx.lineTo(width, height - (30 - minValue) * yScale);
    ctx.stroke();
    
    // วาดเส้นตรงกลาง (50)
    ctx.strokeStyle = 'rgba(150, 150, 150, 0.5)';
    ctx.beginPath();
    ctx.moveTo(0, height - (50 - minValue) * yScale);
    ctx.lineTo(width, height - (50 - minValue) * yScale);
    ctx.stroke();
    
    // วาดเส้น RSI
    ctx.strokeStyle = '#E91E63';
    ctx.lineWidth = 2;
    ctx.beginPath();
    
    dataToDisplay.forEach((point, i) => {
      const x = i * xScale;
      const y = height - (point.value - minValue) * yScale;
      
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    
    ctx.stroke();
    
    // เพิ่มข้อความกำกับ
    ctx.font = '12px Arial';
    ctx.fillStyle = '#D9D9D9';
    
    // ป้ายกำกับค่าล่าสุด
    const lastValue = dataToDisplay[dataToDisplay.length - 1].value.toFixed(2);
    ctx.fillText(`RSI: ${lastValue}`, 10, 20);
    
    // ป้ายกำกับระดับ
    ctx.fillStyle = 'rgba(255, 100, 100, 0.8)';
    ctx.fillText('70 - Overbought', width - 110, height - (70 - minValue) * yScale - 5);
    
    ctx.fillStyle = 'rgba(100, 255, 100, 0.8)';
    ctx.fillText('30 - Oversold', width - 110, height - (30 - minValue) * yScale + 15);
  };

  /**
   * วาดกราฟ MACD ลงบนแคนวาส
   * @param {HTMLCanvasElement} canvas - แคนวาสที่จะวาด
   * @param {Object} data - ข้อมูล MACD
   */
  const drawMACDChart = (canvas, data) => {
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    // เคลียร์แคนวาส
    ctx.clearRect(0, 0, width, height);
    
    // กำหนดข้อมูลที่จะแสดง (30 ข้อมูลล่าสุด หรือทั้งหมดถ้าน้อยกว่า)
    const macdData = data.macdLine.slice(-30);
    const signalData = data.signalLine.slice(-30);
    const histogramData = data.histogram.slice(-30);
    
    // ค้นหาค่าสูงสุดและต่ำสุดของทุกชุดข้อมูล
    const allValues = [
      ...macdData.map(d => d.value),
      ...signalData.map(d => d.value),
      ...histogramData.map(d => d.value)
    ];
    
    const minValue = Math.min(...allValues);
    const maxValue = Math.max(...allValues);
    
    // กำหนดสัดส่วนเพื่อการวาดกราฟ
    const xScale = width / (macdData.length - 1);
    const yScale = height / (maxValue - minValue);
    
    // วาดเส้นศูนย์
    ctx.strokeStyle = 'rgba(150, 150, 150, 0.5)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    const zeroY = height - (0 - minValue) * yScale;
    ctx.moveTo(0, zeroY);
    ctx.lineTo(width, zeroY);
    ctx.stroke();
    
    // วาด histogram
    const barWidth = xScale * 0.6;
    
    histogramData.forEach((point, i) => {
      const x = i * xScale - barWidth / 2;
      const value = point.value;
      const y = height - (value - minValue) * yScale;
      
      ctx.fillStyle = value >= 0 ? '#26a69a' : '#ef5350';
      
      const barHeight = Math.abs(zeroY - y);
      ctx.fillRect(x, Math.min(zeroY, y), barWidth, barHeight);
    });
    
    // วาดเส้น MACD
    ctx.strokeStyle = '#2196F3';
    ctx.lineWidth = 2;
    ctx.beginPath();
    
    macdData.forEach((point, i) => {
      const x = i * xScale;
      const y = height - (point.value - minValue) * yScale;
      
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    
    ctx.stroke();
    
    // วาดเส้นสัญญาณ
    ctx.strokeStyle = '#FF9800';
    ctx.lineWidth = 2;
    ctx.beginPath();
    
    signalData.forEach((point, i) => {
      const x = i * xScale;
      const y = height - (point.value - minValue) * yScale;
      
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    
    ctx.stroke();
    
    // เพิ่มข้อความกำกับ
    ctx.font = '12px Arial';
    ctx.fillStyle = '#2196F3';
    ctx.fillText(`MACD: ${macdData[macdData.length - 1].value.toFixed(4)}`, 10, 20);
    
    ctx.fillStyle = '#FF9800';
    ctx.fillText(`Signal: ${signalData[signalData.length - 1].value.toFixed(4)}`, 10, 40);
    
    const lastHistogramValue = histogramData[histogramData.length - 1].value;
    ctx.fillStyle = lastHistogramValue >= 0 ? '#26a69a' : '#ef5350';
    ctx.fillText(`Histogram: ${lastHistogramValue.toFixed(4)}`, 10, 60);
  };

  return (
    <div className="technical-indicator-view">
      <div className="indicator-section">
        <h4>RSI (Relative Strength Index)</h4>
        <div className="indicator-chart">
          <canvas ref={rsiCanvasRef} width="400" height="200"></canvas>
        </div>
        <div className="indicator-info">
          <p>
            RSI แสดงความแข็งแรงของราคาเมื่อเทียบกับการเคลื่อนไหวในอดีต:
          </p>
          <ul>
            <li><span className="danger">{'>'} 70</span>: ภาวะซื้อมากเกินไป (Overbought) - พิจารณาขาย</li>
            <li><span className="success">{'<'} 30</span>: ภาวะขายมากเกินไป (Oversold) - พิจารณาซื้อ</li>
            <li>ค่าระหว่าง 30-70: อยู่ในช่วงปกติ</li>
          </ul>
        </div>
      </div>
      
      <div className="indicator-section">
        <h4>MACD (Moving Average Convergence Divergence)</h4>
        <div className="indicator-chart">
          <canvas ref={macdCanvasRef} width="400" height="200"></canvas>
        </div>
        <div className="indicator-info">
          <p>
            MACD แสดงความสัมพันธ์ระหว่างค่าเฉลี่ยเคลื่อนที่สองค่า:
          </p>
          <ul>
            <li><span className="primary">เส้น MACD</span>: EMA เร็ว (12) - EMA ช้า (26)</li>
            <li><span className="warning">เส้นสัญญาณ</span>: EMA (9) ของ MACD</li>
            <li>
              <span className="success">แท่งสีเขียว</span>: 
              MACD สูงกว่าสัญญาณ (แนวโน้มขาขึ้น)
            </li>
            <li>
              <span className="danger">แท่งสีแดง</span>: 
              MACD ต่ำกว่าสัญญาณ (แนวโน้มขาลง)
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default TechnicalIndicatorView;
