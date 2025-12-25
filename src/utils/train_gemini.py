import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

# --- CONFIGURATION ---
INPUT_FILE = "Final_option_ltp_features_1m.csv"
TARGET_COL = "ce_up_1m"  # We are trying to predict if CALL price goes UP

def train_and_evaluate():
    # 1. Load Data
    print(f"Loading {INPUT_FILE}...")
    try:
        df = pd.read_csv(INPUT_FILE)
    except FileNotFoundError:
        print("Error: File not found. Run generate_features.py first.")
        return

    # 2. Define Features (X) and Target (y)
    # These are the "Questions" the AI looks at
    features = [
        'nifty_ret_1m_lag1', 
        'nifty_ret_3m_rolling_std', 
        'nifty_ma_5m',
        'ce_ret_1m_lag1', 
        'pe_ret_1m_lag1',
        'ce_rolling_std_5m', 
        'pe_rolling_std_5m',
        'ce_pe_mid', 
        'ce_minus_pe',
        'minute_of_day', 
        'is_opening_hour', 
        'is_closing_hour'
    ]
    
    X = df[features]
    y = df[TARGET_COL]

    # 3. Split Data (Train / Test)
    # CRITICAL: We use time-based splitting (First 80% train, Last 20% test)
    # We DO NOT shuffle, because future data cannot leak into the past.
    split_idx = int(len(df) * 0.8)
    
    X_train = X.iloc[:split_idx]
    y_train = y.iloc[:split_idx]
    
    X_test = X.iloc[split_idx:]
    y_test = y.iloc[split_idx:]
    
    print(f"Training on {len(X_train)} samples, Testing on {len(X_test)} samples.")
    print(f"Baseline Accuracy (Blind Guessing): {y_test.mean():.2%}")

    # 4. Train the Model (Random Forest)
    print("\nTraining Random Forest Model...")
    model = RandomForestClassifier(
        n_estimators=200,      # Number of trees
        max_depth=5,           # Keep it simple to avoid overfitting
        min_samples_leaf=50,   # Require significant evidence for a rule
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train, y_train)

    # 5. Evaluate (The Exam)
    print("\n--- EVALUATION ON UNSEEN DATA ---")
    y_pred = model.predict(X_test)
    
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Model Accuracy: {accuracy:.2%}")
    
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    # 6. Feature Importance (What did the AI learn?)
    importances = pd.DataFrame({
        'Feature': features,
        'Importance': model.feature_importances_
    }).sort_values(by='Importance', ascending=False)
    
    print("\nTop 5 Most Important Features:")
    print(importances.head(5))

    # 7. Simple Profit Simulation (Backtest)
    # We simulate: Buy when AI predicts 1 (UP), Hold for 1 min.
    print("\n--- PROFIT SIMULATION ---")
    
    # Get the actual returns from the test period
    # We need to grab the returns corresponding to X_test indices
    # (Assuming we have 'ce_ret_1m' in the original file, we re-load or slice)
    actual_returns = df['ce_ret_1m'].iloc[split_idx:].values
    
    # Strategy: 
    # If Pred = 1, Profit = Actual Return - Brokerage/Slippage
    # If Pred = 0, Profit = 0 (We stay out)
    
    # Approx cost per trade (0.05% slippage + fees)
    COST_PER_TRADE = 0.0005 
    
    strategy_returns = []
    equity = [100] # Start with Rs 100
    
    for pred, ret in zip(y_pred, actual_returns):
        if pred == 1:
            # We bought
            pnl = ret - COST_PER_TRADE
            equity.append(equity[-1] * (1 + pnl))
        else:
            # We stayed cash
            equity.append(equity[-1])
            
    final_equity = equity[-1]
    total_return = (final_equity - 100)
    
    print(f"Starting Capital: 100")
    print(f"Ending Capital:   {final_equity:.2f}")
    print(f"Total Return:     {total_return:.2f}%")
    
    if total_return > 0:
        print("✅ RESULT: The strategy is PROFITABLE.")
    else:
        print("❌ RESULT: The strategy LOST money.")

    # Optional: Plot Equity Curve
    # plt.plot(equity)
    # plt.title("Strategy Equity Curve")
    # plt.show()

if __name__ == "__main__":
    train_and_evaluate()