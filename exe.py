# src/execution.py
import os
from typing import Dict, Optional
from dotenv import load_dotenv
import requests
import hashlib
import hmac
import time
import numpy as np
import math
from decimal import Decimal, ROUND_DOWN

# Load .env (for local dev; in AWS, use Secrets Manager)
# load_dotenv()

BASE_URL = "https://mock-api.roostoo.com"
# API_KEY = os.getenv("ROOSTOO_API_KEY")
# SECRET_KEY = os.getenv("ROOSTOO_SECRET_KEY")

API_KEY = "wzVdBhwUlDOB4hhpPIKxh0GSlvUnxWQXpoU7t0o69INPArXcyg0poWOa6m8gtayO"
SECRET_KEY = "vcXTcCASuT1qnlG9DPvG7kZfBJTPTvl0IErYG2QbgRYjgwwwmHxzovJVAjfgEJkp"


class Execution:
    def __init__(self, ticker_ratio):
        self.ratio=ticker_ratio


    def generate_signature(self,params):
        query_string = '&'.join(["{}={}".format(k, params[k]) for k in sorted(params.keys())])
        us = SECRET_KEY.encode('utf-8')
        m = hmac.new(us, query_string.encode('utf-8'), hashlib.sha256)
        return m.hexdigest()

    def get_server_time(self):
        r = requests.get(    BASE_URL + "/v3/serverTime",        )
        # print(r.status_code, r.text)
        return r.json()

    def get_ex_info(self):
        r = requests.get(
            BASE_URL + "/v3/exchangeInfo",
        )
        # print(r.status_code, r.text)
        return r.json()


    def get_ticker(self,pair=None):
        payload = {
            "timestamp": int(time.time()),
        }
        if pair:
            payload["pair"] = pair

        r = requests.get(
            BASE_URL + "/v3/ticker",
            params=payload,
        )
        # print(r.status_code, r.text)
        return r.json()


    def get_balance(self):
        payload = {
            "timestamp": int(time.time()) * 1000,
        }

        r = requests.get(
            BASE_URL + "/v3/balance",
            params=payload,
            headers={"RST-API-KEY": API_KEY,
                    "MSG-SIGNATURE": self.generate_signature(payload)}
        )
        # print(r.status_code, r.text)
        return r.json()


    def place_order(self,coin, side, qty, price=None):
        if side==1:
            side='BUY'
        elif side==-1:
            side='SELL'
        payload = {
            "timestamp": int(time.time()) * 1000,
            "pair": coin + "/USD",
            "side": side,
            "quantity": qty,
        }

        if not price:
            payload['type'] = "MARKET"
        else:
            payload['type'] = "LIMIT"
            payload['price'] = price

        r = requests.post(
            BASE_URL + "/v3/place_order",
            data=payload,
            headers={"RST-API-KEY": API_KEY,
                    "MSG-SIGNATURE": self.generate_signature(payload)}
        )
        print(r.status_code, r.text)
        return r.status_code


    def cancel_order(self,coin):
        payload = {
            "timestamp": int(time.time()) * 1000,
            # "order_id": 77,
            "pair": "BNB/USD",
        }

        r = requests.post(
            BASE_URL + "/v3/cancel_order",
            data=payload,
            headers={"RST-API-KEY": API_KEY,
                    "MSG-SIGNATURE": self.generate_signature(payload)}
        )
        print(r.status_code, r.text)


    def query_order(self):
        payload = {
            "timestamp": int(time.time())*1000,
            # "order_id": 77,
            # "pair": "DASH/USD",
            # "pending_only": True,
        }

        r = requests.post(
            BASE_URL + "/v3/query_order",
            data=payload,
            headers={"RST-API-KEY": API_KEY,
                    "MSG-SIGNATURE": self.generate_signature(payload)}
        )
        print(r.status_code, r.text)


    def pending_count(self):
        payload = {
            "timestamp": int(time.time()) * 1000,
        }

        r = requests.get(
            BASE_URL + "/v3/pending_count",
            params=payload,
            headers={"RST-API-KEY": API_KEY,
                    "MSG-SIGNATURE": self.generate_signature(payload)}
        )
        print(r.status_code, r.text)
        return r.json()
    
    def get_portfolio_value(self,bal=None,tick=None,spec=None) -> float:
        balance_resp = bal if bal is not None else self.get_balance()
        wallet = balance_resp.get("SpotWallet", {})  
        total_value = 0.0
        ticker=tick if tick is not None else self.get_ticker()
        for asset, balances in wallet.items():
                free_amount = balances.get("Free", 0.0)
                if asset == "USD":
                    total_value += free_amount
                else:
                    try:
                        pair = f"{asset}/USD"
                        price = float(ticker['Data'][pair]['LastPrice'])
                        usd_value = free_amount * price
                        total_value += usd_value
                    except Exception as e:
                        print(f" Error fetching price for {asset}: {e}")
                        continue
        if spec==None:
            return total_value
        else: 
            value=wallet[spec]['Free']*ticker['Data'][f"{spec}/USD"]['LastPrice']
            proportion_p=value/total_value
            proportion_t=value/(total_value*self.ratio[spec])
            return total_value,proportion_p,proportion_t
            

    def send_order(self, target_position:Dict):
        self.signal=target_position
        coin_lot = {}
        r=self.get_balance()
        tick=self.get_ticker()
        info=self.get_ex_info()
        i=3
        total_value=self.get_portfolio_value(bal=r,tick=tick)
        for asset, ratio in self.ratio.items():
            coin_lot[asset] = total_value * (0.995+0.003)*ratio #prevent fail order due to overlapping capital
        cash=r['SpotWallet']['USD']['Free']
        all_assets = set(self.signal.keys()) # assume signal contain all potential coin 
        for asset in all_assets:
            if asset == "USD": continue  
            curr = r['SpotWallet'].get(asset, {}).get("Free", 0.0)
            price = tick['Data'][f"{asset}/USD"]['LastPrice']
            curr=price*curr
            des=self.signal[asset]*coin_lot[asset]
            targ=des-curr
            if abs(targ)>total_value*0.03:
                if des!=0:
                    step=10**(-info['TradePairs'][f"{asset}/USD"]['AmountPrecision']) 
                    qty=np.sign(targ)*max(math.floor(abs((targ)/price)/step)*step,math.ceil(abs(1/price)/step)*step)
                    # print(cash)
                    cash=cash-targ*(1+0.001)
                    # print(cash)
                    # print(targ)
                    # print(qty*price) 
                    st=self.place_order(coin=asset,side=np.sign(qty),qty=abs(qty))
                    # time.sleep(0.2)
                elif des==0:
                    st=self.clear_all(spec=asset,bal=r)
                if st==200:
                    i+=1
                if i%5==0:
                    time.sleep(1)
            else:
                continue
    def clear_all(self,spec=None,bal=None):
        r= bal if bal is not None else self.get_balance()
        all_assets=set(self.ratio.keys())
        i=1 if bal==None else 0
        if spec==None:
            for asset in all_assets:
                if asset == "USD": continue  
                curr = r['SpotWallet'].get(asset, {}).get("Free", 0.0)
                if curr!=0:
                    self.place_order(coin=asset,side=np.sign(-1),qty=abs(curr))
                    i+=1
                    if i%5==0:
                        time.sleep(1)
        else:
            curr = r['SpotWallet'].get(spec, {}).get("Free", 0.0)
            if curr!=0:
                st=self.place_order(coin=spec,side=np.sign(-1),qty=abs(curr))
                # print('?')
                return st# 

# src/execution.py
# import os
# from typing import Dict, Optional
# from dotenv import load_dotenv
# import requests
# import hashlib
# import hmac
# import time
# import numpy as np
# import math
# from decimal import Decimal, ROUND_DOWN

# # Load .env (for local dev; in AWS, use Secrets Manager)
# load_dotenv()

# BASE_URL = "https://mock-api.roostoo.com"
# API_KEY = os.getenv("ROOSTOO_API_KEY")
# SECRET_KEY = os.getenv("ROOSTOO_SECRET_KEY")

# # API_KEY = "wzVdBhwUlDOB4hhpPIKxh0GSlvUnxWQXpoU7t0o69INPArXcyg0poWOa6m8gtayO"
# # SECRET = "vcXTcCASuT1qnlG9DPvG7kZfBJTPTvl0IErYG2QbgRYjgwwwmHxzovJVAjfgEJkp"

# BASE_URL = "https://mock-api.roostoo.com"


# class Execution:
#     def __init__(self, current_position,target_position, ticker_ratio):#,dry_run: bool = True):
#         """
#         Initialize execution engine.
#         :param dry_run: If True, skip real orders (for testing).
#         """
#         self.signals=target_position
#         self.current=current_position #
#         self.ratio=ticker_ratio
        
#         # self.dry_run = dry_run
#         # self.current_position = {}  # e.g., {"BTC/USD": 0.5}
#         # self.available_capital = 0.0
#         # self._update_balance()

#     def generate_signature(self,params):
#         query_string = '&'.join(["{}={}".format(k, params[k])
#                                 for k in sorted(params.keys())])
#         us = SECRET_KEY.encode('utf-8')
#         m = hmac.new(us, query_string.encode('utf-8'), hashlib.sha256)
#         return m.hexdigest()

#     def get_server_time(self):
#         r = requests.get(
#             BASE_URL + "/v3/serverTime",
#         )
#         print(r.status_code, r.text)
#         return r.json()

#     def get_ex_info(self):
#         r = requests.get(
#             BASE_URL + "/v3/exchangeInfo",
#         )
#         print(r.status_code, r.text)
#         return r.json()


#     def get_ticker(self,pair=None):
#         payload = {
#             "timestamp": int(time.time()),
#         }
#         if pair:
#             payload["pair"] = pair

#         r = requests.get(
#             BASE_URL + "/v3/ticker",
#             params=payload,
#         )
#         print(r.status_code, r.text)
#         return r.json()


#     def get_balance(self):
#         payload = {
#             "timestamp": int(time.time()) * 1000,
#         }

#         r = requests.get(
#             BASE_URL + "/v3/balance",
#             params=payload,
#             headers={"RST-API-KEY": API_KEY,
#                     "MSG-SIGNATURE": self.generate_signature(payload)}
#         )
#         # print(r.status_code, r.text)
#         return r.json()


#     def place_order(self,coin, side, qty, price=None):
#         if side==1:
#             side='BUY'
#         elif side==-1:
#             side='SELL'
#         payload = {
#             "timestamp": int(time.time()) * 1000,
#             "pair": coin + "/USD",
#             "side": side,
#             "quantity": qty,
#         }

#         if not price:
#             payload['type'] = "MARKET"
#         else:
#             payload['type'] = "LIMIT"
#             payload['price'] = price

#         r = requests.post(
#             BASE_URL + "/v3/place_order",
#             data=payload,
#             headers={"RST-API-KEY": API_KEY,
#                     "MSG-SIGNATURE": self.generate_signature(payload)}
#         )
#         print(r.status_code, r.text)


#     def cancel_order(self,coin):
#         payload = {
#             "timestamp": int(time.time()) * 1000,
#             # "order_id": 77,
#             "pair": "BNB/USD",
#         }

#         r = requests.post(
#             BASE_URL + "/v3/cancel_order",
#             data=payload,
#             headers={"RST-API-KEY": API_KEY,
#                     "MSG-SIGNATURE": self.generate_signature(payload)}
#         )
#         print(r.status_code, r.text)


#     def query_order(self):
#         payload = {
#             "timestamp": int(time.time())*1000,
#             # "order_id": 77,
#             # "pair": "DASH/USD",
#             # "pending_only": True,
#         }

#         r = requests.post(
#             BASE_URL + "/v3/query_order",
#             data=payload,
#             headers={"RST-API-KEY": API_KEY,
#                     "MSG-SIGNATURE": self.generate_signature(payload)}
#         )
#         print(r.status_code, r.text)


#     def pending_count(self):
#         payload = {
#             "timestamp": int(time.time()) * 1000,
#         }

#         r = requests.get(
#             BASE_URL + "/v3/pending_count",
#             params=payload,
#             headers={"RST-API-KEY": API_KEY,
#                     "MSG-SIGNATURE": self.generate_signature(payload)}
#         )
#         print(r.status_code, r.text)
#         return r.json()
    
#     def calculate(self):
#         r=self.get_balance()
#         cash=r['SpotWallet']['USD']['Free']
#         signals = {}

#         all_assets = set(self.current.keys()) | set(self.signal.keys())
    
#         for asset in all_assets:
#             curr = self.current.get(asset, 0)
#             targ = self.signal.get(asset, 0)
#             delta = targ - curr
#             signals[asset] = delta

#         return signals
    
#     def get_portfolio_value(self) -> float:

#         # 1. Get balance
#         balance_resp = self.get_balance()
#         wallet = balance_resp.get("SpotWallet", {})  # or "SpotWallet" if needed

#         total_value = 0.0

#         # 2. Loop through each asset in wallet
#         for asset, balances in wallet.items():
#             free_amount = balances.get("Free", 0.0)

#             if asset == "USD":
#                 # USD value is just the amount
#                 usd_value = free_amount
#                 # print(f"USD: {free_amount} → ${usd_value:,.2f}")
#                 total_value += usd_value
#             else:
#                 # For crypto assets: get price via ticker
#                 try:
#                     pair = f"{asset}/USD"
#                     ticker_resp = self.get_ticker(pair=pair)
                    
#                     # Parse price from response
#                     # Assume response is like: {"price": "60234.56", ...}
#                     # or {"data": {"price": "60234.56"}}
#                     price = None
#                     # if "price" in ticker_resp:
#                     #     price = float(ticker_resp["price"])
#                     price = float(ticker_resp["Data"][pair]["LastPrice"])

#                     usd_value = free_amount * price
#                     # print(f"{asset}: {free_amount} @ ${price:,.2f} = ${usd_value:,.2f}")
#                     total_value += usd_value

#                 except Exception as e:
#                     print(f"❌ Error fetching price for {asset}: {e}")
#                     continue

#         # print(f"✅ Total Portfolio Value: ${total_value:,.2f}")
#         return total_value
            
    
#     # def send_order(self):

#     def send_order(self,target_position):
#         # signals=self.calculate()
#         # for asset, ratio in self.signal.items():
#         self.signal=target_position
#         target_usd = {}
#         total_value=100000#self.get_portfolio_value()
#         for asset, ratio in self.ratio.items():
#             target_usd[asset] = total_value * ratio
#             # print(target_usd[asset])
#             # print(f"Target {asset} value: ${target_usd[asset]:,.2f} ({ratio:.1%})")
#         # exe_usd={}
#         # for asset, ratio in self.signal.items():
#         #     target=target_usd[asset]*ratio
#         #     exe_usd[asset]=target
#         #     # print(target)
#         #     # self.place_order(coin=asset,side=ratio/abs(ratio),qty=target)
        
#         r=self.get_balance()
#         # cash=r['SpotWallet']['USD']['Free']
#         # signals = {}
#         tick=self.get_ticker()

#         all_assets = set(self.signal.keys()) #set(r['SpotWallet'].keys()) | set(self.signal.keys())
#         print(all_assets)
    
#         for asset in all_assets:
#             if asset == "USD":
#                 continue  # skip USD
#             curr = r['SpotWallet'].get(asset,0)['Free']#[asset]['Free']
#             # print(curr)
#             pair = f"{asset}/USD"
#             price = tick['Data'][pair]['LastPrice']#self.get_ticker(pair=pair)
            
#             # Parse price from response
#             # Assume response is like: {"price": "60234.56", ...}
#             # or {"data": {"price": "60234.56"}}
#             # price = None
#             # if "price" in ticker_resp:
#             #     price = float(ticker_resp["price"])
#             # price = float(ticker_resp["Data"][pair]["LastPrice"])
#             print(price)
#             curr=price*curr
#             targ = self.signal.get(asset, 0)*target_usd.get(asset,0)
#             # delta = max((targ - curr)/price,1/price)
#             delta=(targ-curr)/price
#             price = Decimal(delta)
#             # Round down to 2 decimals → 123.45
#             rounded = price.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
#             print(delta)
#             print(rounded)
#             self.place_order(coin=asset,side=np.sign(delta),qty=abs(rounded))
#         # signals=self.calculate()
#         # target_usd = {}
#         # total_value=self.get_portfolio_value()
#         # for asset, ratio in self.ratio.items():
#         #     target_usd[asset] = total_value * ratio
#         #     # print(target_usd[asset])
#         #     # print(f"Target {asset} value: ${target_usd[asset]:,.2f} ({ratio:.1%})")
#         # for asset, ratio in signals.items():
#         #     target=target_usd[asset]*ratio
#         #     # print(target)
            
#         #     self.place_order(coin=asset,side=-1,qty=target)
        

# # # src/execution.py
# # import os
# # from typing import Dict, Optional
# # from dotenv import load_dotenv
# # import requests
# # import hashlib
# # import hmac
# # import time
# # import numpy as np
# # import math
# # from decimal import Decimal, ROUND_DOWN

# # # Load .env (for local dev; in AWS, use Secrets Manager)
# # load_dotenv()

# # BASE_URL = "https://mock-api.roostoo.com"
# # API_KEY = os.getenv("ROOSTOO_API_KEY")
# # SECRET_KEY = os.getenv("ROOSTOO_SECRET_KEY")

# # # API_KEY = "wzVdBhwUlDOB4hhpPIKxh0GSlvUnxWQXpoU7t0o69INPArXcyg0poWOa6m8gtayO"
# # # SECRET = "vcXTcCASuT1qnlG9DPvG7kZfBJTPTvl0IErYG2QbgRYjgwwwmHxzovJVAjfgEJkp"

# # BASE_URL = "https://mock-api.roostoo.com"


# # class Execution:
# #     def __init__(self, target_position, ticker_ratio):#,dry_run: bool = True):
# #         """
# #         Initialize execution engine.
# #         :param dry_run: If True, skip real orders (for testing).
# #         """
# #         self.signal1=target_position
# #         # self.current=current_position #
# #         self.ratio=ticker_ratio
        
# #         # self.dry_run = dry_run
# #         # self.current_position = {}  # e.g., {"BTC/USD": 0.5}
# #         # self.available_capital = 0.0
# #         # self._update_balance()
# #     #call alpha 
# #     #position
# #     target_position={'ticker1':1/3}
# #     #aggregate

# #     def generate_signature(self,params):
# #         query_string = '&'.join(["{}={}".format(k, params[k])
# #                                 for k in sorted(params.keys())])
# #         us = SECRET_KEY.encode('utf-8')
# #         m = hmac.new(us, query_string.encode('utf-8'), hashlib.sha256)
# #         return m.hexdigest()

# #     def get_server_time(self):
# #         r = requests.get(
# #             BASE_URL + "/v3/serverTime",
# #         )
# #         print(r.status_code, r.text)
# #         return r.json()

# #     def get_ex_info(self):
# #         r = requests.get(
# #             BASE_URL + "/v3/exchangeInfo",
# #         )
# #         print(r.status_code, r.text)
# #         return r.json()


# #     def get_ticker(self,pair=None):
# #         payload = {
# #             "timestamp": int(time.time()),
# #         }
# #         if pair:
# #             payload["pair"] = pair

# #         r = requests.get(
# #             BASE_URL + "/v3/ticker",
# #             params=payload,
# #         )
# #         # print(r.status_code, r.text)
# #         return r.json()


# #     def get_balance(self):
# #         payload = {
# #             "timestamp": int(time.time()) * 1000,
# #         }

# #         r = requests.get(
# #             BASE_URL + "/v3/balance",
# #             params=payload,
# #             headers={"RST-API-KEY": API_KEY,
# #                     "MSG-SIGNATURE": self.generate_signature(payload)}
# #         )
# #         # print(r.status_code, r.text)
# #         return r.json()


# #     def place_order(self,coin, side, qty, price=None):
# #         if side==1:
# #             side='BUY'
# #         elif side==-1:
# #             side='SELL'
# #         payload = {
# #             "timestamp": int(time.time()) * 1000,
# #             "pair": coin + "/USD",
# #             "side": side,
# #             "quantity": qty,
# #         }

# #         if not price:
# #             payload['type'] = "MARKET"
# #         else:
# #             payload['type'] = "LIMIT"
# #             payload['price'] = price

# #         r = requests.post(
# #             BASE_URL + "/v3/place_order",
# #             data=payload,
# #             headers={"RST-API-KEY": API_KEY,
# #                     "MSG-SIGNATURE": self.generate_signature(payload)}
# #         )
# #         print(r.status_code, r.text)


# #     def cancel_order(self,coin):
# #         payload = {
# #             "timestamp": int(time.time()) * 1000,
# #             # "order_id": 77,
# #             "pair": "BNB/USD",
# #         }

# #         r = requests.post(
# #             BASE_URL + "/v3/cancel_order",
# #             data=payload,
# #             headers={"RST-API-KEY": API_KEY,
# #                     "MSG-SIGNATURE": self.generate_signature(payload)}
# #         )
# #         print(r.status_code, r.text)


# #     def query_order(self):
# #         payload = {
# #             "timestamp": int(time.time())*1000,
# #             # "order_id": 77,
# #             # "pair": "DASH/USD",
# #             # "pending_only": True,
# #         }

# #         r = requests.post(
# #             BASE_URL + "/v3/query_order",
# #             data=payload,
# #             headers={"RST-API-KEY": API_KEY,
# #                     "MSG-SIGNATURE": self.generate_signature(payload)}
# #         )
# #         print(r.status_code, r.text)


# #     def pending_count(self):
# #         payload = {
# #             "timestamp": int(time.time()) * 1000,
# #         }

# #         r = requests.get(
# #             BASE_URL + "/v3/pending_count",
# #             params=payload,
# #             headers={"RST-API-KEY": API_KEY,
# #                     "MSG-SIGNATURE": self.generate_signature(payload)}
# #         )
# #         print(r.status_code, r.text)
# #         return r.json()
    
# #     def calculate(self):
# #         r=self.get_balance()
# #         cash=r['SpotWallet']['USD']['Free']
# #         signals = {}

# #         all_assets = set(self.current.keys()) | set(self.signal.keys())
    
# #         for asset in all_assets:
# #             curr = self.current.get(asset, 0)
# #             targ = self.signal.get(asset, 0)
# #             delta = targ - curr
# #             signals[asset] = delta

# #         return signals
    
# #     def get_portfolio_value(self) -> float:

# #         # 1. Get balance
# #         balance_resp = self.get_balance()
# #         wallet = balance_resp.get("SpotWallet", {})  # or "SpotWallet" if needed

# #         total_value = 0.0

# #         # 2. Loop through each asset in wallet
# #         for asset, balances in wallet.items():
# #             free_amount = balances.get("Free", 0.0)

# #             if asset == "USD":
# #                 # USD value is just the amount
# #                 usd_value = free_amount
# #                 # print(f"USD: {free_amount} → ${usd_value:,.2f}")
# #                 total_value += usd_value
# #             else:
# #                 # For crypto assets: get price via ticker
# #                 try:
# #                     pair = f"{asset}/USD"
# #                     ticker_resp = self.get_ticker(pair=pair)
                    
# #                     # Parse price from response
# #                     # Assume response is like: {"price": "60234.56", ...}
# #                     # or {"data": {"price": "60234.56"}}
# #                     price = None
# #                     # if "price" in ticker_resp:
# #                     #     price = float(ticker_resp["price"])
# #                     price = float(ticker_resp["Data"][pair]["LastPrice"])

# #                     usd_value = free_amount * price
# #                     # print(f"{asset}: {free_amount} @ ${price:,.2f} = ${usd_value:,.2f}")
# #                     total_value += usd_value

# #                 except Exception as e:
# #                     print(f"❌ Error fetching price for {asset}: {e}")
# #                     continue

# #         # print(f"✅ Total Portfolio Value: ${total_value:,.2f}")
# #         return total_value
            
    
# #     # def send_order(self):

# #     def send_order(self,targ):
# #         # signals=self.calculate()
# #         # for asset, ratio in self.signal.items():
# #         self.signal=targ
# #         print(self.signal.keys())
# #         target_usd = {}
# #         total_value=self.get_portfolio_value()
# #         for asset, ratio in self.ratio.items():
# #             target_usd[asset] = total_value * ratio
# #             # print(target_usd[asset])
# #             # print(f"Target {asset} value: ${target_usd[asset]:,.2f} ({ratio:.1%})")
# #         # exe_usd={}
# #         # for asset, ratio in self.signal.items():
# #         #     target=target_usd[asset]*ratio
# #         #     exe_usd[asset]=target
# #         #     # print(target)
# #         #     # self.place_order(coin=asset,side=ratio/abs(ratio),qty=target)
        
# #         r=self.get_balance()
# #         cash=r['SpotWallet']['USD']['Free']
# #         # signals = {}

# #         all_assets = set(r['SpotWallet'].keys()) | set(self.signal.keys())
    
# #         for asset in all_assets:
# #             if asset == "USD":
# #                 continue  # skip USD
# #             curr = r['SpotWallet'].get(asset, 0)['Free']
# #             # print(curr)
# #             pair = f"{asset}/USD"
# #             print(pair)
# #             ticker_resp = self.get_ticker(pair=pair)
            
# #             # Parse price from response
# #             # Assume response is like: {"price": "60234.56", ...}
# #             # or {"data": {"price": "60234.56"}}
# #             price = None
# #             # if "price" in ticker_resp:
# #             #     price = float(ticker_resp["price"])
# #             price = float(ticker_resp["Data"][pair]["LastPrice"])
# #             curr=price*curr
# #             targ = self.signal.get(asset, 0)*target_usd.get(asset,0)
# #             delta = max((targ - curr)/price,1/price)
# #             price = Decimal(delta)
# #             # Round down to 2 decimals → 123.45
# #             rounded = price.quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
# #             print(delta)
# #             print(rounded)
# #             self.place_order(coin=asset,side=np.sign(delta),qty=abs(rounded))
# #         # signals=self.calculate()
# #         # target_usd = {}
# #         # total_value=self.get_portfolio_value()
# #         # for asset, ratio in self.ratio.items():
# #         #     target_usd[asset] = total_value * ratio
# #         #     # print(target_usd[asset])
# #         #     # print(f"Target {asset} value: ${target_usd[asset]:,.2f} ({ratio:.1%})")
# #         # for asset, ratio in signals.items():
# #         #     target=target_usd[asset]*ratio
# #         #     # print(target)
            
# #         #     self.place_order(coin=asset,side=-1,qty=target)
        

