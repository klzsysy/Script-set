#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import time
import win32file
import win32con
import threading
import configparser
import logging
import sys
import subprocess
import re
from email.header import Header
from email.mime.text import MIMEText
from email.utils import parseaddr, formataddr
import smtplib
__author__ = 'Sonny Yang'

config = configparser.RawConfigParser()
try:
    config.read('config.conf', encoding='utf-8-sig')
    topsmain = config['default']
    od = config["Operation detection"]
    email = config["email"]
except Exception as err:
    raise OSError('配置文件致命错误，请检查配置文件是否存在以及正确配置')

# 检测间隔
interval = topsmain.get('interval', 60)
try:
    interval = int(interval)
except Exception:
    interval = 60

# 检测目标目录
detection_path = topsmain.get('detection_path', r'C:\Users')
# 是否打开日志
enable_log = topsmain.getboolean('enable_log', False)
#
enable_debug_stream = topsmain.getboolean('enable_debug_stream', False)
# 日志路径
log_path = topsmain.get('log_path', '.')
# 日志文件名
log_name = topsmain.get('log_name', 'log.txt')
# 判定结果文件路径
result_path = topsmain.get('result_path', '.')
# 判定结果文件名
result_filename = topsmain.get('result_file', 'result.txt')
only_one_process = topsmain.getboolean('only_one_process', True)

'''判定并处理输入的路径'''
path_list = [detection_path, log_path, result_path]
for x in path_list:
    if x == '.':
        path_list[path_list.index(x)] = os.getcwd()
        continue
    path_list[path_list.index(x)] = os.path.expandvars(x)   # 展开环境变量
    if not os.path.exists(os.path.expandvars(x)):           # 判定是否为目录 如果不是尝试创建 失败则设置为当前
        raise IOError('路径不存在:%s' % os.path.expandvars(x))

detection_path, log_path, result_path = path_list[0], path_list[1], path_list[2]
result_file_path = os.path.join(result_path, result_filename)

if detection_path == os.getcwd():
    raise OSError('检测目录不能为自身所在目录，请先修改配置文件中的 detection_path ')

Enable = od.getboolean('Enable', fallback=False)
Enable_sub = {}
Enable_sub['Created'] = od.getboolean('Created', False)
Enable_sub['Deleted'] = od.getboolean('Deleted', False)
Enable_sub['Updated'] = od.getboolean('Updated', False)
Enable_sub['Renamed from something'] = od.getboolean('Renamed_from_something', False)
Enable_sub['Renamed to something'] = od.getboolean('Renamed_to_something', False)
Enable_sub['Unknown'] = od.getboolean('Unknown_Operation', False)

mail_enable = email.getboolean('enable', False)
mail_to_addr = email.get('to_addr')
mail_from_addr = email.get('from_addr')
mail_theme = email.get('mail_theme')
mail_server = email.get('server')
mail_server_port = int(email.get('server_port', 25))
mail_username = email.get('username')
mail_username_aliases = email.get('username_aliases')
mail_password = email.get('password')
mail_flip_logic = email.getboolean('flip_logic', False)
mail_default_text = email.get('default_text', 'default_text读取错误')


def __init_logs():
    formatstr = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    logs = logging.getLogger('log')
    if enable_log:
        logs.setLevel(logging.DEBUG)
        log_name_path = os.path.join(log_path, log_name)
        out_file = logging.FileHandler(filename=log_name_path, encoding='utf8')
        out_file.setLevel(logging.DEBUG)
        out_file.setFormatter(formatstr)
        logs.addHandler(out_file)
    else:
        logs.setLevel(logging.CRITICAL)

    if enable_debug_stream:
        debug_handler = logging.StreamHandler()
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(formatstr)

        logs.addHandler(debug_handler)

    logs.info('初始化完成')
    logs.debug('detection_path = %s ' % detection_path)
    logs.debug('interval = %d' % interval)
    logs.debug('enable_log = %s' % enable_log)
    logs.debug('log_path = %s' % log_path)
    logs.debug('log_name = %s' % log_name)
    logs.debug('result_path = %s' % result_path)
    logs.debug('detection_path = %s' % detection_path)
    logs.debug('result_file = %s' % result_file_path)
    return logs


# def created_configure():
#     # config.add_section('main')
#     config.set('default', 'detection_path', '.')
#     config.set('default', 'interval', '60')
#     config.set('default', 'enable_log', 'False')
#     config.set('default', 'log_path', '.')
#     config.set('default', 'log_name', 'log.txt')
#     config.set('default', 'result_path', '.')
#
#     # config.add_section('Operation detection')
#     config.set('Operation detection', 'Enable', 'False')
#     config.set('Operation detection', 'Created', 'True')
#     config.set('Operation detection', 'Deleted', 'True')
#     config.set('Operation detection', 'Updated', 'True')
#     config.set('Operation detection', 'Renamed from something', 'True')
#     config.set('Operation detection', 'Renamed to something', 'True')
#     config.set('Operation detection', 'Unknown Operation', 'True')
#     with open('config.conf', 'w') as configfile:
#         config.write(configfile)
# created_configure()

path_to_watch = detection_path

class main(object):
    def __init__(self):
        self.temp = False
        self.s_time = time.time()
        self.d_time = interval
        self.ACTIONS = {
            1: "Created",
            2: "Deleted",
            3: "Updated",
            4: "Renamed from something",
            5: "Renamed to something"
        }
        self.FILE_LIST_DIRECTORY = win32con.GENERIC_READ | win32con.GENERIC_WRITE
        try:
            self.hDir = win32file.CreateFile(
                path_to_watch,
                self.FILE_LIST_DIRECTORY,
                win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
                None,
                win32con.OPEN_EXISTING,
                win32con.FILE_FLAG_BACKUP_SEMANTICS,
                None
            )
        except Exception:
            event.error('Handle to the directory to be monitored. This'
                        ' directory must be opened with the FILE_LIST_DIRECTORY access right')
            event.error('监控目标文件夹的权限不足，无法继续')
            sys.exit()

    def __status(self):
        Stat = {
                "Created": [],
                "Deleted": [],
                "Updated": [],
                "Renamed from something": [],
                "Renamed to something": [],
                "Unknown": []
            }
        return Stat

    def monitor_th(self):
        while True:
            results = win32file.ReadDirectoryChangesW(
                                                   self.hDir,  #handle: Handle to the directory to be monitored. This directory must be opened with the FILE_LIST_DIRECTORY access right.
                                                   1024,  #size: Size of the buffer to allocate for the results.
                                                   True,  #bWatchSubtree: Specifies whether the ReadDirectoryChangesW function will monitor the directory or the directory tree.
                                                   win32con.FILE_NOTIFY_CHANGE_FILE_NAME |
                                                    win32con.FILE_NOTIFY_CHANGE_DIR_NAME |
                                                    win32con.FILE_NOTIFY_CHANGE_ATTRIBUTES |
                                                    win32con.FILE_NOTIFY_CHANGE_SIZE |
                                                    win32con.FILE_NOTIFY_CHANGE_LAST_WRITE |
                                                    win32con.FILE_NOTIFY_CHANGE_SECURITY,
                                                   None,
                                                   None)
            # 子进程将处于阻塞状态 直到目标发生变化
            for action, file in results:
                full_filename = os.path.join(path_to_watch, file)
                event.debug([full_filename, self.ACTIONS.get(action, "Unknown")])
                self.ACTIONS_Status[self.ACTIONS.get(action, "Unknown")].append(full_filename)
                self.temp = True

    def start_run(self):
        self.ACTIONS_Status = self.__status()
        # 开始子进程
        T = threading.Thread(target=self.monitor_th, args=())
        T.daemon = True        # 主进程结束时子进程也强行退出
        T.start()

        mail_text = mail_default_text
        self.wrfile('default=True')
        event.debug('初始化结果为true')
        while True:
            time.sleep(self.d_time)
            # 拷贝一份当前状态
            ACTIONS_Status = self.ACTIONS_Status
            self.ACTIONS_Status = self.__status()

            if self.temp:
                self.wrfile('default=True')
                event.info('写入状态为True')
            else:
                self.wrfile('default=False')
                event.info('写入状态为False')

            text = ''
            for x in ACTIONS_Status.items():
                if Enable_sub[x[0]]:
                    for xx in x[1]:
                        if Enable:
                            event.info('写入结果: %s=%s' % (x[0], xx))
                            self.wrfile('\n%s=%s' % (x[0], xx), 'a')
                        text += ('%s=%s\n' % (x[0], xx))
                    x[1].clear()
            mail_text = text

            if mail_enable:
                # 正常邮件触发逻辑
                if not self.temp and not mail_flip_logic:
                    seed_email(mail_default_text, mail_theme)
                    event.debug('正常正常邮件触发逻辑')
                # 反转逻辑
                if self.temp and mail_flip_logic:
                    seed_email(mail_text, mail_theme)
                    mail_text = mail_default_text
                    event.debug('反转逻辑')

            self.temp = False           # 重置
            event.debug('等待...')

    def wrfile(self, text, MODE='w'):
        with open(result_file_path, mode=MODE, encoding='utf8') as ch:
                ch.write(text)


def check_esxit(process_name, enable):
    if not enable:
        return 0
    if os.path.isfile(process_name):
        process_name = os.path.split(process_name)[1]
    process = subprocess.Popen(['tasklist', '|', 'findstr',
                                process_name], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.wait()
    p = process.communicate()[0].decode()
    if len(re.findall(process_name, p)) > 1:
        raise OSError('同名进程已在运行 %s' % process_name)


def seed_email(text, title):
    def _format_addr(s):
        name, addr = parseaddr(s)
        return formataddr((Header(name, 'utf-8').encode(), addr))

    from_addr = mail_from_addr
    password = mail_password
    to_addr = mail_to_addr
    smtp_server = mail_server
    aliases = mail_username_aliases
    port = mail_server_port

    msg = MIMEText('%s' % text, 'plain', 'utf-8')
    msg['From'] = _format_addr('%s <%s>' % (aliases, from_addr))
    msg['To'] = to_addr
    msg['Subject'] = Header('%s' % title, 'utf-8').encode()
    event.debug("mail subject:%s" % title)
    event.debug("构建邮件完成，尝试发送邮件...")
    try:
        server = smtplib.SMTP(smtp_server, port)
        # server.set_debuglevel(1)
        event.debug("开始登录到smtp服务器")
        server.login(from_addr, password)
        event.debug("登录到SMTP服务器成功开始发送邮件")
        server.sendmail(from_addr, [to_addr], msg.as_string())
        server.quit()
    except smtplib.SMTPAuthenticationError:
        event.error("登录到smtp服务器失败！")
    except Exception as err:
        event.warning("邮件发送失败！ Error info:%s" % str(err))
    else:
        event.info("邮件已成功发送到%s" % to_addr)

if __name__ == '__main__':
    check_esxit(sys.argv[0], only_one_process)
    event = __init_logs()
    m = main()
    m.start_run()