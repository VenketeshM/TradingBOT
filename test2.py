from keys import key, secret
from binance.um_futures import UMFutures
import ta
import ta.momentum
import ta.trend
import pandas as pd
from time import sleep
from binance.error import ClientError

client = UMFutures(key=key, secret=secret)

# Constants
tp = 0.3  # Take profit percentage
sl = 0.1  # Stop loss percentage
volume = 10  # Volume for one order
leverage = 10  # Leverage
type = 'ISOLATED'  # Margin type ('ISOLATED' or 'CROSS')
symbol = 'BTCUSDT'  # Symbol to trade

# Getting balance in USDT
def get_balance_usdt():
    try:
        response = client.balance(recvWindow=6000)
        for elem in response:
            if elem['asset'] == 'USDT':
                return float(elem['balance'])
    except ClientError as error:
        print("Error:", error)
        return None

# Getting candles for the needed symbol
def klines(symbol):
    try:
        resp = pd.DataFrame(client.klines(symbol, '15m'))
        resp = resp.iloc[:,:6]
        resp.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
        resp = resp.set_index('Time')
        resp.index = pd.to_datetime(resp.index, unit='ms')
        resp = resp.astype(float)
        return resp
    except ClientError as error:
        print("Error:", error)
        return None

# Set leverage for the needed symbol
def set_leverage(symbol, level):
    try:
        response = client.change_leverage(symbol=symbol, leverage=level, recvWindow=6000)
        print(response)
    except ClientError as error:
        print("Error:", error)

# Set margin type for the needed symbol
def set_mode(symbol, type):
    try:
        response = client.change_margin_type(symbol=symbol, marginType=type, recvWindow=6000)
        print(response)
    except ClientError as error:
        print("Error:", error)

# Open new order with the last price, and set TP and SL
def open_order(symbol, side):
    price = float(client.ticker_price(symbol)['price'])
    qty = volume / price
    if side == 'buy':
        try:
            resp1 = client.new_order(symbol=symbol, side='BUY', type='MARKET', quantity=qty)
            print(symbol, side, "placing order")
            print(resp1)
            sleep(2)
            sl_price = round(price - price * sl, 2)
            resp2 = client.new_order(symbol=symbol, side='SELL', type='STOP_MARKET', quantity=qty, stopPrice=sl_price)
            print(resp2)
            sleep(2)
            tp_price = round(price + price * tp, 2)
            resp3 = client.new_order(symbol=symbol, side='SELL', type='TAKE_PROFIT_MARKET', quantity=qty, stopPrice=tp_price)
            print(resp3)
        except ClientError as error:
            print("Error:", error)
    if side == 'sell':
        try:
            resp1 = client.new_order(symbol=symbol, side='SELL', type='MARKET', quantity=qty)
            print(symbol, side, "placing order")
            print(resp1)
            sleep(2)
            sl_price = round(price + price * sl, 2)
            resp2 = client.new_order(symbol=symbol, side='BUY', type='STOP_MARKET', quantity=qty, stopPrice=sl_price)
            print(resp2)
            sleep(2)
            tp_price = round(price - price * tp, 2)
            resp3 = client.new_order(symbol=symbol, side='BUY', type='TAKE_PROFIT_MARKET', quantity=qty, stopPrice=tp_price)
            print(resp3)
        except ClientError as error:
            print("Error:", error)

# Strategy
def str_signal(symbol):
    kl = klines(symbol)
    rsi = ta.momentum.RSIIndicator(kl.Close).rsi()
    rsi_k = ta.momentum.StochRSIIndicator(kl.Close).stochrsi_k()
    rsi_d = ta.momentum.StochRSIIndicator(kl.Close).stochrsi_d()
    ema = ta.trend.ema_indicator(kl.Close, window=200)
    if rsi.iloc[-1] < 40 and ema.iloc[-1] < kl.Close.iloc[-1] and rsi_k.iloc[-1] < 20 and rsi_k.iloc[-3] < rsi_d.iloc[-3] and rsi_k.iloc[-2] < rsi_d.iloc[-2] and rsi_k.iloc[-1] > rsi_d.iloc[-1]:
        return 'up'
    if rsi.iloc[-1] > 60 and ema.iloc[-1] > kl.Close.iloc[-1] and rsi_k.iloc[-1] > 80 and rsi_k.iloc[-3] > rsi_d.iloc[-3] and rsi_k.iloc[-2] > rsi_d.iloc[-2] and rsi_k.iloc[-1] < rsi_d.iloc[-1]:
        return 'down'
    else:
        return 'none'

# Main Loop
while True:
    balance = get_balance_usdt()
    if balance == None:
        print('Cannot connect to API. Check IP, restrictions or wait some time')
        sleep(10)
        continue
    print("My balance is:", balance, "USDT")
    pos = client.get_position_risk()
    if pos:
        print('Position already open. Waiting for it to close.')
        sleep(60)
        continue
    else:
        signal = str_signal(symbol)
        if signal == 'up':
            print('Found BUY signal for', symbol)
            set_mode(symbol, type)
            sleep(1)
            set_leverage(symbol, leverage)
            sleep(1)
            print('Placing BUY order for', symbol)
            open_order(symbol, 'buy')
            sleep(60)
        elif signal == 'down':
            print('Found SELL signal for', symbol)
            set_mode(symbol, type)
            sleep(1)
            set_leverage(symbol, leverage)
            sleep(1)
            print('Placing SELL order for', symbol)
            open_order(symbol, 'sell')
            sleep(60)
        else:
            print('No trade signal detected.')
            sleep(60)
