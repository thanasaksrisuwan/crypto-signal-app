/**
 * เพิ่มเติมคำอธิบายเกี่ยวกับตัวบ่งชี้เทคนิคอล
 * ไฟล์นี้มีไว้เพื่อให้ข้อมูลเพิ่มเติมเกี่ยวกับตัวบ่งชี้ทางเทคนิคต่างๆที่ใช้ในแอปพลิเคชัน
 */

/**
 * ข้อมูลเกี่ยวกับ RSI (Relative Strength Index)
 * @type {Object}
 */
export const rsiInfo = {
  name: 'Relative Strength Index (RSI)',
  description: 'ตัวบ่งชี้โมเมนตัมที่วัดขนาดของการเปลี่ยนแปลงราคาเพื่อประเมินภาวะซื้อหรือขายมากเกินไป',
  interpretation: [
    { value: 'เมื่อ RSI > 70: สินทรัพย์อาจอยู่ในภาวะซื้อมากเกินไป (overbought) และอาจเกิดการปรับตัวลง' },
    { value: 'เมื่อ RSI < 30: สินทรัพย์อาจอยู่ในภาวะขายมากเกินไป (oversold) และอาจเกิดการฟื้นตัว' },
    { value: 'การทะลุเส้น 50 จากด้านล่างขึ้นบน: อาจเป็นสัญญาณซื้อ' },
    { value: 'การทะลุเส้น 50 จากด้านบนลงล่าง: อาจเป็นสัญญาณขาย' }
  ],
  defaultPeriod: 14,
  formula: 'RSI = 100 - (100 / (1 + RS))\nRS = Average Gain / Average Loss'
};

/**
 * ข้อมูลเกี่ยวกับ MACD (Moving Average Convergence Divergence)
 * @type {Object}
 */
export const macdInfo = {
  name: 'Moving Average Convergence Divergence (MACD)',
  description: 'ตัวบ่งชี้แนวโน้มที่แสดงความสัมพันธ์ระหว่างค่าเฉลี่ยเคลื่อนที่สองค่าของราคา',
  interpretation: [
    { value: 'เมื่อเส้น MACD ตัดเส้นสัญญาณจากล่างขึ้นบน: เป็นสัญญาณซื้อ (bullish)' },
    { value: 'เมื่อเส้น MACD ตัดเส้นสัญญาณจากบนลงล่าง: เป็นสัญญาณขาย (bearish)' },
    { value: 'ความสูงของฮิสโตแกรม: แสดงถึงความแรงของแนวโน้ม' },
    { value: 'การแยกตัวระหว่างราคาและ MACD (divergence): อาจเป็นสัญญาณการกลับตัวของราคา' }
  ],
  components: [
    { name: 'MACD Line', value: 'EMA เร็ว (12 วัน) - EMA ช้า (26 วัน)' },
    { name: 'Signal Line', value: 'EMA ของเส้น MACD (9 วัน)' },
    { name: 'Histogram', value: 'MACD Line - Signal Line' }
  ],
  defaultSettings: {
    fastPeriod: 12,
    slowPeriod: 26,
    signalPeriod: 9
  }
};

/**
 * ข้อมูลเกี่ยวกับ EMA (Exponential Moving Average)
 * @type {Object}
 */
export const emaInfo = {
  name: 'Exponential Moving Average (EMA)',
  description: 'ค่าเฉลี่ยเคลื่อนที่ที่ให้น้ำหนักมากกว่ากับข้อมูลล่าสุด ทำให้ตอบสนองต่อการเปลี่ยนแปลงราคาได้เร็วกว่า SMA',
  interpretation: [
    { value: 'ราคาเหนือ EMA: แนวโน้มขาขึ้น (bullish)' },
    { value: 'ราคาต่ำกว่า EMA: แนวโน้มขาลง (bearish)' },
    { value: 'EMA สั้นตัด EMA ยาวจากล่างขึ้นบน: สัญญาณซื้อ (Golden Cross)' },
    { value: 'EMA สั้นตัด EMA ยาวจากบนลงล่าง: สัญญาณขาย (Death Cross)' }
  ],
  formula: 'EMA = ราคาปัจจุบัน × k + EMA เมื่อวาน × (1 - k)\nเมื่อ k = 2 / (จำนวนวัน + 1)',
  commonPeriods: [9, 12, 21, 50, 200]
};

/**
 * ข้อมูลเกี่ยวกับ SMA (Simple Moving Average)
 * @type {Object}
 */
export const smaInfo = {
  name: 'Simple Moving Average (SMA)',
  description: 'ค่าเฉลี่ยราคาในช่วงระยะเวลาที่กำหนด โดยให้น้ำหนักเท่ากันสำหรับทุกวัน',
  interpretation: [
    { value: 'ราคาเหนือ SMA: แนวโน้มขาขึ้น (bullish)' },
    { value: 'ราคาต่ำกว่า SMA: แนวโน้มขาลง (bearish)' },
    { value: 'SMA สั้นตัด SMA ยาวจากล่างขึ้นบน: สัญญาณซื้อ (Golden Cross)' },
    { value: 'SMA สั้นตัด SMA ยาวจากบนลงล่าง: สัญญาณขาย (Death Cross)' }
  ],
  formula: 'SMA = (P₁ + P₂ + ... + Pₙ) / n',
  commonPeriods: [20, 50, 100, 200]
};
