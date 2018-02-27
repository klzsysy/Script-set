# -*- coding: utf-8 -*-
__author__ = 'Sonny'
import smtplib
from email.mime.text import MIMEText
import time
import subprocess

mailto_list = ["it_support@ish.com.cn"]
mail_host = "smtp.ish.com.cn"
mail_user = "it_yangsy"
mail_pass = "xxxxx"
mail_postfix = "ish.com.cn"
mail_sub = 'DHCP服务器每日备份已执行'
mail_sub2 = 'DHCP服务器每日备份已执行,但没有成功'
mail_msg = r'''<p>DHCP数据库已备份已完成，数据库已从10.8.10.8拷贝至10.8.10.19</p>
            <p>可访问 \\10.8.10.19\d$\DHCPServer_backup 查看备份数据库文件</p>
            <p>恢复方式：登录到10.8.10.19，打开服务管理器停止DHCP server,删除C:\WINDOWS\System32\dhcp 下的dhcp.mdb和tmp.edb(清除旧数据)</p><p>然后启动dhcp服务，执行netsh dhcp server import X:\XXX.txt all(导入新数据,注意X:\XXX.txt为实际路径)，</p><p>其中xxx.txt为D:\DHCPServer_backup下的最后一个副本,以及可能还需要修改三层交换ip helper-address配置使其指向10.8.10.19</p>'''

def send_mail(to_list, sub, content):  # to_list：收件人；sub：主题；content：邮件内容
    me = "Sonny Yang" + "<" + mail_user + "@" + mail_postfix + ">"
    msg = MIMEText(content, _subtype='html', _charset='gb2312')
    msg['Subject'] = sub
    msg['From'] = me
    msg['To'] = ";".join(to_list)
    try:
        s = smtplib.SMTP()
        s.connect(mail_host)
        s.login(mail_user, mail_pass)
        s.sendmail(me, to_list, msg.as_string())
        s.close()
        return True
    except:
        return False

def backupdhcp(local_time):
    dhcpdatabase = subprocess.call("netsh dhcp server export c:\\dhcp.txt all", shell=True,
                                   stdout=open(r'log.temp', 'w'), stderr=subprocess.STDOUT)
    if dhcpdatabase == 1:
        re = 'error: 导出数据库失败'
        return False, re
    else:
        copy = subprocess.call("copy c:\\dhcp.txt \\\\10.8.10.19\\d$\\DHCPServer_backup\\dhcp%s.txt /Y" % local_time,
                        shell=True, stdout=open(r'log.temp', 'w'), stderr=subprocess.STDOUT)
        if copy == 1:
             re = "error: 数据库文件复制到备份服务器失败"
             return False, re
        return True, None

def MacTime():
    temptime = time.localtime()
    a = str(temptime[0])
    b = str(temptime[1])
    c = str(temptime[2])
    timestr = a + b + c
    return timestr

if __name__ == '__main__':
    re, errorinfo = backupdhcp(MacTime())
    if re:
        if send_mail(mailto_list, mail_sub, mail_msg):
            print("日志邮件发送成功")
        else:
            print("日志邮件发送失败")
    else:
        mail_msg2 = 'DHCP数据库备份失败！ 请检查服务器端！%s' % errorinfo
        if send_mail(mailto_list, mail_sub2, mail_msg2):
            print("日志邮件发送成功")
        else:
            print("日志邮件发送失败")
