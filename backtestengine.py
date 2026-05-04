class BacktestEngine:
    def __init__(
        self,
        data_path,
        commission_open=0.0001,
        commission_today=0.0001,
        commission_yesterday=0.0001,
        price_tick=1.0,
        contract_multiplier=1.0,
        contract_symbol="UNKNOWN",
        commission_mode="rate",
        margin_rate=0.0,
    ):
        self.data_path = data_path
        self.contract_symbol = contract_symbol
        self.contract_multiplier = contract_multiplier
        self.price_tick = price_tick
        self.tick_value = price_tick * contract_multiplier
        self.commission_mode = commission_mode
        self.margin_rate = margin_rate

        self.commission_open = commission_open
        self.commission_today = commission_today
        self.commission_yesterday = commission_yesterday

        self.current_tick = None
        self.tick_history = []
        self.volatility_window = 20
        self.position_ledger = []

    def notional_value(self, price, volume):
        return price * self.contract_multiplier * volume

    def calculate_commission(self, price, volume, commission):
        if self.commission_mode == "fixed":
            return commission * volume
        if self.commission_mode != "rate":
            raise ValueError(f"Unsupported commission_mode: {self.commission_mode}")
        return self.notional_value(price, volume) * commission

    def price_diff_to_pnl(self, price_diff, volume):
        return price_diff * self.contract_multiplier * volume

    def required_margin(self, price, volume):
        return self.notional_value(price, volume) * self.margin_rate

    def execute_with_market_impact(self, order_volume, l1_price, l1_volume, is_buy):
        remaining_vol = order_volume
        total_turnover_price = 0.0
        current_level_price = l1_price
        current_level_vol = l1_volume

        while remaining_vol > 0:
            executed_vol = min(remaining_vol, current_level_vol)
            total_turnover_price += executed_vol * current_level_price
            remaining_vol -= executed_vol

            if remaining_vol > 0:
                current_level_price += self.price_tick if is_buy else -self.price_tick
                current_level_vol = l1_volume

        return total_turnover_price / order_volume

    def match_order(self, direction, volume):
        if not self.current_tick:
            return False, "No market data"

        current_date = str(self.current_tick["datetime"])[:10]
        is_opening = True
        if self.position_ledger and self.position_ledger[0]["direction"] != direction:
            is_opening = False

        if direction == "BUY":
            exec_price = self.execute_with_market_impact(
                volume,
                self.current_tick["ask_price1"],
                self.current_tick["ask_volume1"],
                True,
            )
        else:
            exec_price = self.execute_with_market_impact(
                volume,
                self.current_tick["bid_price1"],
                self.current_tick["bid_volume1"],
                False,
            )

        trade_cost = 0.0
        if is_opening:
            trade_cost = self.calculate_commission(exec_price, volume, self.commission_open)
            self.position_ledger.append(
                {
                    "date": current_date,
                    "price": exec_price,
                    "volume": volume,
                    "direction": direction,
                    "margin": self.required_margin(exec_price, volume),
                }
            )
        else:
            temp_vol = volume
            for i in range(len(self.position_ledger) - 1, -1, -1):
                pos = self.position_ledger[i]
                if temp_vol <= 0:
                    break

                close_vol = min(temp_vol, pos["volume"])
                commission = (
                    self.commission_today
                    if pos["date"] == current_date
                    else self.commission_yesterday
                )
                trade_cost += self.calculate_commission(exec_price, close_vol, commission)
                pos["volume"] -= close_vol
                temp_vol -= close_vol

            self.position_ledger = [p for p in self.position_ledger if p["volume"] > 0]

        return True, {"price": exec_price, "volume": volume, "cost": trade_cost}
