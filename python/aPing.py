#!/usr/bin/env python3
# 多线程Ping

import os
import subprocess
import sys
import logging
import logging.handlers
import time
import threading
from locale import getpreferredencoding

monitor_ip = '192.195.30.3 192.195.30.4 192.195.30.8 192.195.30.11'


class Logger(object):
    """
    实例化一个可用的logging
    L = logger()
    logs = L.get_logger
    logs.debug(msg)
    """
    def __init__(self, log_name='run', log_output_file=True, log_output_terminal=True,
                 write_level=10, terminal_level=10):

        # 输出到文件
        self.log_output_file = log_output_file
        # 输出到文件基本
        self.write_level = write_level
        # 输出到终端
        self.log_output_terminal = log_output_terminal
        # 输出到终端基本
        self.terminal_level = terminal_level
        # 日志名
        self.log_name = log_name
        # 日志文件轮转
        self.Rotating = True
        self.formatter = logging.Formatter('%(asctime)s - %(levelname)-7s : %(message)s')

        try:
            if not os.path.exists(os.path.join(os.getcwd(), 'logs')):
                os.mkdir('logs')
        except Exception:
            self.Rotating = False

        self.__write_file_logger()
        self.__terminal_file_logger()

    def __write_file_logger(self):
        """只写入文件"""
        self.write_log = logging.getLogger(self.log_name)
        self.write_log.setLevel(self.write_level)
        if self.Rotating and self.log_output_file:
            # 自动切割，保留10份，每份10M
            # of = logging.handlers.RotatingFileHandler("logs\\%s.log" % self.log_name, mode='a',
            #                                           maxBytes=1024 * 1024 * 10, backupCount=10, encoding='utf8')

            # 自动切割，保留10份，按时间每天一份
            of = logging.handlers.TimedRotatingFileHandler("logs\\%s.log" % self.log_name, when='D', backupCount=10,
                                                           encoding='utf-8')
            of.setLevel(logging.DEBUG)
            of.setFormatter(self.formatter)
            self.write_log.addHandler(of)
            self.write_log.debug('日志写入模块初始化成功!')

    def __terminal_file_logger(self):
        """输出到终端，并继承写入行为"""
        self.terminal_log = logging.getLogger('%s.%s' % (self.log_name, 'terminal'))
        ot = logging.StreamHandler()
        ot.setLevel(self.terminal_level)
        ot.setFormatter(self.formatter)
        if self.log_output_terminal:
            self.terminal_log.addHandler(ot)
            self.terminal_log.debug('日志终端输出模块初始化成功')
            if not self.Rotating:
                self.terminal_log.error('因为没有写入权限，日志无法写入到文件')

    @property
    def get_logger(self):
        return self.terminal_log


def ping(*args, host: str, lasting=False, count=5, interval=30, logs=None):
    """
    :param host: 主机ip
    :param lasting: 保持连续ping
    :param count: 每次ping包数， lasting为True时无效
    :param interval: ping间隔，lasting为True时无效
    :return: 
    """
    if logs is None:
        logs = logging

    th_name = threading.Thread.getName(threading.current_thread())

    def log_mark(msg):
        return 'thread-[%s]: %s' % (th_name, msg)

    encode = getpreferredencoding()
    if 'win' in sys.platform:
        lasting_args = ' -n %s' % count
        if lasting:
            lasting_args = ' -t '
        command = 'ping -w 500 %s %s %s' % (lasting_args, host, ' '.join(args))
    else:
        lasting_args = ' -c %s ' % count
        if lasting:
            lasting_args = ''
        command = 'ping -w 500 %s %s %s' % (lasting_args, host, ' '.join(args))

    logs.info(log_mark('command line: ' + command))

    def run():
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        # 实时读取stdout

        with proc.stdout:
            for line in iter(proc.stdout.readline, b''):
                logs.debug(log_mark(line.decode(encode).strip()))
        proc.wait()
        return proc.returncode

    if not lasting:
        while True:
            result = run()
            logs.info(log_mark('本次结果: %s' % result))
            logs.info('%s' % ('-' * 30))
            time.sleep(interval)
    else:
        run()


class MuThread(threading.Thread):
    def __init__(self, *args,  **kwargs):
        super(MuThread, self).__init__()
        self.kwargs = kwargs
        self.args = args

    def run(self):
        ping(*self.args, **self.kwargs)


def process(ip: str, *args, **kwargs):
    ip_list = ip.split()
    thread_pool = []

    for ip in ip_list:
        L = Logger(log_name=ip)
        log = L.get_logger

        th = MuThread(*args, host=ip, logs=log, **kwargs)
        th.setName(ip)
        th.start()
        thread_pool.append(th)

    print('record running...')
    for th in thread_pool:
        th.join()


if __name__ == '__main__':
    """
    : lasting: True/False 保持连续ping
    : count: ini 每次ping的包数， lasting为 True 时无效
    : interval: int ping间隔，lasting为 True 时无效
    : 可传入更多ping原始参数
    """
    process(monitor_ip,  '-a', lasting=False)
