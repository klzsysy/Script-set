# -*- coding: utf-8 -*-
__author__ = 'Sonny Yang'
import sys
import logging
import requests
import bs4

logging.basicConfig(level=logging.DEBUG)


class ZoneRoute(object):
    def __init__(self):
        self.cn_ipv4_raw = ''
        self.zone_value = 'CN'
        self.count = 3
        self.raw_text = self.__pull_raw_text()
        self.__start()

    @property
    def zone(self):
        print(self.zone_value)
        return

    @zone.setter
    def zone(self, value=''):
        if value:
            self.zone_value = value.upper()
            self.__start()

    def __pull_raw_text(self):
        logging.info('开始从亚太信息中心抓取路由数据库，数据较多请等待...')
        r = requests.get('http://ftp.apnic.net/apnic/stats/apnic/delegated-apnic-latest')
        if r.status_code >= 400:
            if self.count > 0:
                print('pull url failed!, try again')
                self.count -= 1
                self.__pull_raw_text()
            else:
                print('exit')
                sys.exit(-1)
        bs = bs4.BeautifulSoup(r.content, 'html5lib')
        return bs.text.split('\n')

    def __start(self):
        # with open('delegated-apnic-latest.txt', 'r') as f:
        #     self.cn_ipv4_raw = [x for x in f if '%s' % self.zone_value in x and 'ipv4' in x]
        #     if not self.cn_ipv4_raw:
        #         logging.error('无法获得有效文本内容')
        #         os._exit(1)
        #
        self.cn_ipv4_raw = [x for x in self.raw_text if '%s' % self.zone_value in x and 'ipv4' in x]
        if not self.cn_ipv4_raw:
            logging.error('无法获得有效文本内容')
            sys.exit(1)

        network_addr = [x.split('|')[3] for x in self.cn_ipv4_raw]
        cidr = [x.split('|')[4] for x in self.cn_ipv4_raw]

        self.ip_mask = []
        for x in (zip(network_addr, cidr)):
            mask = ''
            s = int(x[1]) / 256
            if s <= 1:
                mask = '255.255.255.{}'.format(256 - int(x[1]))
            elif 256 >= s > 1:
                mask = '255.255.{}.0'.format(256 - int(s))
            elif 65536 >= s > 256:
                mask = '255.{}.0.0'.format((256**2 - int(s))//256)
            elif s > 65536:
                mask = '{}.0.0.0'.format((256**3 - int(s))//256)
            self.ip_mask.append((x[0], mask, x[1]))

    def __build_cisco_acl(self):
        def build_acl(addr):
            wildcard = '.'.join([str(255-int(x)) for x in addr[1].split('.')])
            return " permit ip any {0} {1}".format(addr[0], wildcard)
        return map(build_acl, [x[:-1] for x in self.ip_mask])

    def show_cisco_cal(self):
        """获得 cisco extended acl ipv4 条目"""
        print('ip access-list extended %sZoneRoute' % self.zone_value)
        for x in self.__build_cisco_acl():
            print(x)

    def save_cisco_cal(self):
        """获得 cisco extended acl ipv4 条目保存到文件"""
        with open('cisco extended acl.txt', 'w') as f:
            f.write('ip access-list extended %sZoneRoute\n' % self.zone_value)
            for acl in self.__build_cisco_acl():
                f.write(acl + '\n')

    def show_network_mask(self):
        print('%-18s %-15s' % ('network', 'mask'))
        for x in self.ip_mask:
            print('%-18s %-15s' % (x[0], x[1]))
        print('总计host: %s' % sum([int(x[-1]) for x in self.ip_mask]))
        return

if __name__ == '__main__':
    C = ZoneRoute()
    # 选择区域 默认cn
    # C.zone = 'cn'
    C.save_cisco_cal()

