# -*- coding: utf-8 -*-
import threading
import pandas as pd
import logging
import logging.config
import ConfigParser
from winguiauto import *
from qpython import qconnection
import numpy as np
from qpython.qtype import QException
from pandas import DataFrame
import sys


class StockTransHandler(threading.Thread):
    def __init__(self):
        super(StockTransHandler, self).__init__()
        self._stop = threading.Event()

        logging.config.fileConfig('log.conf')
        self.logger = logging.getLogger('main')

        cf = ConfigParser.ConfigParser()
        cf.read("tradeagent.conf")

        q_host = cf.get("kdb", "host")
        q_port = cf.getint("kdb", "port")
        self.request_table = cf.get("kdb", "request_table")

        hwnd_title = cf.get("hwnd_mode", "wnd_title")
        self.q = qconnection.QConnection(host=q_host, port=q_port, pandas=True)
        self.q.open()

        self.hwnd_parent = findSpecifiedTopWindow(u'网上股票交易系统5.0')
        # self.hwnd_parent = findSpecifiedTopWindow(hwnd_title)
        hwnd_child1 = dumpSpecifiedWindow(self.hwnd_parent, wantedClass='AfxMDIFrame42s')
        hwnd_child2 = dumpSpecifiedWindow(hwnd_child1[0])
        self.hwnd_child3 = dumpSpecifiedWindow(hwnd_child2[5])
        self.logger.debug("found parent hwnd: %ld, child: %d", hwnd_child2[5], len(self.hwnd_child3))
        if len(self.hwnd_child3) == 62:
            self.logger.info("found correct controls")
        else:
            self.logger.error(u'错误, 请确认已运行交易软件软件或者无法获取相应的句柄')
            exit(0)

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()

    def subscribe_request(self):
        # TODO
        self.logger.debug('subscribe trade: table=%s', self.request_table)
        self.q.sync('.u.sub', np.string_(self.request_table), np.string_(''))

    def trade_signal(self):
        try:
            message = self.q.receive(data_only=False, raw=False, pandas=True)
            self.logger.debug('type: %s, message type: %s, data size: %s, is_compressed: %s ',
                              type(message), message.type, message.size, message.is_compressed)

            if isinstance(message.data, list):
                # unpack upd message
                if len(message.data) == 3 and message.data[0] == 'upd' and message.data[1] == self.request_table:
                    if isinstance(message.data[2], DataFrame):
                        df_new_signals = message.data[2]
                        self.logger.debug('new requests data: df_new_signals=%s', df_new_signals.to_string())
                        for key, row in df_new_signals.iterrows():
                            self.order(row.stockcode, str(row.askprice), str(row.askvol), row.contactid, row.seatno)
        except QException, e:
                print(e)
        finally:
            return df_new_signals

    def order(self, stock_code, price, amount, contact_id, seat_no):
        setEditText(self.hwnd_child3[0], stock_code)      # stock code
        setEditText(self.hwnd_child3[3], price)         # price
        setEditText(self.hwnd_child3[5], amount)        # amount
        setEditText(self.hwnd_child3[6], contact_id)     # 约定号
        setEditText(self.hwnd_child3[7], seat_no)    # 对方席位
        clickButton(self.hwnd_child3[9])            # buy
        continue_clicked = False
        while not continue_clicked:
            # time.sleep(0.1)
            hwnd_popup = findPopupWindow(self.hwnd_parent)
            if hwnd_popup:
                hwnd_controls = findControls(hwnd_popup, wantedClass='Button')
                clickButton(hwnd_controls[1])   # 继续买入
                continue_clicked = True

    def run(self):
        self.subscribe_request()
        while True:
            self.trade_signal()


if __name__ == '__main__':
    st_handler = StockTransHandler()
    st_handler.start()
    sys.stdin.readline()
    st_handler.stop()
