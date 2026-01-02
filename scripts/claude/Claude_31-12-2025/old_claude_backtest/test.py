# Test the function
from datetime import datetime, timedelta

def get_futures_symbol(date: datetime) -> str:
    year = date.year
    month = date. month
    
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    
    last_day = next_month - timedelta(days=1)
    days_since_thursday = (last_day. weekday() - 3) % 7
    last_thursday = last_day - timedelta(days=days_since_thursday)
    
    if date.date() > last_thursday.date():
        if month == 12:
            month = 1
            year += 1
        else:
            month += 1
        
        if month == 12:
            next_month = datetime(year + 1, 1, 1)
        else:
            next_month = datetime(year, month + 1, 1)
        
        last_day = next_month - timedelta(days=1)
        days_since_thursday = (last_day.weekday() - 3) % 7
        last_thursday = last_day - timedelta(days=days_since_thursday)
    
    return f"NSE-NIFTY-{last_thursday.strftime('%d%b%y')}-FUT"


# Test with different dates
test_dates = [
    "2025-11-27",  # Before Nov expiry
    "2025-11-28",  # After Nov expiry (Nov 27 was last Thu)
    "2025-12-15",  # Mid December
    "2025-12-27",  # Today (before Dec 25 expiry?  Let's check)
    "2025-12-31",  # After Dec expiry
    "2026-01-15",  # Mid January
]

print("Date         → Futures Symbol")
print("-" * 45)
for d in test_dates: 
    dt = datetime.strptime(d, "%Y-%m-%d")
    symbol = get_futures_symbol(dt)
    print(f"{d}   → {symbol}")