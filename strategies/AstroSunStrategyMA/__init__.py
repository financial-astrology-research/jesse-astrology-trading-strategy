from datetime import datetime
from pathlib import Path
import requests
from io import StringIO
import numpy as np

import jesse.indicators as ta
import pandas as pd
from jesse import utils
from jesse.strategies import Strategy, cached


class AstroSunStrategyMA(Strategy):

    def __init__(self):
        super().__init__()
        self.vars['attempts'] = {}

    def current_candle_date(self) -> datetime:
        return datetime.fromtimestamp(self.candles[-1, 0] / 1000).replace(hour=0, minute=0, second=0, microsecond=0)

    def current_candle_hour(self) -> int:
        return datetime.fromtimestamp(self.candles[-1, 0] / 1000).hour

    def load_astro_data(self):
        here = Path(__file__).parent
        # Dynamically determine the right csv from the self.symbol and shift the index 1 day.
        symbol_parts = self.symbol.split('-')
        astro_asset_indicator_path = here / './ml-{}-USD-daily-index.csv'.format(symbol_parts[0])
        self.vars['astro_asset'] = pd.read_csv(astro_asset_indicator_path, parse_dates=['Date'], index_col=0)

        historical_url = "http://www.sidc.be/silso/INFO/sndtotcsv.php"
        this_month_url = "http://www.sidc.be/silso/DATA/EISN/EISN_current.csv"
        historical_sunspots = requests.get(historical_url).text
        this_month_sunspots = requests.get(this_month_url).text
        historical_sunspots = pd.read_csv(StringIO(historical_sunspots), sep=";", header=None, names=["year", "month", "day", "fraction", "total", "stdev", "observations", "indicator"], parse_dates=[['year', 'month', "day"]], index_col="year_month_day", usecols=["year", "month", "day", "total"])
        historical_sunspots[historical_sunspots < 0] = np.nan
        historical_sunspots = historical_sunspots.loc["2000-01-01":]
        this_month_sunspots = pd.read_csv(StringIO(this_month_sunspots), sep=",", header=None, names=["year", "month", "day", "fraction", "total", "stdev", "observations", "indicator", "empty"], parse_dates=[['year', 'month', "day"]], index_col="year_month_day", usecols=["year", "month", "day", "total"])
        this_month_sunspots[this_month_sunspots < 0] = np.nan
        merged = historical_sunspots.append(this_month_sunspots)
        log_diff = merged.apply(np.log).diff()
        self.vars['sunspots'] = log_diff.dropna()

    def before(self):
        if self.index == 0:
            self.load_astro_data()

        # Filter past data.
        candle_date = self.current_candle_date()
        self.vars['astro_asset'] = self.vars['astro_asset'].loc[candle_date:]
        self.vars['sunspots'] = self.vars['sunspots'].iloc[self.vars['sunspots'].index.get_loc(self.candle_date, method='nearest') - 240:]
        self.vars['sunspots']['slow_mean'] = self.vars['sunspots'].total.rolling('240D').mean()
        self.vars['sunspots']['fast_mean'] = self.vars['sunspots'].total.rolling('30D').mean()

    def increase_entry_attempt(self):
        # Init date attempts counter.
        if self.candle_date not in self.vars['attempts']:
            self.vars['attempts'][self.candle_date] = 0

        # Count the entry attempt.
        self.vars['attempts'][self.candle_date] += 1

    @property
    @cached
    def candle_date(self):
        return str(datetime.fromtimestamp(self.current_candle[0] / 1000).date())

    @property
    def are_attempts_exceeded(self) -> bool:
        if self.candle_date not in self.vars['attempts']:
            return False

        # Limit to N entry attempt per day.
        if self.vars['attempts'][self.candle_date] >= self.hp['max_day_attempts']:
            return True

    def should_long(self) -> bool:
        if self.is_bull_astro_signal and self.is_bull_trend_start and self.sunspots_long and not self.are_attempts_exceeded:
            self.increase_entry_attempt()
            return True

        return False

    def should_short(self) -> bool:
        if self.is_bear_astro_signal and self.is_bear_trend_start and self.sunspots_short and not self.are_attempts_exceeded:
            self.increase_entry_attempt()
            return True

        return False

    def filters(self):
        return []

    def go_long(self):
        entry = self.price + self.entry_atr * self.hp['entry_stop_atr_rate']
        self.vars['entry'] = entry
        stop = self.stop_loss_long
        position_size = self.position_size(entry, stop)
        self.buy = position_size, entry
        self.stop_loss = position_size, stop
        take_profit = self.take_profit_long(entry)
        self.take_profit = position_size, take_profit

    def go_short(self):
        entry = self.price - self.entry_atr * self.hp['entry_stop_atr_rate']
        if entry < 0:
            entry = self.price * 0.95
        self.vars['entry'] = entry
        stop = self.stop_loss_short
        position_size = self.position_size(entry, stop)
        take_profit = self.take_profit_short(entry)
        self.sell = position_size, entry
        self.stop_loss = position_size, stop
        self.take_profit = position_size, take_profit

    def should_cancel(self) -> bool:
        return True

    def update_position(self):
        self.exit_on_reversal()
        self.update_trailing_stop()

    def exit_on_reversal(self):
        if (self.is_long and self.is_bear_trend_start) or (self.is_short and self.is_bull_trend_start):
            self.liquidate()

    # Move the SL following the trend.
    def update_trailing_stop(self):
        if self.position.pnl <= 0:
            return

        # Only move it if we are still in a trend
        if (self.is_long and self.price > self.fast_ma[-1] and self.adx > 25):
            stop = self.price - self.stop_atr * self.hp['trailing_stop_atr_rate']
            if stop >= self.vars['entry'] or stop < 0:
                stop = self.price * 0.95
            if stop < self.price:
                self.stop_loss = self.position.qty, stop

        if (self.is_short and self.price < self.fast_ma[-1] and self.adx > 25):
            stop = self.price + self.stop_atr * self.hp['trailing_stop_atr_rate']
            if stop > self.price:
                self.stop_loss = self.position.qty, stop

    ################################################################
    # # # # # # # # # # # # # indicators # # # # # # # # # # # # # #
    ################################################################

    @property
    @cached
    def sunspots_long(self):
        return self.current_sunspot.fast_mean > self.current_sunspot.slow_mean

    @property
    @cached
    def sunspots_short(self):
        return self.current_sunspot.fast_mean < self.current_sunspot.slow_mean

    @property
    @cached
    def current_sunspot(self):
        return self.vars['sunspots'].iloc[self.vars['sunspots'].index.get_loc(self.candle_date, method='nearest')]

    @property
    @cached
    def is_bull_trend_start(self) -> bool:
        result = utils.crossed(self.fast_ma, self.slow_ma, 'above')
        return result

    @property
    @cached
    def is_bear_trend_start(self) -> bool:
        result = utils.crossed(self.fast_ma, self.slow_ma, 'below')
        return result

    @property
    @cached
    def adx(self):
        return ta.adx(self.candles)

    @property
    @cached
    def stop_atr(self):
        return ta.atr(self.candles, period=self.hp['stop_atr_period'])

    @property
    @cached
    def entry_atr(self):
        return ta.atr(self.candles, period=self.hp['entry_atr_period'])

    @property
    @cached
    def take_profit_atr(self):
        return ta.atr(self.candles, period=self.hp['take_profit_atr_period'])

    def take_profit_short(self, price):
        take_profit = price - (self.take_profit_atr * self.hp['take_profit_atr_rate'])
        if take_profit < 0:
            take_profit = self.vars['entry'] * 0.95
        return take_profit

    def take_profit_long(self, price):
        take_profit = price + (self.take_profit_atr * self.hp['take_profit_atr_rate'])
        return take_profit

    @property
    def stop_loss_long(self):
        stop = self.price - self.stop_atr * self.hp['stop_loss_atr_rate']
        if stop >= self.vars['entry'] or stop < 0:
            stop = self.vars['entry'] * 0.95
        return stop

    @property
    def stop_loss_short(self):
        stop = self.price + self.stop_atr * self.hp['stop_loss_atr_rate']
        if stop <= self.vars['entry']:
            stop = self.vars['entry'] * 1.05
        return stop


    @property
    @cached
    def fast_ma(self):
        if self.hp['ma_source_fast'] == 0:
            source = "close"
        elif self.hp['ma_source_fast'] == 1:
            source = "high"
        elif self.hp['ma_source_fast'] == 2:
            source = "low"
        elif self.hp['ma_source_fast'] == 3:
            source = "open"
        elif self.hp['ma_source_fast'] == 4:
            source = "hl2"
        elif self.hp['ma_source_fast'] == 5:
            source = "hlc3"
        elif self.hp['ma_source_fast'] == 6:
            source = "ohlc4"

        period = int(self.hp['slow_ma_period'] / self.hp['fast_ma_devider'])
        return ta.sma(self.candles[-240:], period = period, source_type = source, sequential=True)

    @property
    @cached
    def slow_ma(self):
        if self.hp['ma_source_slow'] == 0:
          source = "close"
        elif self.hp['ma_source_slow'] == 1:
          source = "high"
        elif self.hp['ma_source_slow'] == 2:
          source = "low"
        elif self.hp['ma_source_slow'] == 3:
          source = "open"
        elif self.hp['ma_source_slow'] == 4:
          source = "hl2"
        elif self.hp['ma_source_slow'] == 5:
          source = "hlc3"
        elif self.hp['ma_source_slow'] == 6:
          source = "ohlc4"
        return ta.sma(self.candles[-240:], period = self.hp['slow_ma_period'], source_type = source, sequential=True)

    def astro_indicator_day_index(self):
        candle_hour = self.current_candle_hour()
        # Use next day signal after shift hour due the fact that astro models are train with
        # mid price (OHLC / 4) so the price action predicted by next day is lagged.
        day_index = 0
        if candle_hour >= self.hp['astro_signal_shift_hour']:
            day_index = 1
        return day_index

    def astro_signal_period_decision(self, astro_indicator):
        start_index = self.astro_indicator_day_index()
        # Select next N signals in order to determine that there is astro energy trend.
        end_index = start_index + self.hp['astro_signal_trend_period']
        signals = astro_indicator.iloc[start_index:end_index]
        count_signals = len(signals)
        buy_signals = signals[signals['Action'] == 'buy']
        sell_signals = signals[signals['Action'] == 'sell']

        if (count_signals == len(buy_signals)):
            return 'buy'
        elif (count_signals == len(sell_signals)):
            return 'sell'

        return 'neutral'


    def astro_asset_signal(self):
        return self.astro_signal_period_decision(self.vars['astro_asset'])

    @property
    def is_bull_astro_signal(self) -> bool:
        if (self.hp['enable_astro_signal'] == 1):
            return self.astro_asset_signal() == 'buy'
        return True

    @property
    def is_bear_astro_signal(self) -> bool:
        if (self.hp['enable_astro_signal'] == 1):
            return self.astro_asset_signal() == 'sell'
        return True

    def position_size(self, entry, stop):
        risk_qty = utils.risk_to_qty(self.available_margin, 30, entry, stop, fee_rate=self.fee_rate)
        # never risk more than 30%
        max_qty = utils.size_to_qty(0.30 * self.available_margin, entry, fee_rate=self.fee_rate)
        qty = min(risk_qty, max_qty)
        return qty

    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Genetic
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    def hyperparameters(self):
        return [
            {'name': 'entry_atr_period', 'type': int, 'min': 10, 'max': 50, 'default': 38},
            {'name': 'entry_stop_atr_rate', 'type': float, 'min': 0.1, 'max': 1.0, 'default': 0.168354},
            {'name': 'stop_atr_period', 'type': int, 'min': 10, 'max': 50, 'default': 28},
            {'name': 'stop_loss_atr_rate', 'type': float, 'min': 1, 'max': 5, 'default': 4.74684},
            {'name': 'trailing_stop_atr_rate', 'type': float, 'min': 1, 'max': 20, 'default': 14.4684},
            {'name': 'take_profit_atr_period', 'type': int, 'min': 10, 'max': 50, 'default': 32},
            {'name': 'take_profit_atr_rate', 'type': int, 'min': 2, 'max': 10, 'default': 2},
            {'name': 'max_day_attempts', 'type': int, 'min': 1, 'max': 5, 'default': 4},
            {'name': 'astro_signal_trend_period', 'type': int, 'min': 1, 'max': 5, 'default': 2},
            {'name': 'astro_signal_shift_hour', 'type': int, 'min': 0, 'max': 23, 'default': 4},
            {'name': 'enable_astro_signal', 'type': int, 'min': 0, 'max': 1, 'default': 1},
            {'name': 'slow_ma_period', 'type': int, 'min': 50, 'max': 100, 'default': 62},
            {'name': 'fast_ma_devider', 'type': float, 'min': 2, 'max': 10, 'default': 2},
            {'name': 'ma_source_slow', 'type': int, 'min': 0, 'max': 6, 'default': 0},
            {'name': 'ma_source_fast', 'type': int, 'min': 0, 'max': 6, 'default': 0},
        ]
