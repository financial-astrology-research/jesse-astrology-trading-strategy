from jesse.config import config

config['app']['trading_mode'] = 'import-candles'

from jesse.services import db

from jesse.modes import import_candles_mode

symbols = ['ADA-USDT', 'BAT-USDT', 'BNB-USDT', 'BTC-USDT', 'DASH-USDT', 'EOS-USDT', 'LINK-USDT', 'LTC-USDT', 'ZEC-USDT', 'ZRX-USDT']
for symbol in symbols:
    print(symbol)
    import_candles_mode.run('Binance', symbol, '2017-01-01', skip_confirmation=True)

db.close_connection()