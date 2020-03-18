import asyncio

import itertools
from typing import List, Tuple
from ready_trader_one import BaseAutoTrader, Instrument, Lifespan, Side

class AutoTrader(BaseAutoTrader):
    def __init__(self, loop: asyncio.AbstractEventLoop):

        """Initialise a new instance of the AutoTrader class."""

        super(AutoTrader, self).__init__(loop)
        self.order_ids = itertools.count(1)
        self.bid_order = self.ask_order = self.future_position = self.ask_id = self.ask_price = self.bid_id = self.bid_price = self.position = 0

    def on_error_message(self, client_order_id: int, error_message: bytes) -> None:

        """Called when the exchange detects an error.
        If the error pertains to a particular order, then the client_order_id
        will identify that order, otherwise the client_order_id will be zero.
        """

        self.logger.warning("error with order %d: %s", client_order_id, error_message.decode())
        self.on_order_status_message(client_order_id, 0, 0, 0)

    def on_order_book_update_message(self, instrument: int, sequence_number: int, ask_prices: List[int],
                                     ask_volumes: List[int], bid_prices: List[int], bid_volumes: List[int]) -> None:

        """Called periodically to report the status of an order book.
        The sequence number can be used to detect missed or out-of-order
        messages. The five best available ask (i.e. sell) and bid (i.e. buy)
        prices are reported along with the volume available at each of those
        price levels.
        """

        if instrument == Instrument.FUTURE:
            new_bid_price = (bid_prices[0]) if bid_prices[0] != 0 else 0
            new_ask_price = (ask_prices[0]) if ask_prices[0] != 0 else 0
            bid_volume = min(min(bid_volumes[0], 25), (99 + self.position))
            ask_volume = min(min(ask_volumes[0], 25), (99 - self.position))

            if (self.bid_id != 0 and new_bid_price not in (self.bid_price, 0)):
                self.send_cancel_order(self.bid_id)
                self.bid_id = 0

            if (self.ask_id != 0 and new_ask_price not in (self.ask_price, 0)):
                self.send_cancel_order(self.ask_id)
                self.ask_id = 0

            if self.bid_id == 0 and new_bid_price != 0 and (self.position < 100 - bid_volume) and (
                    self.future_position - bid_volume > -100) and self.bid_order == 0 and bid_volume != 0:
                self.bid_order = 1
                self.bid_price = new_bid_price
                self.send_insert_order(self.bid_id, Side.BUY, new_bid_price, bid_volume, Lifespan.GOOD_FOR_DAY)

            if self.ask_id == 0 and new_ask_price != 0 and (self.position > -100 + ask_volume) and \
                    (self.future_position + ask_volume < 100) and self.ask_order == 0 and ask_volume != 0:
                self.ask_order = 1
                self.ask_price = new_ask_price
                self.send_insert_order(self.ask_id, Side.SELL, new_ask_price, ask_volume, Lifespan.GOOD_FOR_DAY)

    def on_order_status_message(self, client_order_id: int, fill_volume: int, remaining_volume: int, fees: int) -> None:

        """Called when the status of one of your orders changes.
        The fill_volume is the number of lots already traded, remaining_volume
        is the number of lots yet to be traded and fees is the total fees for
        this order. Remember that you pay fees for being a market taker, but
        you receive fees for being a market maker, so fees can be negative.
        If an order is cancelled its remaining volume will be zero.

        """

        if remaining_volume == 0:
            if client_order_id == self.bid_id:
                self.bid_order = 0
                self.bid_id = 0
            elif client_order_id == self.ask_id:
                self.ask_order = 0
                self.ask_id = 0
        if client_order_id == self.bid_id:
            self.bid_order = 0
        if client_order_id == self.ask_id:
            self.ask_order = 0



    def on_position_change_message(self, future_position: int, etf_position: int) -> None:
        """Called when your position changes.
        Since every trade in the ETF is automatically hedged in the future,
        future_position and etf_position will always be the inverse of each
        other (i.e. future_position == -1 * etf_position).
        """
        self.position = etf_position
        self.future_position = future_position

    def on_trade_ticks_message(self, instrument: int, trade_ticks: List[Tuple[int, int]]) -> None:
        """Called periodically to report trading activity on the market.
        Each trade tick is a pair containing a price and the number of lots
        traded at that price since the last trade ticks message.
        """
        pass