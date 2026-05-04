from tick_strategy_base import TickStrategyBase


class TrendFollowStrategy(TickStrategyBase):
    def __init__(
        self,
        engine,
        momentum_window=90,
        entry_threshold=1.5,
        expected_profit_ticks=8,
        stop_loss_ticks=5,
        max_holding_ticks=300,
        is_ideal=False,
        is_mean_reversion=False,
        min_depth=1,
        max_spread=2.0,
        spread_multiplier=1.0,
        spread_addition=0.0,
    ):
        super().__init__(
            engine=engine,
            expected_profit_ticks=expected_profit_ticks,
            stop_loss_ticks=stop_loss_ticks,
            max_holding_ticks=max_holding_ticks,
            is_ideal=is_ideal,
            min_depth=min_depth,
            max_spread=max_spread,
            spread_multiplier=spread_multiplier,
            spread_addition=spread_addition,
        )
        self.momentum_window = momentum_window
        self.entry_threshold = entry_threshold
        self.is_mean_reversion = is_mean_reversion
        self.price_history = []

    def on_tick(self, tick):
        self.price_history.append(tick["last_price"])
        if len(self.price_history) > self.momentum_window:
            self.price_history.pop(0)

        if len(self.price_history) < self.momentum_window:
            return

        if self._handle_position(tick):
            return

        current_price = tick["last_price"]
        if not self._passes_market_filter(tick, current_price):
            self.pnl_history.append(self.total_pnl)
            return

        momentum_score = (current_price - self.price_history[0]) / self.engine.price_tick
        buy_signal, sell_signal = self._generate_signal(momentum_score)

        if buy_signal:
            self._open_position(tick, "BUY", 1)
        elif sell_signal:
            self._open_position(tick, "SELL", -1)

        self.pnl_history.append(self.total_pnl)

    def _generate_signal(self, momentum_score):
        if self.is_mean_reversion:
            if momentum_score >= self.entry_threshold:
                return False, True
            if momentum_score <= -self.entry_threshold:
                return True, False
        else:
            if momentum_score >= self.entry_threshold:
                return True, False
            if momentum_score <= -self.entry_threshold:
                return False, True
        return False, False


class ObiOnlyStrategy(TickStrategyBase):
    def __init__(
        self,
        engine,
        obi_threshold=0.7,
        expected_profit_ticks=8,
        stop_loss_ticks=5,
        max_holding_ticks=300,
        is_ideal=False,
        is_mean_reversion=False,
        min_depth=1,
        max_spread=2.0,
        spread_multiplier=1.0,
        spread_addition=0.0,
    ):
        super().__init__(
            engine=engine,
            expected_profit_ticks=expected_profit_ticks,
            stop_loss_ticks=stop_loss_ticks,
            max_holding_ticks=max_holding_ticks,
            is_ideal=is_ideal,
            min_depth=min_depth,
            max_spread=max_spread,
            spread_multiplier=spread_multiplier,
            spread_addition=spread_addition,
        )
        self.obi_threshold = obi_threshold
        self.is_mean_reversion = is_mean_reversion

    def on_tick(self, tick):
        if self._handle_position(tick):
            return

        current_price = tick["last_price"]
        if not self._passes_market_filter(tick, current_price):
            self.pnl_history.append(self.total_pnl)
            return

        obi = self.calculate_obi(tick)
        buy_signal, sell_signal = self._generate_signal(obi)

        if buy_signal:
            self._open_position(tick, "BUY", 1)
        elif sell_signal:
            self._open_position(tick, "SELL", -1)

        self.pnl_history.append(self.total_pnl)

    def _generate_signal(self, obi):
        if self.is_mean_reversion:
            if obi >= self.obi_threshold:
                return False, True
            if obi <= -self.obi_threshold:
                return True, False
        else:
            if obi >= self.obi_threshold:
                return True, False
            if obi <= -self.obi_threshold:
                return False, True
        return False, False


PureMomentumStrategy = TrendFollowStrategy
PureOBIStrategy = ObiOnlyStrategy
