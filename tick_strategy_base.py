import numpy as np


class TickStrategyBase:
    def __init__(
        self,
        engine,
        expected_profit_ticks=8,
        stop_loss_ticks=5,
        max_holding_ticks=300,
        is_ideal=False,
        min_depth=1,
        max_spread=2.0,
        spread_multiplier=1.0,
        spread_addition=0.0,
    ):
        self.engine = engine
        self.expected_profit_ticks = expected_profit_ticks
        self.stop_loss_ticks = stop_loss_ticks
        self.max_holding_ticks = max_holding_ticks
        self.is_ideal = is_ideal
        self.min_depth = min_depth
        self.max_spread = max_spread
        self.spread_multiplier = spread_multiplier
        self.spread_addition = spread_addition

        self.ticks_held = 0
        self.pnl_history = []
        self.current_position = 0
        self.entry_price = 0.0
        self.entry_time = None
        self.entry_cost = 0.0
        self.entry_direction = None
        self.trade_count = 0
        self.total_pnl = 0.0
        self.trade_log = []

    @property
    def max_drawdown(self):
        if not self.pnl_history:
            return 0.0
        pnl_array = np.array(self.pnl_history)
        running_max = np.maximum.accumulate(pnl_array)
        drawdowns = running_max - pnl_array
        return np.max(drawdowns)

    def calculate_obi(self, tick):
        bid_volume = tick["bid_volume1"]
        ask_volume = tick["ask_volume1"]
        if bid_volume + ask_volume == 0:
            return 0.0
        return (bid_volume - ask_volume) / (bid_volume + ask_volume)

    def _should_close(self, current_price):
        close_signal = False
        close_reason = None

        if self.current_position == 1:
            if current_price >= self.entry_price + (self.expected_profit_ticks * self.engine.price_tick):
                close_signal = True
                close_reason = "take_profit"
            elif current_price <= self.entry_price - (self.stop_loss_ticks * self.engine.price_tick):
                close_signal = True
                close_reason = "stop_loss"
        elif self.current_position == -1:
            if current_price <= self.entry_price - (self.expected_profit_ticks * self.engine.price_tick):
                close_signal = True
                close_reason = "take_profit"
            elif current_price >= self.entry_price + (self.stop_loss_ticks * self.engine.price_tick):
                close_signal = True
                close_reason = "stop_loss"

        if self.ticks_held >= self.max_holding_ticks:
            close_signal = True
            close_reason = "timeout"

        return close_signal, close_reason

    def _estimate_round_trip_cost(self, tick, current_price):
        estimated_commission = self.engine.calculate_commission(
            current_price,
            1,
            self.engine.commission_open + self.engine.commission_today,
        )
        if self.is_ideal:
            return estimated_commission
        spread = self.engine.price_diff_to_pnl(self._effective_spread(tick), 1)
        return estimated_commission + spread

    def _passes_market_filter(self, tick, current_price):
        expected_return = self.engine.price_diff_to_pnl(
            self.expected_profit_ticks * self.engine.price_tick,
            1,
        )
        if expected_return <= self._estimate_round_trip_cost(tick, current_price):
            return False

        if self.is_ideal:
            return True

        spread = self._effective_spread(tick)
        if spread > self.max_spread:
            return False

        if tick["bid_volume1"] < self.min_depth or tick["ask_volume1"] < self.min_depth:
            return False

        return True

    def _effective_spread(self, tick):
        raw_spread = tick["ask_price1"] - tick["bid_price1"]
        return raw_spread * self.spread_multiplier + self.spread_addition

    def _open_position(self, tick, action, position):
        success, result = self.engine.match_order(action, 1)
        if not success:
            return

        self.current_position = position
        self.entry_price = result["price"]
        self.entry_time = tick.get("datetime")
        self.entry_cost = result["cost"]
        self.entry_direction = "LONG" if position == 1 else "SHORT"
        self.total_pnl -= result["cost"]
        self.trade_count += 1
        self.ticks_held = 0

    def _close_position(self, tick, result, close_reason):
        if self.current_position == 1:
            price_diff = result["price"] - self.entry_price
        else:
            price_diff = self.entry_price - result["price"]

        gross_profit = self.engine.price_diff_to_pnl(price_diff, result["volume"])
        close_cost = result["cost"]
        net_profit = gross_profit - self.entry_cost - close_cost
        self.total_pnl += gross_profit - close_cost

        self._record_trade(tick, result["price"], close_cost, gross_profit, net_profit, close_reason)
        self.current_position = 0
        self.ticks_held = 0

    def _record_trade(self, tick, exit_price, exit_cost, gross_profit, net_profit, close_reason):
        total_cost = self.entry_cost + exit_cost
        self.trade_log.append(
            {
                "entry_time": self.entry_time,
                "exit_time": tick.get("datetime") if tick else None,
                "direction": self.entry_direction,
                "entry_price": self.entry_price,
                "exit_price": exit_price,
                "gross_profit": gross_profit,
                "entry_cost": self.entry_cost,
                "exit_cost": exit_cost,
                "total_cost": total_cost,
                "net_profit": net_profit,
                "holding_ticks": self.ticks_held,
                "close_reason": close_reason or "unknown",
                "equity_after_trade": self.total_pnl,
            }
        )
        self.entry_time = None
        self.entry_cost = 0.0
        self.entry_direction = None

    def _handle_position(self, tick):
        if self.current_position == 0:
            return False

        self.ticks_held += 1
        close_signal, close_reason = self._should_close(tick["last_price"])
        if close_signal:
            action = "SELL" if self.current_position == 1 else "BUY"
            success, result = self.engine.match_order(action, 1)
            if success:
                self._close_position(tick, result, close_reason)

        self.pnl_history.append(self.total_pnl)
        return True

    def force_close_at_end(self):
        if self.current_position != 0:
            action = "SELL" if self.current_position == 1 else "BUY"
            success, result = self.engine.match_order(action, 1)
            if success:
                self._close_position(self.engine.current_tick, result, "force_close")
            self.pnl_history.append(self.total_pnl)


BaseTickStrategy = TickStrategyBase
