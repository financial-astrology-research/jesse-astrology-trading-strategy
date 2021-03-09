# # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# Make sure to read the docs about routes if you haven't already:
# https://docs.jesse.trade/docs/routes.html
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

from jesse.utils import anchor_timeframe

# trading routes
routes = [
    ('Binance', 'ADA-USDT', '15m', 'AstroStrategyMA'),
    ('Binance', 'BAT-USDT', '15m', 'AstroStrategyMA'),
    ('Binance', 'BNB-USDT', '15m', 'AstroStrategyMA'),
    ('Binance', 'BTC-USDT', '15m', 'AstroStrategyMA'),
    # ('Binance', 'DASH-USDT', '15m', 'AstroStrategyMA'),
    # ('Binance', 'EOS-USDT', '15m', 'AstroStrategyMA'),
    ('Binance', 'LINK-USDT', '15m', 'AstroStrategyMA'),
    # ('Binance', 'LTC-USDT', '15m', 'AstroStrategyMA'),
    # ('Binance', 'ZEC-USDT', '15m', 'AstroStrategyMA'),
    # ('Binance', 'ZRX-USDT', '15m', 'AstroStrategyMA'),
]

# in case your strategy requires extra candles, timeframes, ...
extra_candles = [
    ('Binance', 'ADA-USDT', '1D'),
    ('Binance', 'BAT-USDT', '1D'),
    ('Binance', 'BNB-USDT', '1D'),
    ('Binance', 'BTC-USDT', '1D'),
    # ('Binance', 'DASH-USDT', '1D'),
    # ('Binance', 'EOS-USDT', '1D'),
    ('Binance', 'LINK-USDT', '1D'),
    # ('Binance', 'LTC-USDT', '1D'),
    # ('Binance', 'ZEC-USDT', '1D'),
    # ('Binance', 'ZRX-USDT', '1D'),
]
