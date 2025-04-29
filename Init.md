Initial Development Steps
Scaffold Backend

Use Copilot prompt to generate app.py with FastAPI setup.

Add WebSocket client script to ingest Binance 2-min klines.

Implement Signal Service

Write the grading logic (EMA/SMA/RSI + ARIMA stub).

Expose REST endpoints.

Scaffold Frontend

Generate a React app via create-react-app.

Add WebSocket hook and basic candlestick chart.

Wire It Together

Configure Redis and InfluxDB connections.

Test end-to-end: ingest → grade → API → UI.

Iterate with Copilot

For each new feature (alerts, backtesting, user settings), craft a focused prompt and let Copilot bootstrap the code.

Best Practices
Commit Often: small, focused PRs so Copilot suggestions are easy to review.

Prompt Refinement: start broad (“scaffold a service...”), then narrow (“add error handling...”).

Document Prompts: keep your .copilot-prompts.md updated so team members can reuse them.

Review & Refactor: Copilot’s scaffolding is a starting point—always clean up and optimize.