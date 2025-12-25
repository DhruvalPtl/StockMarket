# src/train_pipeline.py
"""
Baseline training pipeline for NIFTY (default data: nifty_1m.csv)
- LightGBM baseline
- PyTorch LSTM baseline (small quick test settings)
Run:
    python src/train_pipeline.py --data nifty_1m.csv
"""

import argparse
import os
import joblib
from datetime import timedelta
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error

# LightGBM
import lightgbm as lgb

# PyTorch for LSTM
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

# -------------------------
# Config / Hyperparams
# -------------------------
SEED = 42
np.random.seed(SEED)
torch.manual_seed(SEED)

LSTM_SEQ_LEN = 30   # quicker for testing
BATCH_SIZE = 128
LSTM_EPOCHS = 2    # small number for smoke test
LR = 1e-3
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# -------------------------
# Utility functions
# -------------------------
def load_data(path):
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df

def add_features(df):
    df = df.copy()

    # Basic returns (fill 0 for the very first row)
    df["return_1"] = df["close"].pct_change().fillna(0)
    df["logret_1"] = np.log1p(df["return_1"].fillna(0))

    # lags
    for lag in (1, 2, 3, 5, 10, 20):
        df[f"close_lag_{lag}"] = df["close"].shift(lag)

    # rolling stats
    df["rmean_5"] = df["close"].rolling(5).mean()
    df["rstd_5"] = df["close"].rolling(5).std()
    df["rmean_20"] = df["close"].rolling(20).mean()
    df["rstd_20"] = df["close"].rolling(20).std()

    # volume features
    df["vol_rolling_10"] = df["volume"].rolling(10).mean()

    # typical price and vwap
    df["typ_price"] = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap_10"] = (df["typ_price"] * df["volume"]).rolling(10).sum() / (df["volume"].rolling(10).sum() + 1e-9)

    # time features
    df["minute"] = df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute
    df["minute_sin"] = np.sin(2 * np.pi * df["minute"] / (24*60))
    df["minute_cos"] = np.cos(2 * np.pi * df["minute"] / (24*60))

    # --- DO NOT dropna here ---
    # Fill reasonable NaNs for feature columns so we keep as many rows as possible.
    # - For lag/rolling features at the start, use forward/backfill so sequence models still work.
    # - For rstd (std) NaNs, fill with 0 (no volatility).
    roll_cols = ["rstd_5", "rstd_20"]
    df[roll_cols] = df[roll_cols].fillna(0)

    # For other rolling/lag columns, backfill then forward-fill as a conservative choice.
    fill_cols = [c for c in df.columns if c not in ("timestamp", "open", "high", "low", "close", "volume")]
    df[fill_cols] = df[fill_cols].fillna(method="bfill").fillna(method="ffill").fillna(0)

    return df


def make_target(df, horizon=1):
    """
    Safer target creation:
    target = (close at t+horizon / close at t) - 1
    We only drop rows where the target itself is NaN (preserves feature rows).
    """
    df = df.copy()
    df[f"target_r_{horizon}"] = df["close"].shift(-horizon) / df["close"] - 1.0
    df = df.dropna(subset=[f"target_r_{horizon}"]).reset_index(drop=True)
    return df



# -------------------------
# LightGBM training
# -------------------------
def train_lgbm(X_train, y_train, X_val, y_val, feature_names, save_path="lgbm_model.pkl"):
    dtrain = lgb.Dataset(X_train, label=y_train, feature_name=feature_names)
    dvalid = lgb.Dataset(X_val, label=y_val, reference=dtrain, feature_name=feature_names)
    params = {
        "objective": "regression",
        "metric": "rmse",
        "learning_rate": 0.05,
        "num_leaves": 64,
        "seed": SEED,
        "verbosity": -1,
    }
    model = lgb.train(params, dtrain, num_boost_round=200, valid_sets=[dtrain, dvalid],
                      early_stopping_rounds=20, verbose_eval=50)
    joblib.dump(model, save_path)
    return model

# -------------------------
# PyTorch LSTM model
# -------------------------
class SequenceDataset(Dataset):
    def __init__(self, data, seq_len, features, target_col):
        self.data = data
        self.seq_len = seq_len
        self.features = features
        self.target_col = target_col

    def __len__(self):
        return len(self.data) - self.seq_len

    def __getitem__(self, idx):
        start = idx
        end = idx + self.seq_len
        seq = self.data[self.features].iloc[start:end].values.astype(np.float32)
        target = self.data[self.target_col].iloc[end]
        return torch.from_numpy(seq), torch.tensor(target, dtype=torch.float32)

class LSTMPredictor(nn.Module):
    def __init__(self, n_features, hidden_dim=64, n_layers=2, dropout=0.1):
        super().__init__()
        self.lstm = nn.LSTM(input_size=n_features, hidden_size=hidden_dim,
                            num_layers=n_layers, batch_first=True, dropout=dropout)
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 1)
        )

    def forward(self, x):
        out, _ = self.lstm(x)
        out = out[:, -1, :]
        return self.fc(out).squeeze(-1)

def train_lstm_model(df, features, target_col, seq_len=LSTM_SEQ_LEN, epochs=LSTM_EPOCHS, save_path="lstm.pth"):
    ds = SequenceDataset(df, seq_len, features, target_col)
    loader = DataLoader(ds, batch_size=BATCH_SIZE, shuffle=True, drop_last=True)
    model = LSTMPredictor(n_features=len(features)).to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    loss_fn = nn.MSELoss()
    model.train()
    for epoch in range(epochs):
        total_loss = 0.0
        for X_batch, y_batch in loader:
            X_batch = X_batch.to(DEVICE)
            y_batch = y_batch.to(DEVICE)
            pred = model(X_batch)
            loss = loss_fn(pred, y_batch)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * X_batch.size(0)
        avg = total_loss / len(ds)
        print(f"[LSTM] Epoch {epoch+1}/{epochs}, train_loss={avg:.6f}")
    torch.save(model.state_dict(), save_path)
    return model

# -------------------------
# Main orchestration
# -------------------------
def main(args):
    df = load_data(args.data)
    print("Loaded rows:", len(df))
    df = add_features(df)
    df = make_target(df, horizon=1)
    print("After features/target rows:", len(df))
    # quick diagnostics: how many NaNs remain in each feature column
    nan_counts = df.isna().sum()
    print("NaN counts (top 10 cols):")
    print(nan_counts[nan_counts > 0].sort_values(ascending=False).head(10))
    if len(df) == 0:
        raise RuntimeError("No rows after target creation — check input CSV and feature generation.")


    exclude = {"timestamp", "target_r_1"}
    features = [c for c in df.columns if c not in exclude and df[c].dtype in [np.float64, np.float32, np.int64, np.int32]]
    print("Using features:", features)

    split_idx = int(len(df) * 0.9)
    train_df = df.iloc[:split_idx].reset_index(drop=True)
    test_df = df.iloc[split_idx:].reset_index(drop=True)

    X_train = train_df[features].values
    y_train = train_df["target_r_1"].values
    X_test = test_df[features].values
    y_test = test_df["target_r_1"].values

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)
    joblib.dump(scaler, "scaler.pkl")

    print("Training LightGBM baseline...")
    lgb_model = train_lgbm(X_train, y_train, X_test, y_test, feature_names=features, save_path="lgbm_model.pkl")
    preds = lgb_model.predict(X_test)
    rmse = mean_squared_error(y_test, preds, squared=False)
    print(f"LightGBM RMSE on test: {rmse:.6e}")

    df_scaled = df.copy()
    df_scaled[features] = scaler.transform(df[features].values)
    train_for_lstm = df_scaled.iloc[:split_idx].reset_index(drop=True)
    print("Training LSTM baseline (this may take longer)...")
    lstm_model = train_lstm_model(train_for_lstm, features, target_col="target_r_1", save_path="lstm.pth")

    test_for_eval = df_scaled.iloc[split_idx - LSTM_SEQ_LEN:].reset_index(drop=True)
    seq_ds = SequenceDataset(test_for_eval, seq_len=LSTM_SEQ_LEN, features=features, target_col="target_r_1")
    seq_loader = DataLoader(seq_ds, batch_size=BATCH_SIZE, shuffle=False)
    lstm_model.eval()
    preds_l = []
    trues_l = []
    with torch.no_grad():
        for X_batch, y_batch in seq_loader:
            X_batch = X_batch.to(DEVICE)
            out = lstm_model(X_batch).cpu().numpy()
            preds_l.extend(out.tolist())
            trues_l.extend(y_batch.numpy().tolist())
    rmse_lstm = mean_squared_error(trues_l, preds_l, squared=False)
    print(f"LSTM RMSE on test: {rmse_lstm:.6e}")

    out_df = test_df.copy()
    out_df["pred_lgb"] = preds
    pad = len(out_df) - len(preds_l)
    if pad >= 0:
        out_df["pred_lstm"] = [np.nan]*pad + preds_l
    else:
        out_df["pred_lstm"] = preds_l[-len(out_df):]
    out_df.to_csv("predictions_test.csv", index=False)
    print("Saved predictions_test.csv")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, default="nifty_1m.csv", help="Path to candle CSV (default: nifty_1m.csv)")
    args = parser.parse_args()
    main(args)
