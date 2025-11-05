import sys
import json
from datetime import datetime
sys.path.append('/app')

from backtester.engine.backtester import Backtester
from backtester.api.algorithm import Algorithm

try:
    with open('/tmp/user/user_code.py', 'r') as f:
        user_code = f.read()
    
    import pandas as pd
    import numpy as np
    try:
        import ta
    except:
        ta = None
    
    namespace = {
        'Algorithm': Algorithm,
        'pd': pd,
        'pandas': pd,
        'np': np,
        'numpy': np,
        'ta': ta
    }
    exec(user_code, namespace)
    
    strategy_class = None
    for name, obj in namespace.items():
        if isinstance(obj, type) and issubclass(obj, Algorithm) and obj != Algorithm:
            strategy_class = obj
            break
    
    temp_algo = strategy_class()
    temp_algo.Initialize()
    symbols = list(temp_algo._subscriptions) if hasattr(temp_algo, '_subscriptions') else ['AAPL']
    
    backtester = Backtester(algorithm_class=strategy_class)
    results = backtester.run_backtest(
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2024, 1, 1),
        symbols=symbols
    )
    
    perf = results['performance_report']
    
    output_lines = []
    output_lines.append(f"Initial Cash: ${results['initial_cash']:,.2f}")
    output_lines.append(f"Final Equity: ${results['final_snapshot']['total_equity']:,.2f}")
    output_lines.append(f"Total Return: {((results['final_snapshot']['total_equity'] - results['initial_cash']) / results['initial_cash']) * 100:.2f}%")
    output_lines.append(f"Number of Trades: {len(results['fills'])}")
    output_lines.append("")
    
    if perf.get('summary'):
        output_lines.append("SUMMARY:")
        for key, val in perf['summary'].items():
            if isinstance(val, float):
                output_lines.append(f"  {key}: {val:.4f}")
            else:
                output_lines.append(f"  {key}: {val}")
        output_lines.append("")
    
    if perf.get('returns_metrics'):
        output_lines.append("RETURNS:")
        for key, val in perf['returns_metrics'].items():
            if isinstance(val, float):
                output_lines.append(f"  {key}: {val:.4f}")
            else:
                output_lines.append(f"  {key}: {val}")
        output_lines.append("")
    
    if perf.get('risk_metrics'):
        output_lines.append("RISK:")
        for key, val in perf['risk_metrics'].items():
            if isinstance(val, float):
                output_lines.append(f"  {key}: {val:.4f}")
            else:
                output_lines.append(f"  {key}: {val}")
    
    print(json.dumps({'success': True, 'results': '\n'.join(output_lines)}))
    
except Exception as e:
    print(json.dumps({'success': False, 'error': str(e)}))