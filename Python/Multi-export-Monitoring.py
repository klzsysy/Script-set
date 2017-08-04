# -*- coding: utf-8 -*-
import socket
import queue
import sys
import subprocess
import threading
import os
import shlex
import locale
import re
import time
import smtplib
import logging
import logging.handlers
from email.header import Header
from email.mime.text import MIMEText
from email.utils import parseaddr, formataddr


lang = locale.getdefaultlocale()
test_ip_list = ['114.114.114.114', '8.8.8.8', '202.14.67.4']
localhost = socket.gethostbyname(socket.gethostname())
detect_list = ["10.8.10.236", "10.8.10.237", "10.8.10.238", "10.8.10.239", "10.8.10.240", "10.8.10.241", "10.8.10.242"]

DNS = "10.8.10.10"
SLEEP_TIME = 300
LOCK = threading.Lock()

class Check_Network(object):
    def __init__(self):
        self.return_number = {}
        self.log = {}

    def __testing__(self, q):
        ONLY_OF.debug('thread %s is running...' % threading.current_thread().name)
        while True:
            if q.empty():
                break
            target_ip = q.get()
            LOCK.acquire()
            ONLY_OF.debug('thread %s is start....' % threading.current_thread().name)
            ONLY_OF.debug("开始使用网关%s测试目标%s" % (self.sources_gw, target_ip))
            if os.name == 'nt':
                cmd = 'ping -n 4 -w 800 %s' % target_ip
            else:
                cmd = 'ping -c 4 -w 800 %s' % target_ip
            command = shlex.split(cmd)
            ONLY_OF.debug(command)
            LOCK.release()
            ping = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            re_ping = str(ping.stdout.read(), encoding=lang[-1])
            # print(re_ping)
            self.return_number[target_ip] = subprocess.call(cmd, shell=True, stdout=temp_out)
            self.log[target_ip] = re_ping
            q.task_done()
        ONLY_OF.debug('thread %s is ended' % threading.current_thread().name)

    def __count_return_number__(self):
        x1 = False
        for x in self.return_number.values():
            if x == 0:
                x1 = True
        self.return_number.clear()
        return x1

    def __write_log__(self):
        self.stdout_file.info("使用目标网关：%s" % self.sources_gw)
        for x in self.log.items():
            self.stdout_file.info('目标%-10s输出信息如下↓' % x[0])
            self.stdout_file.info(x[1] + '\n' + '-' * 40)
        self.stdout_file.info('本次检测已结束 ' + '%s' % ('*' * 30))

    def run(self, target, sources_gw):
        self.sources_gw = sources_gw
        self.ip_queue = queue.Queue()
        self.stdout_file = gw_logs[sources_gw]
        for ip in target:
            self.ip_queue.put(ip)
        OF_OT.info("使用网关%s开始测试" % self.sources_gw)
        for i in target:
            # 创建一个threading.Thread()的实例，给它一个函数和函数的参数
            run = threading.Thread(target=self.__testing__, args=(self.ip_queue,))
            run.setDaemon(True)                        # 这个True是为worker.start设置的，如果没有设置的话会挂起的，因为check是使用循环实现的
            run.start()                                 # 开始线程的工作
        self.ip_queue.join()                            # 线程队列执行关闭
        self.__write_log__()
        self.log.clear()
        return self.__count_return_number__()


def network_card_info():
    IP, MASK, GW, NAME = None, None, None, None
    temp = False
    eth_sources = subprocess.check_output('ipconfig', shell=True)
    eth_sources = str(eth_sources, encoding=lang[-1])
    ipstr = '([0-9]{1,3}\.){3}[0-9]{1,3}'
    ip_pattern = re.compile(ipstr)
    ipre = re.compile("IPv4.*%s|IP Address.*%s" % (ipstr, ipstr))
    maskre = re.compile("子网掩码.*%s|Subnet Mask.*%s" % (ipstr, ipstr))
    gwre = re.compile("默认网关.*%s|Default Gateway.*%s" % (ipstr, ipstr))
    name_tup = ["以太网适配器(.*)\n","Ethernet adapter(.*)\n", "无线局域网适配器(.*)\n"]
    namere2 = re.compile("虚拟.*|隧道.*|virtual.*|VMware.*|Virtual.*|Bluetooth.*")
    for namere in name_tup:
        try:
            for nameaddr in re.finditer(namere, eth_sources):
                name = nameaddr.group(1)
                if not re.match(namere2, name.strip()):
                    NAME = name.strip().strip(':')
                    temp = eth_sources.index(name)
        except Exception as err:
            OF_OT.error('无法确认网络卡，即将退出!')
            raise ValueError("无法确认网络卡，即将退出!")
    if temp:
        try:
            for ipaddr in re.finditer(ipre, eth_sources[temp:]):
                ip = ip_pattern.search(ipaddr.group())
                if ip.group() != "127.0.0.1":
                    IP = ip.group()
            for maskaddr in re.finditer(maskre, eth_sources[temp:]):
                mask = ip_pattern.search(maskaddr.group())
                MASK = mask.group()
            for gwaddr in re.finditer(gwre, eth_sources[temp:]):
                gw = ip_pattern.search(gwaddr.group())
                GW = gw.group()
        except Exception as err:
            OF_OT.error('获取本机IP信息时失败：%s' % str(err))
        else:
            for x in iter([NAME, IP, MASK, GW]):
                if x is None:
                    OF_OT.error("无法获取正确的IP信息！")
                    raise ValueError("无法获取正确的IP信息")
    else:
        OF_OT('无法确认网络卡!')
        raise ValueError("无法确认网络卡，即将退出!")
    OF_OT.info(['成功获取网络卡信息', NAME, IP, MASK, GW])
    return NAME, IP, MASK, GW


def set_ip(name, ip, mask, gw):
    command = "netsh interface ip set address \"%s\" static %s %s %s 1" % (name, ip, mask, gw)
    set_dns = "netsh interface ip set dns \"%s\" static %s none" % (name, DNS)
    proc = subprocess.call(command, shell=True, stdout=temp_out)
    if proc == 0:
        ONLY_OF.debug(command+":执行成功")
        p = subprocess.Popen(set_dns, shell=True, stdout=temp_out)
        ONLY_OF.debug(set_dns)
        return p
    else:
        return False


def has_admin():
    if os.name == 'nt':
        try:
            # only windows users with admin privileges can read the C:windows	emp
            temp = os.listdir(os.sep.join([os.environ.get('SystemRoot', 'C:\windows'), 'temp']))
        except PermissionError:
            return (os.environ['USERNAME'],False)
        else:
            return (os.environ['USERNAME'],True)
    else:
        print("本工具目前只支持windows!")
        sys.exit()
        # linux function
        # if 'SUDO_USER' in os.environ and os.geteuid() == 0:
        #     return (os.environ['SUDO_USER'],True)
        # else:
        #     return (os.environ['USERNAME'],False)


def seed_email(text, errinfo):
    def _format_addr(s):
        name, addr = parseaddr(s)
        return formataddr((Header(name, 'utf-8').encode(), addr))

    from_addr = 'it_yangsy@ish.com.cn'
    password = "******"
    to_addr = "it_yangsy@ish.com.cn"
    smtp_server = "mail.ish.com.cn"

    msg = MIMEText('%s' % text, 'plain', 'utf-8')
    msg['From'] = _format_addr('网络监控程序 <%s>' % from_addr)
    msg['To'] = to_addr
    msg['Subject'] = Header('线路 %s 发生中断' % errinfo, 'utf-8').encode()
    ONLY_OF.debug("mail subject:线路 %s 发生中断" % errinfo)
    OF_OT.debug("构建邮件完成，尝试发送邮件...")
    try:
        ONLY_OF.debug("开始解析邮件服务器信息")
        server = smtplib.SMTP(smtp_server, 25)
        # server.set_debuglevel(1)
        ONLY_OF.debug("开始登录到smtp服务器")
        server.login(from_addr, password)
        ONLY_OF.debug("登录到SMTP服务器成功开始发送邮件")
        server.sendmail(from_addr, [to_addr], msg.as_string())
        server.quit()
    except smtplib.SMTPAuthenticationError:
        OF_OT.error("登录到smtp服务器失败！")
    except Exception as err:
        OF_OT.info("邮件发送失败！ Error info:%s" % str(err))
    else:
        OF_OT.info("邮件已成功发送到%s" % to_addr)


def has_send_mail(obj):
    t = False
    gw = ''
    for x in obj.items():
        if not x[1]:
            t = True
            gw += x[0] + ';'
    return [t, gw]


class Logger(object):
    def __init__(self):
        self.formatter = logging.Formatter('%(asctime)s - %(levelname)-7s : %(message)s')
        try:
            if not os.path.exists(os.getcwd()+'\\log'):
                os.mkdir('log')
        except Exception as err:
            raise IOError("无法创建日志文件夹!\n%s" % str(err))

    def global_logger(self):
        # 创建一个写入文件又输出到终端的记录实例
        of_ot = logging.getLogger("run_log")
        of_ot.setLevel(logging.DEBUG)
        # 创建一个写入文件的记录实例
        only_of = logging.getLogger("log_all_log")
        only_of.setLevel(logging.DEBUG)
        # 创建一个handler输出到文件
        of = logging.handlers.RotatingFileHandler('log\\info.txt', maxBytes=1024*1024*10, backupCount=5)
        of.setLevel(logging.DEBUG)
        of.setFormatter(self.formatter)
        # 创建一个handler到终端
        ot = logging.StreamHandler()
        ot.setLevel(logging.DEBUG)
        ot.setFormatter(self.formatter)

        of_ot.addHandler(of)
        of_ot.addHandler(ot)

        only_of.addHandler(of)
        try:
            of_ot.info("日志记录模块已成功初始化!")
        except IOError:
            raise IOError("无法写入日志文件!")
        return of_ot, only_of

    def sub_logger(self, name):
        "只写入文件"
        sublog = logging.getLogger(str(name))
        sublog.setLevel(logging.DEBUG)

        of = logging.handlers.RotatingFileHandler("log\\%s.log" % str(name), maxBytes=1024*1024*10, backupCount=2)
        of.setLevel(logging.DEBUG)
        of.setFormatter(self.formatter)

        sublog.addHandler(of)
        return sublog


def build_gw_log(obj):
    logs = {}
    for x in detect_list:
        logs[x] = obj.sub_logger(x)
    return logs


def process():
    GW_dict = {}
    test = Check_Network()
    NAME, IP, MASK, GW = network_card_info()

    # if GW not in detect_list:
    # detect_list.append(GW)
    for gw in detect_list:
        dns_wait = set_ip(NAME, IP, MASK, gw)
        if dns_wait:
            dns_wait.wait()
            time.sleep(5)
            GW_dict[gw] = test.run(test_ip_list, gw)
            # write_log(log, gw)
        else:
            OF_OT.error("修改IP信息失败！")
            raise OSError("修改IP信息失败！")
    return GW_dict

if __name__ == '__main__':
    system_type = has_admin()
    if system_type[-1]:
        gw_logs = {}
        status = {}
        ll = Logger()
        OF_OT, ONLY_OF = ll.global_logger()
        gw_logs = build_gw_log(ll)
        while True:
            temp_out = open("log\\temp.txt", 'w')
            value = process()
            text = ""
            for x in value.items():
                t = "中断"
                if x[1]:
                    t = "正常"
                status[x[0]] = x[1]
                OF_OT.info("线路出口 %-12s is : %s" % (x[0], t))
                text += "线路出口 %-15s is : %s\n" % (x[0], t)
            line_status = has_send_mail(status)
            if line_status[0]:
                OF_OT.warning("检测到网络异常,尝试发送邮件到管理员！")
                seed_email(text, line_status[1])
            else:
                OF_OT.info("本次检测结果一切正常!")
            temp_out.close()
            OF_OT.info("等待进行下一次检测...")
            time.sleep(SLEEP_TIME)
    else:
        print("当前用户 %s 没有管理员权限!\n请切换到管理员用户或以管理员身份运行" % system_type[0])
