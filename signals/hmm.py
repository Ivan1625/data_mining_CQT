import numpy as np
import pandas as pd
from Signal_Template import SignalTemplate
import warnings
warnings.filterwarnings("ignore")

from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple, Any
import time
from datetime import datetime
import ccxt
from sklearn.preprocessing import StandardScaler
from hmmlearn.hmm import GaussianHMM

@dataclass
class ModelConfig:
    n_states: int = 3
    max_em_iter: int = 200
    tol: float = 1e-3
    seed: int = 42
    min_history_points: int = 200
    refit_every: int = 24
    lookback_fit: Optional[int] = 2000

class hmm_signal(SignalTemplate):
    def __init__(self, weight, ticker='BNB', signal_update_frequency_seconds=3600, window_size=7):
        super().__init__(weight, ticker, signal_update_frequency_seconds)
        self.window_size = window_size
        self.exchange_id = "binanceus"
        self.timeframe = "1h"
        self.limit = 1000
        self.model_config = ModelConfig()
        self.tx_cost_bps = 5.0
        self.symbol = f"{ticker}/USDT"
        self.state_means = {}
        self.running_means = {}
        self.running_counts = {}
        self.signal = 0.0
        self.current_state = None
    
    def data(self):
        """Fetch OHLCV data from exchange"""
        try:
            # Initialize exchange
            ex_class = getattr(ccxt, self.exchange_id)
            exchange = ex_class({"enableRateLimit": True})
            
            # Fetch data
            all_rows = []
            limit = self.limit
            
            # Fetch most recent data
            # change from exchange to ccxt binance
            ohlcv = exchange.fetch_ohlcv(symbol=self.symbol, timeframe=self.timeframe, limit=limit)
            if not ohlcv:
                return pd.DataFrame()
            
            all_rows.extend(ohlcv)
            
            # Convert to DataFrame
            cols = ["timestamp", "Open", "High", "Low", "Close", "Volume"]
            df = pd.DataFrame(all_rows, columns=cols)
            
            # Convert timestamp to datetime
            df["date"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.tz_convert(None)
            
            # Remove duplicates and sort
            df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
            
            # Basic data cleaning
            df = df.replace([np.inf, -np.inf], np.nan)
            df = df.dropna(subset=["Open", "High", "Low", "Close"])
            df = df[(df["Open"] > 0) & (df["High"] > 0) & (df["Low"] > 0) & (df["Close"] > 0)]
            df = df[df["Volume"].fillna(0) >= 0]
            
            return df[["date", "Open", "High", "Low", "Close", "Volume"]]
        except Exception as e:
            print(f"Error fetching data: {e}")
            return pd.DataFrame()
    
    def features(self, df):
        """Compute technical features from OHLCV data"""
        if df.empty:
            return pd.DataFrame()
        
        dfx = df.copy()

        # Clean raw data first
        dfx = dfx.replace([np.inf, -np.inf], np.nan)
        dfx = dfx.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
        dfx = dfx[(dfx["Close"] > 0) & (dfx["High"] > 0) & (dfx["Low"] > 0) & (dfx["Open"] > 0)]
        dfx = dfx[dfx["Volume"].fillna(0) >= 0]

        # Compute features
        dfx["ret"] = dfx["Close"].pct_change()

        vol_window = 20
        dfx["vol"] = dfx["ret"].rolling(vol_window, min_periods=max(5, vol_window // 2)).std()

        # Avoid division by zero in hl_spread
        dfx["hl_spread"] = (dfx["High"] - dfx["Low"]) / dfx["Close"].replace(0, np.nan)

        # Volume change; avoid div by zero by replacing 0 with NaN in lag
        vol_prev = dfx["Volume"].shift(1).replace(0, np.nan)
        dfx["vol_chg"] = (dfx["Volume"] - vol_prev) / vol_prev

        # Replace infs with NaN
        for col in ["ret", "vol", "hl_spread", "vol_chg"]:
            dfx[col] = dfx[col].replace([np.inf, -np.inf], np.nan)

        # Winsorize to reduce impact of outliers
        def winsorize(s: pd.Series, p: float = 0.001) -> pd.Series:
            s_no_na = s.dropna()
            if s_no_na.empty:
                return s
            lo, hi = s_no_na.quantile([p, 1 - p])
            return s.clip(lo, hi)

        dfx["ret"] = winsorize(dfx["ret"])
        dfx["vol_chg"] = winsorize(dfx["vol_chg"])
        dfx["hl_spread"] = winsorize(dfx["hl_spread"])
        
        # Ensure we have enough data for quantile calculation
        if len(dfx) > 1:
            dfx["vol"] = dfx["vol"].clip(upper=dfx["vol"].quantile(0.999))

        dfx = dfx.dropna(subset=["ret", "vol", "hl_spread", "vol_chg"]).reset_index(drop=True)

        # Final sanity checks
        X_cols = ["ret", "vol", "hl_spread", "vol_chg"]
        bad_mask = ~np.isfinite(dfx[X_cols]).all(axis=1)
        if bad_mask.any():
            dfx = dfx.loc[~bad_mask].reset_index(drop=True)

        # Clip absolute bounds to prevent absurd magnitudes slipping through
        clip_bounds = {
            "ret": 1.0,          # +/- 100% per bar cap
            "vol": 5.0,          # reasonably high per-bar std
            "hl_spread": 1.0,    # 100% high-low spread cap
            "vol_chg": 10.0,     # +/- 1000% volume change cap
        }
        for c, bound in clip_bounds.items():
            dfx[c] = dfx[c].clip(-bound, bound)

        return dfx
    
    def fit_hmm(self, features):
        """Fit HMM model and predict current state"""
        X_cols = ["ret", "vol", "hl_spread", "vol_chg"]
        cfg = self.model_config
        
        if len(features) < cfg.min_history_points:
            return None, {}
        
        # Use the most recent data for training
        train_end = len(features)
        start = max(0, train_end - cfg.lookback_fit) if cfg.lookback_fit is not None else 0
        
        if train_end - start < cfg.min_history_points:
            return None, {}
            
        X_window_full = features.loc[start:train_end - 1, X_cols].values
        
        # Safety: drop any non-finite rows
        finite_mask = np.isfinite(X_window_full).all(axis=1)
        X_window = X_window_full[finite_mask]
        
        if X_window.shape[0] < cfg.min_history_points:
            return None, {}
            
        # Additional magnitude guard: cap extreme z-scores row-wise before scaling
        X_window = np.clip(X_window, -10.0, 10.0)
        
        scaler_w = StandardScaler()
        try:
            Xw = scaler_w.fit_transform(X_window)
        except Exception:
            return None, {}
            
        hmm = GaussianHMM(
            n_components=cfg.n_states,
            covariance_type="full",
            n_iter=cfg.max_em_iter,
            tol=cfg.tol,
            random_state=cfg.seed,
        )
        
        try:
            hmm.fit(Xw)
        except Exception:
            return None, {}
            
        # Get current state (last point in the features)
        x_i = features.iloc[[-1]][X_cols].values
        
        if not np.isfinite(x_i).all():
            return None, {}
            
        x_i = np.clip(x_i, -10.0, 10.0)
        
        try:
            x_i_s = scaler_w.transform(x_i)
            current_state = hmm.predict(x_i_s)[0]
        except Exception:
            return None, {}
            
        # Calculate state means
        try:
            st_seq = hmm.predict(Xw)
            train_returns = features.loc[start:train_end - 1, "ret"].reset_index(drop=True)
            means = pd.Series(train_returns.groupby(st_seq).mean())
            state_means = means.to_dict()
            return current_state, state_means
        except Exception:
            return current_state, {}
    
    def update_running_means(self, state, return_value):
        """Update running means for each state"""
        if state is None:
            return
            
        cnt_prev = self.running_counts.get(state, 0)
        mean_prev = self.running_means.get(state, 0.0)
        self.running_means[state] = (mean_prev * cnt_prev + return_value) / (cnt_prev + 1)
        self.running_counts[state] = cnt_prev + 1
    
    def get_best_state(self):
        """Determine the best state based on running means"""
        if not self.running_means:
            return None
        return max(self.running_means.items(), key=lambda kv: kv[1])[0]
    
    def get_signal(self):
        """
        Calculate and return the trading signal.
        Returns 1.0 (buy) or 0.0 (stay out)
        """
        try:
            # Get data
            df = self.data()
            if df.empty:
                return self.signal  # Return previous signal if no data
                
            # Compute features
            feat = self.features(df)
            if len(feat) < self.model_config.min_history_points:
                return self.signal
                
            # Get latest return for updating running means
            latest_return = feat["ret"].iloc[-1] if not feat.empty else 0
                
            # Fit HMM and get current state
            current_state, state_means = self.fit_hmm(feat)
            self.current_state = current_state
            
            # Update state means if we got new ones
            if state_means:
                self.state_means = state_means
                
            # If we have a valid state, update running means
            if current_state is not None:
                self.update_running_means(current_state, latest_return)
                
            # Get the best state
            best_state = self.get_best_state()
            
            # Generate signal
            if best_state is not None and current_state is not None:
                self.signal = 1.0 if current_state == best_state else 0.0
            
            # Log current state and signal
            print(f"[{datetime.now()}] {self.ticker}: State={current_state}, Best={best_state}, Signal={self.signal}")
            if self.state_means:
                print(f"State means: {self.state_means}")
                
            return self.signal
            
        except Exception as e:
            print(f"Error in get_signal: {e}")
            return self.signal  # Return previous signal on error



