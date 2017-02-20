# -*- coding: utf-8 -*-
import threading
import logging
import logging.config
import ConfigParser
from winguiauto import *
import sys
import redis
import mdl_neeq_msg_pb2
import time


class StockTransHandler(threading.Thread):
    def __init__(self, amount):
        super(StockTransHandler, self).__init__()
        self._stop = threading.Event()
        self.amount = amount

        logging.config.fileConfig('log.conf')
        self.logger = logging.getLogger('main')

        cf = ConfigParser.ConfigParser()
        cf.read("tradeagent.conf")

        self.r_host = cf.get("rdb", "host")
        self.r_port = cf.getint("rdb", "port")
        self.r = None
        self.p = None

        hwnd_title = cf.get("hwnd_mode", "wnd_title")

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
        self.logger.debug('subscribe messages ...')
        self.r = redis.Redis(host=self.r_host, port=self.r_port, db=0)
        self.p = self.r.pubsub()
        self.p.subscribe(['mdl.14.3.*'])

    def on_need_matched_bargain_order(self, data):
        try:
            msg = mdl_neeq_msg_pb2.MatchedBargainOrder()
            msg.ParseFromString(data)
            self.logger.debug(msg)
            if msg.Price.Value/float(msg.Price.DecimalShift) <= 0.5 and msg.TranscationType == "6S" and msg.SecurityID != "833794":
                self.logger.debug(msg)
                # print msg.SecurityID, msg.TranscationUnit, msg.TranscationType, msg.Volume, msg.Price.Value/float(msg.Price.DecimalShift),\
                #     msg.TranscationNo, msg.OrderTime, msg.RecordStatus, msg.ReservedFlag, msg.UpdateTime
                askprice = msg.Price.Value/float(msg.Price.DecimalShift)
                limit = self.amount
                if 0.5 < askprice:
                    limit = 0
                elif 0.4 < askprice <= 0.5:
                    limit = min(limit, 40000)
                elif 0.3 < askprice <= 0.4:
                    limit = min(limit, 60000)
                elif 0.2 < askprice <= 0.3:
                    limit = min(limit, 80000)
                elif 0.1 < askprice <= 0.2:
                    limit = min(limit, 100000)
                elif askprice <= 0.1:
                    limit = min(limit, self.amount)
                self.logger.debug("askprice: %f, limit: %d", askprice, limit)

                askvol = 0
                if askprice * int(msg.Volume) > limit:
                    askvol = int(limit/askprice)
                    askvol = int(askvol / 1000) * 1000
                else:
                    askvol = int(msg.Volume)

                self.logger.debug("askvol: %d", askvol)
                self.logger.debug("stockcode: %s, askprice: %f, askvol: %d, contactid: %d, seatno: %s",
                                  msg.SecurityID, askprice, askvol, msg.TranscationNo, msg.TranscationUnit)
                self.logger.debug("stockcode: %s, askprice: %s, askvol: %s, contactid: %s, seatno: %s",
                                  str(msg.SecurityID), str(askprice), str(askvol), str(msg.TranscationNo), str(msg.TranscationUnit))
                if askvol >= 8000:
                    self.logger.info('buying ...... ')
                    self.order(str(msg.SecurityID), str(askprice), str(askvol), str(msg.TranscationNo), str(msg.TranscationUnit))
                    #time.sleep(1)
                    #self.order(str(msg.SecurityID), ("%.2f" % askprice), str(askvol), str(msg.TranscationNo), str(msg.TranscationUnit))

        except Exception, e:
                self.logger.error(e)

    def order(self, stock_code, price, amount, contact_id, seat_no):
        setEditText(self.hwnd_child3[0], stock_code)      # stock code
        setEditText(self.hwnd_child3[3], price)         # price
        #time.sleep(5)
        setEditText(self.hwnd_child3[5], amount)        # amount
        # time.sleep(5)
        setEditText(self.hwnd_child3[6], contact_id)     # 约定号
        setEditText(self.hwnd_child3[7], seat_no)    # 对方席位
        # time.sleep(5)
        clickButton(self.hwnd_child3[9])            # buy
        continue_clicked = False
        while not continue_clicked:
            # time.sleep(0.1)
            hwnd_popup = findPopupWindow(self.hwnd_parent)
            if hwnd_popup:
                #time.sleep(5)
                hwnd_controls = findControls(hwnd_popup, wantedClass='Button')
                clickButton(hwnd_controls[1])   # 继续买入
                continue_clicked = True

    def run(self):
        self.subscribe_request()
        self.logger.info("receiving message...")
        # self.order('834379', '0.25', '1000', '99996807', '727200')
        for item in self.p.listen():
            if str(item['type']) == 'message':
		channel = str(item['channel'])
		if channel[0:9] == "mdl.14.3.":
			self.on_need_matched_bargain_order(item['data'])                     
		else:
			print "unknown channel: %s" % (channel)
        # while True:
            #self.trade_signal()
            # self.on_need_matched_bargain_order()


if __name__ == '__main__':
    st_handler = StockTransHandler(amount=90000)
    st_handler.start()
    sys.stdin.readline()
    st_handler.stop()
