/**
 * Utility functions for technical indicator calculations.
 */

/**
 * Calculate RSI (Relative Strength Index).
 * @param {Array} data - Array of candlestick data.
 * @param {number} period - Number of periods for RSI calculation (default: 14).
 * @returns {Array} - Array of RSI values with timestamps.
 */
export const calculateRSI = (data, period = 14) => {
  if (data.length < period + 1) {
    return [];
  }

  const rsiData = [];
  let gains = 0;
  let losses = 0;

  // Calculate initial average gain and loss
  for (let i = 1; i <= period; i++) {
    const difference = data[i].close - data[i - 1].close;
    if (difference >= 0) {
      gains += difference;
    } else {
      losses -= difference; // Convert to positive value
    }
  }

  let avgGain = gains / period;
  let avgLoss = losses / period;

  // Calculate initial RSI value
  let rs = avgGain / (avgLoss === 0 ? 0.00001 : avgLoss); // Prevent division by zero
  rsiData.push({
    time: data[period].time,
    value: 100 - (100 / (1 + rs))
  });

  // Calculate RSI for the rest of the data
  for (let i = period + 1; i < data.length; i++) {
    const difference = data[i].close - data[i - 1].close;
    let currentGain = 0;
    let currentLoss = 0;

    if (difference >= 0) {
      currentGain = difference;
    } else {
      currentLoss = -difference;
    }

    // Apply Wilder's Smoothing Method
    avgGain = ((avgGain * (period - 1)) + currentGain) / period;
    avgLoss = ((avgLoss * (period - 1)) + currentLoss) / period;

    rs = avgGain / (avgLoss === 0 ? 0.00001 : avgLoss);

    try {
      rsiData.push({
        time: data[i].time,
        value: 100 - (100 / (1 + rs))
      });
    } catch (err) {
      console.error('Error calculating RSI:', err);
    }
  }

  return rsiData;
};

/**
 * คำนวณค่า EMA (Exponential Moving Average)
 * @param {Array} data - ข้อมูล candlestick ที่ใช้ในการคำนวณ
 * @param {number} period - จำนวนช่วงเวลาสำหรับการคำนวณ EMA
 * @returns {Array} - อาร์เรย์ของค่า EMA พร้อมกับเวลา
 */
export const calculateEMA = (data, period) => {
  if (!data || data.length < period) {
    return [];
  }

  const emaData = [];
  let multiplier = 2 / (period + 1);
  let sma = 0;

  // คำนวณค่าเฉลี่ยเคลื่อนที่แบบง่ายสำหรับช่วงแรก
  for (let i = 0; i < period; i++) {
    sma += data[i].close;
  }
  sma = sma / period;

  // เริ่มต้นด้วยค่าเฉลี่ย SMA
  emaData.push({
    time: data[period - 1].time,
    value: sma
  });

  // คำนวณ EMA สำหรับข้อมูลที่เหลือ
  for (let i = period; i < data.length; i++) {
    try {
      const ema = (data[i].close - emaData[emaData.length - 1].value) * multiplier + emaData[emaData.length - 1].value;
      emaData.push({
        time: data[i].time,
        value: ema
      });
    } catch (err) {
      console.error('Error calculating EMA:', err);
    }
  }

  return emaData;
};
