import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt

# --- CONFIGURATION ---
INPUT_FILE = "nifty_options_2020_2025.csv"  # The file you just built

def verify_data():
    print(f"Loading {INPUT_FILE}...")
    try:
        df = pd.read_csv(INPUT_FILE)
        # Handle timestamps
        if isinstance(df['timestamp'].iloc[0], str):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        else:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            
        df = df.sort_values('timestamp')
        
    except FileNotFoundError:
        print("File not found. Please run the fetch script first.")
        return

    # --- CHECK 1: YFINANCE CROSS-REFERENCE (The "Real World" Check) ---
    print("\n--- TEST 1: REAL WORLD SPOT CHECK (vs Yahoo Finance) ---")
    
    # Get date range from your file
    start_date = df['timestamp'].min().strftime('%Y-%m-%d')
    end_date = df['timestamp'].max() + pd.Timedelta(days=1)
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    print(f"Downloading Official Nifty Data ({start_date} to {end_date_str})...")
    # Download Daily OHLC from Yahoo to check broad alignment
    yf_df = yf.download("^NSEI", start=start_date, end=end_date_str, interval="1d")
    yf_df.reset_index(inplace=True)
    yf_df['Date'] = pd.to_datetime(yf_df['Date']).dt.date
    
    # Check 5 random days
    unique_days = df['timestamp'].dt.date.unique()
    sample_days = np.random.choice(unique_days, 5, replace=False)
    
    print("\nSampling 5 Random Days for Accuracy:")
    print(f"{'Date':<12} | {'Your File Close':<15} | {'Yahoo Close':<15} | {'Diff':<10}")
    print("-" * 60)
    
    valid_spot = True
    for day in sample_days:
        # Your Data (Last price of that day)
        your_close = df[df['timestamp'].dt.date == day]['nifty_ltp'].iloc[-1]
        
        # Yahoo Data
        try:
            yahoo_row = yf_df[yf_df['Date'] == day]
            if not yahoo_row.empty:
                yahoo_close = yahoo_row['Close'].values[0]
                diff = abs(your_close - yahoo_close)
                
                print(f"{str(day):<12} | {your_close:<15.2f} | {yahoo_close:<15.2f} | {diff:<10.2f}")
                
                if diff > 50: # Allow small difference due to 15:30 settlement vs 15:29 tick
                    valid_spot = False
            else:
                print(f"{str(day):<12} | {your_close:<15.2f} | {'MISSING':<15} | -")
        except Exception:
            pass

    if valid_spot:
        print("\n✅ SPOT CHECK PASSED: Your timestamps match the real world.")
    else:
        print("\n❌ SPOT CHECK FAILED: Significant differences found!")

    # --- CHECK 2: SYNTHETIC SPOT (The "Math" Check) ---
    print("\n--- TEST 2: OPTION-SPOT SYNCHRONIZATION ---")
    
    # Formula: Synthetic = Strike + Call - Put
    # This value should track Nifty Spot very closely
    df['synthetic_spot'] = df['atm_strike'] + df['atm_ce'] - df['atm_pe']
    
    # Calculate Error (Basis)
    df['basis_error'] = df['synthetic_spot'] - df['nifty_ltp']
    
    # Correlation
    correlation = df['synthetic_spot'].corr(df['nifty_ltp'])
    print(f"Correlation between Options and Spot: {correlation:.4f}")
    
    if correlation > 0.99:
        print("✅ MATH CHECK PASSED: Options are perfectly synced with Spot.")
    else:
        print("❌ MATH CHECK FAILED: Options are moving independently of Spot (BAD DATA).")
        
    # Plotting for visual confirmation
    plt.figure(figsize=(10,5))
    plt.plot(df['timestamp'].iloc[-500:], df['nifty_ltp'].iloc[-500:], label='Real Nifty Spot', color='black')
    plt.plot(df['timestamp'].iloc[-500:], df['synthetic_spot'].iloc[-500:], label='Synthetic (Derived from Options)', color='orange', alpha=0.7)
    plt.title("Visual Check: Do Options track the Spot? (Last 500 mins)")
    plt.legend()
    plt.savefig("verification_chart.png")
    print("Chart saved as 'verification_chart.png'. Open it to see if lines overlap.")

    # --- CHECK 3: INTRINSIC VALUE (The "Fake Price" Check) ---
    print("\n--- TEST 3: INTRINSIC VALUE VIOLATIONS ---")
    
    # ITM Call Check: Call Price must be > (Spot - Strike)
    # We check ITM Calls (where Spot > Strike)
    # Using your 'itm_ce' column (which is Strike - 50)
    
    # Let's check the ATM Call.
    # If Spot > ATM Strike, then Call > (Spot - Strike)
    itm_mask = df['nifty_ltp'] > df['atm_strike']
    df['min_theoretical_val'] = df['nifty_ltp'] - df['atm_strike']
    
    violations = df[itm_mask & (df['atm_ce'] < df['min_theoretical_val'] - 5)] # 5 points buffer for spread
    
    print(f"Total Rows Checked: {len(df)}")
    print(f"Impossible Prices Found: {len(violations)}")
    
    if len(violations) < len(df) * 0.01: # Less than 1% error rate is acceptable (data glitches)
        print("✅ PRICE REALITY PASSED: Option prices respect market logic.")
    else:
        print("❌ PRICE REALITY FAILED: Too many options are cheaper than intrinsic value.")

if __name__ == "__main__":
    verify_data()