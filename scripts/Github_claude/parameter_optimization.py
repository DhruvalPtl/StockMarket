"""
Strategy Parameter Optimization
"""

import itertools
from concurrent.futures import ProcessPoolExecutor

class StrategyOptimizer:
    def __init__(self, data, initial_capital=10000):
        self.data = data
        self.initial_capital = initial_capital
        
    def optimize_parameters(self):
        """
        Grid search optimization for strategy parameters
        """
        # Parameter ranges to test
        param_grid = {
            'rsi_overbought': [55, 60, 65, 70],
            'rsi_oversold': [30, 35, 40, 45],
            'pcr_bullish_min': [1.05, 1.10, 1.15, 1.20],
            'pcr_bearish_max': [0.80, 0.85, 0.90, 0.95],
            'target_percent':  [0.10, 0.15, 0.20, 0.25],
            'stop_percent': [0.08, 0.10, 0.12, 0.15]
        }
        
        # Generate all combinations
        param_combinations = list(itertools.product(*param_grid.values()))
        
        best_result = None
        best_roi = -float('inf')
        
        print(f"Testing {len(param_combinations)} parameter combinations...")
        
        for i, params in enumerate(param_combinations):
            # Create backtester with these parameters
            backtester = NiftyOptionsBacktester(self.initial_capital)
            backtester.RSI_OVERBOUGHT = params[0]
            backtester.RSI_OVERSOLD = params[1]
            backtester.PCR_BULLISH_MIN = params[2]
            backtester.PCR_BEARISH_MAX = params[3]
            backtester. target_profit_percent = params[4]
            backtester.stop_loss_percent = params[5]
            
            # Run backtest
            results = backtester.run_backtest(self.data)
            
            if 'error' not in results:
                roi = results['summary']['roi_percent']
                
                if roi > best_roi: 
                    best_roi = roi
                    best_result = {
                        'params': dict(zip(param_grid.keys(), params)),
                        'results': results
                    }
            
            if (i + 1) % 100 == 0:
                print(f"Tested {i + 1}/{len(param_combinations)} combinations...")
        
        return best_result


# Usage: 
# optimizer = StrategyOptimizer(data)
# best = optimizer.optimize_parameters()
# print("Best parameters:", best['params']) 