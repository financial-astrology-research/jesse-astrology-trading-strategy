from datetime import datetime
from pathlib import Path
from pprint import pprint

import jesse.indicators as ta
import numpy as np
import pandas as pd
from jesse import utils
from jesse.strategies import Strategy


class AstroStrategyMA(Strategy):

    def __init__(self):
        super().__init__()
        self.vars['attempts'] = {}

    def current_candle_date(self) -> datetime:
        return datetime.fromtimestamp(self.candles[-1, 0] / 1000).replace(hour=0, minute=0, second=0, microsecond=0)

    def current_candle_hour(self) -> datetime:
        return datetime.fromtimestamp(self.candles[-1, 0] / 1000).hour

    def load_astro_data(self):
        here = Path(__file__).parent
        # Dynamically determine the right csv from the self.symbol and shift the index 1 day.
        symbol_parts = self.symbol.split('-')
        astro_asset_indicator_path = here / './ml-{}-USD-daily-index.csv'.format(symbol_parts[0])
        self.vars['astro_asset'] = pd.read_csv(astro_asset_indicator_path, parse_dates=['Date'], index_col=0)
        astro_sector_indicator_path = here / './ml-all-daily-index.csv'
        self.vars['astro_sector'] = pd.read_csv(astro_sector_indicator_path, parse_dates=['Date'], index_col=0)
        moon_phase_indicator_path = here / './daily_moon_phase_positions.csv'
        self.vars['astro_moon_phase'] = pd.read_csv(moon_phase_indicator_path, parse_dates=['Date'], index_col=0)
        planets_position_indicator_path = here / './daily_planets_positions_long.csv'
        planets_positions = pd.read_csv(planets_position_indicator_path, parse_dates=['Date'], index_col=0)
        self.vars['moon_position'] = planets_positions[planets_positions['pID'] == 'MO']

    def before(self):
        if self.index == 0:
            self.load_astro_data()

        # Filter past data.
        candle_date = self.current_candle_date()
        self.vars['astro_asset'] = self.vars['astro_asset'].loc[candle_date:]
        self.vars['astro_sector'] = self.vars['astro_sector'].loc[candle_date:]
        self.vars['astro_moon_phase'] = self.vars['astro_moon_phase'].loc[candle_date:]
        self.vars['moon_position'] = self.vars['moon_position'].loc[candle_date:]

    def increase_entry_attempt(self):
        candle_date = str(datetime.fromtimestamp(self.current_candle[0] / 1000).date())
        # Init date attempts counter.
        if candle_date not in self.vars['attempts']:
            self.vars['attempts'][candle_date] = 0

        # Count the entry attempt.
        self.vars['attempts'][candle_date] += 1

    @property
    def are_attempts_exceeded(self) -> bool:
        candle_date = str(datetime.fromtimestamp(self.current_candle[0] / 1000).date())

        if candle_date not in self.vars['attempts']:
            return False

        # Limit to N entry attempt per day.
        if self.vars['attempts'][candle_date] >= self.hp['max_day_attempts']:
            return True

    def should_long(self) -> bool:
        if self.is_bull_astro_signal and self.is_bull_trend_start and not self.are_attempts_exceeded:
            self.increase_entry_attempt()
            return True

        return False

    def should_short(self) -> bool:
        if self.is_bear_astro_signal and self.is_bear_trend_start and not self.are_attempts_exceeded:
            self.increase_entry_attempt()
            return True

        return False

    def filters(self):
        # candle_date = datetime.fromtimestamp(self.current_candle[0] / 1000)
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
        self.vars['entry'] = entry
        stop = self.stop_loss_short
        position_size = self.position_size(entry, stop)
        take_profit = self.take_profit_short(entry)
        self.sell = position_size, entry
        self.stop_loss = position_size, stop
        self.take_profit = position_size, take_profit

    def should_cancel(self) -> bool:
        return False

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
        if (self.is_long and self.price > self.fast_ma[-1]):
            stop = self.price - self.atr * self.hp['trailing_stop_atr_rate']
            if stop < self.price:
                self.stop_loss = self.position.qty, stop

        if (self.is_short and self.price < self.fast_ma[-1]):
            stop = self.price + self.atr * self.hp['trailing_stop_atr_rate']
            if stop > self.price:
                self.stop_loss = self.position.qty, stop

    ################################################################
    # # # # # # # # # # # # # indicators # # # # # # # # # # # # # #
    ################################################################

    def position_price(self, price = -1):
        if price == -1:
            price = self.price
        return price

    def take_profit_short(self, price=-1):
        take_profit = self.position_price(price) - (self.daily_atr_average * self.hp['take_profit_atr_rate'])
        return take_profit

    def take_profit_long(self, price=-1):
        take_profit = self.position_price(price) + (self.daily_atr_average * self.hp['take_profit_atr_rate'])
        return take_profit

    @property
    def is_bull_trend_start(self) -> bool:
        result = utils.crossed(self.fast_ma, self.slow_ma, 'above')
        return result

    @property
    def is_bear_trend_start(self) -> bool:
        result = utils.crossed(self.fast_ma, self.slow_ma, 'below')
        return result

    @property
    def atr(self):
        return ta.atr(self.candles, period=self.hp['atr_period'])

    @property
    def entry_atr(self):
        return ta.atr(self.candles, period=self.hp['entry_atr_period'])

    @property
    def stop_loss_long(self):
        exit = self.price - self.atr * self.hp['stop_loss_atr_rate']
        if exit >= self.vars['entry']:
            exit = self.vars['entry'] * 0.98
        return exit

    @property
    def stop_loss_short(self):
        exit = self.price + self.atr * self.hp['stop_loss_atr_rate']
        if exit <= self.vars['entry']:
            exit = self.vars['entry'] * 1.02
        return exit

    @property
    def daily_candles(self):
        return self.get_candles(self.exchange, self.symbol, '1D')

    @property
    def daily_atr_average(self):
        daily_atr = ta.atr(self.daily_candles, self.hp['atr_take_profit_period'])
        return daily_atr

    @property
    def fast_ma(self):
        return ta.sma(self.candles, self.hp['fast_ma_period'], 'close', True)

    @property
    def slow_ma(self):
        return ta.sma(self.candles, self.hp['slow_ma_period'], 'close', True)

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

    # The astro sector signal don't reduce the astro ML asset signal errors, not used.
    def astro_sector_signal(self):
        index = self.astro_indicator_day_index()
        signal = self.vars['astro_sector'].iloc[index]
        return signal['Action']

    def astro_asset_signal(self):
        return self.astro_signal_period_decision(self.vars['astro_asset'])

    # The moon phase filter don't reduce the astro ML asset signal errors, not used.
    def moon_phase(self):
        index = self.astro_indicator_day_index()
        signal = self.vars['astro_moon_phase'].iloc[index]
        return signal['MoonPhaseID']

    # The moon phase zodsign filter don't reduce the astro ML asset signal errors, not used.
    def moon_phase_zodsign(self):
        index = self.astro_indicator_day_index()
        signal = self.vars['astro_moon_phase'].iloc[index]
        return signal['ZodSignID']

    def is_air_zodsign(self, zodsign):
        return zodsign in ['GEM', 'LIB', 'AQU']

    def is_fire_zodsign(self, zodsign):
        return zodsign in ['ARI', 'LEO', 'SAG']

    def is_water_zodsign(self, zodsign):
        return zodsign in ['CAN', 'SCO', 'PIS']

    def is_earth_zodsign(self, zodsign):
        return zodsign in ['TAU', 'VIR', 'CAP']

    def is_bull_moon_phase_zodsign(self):
        phase_zodsign = self.moon_phase_zodsign()
        return self.is_air_zodsign(phase_zodsign) \
            or self.is_earth_zodsign(phase_zodsign) \
            or self.is_fire_zodsign(phase_zodsign)

    def moon_zodsign(self):
        index = self.astro_indicator_day_index()
        signal = self.vars['moon_position'].iloc[index]
        return signal['ZodSignID']

    def is_bull_moon_zodsign(self):
        moon_zodsign = self.moon_zodsign()
        return self.is_air_zodsign(moon_zodsign) \
            or self.is_water_zodsign(moon_zodsign) \

    def is_bear_moon_zodsign(self):
        moon_zodsign = self.moon_zodsign()
        return self.is_earth_zodsign(moon_zodsign) \
            or self.is_fire_zodsign(moon_zodsign)

    @property
    def is_bull_astro_signal(self) -> bool:
        return self.is_bull_moon_zodsign() and self.astro_asset_signal() == 'buy'

    @property
    def is_bear_astro_signal(self) -> bool:
        return self.is_bear_moon_zodsign() and self.astro_asset_signal() == 'sell'

    def position_size(self, entry, stop):
        max_qty = utils.size_to_qty(self.capital / self.hp['capital_slices'], entry, precision=6, fee_rate=self.fee_rate)
        return max_qty

    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Genetic
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    def hyperparameters(self):
        return [
            {'name': 'entry_stop_atr_rate', 'type': float, 'min': 0.1, 'max': 1.0, 'default': 0.1},
            {'name': 'trailing_stop_atr_rate', 'type': float, 'min': 10, 'max': 20, 'default': 15},
            {'name': 'stop_loss_atr_rate', 'type': float, 'min': 1, 'max': 4, 'default': 2},
            {'name': 'take_profit_atr_rate', 'type': int, 'min': 2, 'max': 10, 'default': 3},
            {'name': 'atr_period', 'type': int, 'min': 5, 'max': 40, 'default': 30},
            {'name': 'entry_atr_period', 'type': int, 'min': 5, 'max': 20, 'default': 15},
            {'name': 'atr_take_profit_period', 'type': int, 'min': 7, 'max': 21, 'default': 10},
            {'name': 'fast_ma_period', 'type': int, 'min': 20, 'max': 40, 'default': 30},
            {'name': 'slow_ma_period', 'type': int, 'min': 40, 'max': 80, 'default': 60},
            {'name': 'max_day_attempts', 'type': int, 'min': 1, 'max': 3, 'default': 1},
            {'name': 'astro_signal_trend_period', 'type': int, 'min': 1, 'max': 5, 'default': 2},
            {'name': 'astro_signal_shift_hour', 'type': int, 'min': 0, 'max': 23, 'default': 9},
            {'name': 'capital_slices', 'type': int, 'min': 2, 'max': 20, 'default': 10},
        ]
