// ฟังก์ชันสำหรับสร้างรหัส hash ของข้อมูลเพื่อใช้ในการแคช
function hashData(data, period) {
  // ใช้เฉพาะราคาปิดล่าสุด และจำนวนข้อมูลสำหรับการระบุตัวตน
  const lastIndex = data.length - 1;
  return `${data[lastIndex].time}_${data[lastIndex].close}_${data.length}_${period}`;
}

// ขนาดสูงสุดสำหรับแคช
const MAX_CACHE_SIZE = 50;

// ฟังก์ชันล้างแคชเก่า
function pruneCaches() {
  if (rsiCache.size > MAX_CACHE_SIZE) {
    // ลบแคชเก่าสุด 20%
    const keysToDelete = Array.from(rsiCache.keys()).slice(0, Math.floor(MAX_CACHE_SIZE * 0.2));
    keysToDelete.forEach(key => rsiCache.delete(key));
  }
}

// Web Worker สำหรับการจัดการการคำนวณแผนภูมิ
// ใช้บริบทของ Worker โดยต้องปลอดภัยจาก ESLint errors
/* eslint-disable no-restricted-globals */
// onmessage handler รับข้อความจาก main thread
onmessage = function(e) {
  const { type, data } = e.data;
  
  switch (type) {
    case 'processCandle':
      const processedCandles = processCandleData(data);
      postMessage({ type: 'candleResult', data: processedCandles });
      break;
      
    case 'processVolume':
      const processedVolume = processVolumeData(data);
      postMessage({ type: 'volumeResult', data: processedVolume });
      break;
      
    case 'calculateIndicators':
      const indicators = calculateIndicators(data);
      postMessage({ type: 'indicatorResult', data: indicators });
      
      // ล้างแคชหลังการคำนวณตัวบ่งชี้ เพื่อประหยัดหน่วยความจำ
      pruneCaches();      break;
    case 'clearCache':
      // ล้างแคชทั้งหมดเมื่อได้รับคำสั่ง (เช่น เมื่อเปลี่ยนคู่เหรียญหรือกรอบเวลา)
      rsiCache.clear();
      postMessage({ type: 'cacheCleared' });
      break;
  }
};

// Efficient candle data processing
function processCandleData(data) {
  try {
    return data.map(candle => ({
      time: candle.time / 1000, // Convert to seconds for lightweight-charts
      open: parseFloat(candle.open),
      high: parseFloat(candle.high),
      low: parseFloat(candle.low),
      close: parseFloat(candle.close)
    }));
  } catch (error) {
    console.error('Error processing candle data:', error);
    return [];
  }
}

// Optimized volume data processing
function processVolumeData(data) {
  try {
    return data.map(candle => ({
      time: candle.time / 1000,
      value: parseFloat(candle.volume),
      color: parseFloat(candle.close) >= parseFloat(candle.open) ? '#26a69a' : '#ef5350'
    }));
  } catch (error) {
    console.error('Error processing volume data:', error);
    return [];
  }
}

// Efficient technical indicator calculations
function calculateIndicators(data) {
  try {
    const ema9 = calculateEMA(data, 9);
    const ema21 = calculateEMA(data, 21);
    const rsi = calculateRSI(data);
    const macd = calculateMACD(data);
    
    return {
      ema9,
      ema21,
      rsi,
      macd
    };
  } catch (error) {
    console.error('Error calculating indicators:', error);
    return {};
  }
}

// EMA calculation with optimized algorithm using TypedArrays for better performance
function calculateEMA(data, period) {
  const k = 2 / (period + 1);
  const dataLength = data.length;
  
  // ใช้ Float64Array เพื่อประสิทธิภาพสูงสุด
  const ema = new Float64Array(dataLength);
  const closes = new Float64Array(dataLength);
  
  // แปลงข้อมูลราคาปิดเป็น TypedArray เพื่อเพิ่มความเร็ว
  for (let i = 0; i < dataLength; i++) {
    closes[i] = data[i].close;
  }
  
  // คำนวณ SMA เริ่มต้น
  let sum = 0;
  for (let i = 0; i < period; i++) {
    sum += closes[i];
  }
  
  // กำหนดค่า EMA เริ่มต้น
  ema[period - 1] = sum / period;
  
  // คำนวณ EMA ที่เหลือ ด้วยการเข้าถึง TypedArray โดยตรง
  for (let i = period; i < dataLength; i++) {
    ema[i] = closes[i] * k + ema[i - 1] * (1 - k);
  }
  
  // แปลงกลับเป็น Array ปกติเพื่อความเข้ากันได้กับ lightweight-charts
  return Array.from(ema);
}

// Highly optimized RSI calculation with memoization
const rsiCache = new Map();

function calculateRSI(data, period = 14) {
  // คำนวณรหัส hash สำหรับข้อมูลเพื่อใช้ในการแคช
  const hash = hashData(data, period);
  
  // ตรวจสอบแคชก่อน
  if (rsiCache.has(hash)) {
    return rsiCache.get(hash);
  }
  
  // ถ้าไม่มีในแคชให้คำนวณใหม่
  const dataLength = data.length;
  const changes = new Float64Array(dataLength - 1);
  const gains = new Float64Array(dataLength - 1);
  const losses = new Float64Array(dataLength - 1);
  
  // คำนวณการเปลี่ยนแปลงของราคาและแยกเป็นกำไร/ขาดทุน
  for (let i = 1; i < dataLength; i++) {
    changes[i - 1] = data[i].close - data[i - 1].close;
    gains[i - 1] = Math.max(0, changes[i - 1]);
    losses[i - 1] = Math.max(0, -changes[i - 1]);
  }
  
  // Calculate initial averages
  let avgGain = gains.slice(0, period).reduce((a, b) => a + b) / period;
  let avgLoss = losses.slice(0, period).reduce((a, b) => a + b) / period;
  
  const rsi = new Float64Array(data.length);
  rsi[period] = 100 - (100 / (1 + avgGain / avgLoss));
  
  // Calculate subsequent values using Wilder's smoothing
  for (let i = period + 1; i < data.length; i++) {
    avgGain = ((avgGain * (period - 1)) + gains[i - 1]) / period;
    avgLoss = ((avgLoss * (period - 1)) + losses[i - 1]) / period;
    rsi[i] = 100 - (100 / (1 + avgGain / avgLoss));
  }
  
  return rsi;
}

// MACD calculation with performance optimization
function calculateMACD(data, fastPeriod = 12, slowPeriod = 26, signalPeriod = 9) {
  const fastEMA = calculateEMA(data, fastPeriod);
  const slowEMA = calculateEMA(data, slowPeriod);
  
  const macdLine = new Float64Array(data.length);
  for (let i = slowPeriod - 1; i < data.length; i++) {
    macdLine[i] = fastEMA[i] - slowEMA[i];
  }
  
  const signalLine = new Float64Array(data.length);
  let sum = 0;
  for (let i = slowPeriod - 1; i < slowPeriod - 1 + signalPeriod; i++) {
    sum += macdLine[i];
  }
  signalLine[slowPeriod - 1 + signalPeriod - 1] = sum / signalPeriod;
  
  const k = 2 / (signalPeriod + 1);
  for (let i = slowPeriod - 1 + signalPeriod; i < data.length; i++) {
    signalLine[i] = macdLine[i] * k + signalLine[i - 1] * (1 - k);
  }
  
  return {
    macdLine,
    signalLine,
    histogram: macdLine.map((v, i) => v - signalLine[i])
  };
}
