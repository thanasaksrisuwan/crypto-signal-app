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

3. Set up environment variables:

```bash
cp .env.example .env
```

4. Edit the `.env` file with your configuration values (API keys, database credentials, etc.)

5. Configure trading symbols using one of these methods:

```
# Method 1: Edit in .env file
AVAILABLE_SYMBOLS=BTCUSDT,ETHUSDT,DOGEUSDT

# Method 2: Use the command line tool
crypto-symbol-manager.bat list
crypto-symbol-manager.bat add DOGEUSDT
crypto-symbol-manager.bat remove SOLUSDT

# Method 3: Use the UI in the Settings panel
```

See [SYMBOL-MANAGEMENT.md](SYMBOL-MANAGEMENT.md) for more details on symbol management.

5. Install frontend dependencies:

```bash
cd frontend
npm install
```

## ⚙️ Environment Configuration

The application uses a centralized environment management system. Please see [ENV-USAGE.md](ENV-USAGE.md) for detailed documentation on:

- How to configure your environment variables
- Available configuration options
- Adding custom environment variables
- Best practices for development and production

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
- Add/remove symbols via UI
- Select trading pairs

For detailed instructions on managing trading symbols, see [SYMBOL-MANAGEMENT.md](SYMBOL-MANAGEMENT.md).

### System Settings

- Data retention periods
- Alert thresholds
- Backtesting parameters
- ML parameters

## 📊 Dashboard Features

### Signal Generation

- Real-time technical analysis
- ML-based price predictions
- Confidence scoring
- Signal categorization

### Market Data

- Live candlestick charts
- Signal overlay markers
- Historical signal feed
- Performance metrics

### Alerts

- Email alerts
- SMS notifications
- Webhook integration
- Custom alert conditions

### Backtesting

- Historical data replay
- Performance metrics
- Sharpe ratio calculation
- Maximum drawdown analysis

## 🔒 Security

- HTTPS for all endpoints
- Secure storage of API keys
- Environment-based configuration
- Rate limiting

## 📝 License

MIT

## 👥 Contributors

- [Your Name](https://github.com/yourusername)
