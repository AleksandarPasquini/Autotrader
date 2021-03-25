# Copyright 2021 Optiver Asia Pacific Pty. Ltd.
#
# This file is part of Ready Trader One.
#
#     Ready Trader One is free software: you can redistribute it and/or
#     modify it under the terms of the GNU Affero General Public License
#     as published by the Free Software Foundation, either version 3 of
#     the License, or (at your option) any later version.
#
#     Ready Trader One is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU Affero General Public License for more details.
#
#     You should have received a copy of the GNU Affero General Public
#     License along with Ready Trader One.  If not, see
#     <https://www.gnu.org/licenses/>.
import asyncio
import itertools

from typing import List

from ready_trader_one import BaseAutoTrader, Instrument, Lifespan, Side

LOT_SIZE = 10
POSITION_LIMIT = 1000
TICK_SIZE_IN_CENTS = 100


class AutoTrader(BaseAutoTrader):
    """Example Auto-trader.

    When it starts this auto-trader places ten-lot bid and ask orders at the
    current best-bid and best-ask prices respectively. Thereafter, if it has
    a long position (it has bought more lots than it has sold) it reduces its
    bid and ask prices. Conversely, if it has a short position (it has sold
    more lots than it has bought) then it increases its bid and ask prices.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop, team_name: str, secret: str):
        """Initialise a new instance of the AutoTrader class."""
        super().__init__(loop, team_name, secret)
        self.order_ids = itertools.count(1)
        self.bids = {}
        self.asks = {}
        self.ask_id = self.ask_price = self.bid_id = self.bid_price = self.position = self.marketbid = self.marketask = 0
        self.sequence_number = -1

    def on_error_message(self, client_order_id: int, error_message: bytes) -> None:
        """Called when the exchange detects an error.

        If the error pertains to a particular order, then the client_order_id
        will identify that order, otherwise the client_order_id will be zero.
        """
        self.logger.warning("error with order %d: %s", client_order_id, error_message.decode())
        if client_order_id != 0:
            self.on_order_status_message(client_order_id, 0, 0, 0)

    def on_order_book_update_message(self, instrument: int, sequence_number: int, ask_prices: List[int],
                                     ask_volumes: List[int], bid_prices: List[int], bid_volumes: List[int]) -> None:
        """Called periodically to report the status of an order book.

        The sequence number can be used to detect missed or out-of-order
        messages. The five best available ask (i.e. sell) and bid (i.e. buy)
        prices are reported along with the volume available at each of those
        price levels.
        """

        if instrument == Instrument.FUTURE and sequence_number >= self.sequence_number:
            self.sequence_number = sequence_number
            price = ((bid_prices[0] + ask_prices[0]) // 200) * 100 if bid_prices[0] != 0 or ask_prices[0] != 0 else 0
            new_bid_price = price
            new_ask_price = price + 200
            volume_change = int((self.position / POSITION_LIMIT) * 100)
            bid_order_volumne = 100 - volume_change
            ask_order_volumne = 100 + volume_change
            if new_bid_price not in (self.bid_price, 0):
                if self.bid_id != 0:
                    self.send_cancel_order(self.bid_id)
                    self.bid_id = 0
            if new_ask_price not in (self.ask_price, 0):
                if self.ask_id != 0:
                    self.send_cancel_order(self.ask_id)
                    self.ask_id = 0

            if self.bid_id == 0 and new_bid_price != 0 and self.position + bid_order_volumne + self.marketbid <= POSITION_LIMIT \
                    and bid_order_volumne != 0:
                self.bid_id = next(self.order_ids)
                self.bid_price = new_bid_price
                self.marketbid += bid_order_volumne
                self.send_insert_order(self.bid_id, Side.BUY, new_bid_price, bid_order_volumne, Lifespan.GOOD_FOR_DAY)
                self.bids[self.bid_id] = bid_order_volumne

            if self.ask_id == 0 and new_ask_price != 0 and self.position - ask_order_volumne - self.marketask >= -POSITION_LIMIT \
                    and ask_order_volumne != 0:
                self.ask_id = next(self.order_ids)
                self.ask_price = new_ask_price
                self.marketask += ask_order_volumne
                self.send_insert_order(self.ask_id, Side.SELL, new_ask_price, ask_order_volumne, Lifespan.GOOD_FOR_DAY)
                self.asks[self.ask_id] = ask_order_volumne

    def on_order_filled_message(self, client_order_id: int, price: int, volume: int) -> None:
        """Called when when of your orders is filled, partially or fully.

        The price is the price at which the order was (partially) filled,
        which may be better than the order's limit price. The volume is
        the number of lots filled at that price.
        """
        if client_order_id in self.bids:
            self.position += volume
            self.marketbid -= volume
            self.bids[client_order_id] -= volume
        elif client_order_id in self.asks:
            self.position -= volume
            self.marketask -= volume
            self.asks[client_order_id] -= volume

    def on_order_status_message(self, client_order_id: int, fill_volume: int, remaining_volume: int,
                                fees: int) -> None:
        """Called when the status of one of your orders changes.

        The fill_volume is the number of lots already traded, remaining_volume
        is the number of lots yet to be traded and fees is the total fees for
        this order. Remember that you pay fees for being a market taker, but
        you receive fees for being a market maker, so fees can be negative.

        If an order is cancelled its remaining volume will be zero.
        """
        if remaining_volume == 0:
            if client_order_id == self.bid_id:
                self.bid_id = 0
            elif client_order_id == self.ask_id:
                self.ask_id = 0
            # It could be either a bid or an ask
            if client_order_id in self.bids:
                self.marketbid -= self.bids[client_order_id]
                del self.bids[client_order_id]
            elif client_order_id in self.asks:
                self.marketask -= self.asks[client_order_id]
                del self.asks[client_order_id]
