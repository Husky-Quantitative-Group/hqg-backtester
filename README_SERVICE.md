# Backtester as a Service

## Setup

### Backend
```bash
cd api
pip install -r requirements.txt
./build.sh
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Usage

1. Start backend server on port 8000
2. Start frontend on port 5173
3. Write strategy code in Monaco editor
4. Configure symbols, dates, cash in header
5. Click "Run Backtest" to execute

## Strategy Template

```python
import ta
import pandas as pd

class Strategy(Algorithm):
    def Initialize(self):
        self.SetCash(100000)
        self.AddEquity("AAPL")
    
    def OnData(self, data):
        pass
```