import { useState } from 'react';
import Editor from '@monaco-editor/react';
import './App.css';

function App() {
  const [code, setCode] = useState('class Strategy(Algorithm):\n    def Initialize(self):\n        self.SetCash(100000)\n        self.AddEquity("AAPL")\n    \n    def OnData(self, data):\n        pass');
  const [results, setResults] = useState('');
  const [loading, setLoading] = useState(false);

  const runBacktest = async () => {
    setLoading(true);
    setResults('Running...');
    
    const response = await fetch('http://localhost:8000/backtest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code }),
    });
    
    const data = await response.json();
    setResults(data.success ? data.results : data.error);
    setLoading(false);
  };

  return (
    <div className="App">
      <div className="header">
        <h1>Backtester</h1>
        <button onClick={runBacktest} disabled={loading}>
          {loading ? 'Running...' : 'Run'}
        </button>
      </div>
      
      <div className="main-content">
        <div className="editor-panel">
          <Editor
            height="100%"
            defaultLanguage="python"
            value={code}
            onChange={(value) => setCode(value || '')}
            theme="vs-dark"
          />
        </div>
        
        <div className="results-panel">
          <pre>{results}</pre>
        </div>
      </div>
    </div>
  );
}

export default App;