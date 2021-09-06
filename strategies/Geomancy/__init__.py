import jesse.indicators as ta
import numpy as np
from jesse import utils
from jesse.strategies import Strategy, cached


class Geomancy(Strategy):

    def before(self):
        self.generate_all_symbols()

    def should_long(self) -> bool:
        return self.signal == 1

    def should_short(self) -> bool:
        return self.signal == -1

    def go_long(self):
        entry = self.price + self.entry_atr * self.hp['entry_stop_atr_rate']
        stop = self.stop_loss_long(entry)
        take_profit = self.take_profit_long(entry)
        qty = self.position_size(entry, stop)
        self.buy = qty, entry
        self.take_profit = qty, take_profit
        self.stop_loss = qty, stop

    def go_short(self):
        entry = self.price - self.entry_atr * self.hp['entry_stop_atr_rate']
        # sometimes an extreme ATR value can lead to a negative price
        if entry <= 0:
            entry = self.price
        stop = self.stop_loss_short(entry)
        take_profit = self.take_profit_short(entry)
        qty = self.position_size(entry, stop)
        self.sell = qty, entry
        self.take_profit = qty, take_profit
        self.stop_loss = qty, stop

    def update_position(self):
        if self.is_long and self.signal == -1:
            self.liquidate()

        if self.is_short and self.signal == 1:
            self.liquidate()

    def should_cancel(self) -> bool:
        return True

    def take_profit_long(self, entry):
        take_profit = entry + self.take_profit_atr * self.hp['take_profit_atr_rate']
        if take_profit <= entry:
            # fallback to donchian channel
            take_profit = self.dc.upperband
        if take_profit <= entry:
            take_profit = entry * 1.1
        return take_profit

    def take_profit_short(self, entry):
        take_profit = entry - self.take_profit_atr * self.hp['take_profit_atr_rate']
        # sometimes an extreme ATR value can lead to a negative price
        if take_profit <= 0 or take_profit >= entry:
            # fallback to donchian channel
            take_profit = self.dc.lowerband
        if take_profit >= entry:
            take_profit = entry * 0.9
        return take_profit

    def stop_loss_long(self, entry):
        exit = entry - self.stop_atr * self.hp['stop_loss_atr_rate']
        # sometimes an extreme ATR value can lead to a negative price
        if exit <= 0 or exit >= entry:
            # fallback to donchian channel
            exit = self.dc.lowerband
        if exit >= entry:
            exit = entry * 0.9
        return exit

    def stop_loss_short(self, entry):
        exit = entry + (self.stop_atr * self.hp['stop_loss_atr_rate'])
        if exit <= entry:
            # fallback to donchian channel
            exit = self.dc.upperband
        if exit <= entry:
            exit = entry * 1.1
        return exit

    def position_size(self, entry, stop):
        return utils.risk_to_qty(
            self.capital,
            self.hp['risk'],
            entry,
            stop,
            precision=6,
            fee_rate=self.fee_rate,
        )


    ################################################################
    # # # # # # # # # # # # # indicators # # # # # # # # # # # # # #
    ################################################################

    def generate_symbol_from_price(self, candles):
        symbol = []
        for candle in candles[:, 2]:
            if (self.sum_digits(candle) % 2) == 0:
                # even
                symbol.append(0)
            else:
                # odd
                symbol.append(1)
        return symbol

    def generate_symbol_from_color(self, candles):
        symbol = []
        # maybe reverse order reversed(candles)
        for candle in candles:
            open = candle[1]
            close = candle[2]
            high = candle[3]
            low = candle[4]
            if close < open or (close == open and low < high):
                # even
                # green candle
                symbol.append(0)
            else:
                # odd
                # red candle
                symbol.append(1)
        return symbol

    def symbol_name(self, symbol):
        # 0 = even || 1 = odd
        if symbol == [0, 0, 0, 0]:
            name = "Populus"
        elif symbol == [1, 1, 1, 1]:
            name = "Via"
        elif symbol == [1, 1, 1, 0]:
            name = "Cauda Draconis"
        elif symbol == [0, 1, 1, 1]:
            name = "Caput Draconis"
        elif symbol == [1, 1, 0, 1]:
            name = "Puer"
        elif symbol == [1, 0, 1, 1]:
            name = "Puella"
        elif symbol == [1, 1, 0, 0]:
            name = "Fortuna Minor"
        elif symbol == [0, 0, 1, 1]:
            name = "Fortuna Major"
        elif symbol == [0, 1, 1, 0]:
            name = "Conjunctio"
        elif symbol == [1, 0, 0, 1]:
            name = "Carcer"
        elif symbol == [0, 1, 0, 1]:
            name = "Acquisitio"
        elif symbol == [1, 0, 1, 0]:
            name = "Amissio"
        elif symbol == [1, 0, 0, 0]:
            name = "Laetitia"
        elif symbol == [0, 0, 0, 1]:
            name = "Tristitia"
        elif symbol == [0, 1, 0, 0]:
            name = "Rubeus"
        elif symbol == [0, 0, 1, 0]:
            name = "Albus"
        else:
            raise ValueError(f"Symbol {symbol} not matched with name.")
        return name

    @property
    def yin_or_yang(self):
        name = self.symbol_name(self.vars['symbols'][self.vars['part_of_fortune'] - 1])
        if name in ["Puer", "Amissio", "Albus", "Populus", "Fortuna Major", "Conjunctio", "Tristitia",
                    "Cauda Draconis"]:
            return -1
        elif name in ["Puella", "Acquisitio", "Rubeus", "Via", "Fortuna Minor", "Carcer", "Laetitia", "Caput Draconis"]:
            return 1
        else:
            raise ValueError(f"Yin and Yang of {name} not matched.")

    def meaning(self, name: str, house: int):
        # http://www.erwinhessle.com/writings/geofig.php
        effects = {
            "Via": [-1, -1, 0, 1, 1, 1, -1, 1, -1, 0, 1, 1, 1],
            "Cauda Draconis": [0, -1, -1, -1, 1, -1, 1, -1, -1, -1, -1, -1, 1],
            "Puer": [-1, 0, 1, 1, -1, 1, 0, -1, -1, -1, -1, 0, 1],
            "Puella": [1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1],
            "Caput Draconis": [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1],
            "Fortuna Minor": [1, 1, 1, 1, -1, 1, 0, -1, -1, 1, 1, 1, 1],
            "Amissio": [0, -1, -1, -1, -1, -1, -1, 0, 1, -1, -1, -1, -1],
            "Carcer": [-1, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1],
            "Conjunctio": [0, 0, 1, 1, 1, 0, 1, 1, -1, 1, 0, 1, 0],
            "Acquisitio": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1],
            "Fortuna Major": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            "Laetitia": [1, 1, -1, -1, 1, 1, -1, 0, -1, 1, 1, 1, -1],
            "Rubeus": [0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            "Albus": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            "Tristitia": [-1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            "Populus": [0, 1, 1, 1, 1, 1, 1, 1, -1, 0, 1, 1, -1],
        }

        return effects.get(name)[house]

    @property
    def jugdge_meaning(self):
        # http://www.erwinhessle.com/writings/geofig.php

        name_judge = self.symbol_name(self.vars['symbols'][14])
        name_wittnes_1 = self.symbol_name(self.vars['symbols'][12])
        name_wittnes_2 = self.symbol_name(self.vars['symbols'][13])
        # only related to money see hanndbook of geomancy
        effects = {
            "Via": {"Populus+Via": -1, "Via+Populus": -1, "Fortuna Major+Fortuna Minor": 0,
                    "Fortuna Minor+Fortuna Major": 0, "Conjunctio+Carcer": 0, "Carcer+Conjunctio": 0, "Acquisitio+Amissio":0,  "Amissio+Acquisitio": 0},
        "Cauda Draconis": {"Caput Draconis+Carcer": 1, "Puer+Fortuna Major": -1, "Cauda Draconis+Populus": -1,
                    "Puella+Acquisitio": 1, "Rubeus+Amissio": 0, "Albus+Fortuna Major": 0, "Laetitia+Conjunctio":1,  "Tristitia+Via": -1},
        "Puer": {"Puella+Conjunctio": 1, "Albus+Via": 0, "Puer+Populus": -1,
                    "Rubeus+Carcer": -1, "Caput Draconis+Amissio": 0, "Cauda Draconis+Fortuna Major": -1, "Tristitia+Acquisitio": 0,  "Laetitia+Fortuna Minor": -1},
        "Puella": {"Puer+Conjunctio": 0, "Laetitia+Fortuna Major": 1, "Puella+Populus": 1,
                    "Albus+Carcer": 1, "Rubeus+Via": 0, "Tristitia+Amissio": 0, "Caput Draconis+Fortuna Minor": 1,  "Cauda Draconis+Acquisitio": -1},
        "Caput Draconis": {"Cauda Draconis+Carcer": -1, "Albus+Acquisitio": 1, "Caput Draconis+Populus": 1,
                    "Tristitia+Conjunctio": 0, "Rubeus+Fortuna Major": 0, "Laetitia+Via": 1, "Puer+Amissio": -1,  "Puella+Fortuna Minor": 1},
        "Fortuna Minor":  {"Fortuna Major+Via": 1, "Conjunctio+Amissio": 0, "Fortuna Minor+Populus": 0,
                    "Acquisitio+Carcer": 1, "Amissio+Conjunctio": -1, "Via+Fortuna Major": -1, "Populus+Fortuna Minor": 1,  "Carcer+Acquisitio": 0},
        "Amissio":  {"Acquisitio+Via": 1, "Fortuna Major+Carcer": 0, "Amissio+Populus": -1,
                    "Fortuna Minor+Conjunctio": 0, "Populus+Amissio": 0, "Via+Acquisitio": -1, "Conjunctio+Fortuna Minor": -1,  "Carcer+Fortuna Major": 0},
        "Carcer": {"Populus+Carcer": 1, "Via+Conjunctio": -1, "Acquisitio+Fortuna Minor": 1,
                    "Amissio+Fortuna Major": 0, "Fortuna Major+Amissio": 0, "Fortuna Minor+Acquisitio": 0, "Carcer+Populus": -1,  "Conjunctio+Via": 0},
        "Conjunctio": {"Acquisitio+Fortuna Major": 1, "Amissio+Fortuna Minor": 0, "Conjunctio+Populus": 0,
                    "Populus+Conjunctio": 1, "Via+Carcer": -1, "Fortuna Major+Acquisitio": 1, "Fortuna Minor+Amissio": 0,  "Carcer+Via": 0},
        "Acquisitio": {"Populus+Acquisitio": 0, "Via+Amissio": 0, "Acquisitio+Populus": 1,
                    "Amissio+Via": -1, "Fortuna Major+Conjunctio": 1, "Fortuna Minor+Carcer": 0, "Carcer+Fortuna Minor": 0,  "Conjunctio+Fortuna Major": 1},
        "Fortuna Major":  {"Fortuna Major+Populus": 1, "Amissio+Carcer": -1, "Acquisitio+Conjunctio": 1,
                    "Conjunctio+Acquisitio": 0, "Fortuna Minor+Via": 0, "Carcer+Amissio": 0, "Populus+Fortuna Major": 1,  "Via+Fortuna Minor": 0},
        "Laetitia": {"Caput Draconis+Via": 1, "Cauda Draconis+Conjunctio": -1, "Albus+Amissio": 0,
                    "Rubeus+Fortuna Minor": 0, "Puella+Fortuna Major": 1, "Puer+Acquisitio": -1, "Tristitia+Carcer": 0,  "Laetitia+Populus": 0},
        "Rubeus": {"Laetitia+Fortuna Minor": 1, "Tristitia+Acquisitio": 0, "Albus+Conjunctio": 0,
                    "Caput Draconis+Fortuna Major": 1, "Cauda Draconis+Amissio": -1, "Puella+Via": 1, "Puer+Carcer": -1,  "Rubeus+Populus": -1},
        "Albus": {"Puer+Via": -1, "Puella+Carcer": 1, "Rubeus+Conjunctio": 0,
                    "Laetitia+Amissio": 1, "Tristitia+Fortuna Major": 0, "Caput Draconis+Acquisitio": 1, "Cauda Draconis+Fortuna Minor": -1,  "Albus+Populus": 0},
        "Tristitia": {"Tristitia+Populus": 0, "Albus+Fortuna Major": 0, "Rubeus+Acquisitio": -1,
                    "Laetitia+Carcer": 0, "Puer+Fortuna Minor": -1, "Puella+Amissio": 0, "Caput Draconis+Conjunctio": 1,  "Cauda Draconis+Via": -1},
        "Populus": {"Populus+Populus": 0, "Fortuna Major+Fortuna Major": 1, "Fortuna Minor+Fortuna Minor": 1,
                    "Via+Via": -1, "Conjunctio+Conjunctio": 0, "Carcer+Carcer": -1, "Acquisitio+Acquisitio": 0,  "Amissio+Amissio": 1},
        }

        return effects.get(name_wittnes_2).get(f"{name_wittnes_1}+{name_judge}")

    @property
    def signal(self):
        name_fortune = self.symbol_name(self.vars['symbols'][self.vars['part_of_fortune'] - 1])
        # 2nd house = money / Second Daughter
        name_2nd = self.symbol_name(self.vars['symbols'][5])
        name_judge = self.symbol_name(self.vars['symbols'][14])
        name_reconciler = self.symbol_name(self.vars['symbols'][15])

        # always check in 2n house meanings because its related to money.
        # part of fortune tells us the house to look in

        meaning_fortune = self.meaning(name_fortune, self.vars['part_of_fortune'] - 1)
        meaning_2nd = self.meaning(name_2nd, 1)
        meaning_reconciler = self.meaning(name_reconciler, 1)
        meaning_judge_simple = self.meaning(name_judge, 1)

        if meaning_fortune == 1:
            return 1

        elif meaning_fortune == -1:
            return -1

        else:

            if self.jugdge_meaning == 1:
                return 1
            elif self.jugdge_meaning == -1:
                return -1
            else:
                # judge uncertain
                if meaning_reconciler == 1:
                    return 1
                elif meaning_reconciler == -1:
                    return -1
        return 0

    def generate_symbol(self, candles):
        if self.hp['symbol_method'] == 0:
            return self.generate_symbol_from_color(candles)
        else:
            return self.generate_symbol_from_price(candles)

    def generate_all_symbols(self):
        mother_1 = self.generate_symbol(self.candles[-16:-12, :])
        mother_2 = self.generate_symbol(self.candles[-12:-8, :])
        mother_3 = self.generate_symbol(self.candles[-8:-4, :])
        mother_4 = self.generate_symbol(self.candles[-4:, :])

        dautghers = np.column_stack((np.array(mother_1), np.array(mother_2), np.array(mother_3), np.array(mother_4)))
        niece_1 = self.combine_symbols(mother_1, mother_2)
        niece_2 = self.combine_symbols(mother_3, mother_4)
        niece_3 = self.combine_symbols(dautghers[0], dautghers[1])
        niece_4 = self.combine_symbols(dautghers[2], dautghers[3])
        witness_1 = self.combine_symbols(niece_1, niece_2)
        witness_2 = self.combine_symbols(niece_3, niece_4)
        judge = self.combine_symbols(witness_1, witness_2)

        # If the divination concerns money, which falls under the second house, then the reconciler is obtained by comparing the lines of the judge and the second daughter.
        reconciler = self.combine_symbols(judge, dautghers[1])

        self.vars['symbols'] = [mother_1, mother_2, mother_3, mother_4, dautghers[0].tolist(), dautghers[1].tolist(),
                                dautghers[2].tolist(), dautghers[3].tolist(), niece_1, niece_2, niece_3, niece_4,
                                witness_1, witness_2, judge, reconciler]

        # the part of fortune, a symbol of ready money and of the greatest importance in all questions of money
        part_of_fortune = (mother_1.count(1) + mother_2.count(1) + mother_3.count(1) + mother_4.count(1) + dautghers[
            0].tolist().count(1) + dautghers[1].tolist().count(1) + dautghers[2].tolist().count(1) + dautghers[
                               3].tolist().count(1) + niece_1.count(1) + niece_2.count(1) + niece_3.count(
            1) + niece_4.count(1)) % 12

        self.vars['part_of_fortune'] = 12 if part_of_fortune == 0 else part_of_fortune

    def combine_symbols(self, symbol1, symbol2):
        return [
            0 if (symbol1[0] + symbol2[0]) % 2 == 0 else 1,
            0 if (symbol1[1] + symbol2[1]) % 2 == 0 else 1,
            0 if (symbol1[2] + symbol2[2]) % 2 == 0 else 1,
            0 if (symbol1[3] + symbol2[3]) % 2 == 0 else 1,
        ]

    @property
    @cached
    def take_profit_atr(self):
        return ta.atr(self.candles, self.hp['take_profit_atr_period'])

    @property
    @cached
    def stop_atr(self):
        return ta.atr(self.candles, self.hp['stop_atr_period'])

    @property
    @cached
    def entry_atr(self):
        return ta.atr(self.candles, self.hp['entry_atr_period'])

    @property
    @cached
    def dc(self):
        return ta.donchian(self.candles, period=self.hp['stop_dc_period'])

    def watch_list(self):
        conversion_line, base_line, span_a, span_b = self.ichimoku_cloud

        return [
            ('self.price > span_a', self.price > span_a),
            ('self.price < span_a', self.price < span_a),
            ('self.small_trend', self.small_trend),
            ('span_a > span_b', span_a > span_b),
            ('span_a < span_b', span_a < span_b),
        ]

    def sum_digits(self, integ):
        integ = int(integ)
        if integ <= 9:
            return integ
        res = sum(divmod(integ, 10))
        return self.sum_digits(res)

    ###############################################################
    # # # # # # # # # # # # # filters # # # # # # # # # # # # # # #
    ###############################################################

    def filters(self):
        return []

    def hyperparameters(self):
        return [
            {'name': 'entry_stop_atr_rate', 'type': float, 'min': 0.02, 'max': 1.5, 'default': 0.1},
            {'name': 'stop_loss_atr_rate', 'type': float, 'min': 1, 'max': 4, 'default': 1.8},
            {'name': 'take_profit_atr_rate', 'type': int, 'min': 1, 'max': 15, 'default': 10},
            {'name': 'entry_atr_period', 'type': int, 'min': 2, 'max': 50, 'default': 14},
            {'name': 'stop_atr_period', 'type': int, 'min': 2, 'max': 50, 'default': 28},
            {'name': 'take_profit_atr_period', 'type': int, 'min': 2, 'max': 50, 'default': 28},
            {'name': 'stop_dc_period', 'type': int, 'min': 2, 'max': 50, 'default': 14},
            {'name': 'risk', 'type': int, min: 1, max: 10, 'default': 6},
            {'name': 'symbol_method', 'type': int, min: 0, max: 1, 'default': 0},
        ]
