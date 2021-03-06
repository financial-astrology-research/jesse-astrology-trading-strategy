# # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# Make sure to read the docs about routes if you haven't already:
# https://docs.jesse.trade/docs/routes.html
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

from jesse.utils import anchor_timeframe

# trading routes
routes = [
    ('Binance', 'ADA-USDT', '15m', 'AstroStrategyMA'),
#     ('Binance', 'BAT-USDT', '15m', 'AstroStrategyMA'),
#     ('Binance', 'BNB-USDT', '15m', 'AstroStrategyMA'),
#     ('Binance', 'BTC-USDT', '15m', 'AstroStrategyMA'),
#     ('Binance', 'DASH-USDT', '15m', 'AstroStrategyMA'),
#     ('Binance', 'EOS-USDT', '15m', 'AstroStrategyMA'),
#     ('Binance', 'LINK-USDT', '15m', 'AstroStrategyMA'),
#     ('Binance', 'LTC-USDT', '15m', 'AstroStrategyMA'),
#     ('Binance', 'ZEC-USDT', '15m', 'AstroStrategyMA'),
#     ('Binance', 'ZRX-USDT', '15m', 'AstroStrategyMA'),
]

# in case your strategy requires extra candles, timeframes, ...
extra_candles = [
    ('Binance', 'ADA-USDT', anchor_timeframe('4h')),
    ('Binance', 'BAT-USDT', anchor_timeframe('4h')),
    ('Binance', 'BNB-USDT', anchor_timeframe('4h')),
    ('Binance', 'BTC-USDT', anchor_timeframe('4h')),
    ('Binance', 'DASH-USDT', anchor_timeframe('4h')),
    ('Binance', 'EOS-USDT', anchor_timeframe('4h')),
    ('Binance', 'LINK-USDT', anchor_timeframe('4h')),
    ('Binance', 'LTC-USDT', anchor_timeframe('4h')),
    ('Binance', 'ZEC-USDT', anchor_timeframe('4h')),
    ('Binance', 'ZRX-USDT', anchor_timeframe('4h')),
]
