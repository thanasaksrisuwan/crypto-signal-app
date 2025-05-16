# Crypto Signal App

A real-time cryptocurrency trading signal application that provides actionable insights based on technical analysis and machine learning predictions.

## 🚀 Features

- Real-time 2-minute OHLCV data streaming for BTCUSDT & ETHUSDT
- Advanced technical indicators (EMA, SMA, RSI) calculation
- ML-based price forecasting with confidence scoring
- Signal categorization (strong/weak buy/sell/hold)
- Interactive dashboard with real-time charts
- Configurable alert system
- Backtesting capabilities
- User-customizable settings

## 🏗️ Architecture

### Backend Stack
- **Python/FastAPI**: High-performance API server
- **Redis**: Real-time pub/sub messaging and caching
- **InfluxDB**: Time-series data storage
- **Binance WebSocket**: Market data source
- **ML Models**: ARIMA/LSTM for price prediction

### Frontend Stack
- **React**: Modern UI framework
- **Chart.js**: Real-time candlestick charts
- **WebSocket**: Live data streaming
- **Local Storage**: User preferences

## 🛠️ Prerequisites

- Python 3.x
- Node.js & npm
- Redis Server
- InfluxDB
- Binance API credentials (for market data)

## 📦 Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd crypto-signal-app
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Install frontend dependencies:
```bash
cd frontend
npm install
```

4. Configure environment variables:
- Create `.env` file with necessary credentials
- Set up Binance API keys
- Configure notification settings

## 🚀 Running the Application

### Using Batch Scripts (Windows)

Start all components:
```bash
start-all.bat
```

Or start components individually:
```bash
start-redis.bat
start-backend.bat
start-frontend.bat
```

The application will be available at:
- Frontend: http://localhost:3000
- API Documentation: http://localhost:8000/docs

## 🔧 Configuration

### User Settings
- Adjust confidence threshold
- Toggle weak signal visibility
- Configure notification preferences
- Select trading pairs

### System Settings
- Data retention periods
- Alert thresholds
- Backtesting parameters

## 📊 Features Detail

### Signal Generation
- Real-time technical analysis
- ML-based price predictions
- Confidence scoring
- Signal categorization

### Dashboard
- Live candlestick charts
- Signal overlay markers
- Historical signal feed
- Performance metrics

### Notifications
- Email alerts
- SMS notifications
- Webhook integration
- Custom alert conditions

### Backtesting
- Historical data replay
- Performance metrics
- Sharpe ratio calculation
- Maximum drawdown analysis

## 🔐 Security

- HTTPS for all endpoints
- Secure storage of API keys
- Environment-based configuration
- Input validation and sanitization

## ⚡ Performance

- <5s end-to-end latency
- 99.9% uptime target
- Automatic WebSocket reconnection
- Scalable architecture

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes with clear messages
4. Push to your branch
5. Create a Pull Request

## 📝 License

[Your License Here]

## 📞 Support

For support and questions, please [open an issue]([repository-url]/issues).

## 🔄 Updates

Check the [changelog](CHANGELOG.md) for recent updates and changes.
