import mmap
import contextlib
import time
import re
import logging
import xlsxwriter
import subprocess
from os import path
from datetime import datetime, timedelta
from Evtx.Evtx import FileHeader
from Evtx.Views import evtx_file_xml_view
import os


class Initlog(object):
    """
    初始化日志
    """
    def __init__(self, lev=1, levels='DEBUG'):
        """
        记录日志，输出到控制台和文件
        lev
        0 关闭日志
        1 输出到控制台
        2 输出到文件
        3 同时输出到文件和控制台
        """
        self.logs = logging.getLogger('log')
        levels = levels.upper()
        LEVEL = {
            'NOTSET': logging.NOTSET,
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        level = LEVEL[levels]
        formatstr = logging.Formatter('%(asctime)s - %(levelname)-5s - %(message)s')
        e = False
        if lev is 0:
            return
        if lev is 2 or lev is 3:
            self.logs.setLevel(level)
            try:
                out_file = logging.FileHandler(filename='run_logs.log', encoding='utf8')
            except IOError:
                lev = 1
                e = True
            else:
                out_file.setLevel(level)
                out_file.setFormatter(formatstr)
                self.logs.addHandler(out_file)
        if lev is 1 or lev is 3:
            self.logs.setLevel(level)
            debug_handler = logging.StreamHandler()
            debug_handler.setLevel(level)
            debug_handler.setFormatter(formatstr)
            self.logs.addHandler(debug_handler)
            if e:
                self.logs.warning('The log can not be written to the file')
        self.logs.info('log config complete')

    @property
    def get_logging(self):
        return self.logs


class CHECK_PATH(object):
    def __init__(self, user, password, file):
        self.__connect_stats = []
        self.user = user
        self.password = password
        self.__connect()
        self.file_path = file

    def __connect(self):
            if path.exists(self.file_path):
                return True
            else:
                if re.match(r'^\\', self.file_path):
                    proc = subprocess.Popen(r'net use %s %s /user:%s' % (path, self.password, self.user),
                                            stderr=subprocess.PIPE)
                    code = proc.wait()
                    if code != 0:
                        logs.debug(str(proc.stderr.read(), encoding='gbk').replace('\r\n', ' '))
                        logs.error('无法登录到路径 %s ' % path)
                        return False
                    else:
                        return True
                else:
                    return False


class save_xlsx(object):
    def __init__(self, filename='login_Total_%s.xlsx' % time.strftime('%Y_%m_%d-%H_%M'), worksheet='Total'):
        """
        :param filename: excel文件名
        """
        self.column_width = []
        self.row_location = 0  # 行位置
        self.book = xlsxwriter.Workbook(filename, {'constant_memory': True})
        self.worksheet = self.book.add_worksheet(name=worksheet)

    def __str_len(self, strs):
        """计算字符串长度"""
        try:
            row_l = len(strs)
            utf8_l = len(strs.encode('utf-8'))
            return (utf8_l - row_l) / 2 + row_l
        except BaseException:
            return len(strs)

    def pre_init(self,  row=0, col=0, set_col=False):
        title_cn = "序列号 类型 时间 服务器地址 登录账号 客户端IP 客户端主机名 登录ID"
        # 加粗
        bold = self.book.add_format({'bold': True})

        for value in title_cn.split():
            self.worksheet.write(row, col, value, bold)
            if set_col:
                """ 自动计算并设置列宽 """
                x_len = self.__str_len(value)
                self.column_width.append(x_len)
                # cn_len = self.__str_len(title_cn.split()[location])
                # if x_len > cn_len:
                #     set_column = x_len + 2
                # else:
                #     set_column = cn_len + 2
                # 加粗首行
                self.worksheet.set_column(col, col, x_len)
                # column_list.append(set_column)

            col += 1
        self.row_location += 1

    def write_line(self, data_list, col=1):
        """
        写入列表到excel一行
        :param data_list: 列表结构数据
        :param col: 起始列
        :return: 
        """
        # 写入序号
        self.worksheet.write(self.row_location, 0, self.row_location)
        for value in data_list:
            # 获得列宽
            value_len = self.__str_len(value)
            # 设置列宽
            if value_len > self.column_width[col]:
                self.worksheet.set_column(col, col, value_len + 2)
                # 更新列宽列表
                self.column_width[col] = value_len
            # 写入数据
            self.worksheet.write(self.row_location, col, value)
            # 移动到下一列
            col += 1
        # 移动到下一行
        self.row_location += 1


class Event_log(object):
    # 日志文件的路径
    def __init__(self, stream=print):
        self.stream = stream

    @staticmethod
    def __beijin_time(time_str):
        event_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S.%f")
        event_time = event_time + timedelta(hours=8)
        return event_time.strftime('%Y-%m-%d %H:%M:%S')

    def _logout(self, xml, server=''):

        if r'>4779</EventID>' in xml:
            event_time = re.search('<TimeCreated SystemTime="(.+?)"></TimeCreated>', xml).group(1)
            account_name = re.search('<Data Name="AccountName">(.+?)</Data>', xml).group(1)
            login_id = re.search('<Data Name="LogonID">(.+?)</Data>', xml).group(1)
            client_name = re.search('<Data Name="ClientName">(.+?)</Data>', xml).group(1)
            client_address = re.search('<Data Name="ClientAddress">(.+?)</Data>', xml).group(1)

            event_time = self.__beijin_time(event_time)
            server_addr = server

            logs.debug('logout time=%s | server=%s | account=%s | client-addr=%s | client_name=%s | login_id=%s' %
                       (event_time, server_addr, account_name, client_address, client_name, login_id))
            excel.write_line(['logout', event_time, server_addr, account_name, client_address, client_name, login_id])
            # print(xml)
        # print(count)

    def _login_event(self, xml, server=''):
        if r'"LogonType">10</Data>' in xml and r'>4624</EventID>' in xml:
            event_time = re.search('<TimeCreated SystemTime="(.+?)"></TimeCreated>', xml).group(1)
            server_addr = server
            account_name = re.search('"TargetUserName">(.+?)</Data>', xml).group(1)
            client_address = re.search('<Data Name="IpAddress">(.+?)</Data>', xml).group(1)
            login_id = re.search('<Data Name="TargetLogonId">(.+?)</Data>', xml).group(1)

            event_time = self.__beijin_time(event_time)

            logs.debug('login  time=%s | server=%s | account=%s | client-addr=%s | client_name=%s | login_id=%s' %
                       (event_time, server_addr, account_name, client_address, '', login_id))
            excel.write_line(['login', event_time, server_addr, account_name, client_address, '', login_id])
            # print(xml)
            # xml = re.sub(r'<TimeCreated SystemTime="(.+?)"></TimeCreated>',
            #              '<TimeCreated SystemTime="%s"></TimeCreated>' % event_time, xml)
            # self.stream(xml)

    @staticmethod
    def __process_path(file):
        return path.expandvars(file)

    def get_rdp_connect_event(self, event_path):
        event_path = self.__process_path(event_path)
        with open(event_path, 'r') as f:
            with contextlib.closing(mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)) as buf:
                fh = FileHeader(buf, 0)
                # 构建一个xml文件，根元素是Events

                # self.stream("<?xml version=\"1.0\" encoding=\"utf-8\"standalone=\"yes\" ?>")
                # self.stream("<Events>")
                # 遍历事件
                for xml, record in evtx_file_xml_view(fh):
                    # print(xml)
                    self._login_event(xml)
                    self._logout(xml)
                    # self._write_off_4779(xml)
                    # self.stream('--' * 30)

                # self.stream("</Events>")

    def displacement_process(self, lists):
        for file in lists:
            server_addr = re.search('(\d+\.){3}\d+', file).group()
            with open(file, 'r') as f:
                mem = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
                with contextlib.closing(mem) as buf:
                    fh = FileHeader(buf, 0)
                    print("file name: %s" % file)
                    try:
                        for xml, record in evtx_file_xml_view(fh):
                            # print(xml)
                            self._login_event(xml, server=server_addr)
                            self._logout(xml, server=server_addr)
                    except BaseException as err:
                        print("error:" + str(err))
                        # if '"LogonType">10</Data>' in xml:
                        #     print(xml)
                mem.close()


def load_file(folder):
    file_list = []
    for root, dirs, files in os.walk(folder):
        for file in files:
            if re.match('.*evtx$', file):
                file_list.append(os.path.join(root, file))
    return file_list


if __name__ == '__main__':
    start_time = time.time()
    log = Initlog(lev=1)
    logs = log.get_logging

    event = Event_log()

    excel = save_xlsx()
    excel.pre_init(set_col=True)

    files = load_file(r'F:\event')
    event.displacement_process(files)
    excel.book.close()

    end_time = time.time()
    print('run time %s' % (end_time - start_time))
