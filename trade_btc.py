# Import necessary libraries
from keys import key, secret
from binance.um_futures import UMFutures
import ta
import ta.momentum
import ta.trend
import pandas as pd
from time import sleep
from binance.error import ClientError

# Initialize the Binance client
client = UMFutures(key=key, secret=secret)

# Constants for trading
tp = 0.010  # 1 percent
sl = 0.005  # 0.5 percent
volume = 10  # Volume for one order
leverage = 10
margin_type = 'ISOLATED'  # 'ISOLATED' or 'CROSS'
qty = 1  # Amount of concurrent opened positions
symbol = 'BTCUSDC'  # Symbol for trading

# Function to get the trading balance
def get_trading_balance(trading_active):
    try:
        response = client.balance(recvWindow=6000)
        for elem in response:
            if elem['asset'] == 'USDT':
                balance = float(elem['balance'])
                if trading_active:
                    return balance / 2  # Using only half of the balance during trading
                else:
                    return balance
    except ClientError as error:
        print("Error occurred:", error)

# Function to get the price precision of a symbol
def get_price_precision(symbol):
    symbols_info = client.exchange_info()['symbols']
    for symbol_info in symbols_info:
        if symbol_info['symbol'] == symbol:
            return symbol_info['pricePrecision']

# Function to get the quantity precision of a symbol
def get_qty_precision(symbol):
    symbols_info = client.exchange_info()['symbols']
    for symbol_info in symbols_info:
        if symbol_info['symbol'] == symbol:
            return symbol_info['quantityPrecision']

# Function to open a new order with the last price, and set TP and SL
def open_order(symbol, side, balance):
    price = float(client.ticker_price(symbol)['price'])
    qty_precision = get_qty_precision(symbol)
    price_precision = get_price_precision(symbol)
    qty = round(min(volume / price, balance), qty_precision)
    if side == 'buy':
        try:
            resp1 = client.new_order(symbol=symbol, side='BUY', type='MARKET', quantity=qty)
            print(symbol, side, "placing order")
            print(resp1)
            sleep(2)
            sl_price = round(price - price * sl, price_precision)
            resp2 = client.new_order(symbol=symbol, side='SELL', type='STOP_MARKET', quantity=qty,
                                     stopPrice=sl_price)
            print(resp2)
            sleep(2)
            tp_price = round(price + price * tp, price_precision)
            resp3 = client.new_order(symbol=symbol, side='SELL', type='TAKE_PROFIT_MARKET', quantity=qty,
                                     stopPrice=tp_price)
            print(resp3)
        except ClientError as error:
            print("Error occurred:", error)
    if side == 'sell':
        try:
            resp1 = client.new_order(symbol=symbol, side='SELL', type='MARKET', quantity=qty)
            print(symbol, side, "placing order")
            print(resp1)
            sleep(2)
            sl_price = round(price + price * sl, price_precision)
            resp2 = client.new_order(symbol=symbol, side='BUY', type='STOP_MARKET', quantity=qty,
                                     stopPrice=sl_price)
            print(resp2)
            sleep(2)
            tp_price = round(price - price * tp, price_precision)
            resp3 = client.new_order(symbol=symbol, side='BUY', type='TAKE_PROFIT_MARKET', quantity=qty,
                                     stopPrice=tp_price)
            print(resp3)
        except ClientError as error:
            print("Error occurred:", error)

# Function to check the RSI signal for a given symbol
def str_rsi_signal(symbol):
    kl = klines(symbol)
    rsi = ta.momentum.RSIIndicator(kl.Close).rsi()
    rsi_k = ta.momentum.StochRSIIndicator(kl.Close).stochrsi_k()
    rsi_d = ta.momentum.StochRSIIndicator(kl.Close).stochrsi_d()
    kl['macd'] = ta.trend.macd_diff(kl.Close)

    if (rsi.iloc[-1] < 40 and
            rsi_k.iloc[-1] < 20 and rsi_k.iloc[-3] < rsi_d.iloc[-3] and
            rsi_k.iloc[-2] < rsi_d.iloc[-2] and rsi_k.iloc[-1] > rsi_d.iloc[-1] and
            kl['macd'].iloc[-1] > 0):
        return 'up'
    elif (rsi.iloc[-1] > 60 and
          rsi_k.iloc[-1] > 80 and rsi_k.iloc[-3] > rsi_d.iloc[-3] and
          rsi_k.iloc[-2] > rsi_d.iloc[-2] and rsi_k.iloc[-1] < rsi_d.iloc[-1] and
          kl['macd'].iloc[-1] < 0):
        return 'down'
    elif rsi.iloc[-2] < 30 < rsi.iloc[-1] and kl['macd'].iloc[-1] > 0:
        return 'up'
    elif rsi.iloc[-2] > 70 > rsi.iloc[-1] and kl['macd'].iloc[-1] < 0:
        return 'down'
    else:
        return 'none'

# Function to get candles for the needed symbol
def klines(symbol):
    try:
        resp = pd.DataFrame(client.klines(symbol, '15m'))
        resp = resp.iloc[:, :6]
        resp.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
        resp = resp.set_index('Time')
        resp.index = pd.to_datetime(resp.index, unit='ms')
        resp = resp.astype(float)
        return resp
    except ClientError as error:
        print("Error occurred:", error)

# Main trading loop
trading_active = False  # Initialize trading status
while True:
    balance = get_trading_balance(trading_active)
    sleep(1)
    if balance is None:
        print('Cannot connect to API. Check IP, restrictions, or wait some time')
    if balance is not None:
        print("My balance is: ", balance, " USDT")

        signal = str_rsi_signal(symbol)
        if signal != 'none':
            print(f'Found {signal.upper()} signal for {symbol}')
            trading_active = True  # Activate trading
            try:
                open_order(symbol, 'buy' if signal == 'up' else 'sell', balance)
            except ClientError as error:
                print("Error occurred:", error)
        else:
            trading_active = False  # Deactivate trading

    print('Waiting for the next trading opportunity...')
    sleep(60)
