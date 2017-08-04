#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 一个文件复制工具
import os
import hashlib
import logging
import logging.handlers
import subprocess
import time
import re
import sys
import threading
import shutil
import smtplib
import locale
from email import encoders
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.utils import parseaddr, formataddr
__author__ = 'Sonny Yang'

# -------------------------- 自定义配置区域 开始  -------------------
# """ 源路径配置 """
source_path = r'F:\PC CC\Adobe_Photoshop_CC_64Bit'
# 账号密码可选
source_user = ''
source_password = ''
# """ 目标路径配置"""
target_path = r'\\172.16.10.4\inetpub\wwwroot'
target_user = 'administrator'
target_password = 'dev.5566'
#
include_subdirectory = True     # 是否包含子目录，否为 False
# 要复制的文件名，为Perl风格的正则表达式, 如只要jar为'^.+\.jar$'
# 只要没有后缀名的 '^[^.]+$',
# 只要jar和py类型为 '^.+\.(jar|py)$'
# 任意为 '^.+$',
# 均不区分大小写
include_file_type = '^.+$'

include_min_size = 0            # 最小文件大小，单位kB , 1M=1024KB
include_max_size = -1           # 最大文件大小，负数为不限制

# 要排除的内容，排除优先与包含
exclude_folder = ''             # 排除目录, 排除目录的子目录也将排除
exclude_file_type = ''          # 排除文件类型，Perl风格的正则表达式
exclude_file = ''               # 完整文件名，不区分大小写

# n/minute
time_limit_on = True           # 开启关闭时间限定
time_limit = 24 * 60            # 限定文件修改的时间范围，单位分钟

# 复制前清空目标目录下的文件，不包含文件夹
emptied = True

# 日志配置
log_output_file = True          # 保存到文件
log_output_terminal = True      # 输出到屏幕
# 其它
keep_directory_tree = True      # 保持目录结构，False将所有源文件复制到目标根目录，重名的文件将被重命名

# 邮件配置
email = False                    # 开启邮件通知功能
variable = {
    # email parameter
    'smtp_server': 'smtp.exmail.qq.com',
    'from_address': 'x.x@xx.cn',
    'password': 'xxxxxx',
    # 收件人信息
    'to_address': 'x.xx@xxx.cn',
    'cc_address': '',
    'mail_text': 'Scripts Program exec complete ',
    'title': '脚本程序已运行'
}

# ----------------------------- 自定义配置区域 结束 -------------------------------------


class Public(object):
    system_code = locale.getpreferredencoding()
    system_plat = sys.platform


class Logger(object):
    def __init__(self):
        self.log_stats = True
        self.formatter = logging.Formatter('%(asctime)s - %(levelname)-7s : %(message)s')
        try:
            if not os.path.exists(os.path.join(os.getcwd(), 'logs')):
                os.mkdir('logs')
        except Exception:
            self.log_stats = False

        self.__write_file_logger()
        self.__terminal_file_logger()

    def __write_file_logger(self):
        """只写入文件"""
        self.write_log = logging.getLogger('file')
        self.write_log.setLevel(logging.DEBUG)
        if self.log_stats and log_output_file:
            of = logging.handlers.RotatingFileHandler("logs\\%s.log" % str('run_log'), mode='a',
                                                      maxBytes=1024 * 1024 * 10, backupCount=10)
            of.setLevel(logging.DEBUG)
            of.setFormatter(self.formatter)
            self.write_log.addHandler(of)
            self.write_log.debug('日志写入模块初始化成功!')

    def __terminal_file_logger(self):
        """输出到终端，并继承写入行为"""
        self.terminal_log = logging.getLogger('file.terminal')
        ot = logging.StreamHandler()
        ot.setLevel(logging.DEBUG)
        ot.setFormatter(self.formatter)
        if log_output_terminal:
            self.terminal_log.addHandler(ot)
            self.terminal_log.debug('日志终端输出模块初始化成功')
            if not self.log_stats:
                self.terminal_log.error('因为没有写入权限，日志无法写入到文件')

    def get_logger(self):
        return self.terminal_log


def emptied_folder(path):
    """清空目录下的文件，不包含文件夹"""
    for file in os.listdir(path):
        file = os.path.join(path, file)
        if os.path.isfile(file):
            os.remove(file)


class GETFILE(object):
    def __init__(self):
        self.__curr_time = time.time()
        self.final_copy_list = {}
        self.__make_file_list()

    def __time_filter(self, path, file):
        if not time_limit_on:
            return True
        file_mtime = os.path.getmtime(os.path.join(path, file))
        if self.__curr_time - (time_limit * 60) < file_mtime:
            return True
        else:
            return False

    @staticmethod
    def __size_filter(path, file):
        file_size = os.path.getsize(os.path.join(path, file))
        if include_max_size > 0:
            if include_max_size > file_size > include_min_size:
                return True
            else:
                return False
        else:
            if file_size > include_min_size:
                return True
            else:
                return False

    @staticmethod
    def __type_filter(file):
        if re.match(include_file_type, file, re.I):
            return True
        else:
            return False

    @staticmethod
    def __exclude_property(path='', file=''):
        if file != '' and exclude_file_type != '':
            if re.match(exclude_file_type, file, re.I):
                return False
        if path != '' and exclude_folder != '':
            if re.search('^%s' % exclude_folder, path, re.I):
                return False
        if file != '' and exclude_file.upper() == file.upper():
            return False
        return True

    def __make_file_list(self):
        for root, dirs, files in os.walk(source_path):
            if not self.__exclude_property(path=root):
                continue                                        # 被排除的目录
            for file in files:
                if not self.__exclude_property(file=file):
                    continue                                    # 被排除的文件
                if not self.__time_filter(root, file):
                    continue                                    # 时间限定
                if not self.__size_filter(root, file):
                    continue                                    # 大小限定
                if not self.__type_filter(file):
                    continue                                    # 类型限定

                src_file_full_path = os.path.join(root, file)

                if keep_directory_tree:                         # 保持目录结构
                    # 复制目的地的目标路径
                    dst_file_path = os.path.join(target_path, root.split(source_path)[-1].strip('\\'))
                    dst_file_path = dst_file_path.rstrip('\\') + '\\'

                    dst_file_full_path = os.path.join(dst_file_path, file)

                else:
                    dst_file_path = target_path
                    dst_file_full_path = os.path.join(target_path, file)
                    count = 0

                    def check(name, count):
                        """处理可能文件名重名的问题"""
                        test_name = name
                        a = '.'.join(test_name.split('.')[:-1])
                        b = test_name.split('.')[-1]
                        while True:
                            for key, value in self.final_copy_list.items():
                                if value[-1] == test_name:
                                    test_name = a + ' - %s.' % str(count) + b
                                    count += 1
                                    break
                            else:
                                return test_name
                    dst_file_full_path = check(dst_file_full_path, count)

                self.final_copy_list[src_file_full_path] = [dst_file_path, dst_file_full_path]

            if not include_subdirectory:
                break                                           # 不包含子目录 一次后跳出

    @property
    def get_result(self):
        return self.final_copy_list


class CHECK_PATH(object):
    def __init__(self):
        self.__connect_stats = []
        self.dst_user = target_user
        self.dst_password = target_password
        self.src_user = source_user
        self.src_password = source_password
        self.__connect()
        self._write_check()

    def __connect(self):
        for path, user, password in zip([target_path, source_path], [self.dst_user, self.src_user],
                                        [self.dst_password, self.src_password]):

            if re.match(r'^\\\\', path) and user != "":
                logs.info('尝试登陆 %s ...' % path)
                if re.match(r'^(\\\\\S+?\\\w\$)', path):
                    command = r'net use %s %s /user:%s' % (re.match(r'^(\\\\\S+?\\\w\$)', path).group(), password, user)
                else:
                    command = r'net use %s %s /user:%s' % (re.match(r'^(\\\\\S+?\\)', path).group(), password, user)

                proc = subprocess.Popen(command, stderr=subprocess.PIPE)
                code = proc.wait()
                if code != 0:
                    if Public.system_plat == 'win32':
                        logs.debug(str(proc.stderr.read(), encoding=Public.system_code).replace('\r\n', ' '))
                    else:
                        logs.debug(str(proc.stderr.read(), encoding=Public.system_code).replace('\n', ' '))
                    logs.error('无法登录到路径 %s ' % path)
                    sys.exit(-1)
                else:
                    logs.info('登陆成功: %s' % path)
                    if self.__dir_check(path):
                        self.__connect_stats.append(path)
                    else:
                        sys.exit(-1)
            else:
                if self.__dir_check(path):
                    self.__connect_stats.append(path)
                else:
                    logs.critical('无法连接到路径 %s ' % path)
                    sys.exit(-1)

    def __dir_check(self, path):
        if os.path.exists(path):
            return True
        else:
            try:
                os.makedirs(path)
            except BaseException as err:
                logs.critical('%s ,不存在且无法创建' % err)
                return False
            else:
                return True

    @staticmethod
    def _write_check():
        try:
            with open(os.path.join(target_path, 'test'), 'w') as f:
                f.write('write.test')
        except PermissionError as err:
            logs.critical('没有权限写入目标路径，程序结束\n%s' % str(err))
            sys.exit(-1)
        except FileNotFoundError as err:
            logs.critical(' 目标路径不存在，程序结束\n%s' % str(err))
            sys.exit(-1)
        else:
            try:
                os.remove(os.path.join(target_path, 'test'))
            except BaseException:
                pass

    def dis_connect(self):
        for path in self.__connect_stats:
            os.system(r'net use %s /delete' % path)


class MD5(object):
    def __init__(self, copy_list):
        self.compared_result = {}
        self.compared_list = {}
        self.src_md5 = {}
        self.dst_md5 = {}
        self.raw = copy_list

        self.__pre_process()

    def __pre_process(self):
        """处理成字典 {src:dst}"""
        for key, value in self.raw.items():
            self.compared_list[key] = value[-1]

    @staticmethod
    def __run_file_md5(file):
        m = hashlib.md5()
        with open(file, 'rb') as f:
            while True:
                data = f.read(10240000)
                if not data:
                    break
                m.update(data)
        return m.hexdigest()

    def make_src_md5(self):
        logs.debug('计算源文件md5...')
        for f_list in self.compared_list.keys():
            self.src_md5[f_list] = self.__run_file_md5(f_list)

    def make_dst_md5(self):
        logs.debug(' ----------------------开始计算md5---------------------')
        for dst in self.compared_list.values():
            try:
                md5_text = self.__run_file_md5(dst)
                self.dst_md5[dst] = md5_text
            except FileNotFoundError:
                self.dst_md5[dst] = '0000000000'              # 目标文件不存在
            else:
                logs.debug('file md5 %s = %s' % (dst, md5_text))
        self.__compared_md5()

    def __compared_md5(self):
        for src, dst in self.compared_list.items():
            if self.src_md5[src] == self.dst_md5[dst]:
                logs.debug('OK! Check through, src file %s, dst file %s,  %s = %s' %
                           (src, dst, self.src_md5[src], self.dst_md5[dst]))
                self.compared_result[src] = True
            else:
                logs.debug('ERROR! Check Fail, src file %s, dst file %s, %s != %s' %
                           (src, dst, self.src_md5[src], self.dst_md5[dst]))
                self.compared_result[src] = False

    @property
    def get_result(self):
        return self.compared_result


class COPYFILE(Public):
    def __init__(self, copy_list):
        self.err_log = {}
        self.final_copy_list = copy_list
        if 'win32' == Public.system_plat:
            self.__copy_file_windows()
        else:
            self.__copy_file()

    def __copy_file_windows(self):
        for src, dst in self.final_copy_list.items():
            command = 'xcopy "%s" "%s" /C /R /I /Y' % (src, dst[0])
            proc = subprocess.Popen(command,  bufsize=-1, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            recode = proc.wait()

            stdout = str(proc.stdout.read(), encoding=Public.system_code).replace('\r\n', ' ')
            errout = str(proc.stderr.read(), encoding=Public.system_code)
            logs.debug('OK! file: %s , stdout: %s' % (src, stdout))
            if recode != 0:
                self.err_log[src] = errout
                logs.error('ERROR! file %s is error: %s' % (src, errout))

    def __copy_file(self):
        for src, dst in self.final_copy_list.items():
            if not os.path.exists(dst[0]):
                try:
                    os.makedirs(dst[0])
                except BaseException as err:
                    logs.error('目标路径 %s 无法创建:%s , 文件 %s 停止复制。' % (dst[0], str(err), src))
                    continue
            logs.debug('copy source file %s to %s' % (src, shutil.copy2(src=src, dst=dst[0])))


class Send_Mail(object):
    def __init__(self, text=variable['mail_text'], filename='', title=variable['title']):
        # 发件人
        self.from_addr = variable['from_address']
        # 发件人密码
        self.password = variable['password']
        # 收件人列表
        self.to_addr = [x.strip() for x in variable['to_address'].split(';')]
        self.Cc_addr = [x.strip() for x in variable['cc_address'].split(';')]
        # 邮件主题
        self.mail_title = title
        self.smtp_server = variable['smtp_server']
        self.mail_text = text
        self.filename = filename

    @staticmethod
    def __format_addr(s):
        name, addr = parseaddr(s)
        return formataddr((Header(name, 'utf-8').encode(), addr))

    def __sendmail(self):
        self.msg = MIMEMultipart()
        self.msg.attach(MIMEText('%s' % self.mail_text, 'plain', 'utf-8'))

        self.msg['From'] = self.__format_addr('Python Program <%s>' % self.from_addr)
        self.msg['To'] = ';'.join(self.to_addr)
        self.msg['Cc'] = ';'.join(self.Cc_addr)
        self.msg['Subject'] = Header(self.mail_title, 'utf-8').encode()

        self.mime = MIMEBase('text', 'xlsx', filename=os.path.split(self.filename)[-1])
        self.mime.add_header('Content-Disposition', 'attachment', filename=os.path.split(self.filename)[-1])
        self.mime.add_header('Content-ID', '<0>')
        self.mime.add_header('X-Attachment-Id', '0')
        if os.path.isfile(self.filename):
            with open(self.filename, 'rb') as f:
                logs.debug('开始读取附件...')
                self.mime.set_payload(f.read())
            encoders.encode_base64(self.mime)
            self.msg.attach(self.mime)
        try:
            logs.info("开始解析邮件服务器信息")
            server = smtplib.SMTP_SSL(self.smtp_server, 465)
            # server.set_debuglevel(1)
            logs.info("开始登录到smtp服务器")
            server.login(self.from_addr, self.password)
            logs.info("登录到SMTP服务器成功开始发送邮件")
            server.sendmail(self.from_addr, self.to_addr, self.msg.as_string())
            server.close()
        except smtplib.SMTPAuthenticationError:
            logs.error("登录到smtp服务器失败, 无法发送邮件")
        except Exception as err:
            logs.error('邮件发送失败\nError:\n' + str(err) + '\n\nHeader:\n' + self.msg.as_string())
        else:
            logs.info("邮件已成功发送到%s" % self.to_addr)

    def send(self):
        self.__sendmail()


class RESULT(object):
    def __init__(self, compared_result, attached):
        self.fail_list = []
        self.success_list = []
        self.attached = attached
        self.compared_result = compared_result
        # self.err_log = err_log
        self.__check_fail()
        self.__show_fail()

    def __check_fail(self):
        logs.debug('--------------# check copy result ----------')
        for file, result in self.compared_result.items():
            if result:
                self.success_list.append(file)
            else:
                self.fail_list.append(file)

    def __show_fail(self):
        if len(self.fail_list) == 0:
            logs.info('所有复制已完成，没有错误信息，校验通过！')
        else:
            for file in self.fail_list:
                logs.error('Source File %s Md5 Check fail!  ' % file)

    def send_mail(self):
        """构建邮件内容"""
        if not email:
            return 0
        title = variable['title']
        if len(self.fail_list) != 0:
            mail_text = '文件复制中出现错误!\n'
            for file in self.fail_list:
                mail_text += '文件MD5校验失败，请检查。 from  %s\n' % file
            # for filename, err in self.err_log.items():
            #     mail_text = mail_text + '错误信息: %s %s\n' % (filename, err)
            mail_text = mail_text + self.attached
            title += '，但出现了错误！'
        else:
            mail_text = '所有复制已完成，没有错误信息，校验通过！\n' + self.attached
            title += ', 并正确完成'

        mail = Send_Mail(text=mail_text, title=title)
        mail.send()

    def delete_fail_file(self):
        pass


def main_process():
    start = time.time()
    # 检查源于目标路径
    check_path = CHECK_PATH()
    # 确定要复制的文件
    get_file = GETFILE()
    copy_file_list = get_file.get_result
    #
    if emptied:
        emptied_folder(target_path)
    # 计算源文件md5
    md5 = MD5(copy_file_list)
    # 多线程处理
    make_md5 = threading.Thread(target=md5.make_src_md5, args=())
    make_copy = threading.Thread(target=COPYFILE, args=(copy_file_list, ))
    make_md5.start()
    make_copy.start()
    make_md5.join()
    make_copy.join()
    # 单线程
    # md5.make_src_md5()
    # COPYFILE(copy_file_list)

    md5.make_dst_md5()
    md5_result = md5.get_result

    end = time.time()
    check_path.dis_connect()
    use_time = '本次用时 %.2f s' % (end - start)
    logs.debug(use_time)
    result_process = RESULT(md5_result, use_time)
    # 后续邮件
    result_process.send_mail()


if __name__ == '__main__':
    logger = Logger()
    logs = logger.get_logger()
    main_process()

