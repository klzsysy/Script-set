# -*- coding: utf-8 -*-
__author__ = 'Sonny Yang'
import os
import subprocess
from os.path import join, getsize
import smtplib
from email.mime.text import MIMEText
import time
import datetime

# ----------------------------------------------------------------------
# 定义复制源于目标路径 , 网络路径双\\  本地路径单\

soulist1 = [r'\\10.8.10.18\\AutoWork_data',
            r'\\10.8.10.18\\drivers',
            r'\\10.8.10.18\\IT部',
            r'\\10.8.10.18\\Tools',
            r'\\10.8.10.18\\财务部',
            r'\\10.8.10.18\\董事会办公室',
            r'\\10.8.10.18\\风险管理部',
            r'\\10.8.10.18\\公司文档',
            r'\\10.8.10.18\\供应链金融部',
            r'\\10.8.10.18\\进出口部',
            r'\\10.8.10.18\\客服部',
            r'\\10.8.10.18\\人事部',
            r'\\10.8.10.18\\市场部',
            r'\\10.8.10.18\\数据暂存区',
            r'\\10.8.10.18\\数据组专用（mapics）',
            r'\\10.8.10.18\\丝印组',
            r'\\10.8.10.18\\物业安全部',
            r'\\10.8.10.18\\员工关系部',
            r'\\10.8.10.18\\相册专区',
            r'\\10.8.10.18\\运输组',
            r'\\10.8.10.18\\总经办',
            r'\\10.8.10.18\\运作部'
            ]
soulist2 = [r'\\10.8.10.18\\运作部']
target1 = r'''e:'''  # 目标 1
target2 = r'''f:'''  # 目标 2
mailto_list = ["xxxxx@xxx.com.cn", "xxx@live.com", "xxx@x.com.cn"]
log = []
err = []

# -------------------------------------------------------------------------
def copyfile(sou, target, start):
    errinfo = None
    try:
        logfile = open('%s\\log\\backup_file_log-%s.txt' % (os.getcwd(), start), mode='a')
    except Exception:
        print('无法保存日志，即将退出！')
        return 'LOGERROR'
    else:
        for soutemp in sou:
            print('复制中......................\n')
            command = "xcopy %s %s /S /C /R /I /D /Y /O" % (soutemp, target[sou.index(soutemp)])
            proc = subprocess.Popen(command, bufsize=-1, shell=False, stdout=logfile, stderr=subprocess.PIPE)
            proc.wait()
            errinfo = proc.stderr.read()
            if errinfo:
                errinfo = str(errinfo, encoding='gbk')
                print('错误:' + errinfo)
                logfile.write(errinfo)
        logfile.close()
        return errinfo


def filter_srt(liststr):  # 过滤无效的源路径
    global err
    temp_str = []
    for temp in liststr:
        if not os.path.exists(temp):
            err.append('找不到路径: %s ' % temp)
            print('找不到路径: %s ' % temp)
            temp_str.append(temp)
    for x in temp_str:
        liststr.remove(x)

def targetconver(slist):  # 取出要copy的源文件夹的名字
    targetname = []
    for temp2 in slist:
        namere = temp2.split('\\')
        targetname.append(namere[-1])
    return targetname

def targetlist(sources, target_fold, converlist):  # 组合成目标路径
    target = []
    x = 0
    for temp in converlist:
        target.append(target_fold + '\\' + temp)
        x += 1
    return target, sources

def getdirsize(dir):  # 获取文件夹大小
    i = dir.split('\\')[-1]
    print('开始计算文件夹 %s 大小.....' % i)
    size = 0
    for root, dirs, files in os.walk(dir):  # 返回一个3元组 根目录，目录列表，文件列表
        size += sum([getsize(join(root, name)) for name in files])
    log.append("文件夹 {0} 的大小是{1:>{2}.1f} GB\n".format(i, size / 1024 / 1024 / 1024, 50 - len(dir)))
    return (size / 1024 / 1024 / 1024)

def dirsize_total(dir):  # 返回目标文件夹文件名及大小信息的元组
    total_size = []
    for i in dir:
        size = getdirsize(i)
        fold_name = i.split('\\')[-1]
        total_size.append(('{0}{1:->{2}.2f} GB'.format(fold_name, size, 50 - len(fold_name))))  # 组合成元组
    return total_size

def disk_size(p):  # 获取分区大小
    print("开始获取分区大小...")
    try:
        part = subprocess.check_output("wmic LogicalDisk where " + "Caption='%s:'" % p + " get FreeSpace,Size /value")
    except Exception:
        return 0, 0
    else:
        try:
            part = str(part, encoding='utf-8')
            part = part.strip()
            FreeSpace = (part[0:part.index('\r')])
            Partsize = part[part.index('Size'):]
            FreeSpace = int(FreeSpace[FreeSpace.index('=') + 1:]) / 1024 / 1024 / 1024  # 算出大小 单位Gb
            Partsize = int(Partsize[Partsize.index('=') + 1:]) / 1024 / 1024 / 1024
            print("获取结束")
        except Exception:
            return 0, 0
        else:
            return FreeSpace, Partsize

def mail(number, error, fold_size, part_size, copy_time):  # 发送邮件
    to_emailaddress = []
    if time_point:
        Morning_Afternoon = "首次"
        for x in mailto_list[1:]:
            to_emailaddress.append(x)
    else:
        Morning_Afternoon = "第二次"
        for x in mailto_list[0:2]:
            to_emailaddress.append(x)
    error_str = ''
    fold_size_str = str()
    mail_host = "smtp.ish.com.cn"
    mail_user = "it_yangsy"
    mail_pass = "xxxxxxx"
    mail_postfix = "ish.com.cn"
    sub_info = ['并正确完成',
                '但出现了一些错误',
                '但出现严重错误']
    mail_sub = '文件服务器每日%s备份已按计划执行，%s' % (Morning_Afternoon, sub_info[number])

    mail_info = ["<p>操作已完成，没有出现错误信息</p>",
                 '<p>任务已完成，但是出现了部分错误，以下是产生的错误信息:<p>',
                 '<p>文件复制已停止。源路径无效或无法保存日志，请检查网络以及目录是否正常<p>']
    for i in error:
        error_str += '<p>' + i + '</p>'
    for f in fold_size:
        fold_size_str += "<p>%s</p>" % f
    mail_msg = "%s %s</p>*********************************************************</p><p>" \
               "磁盘及目录空间</p> %s %s<p></p><>本次运行累计耗时: %s<><p></p>恢复说明:备份服务器为10.8.10.19，E盘数据为每日上午12:00的备份，F盘为晚上22:00开始的备份\n"\
				"如需要恢复数据则找到离删除数据最近的一次备份即可，如早上删除的找昨天晚上的副本，下午删除的找中午的副本." % \
               (mail_info[number], error_str, fold_size_str, part_size, copy_time)

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
            print('邮件发送成功')
            return True, to_emailaddress
        except:
            print('邮件发送失败')
            return False, to_emailaddress
    return send_mail(to_emailaddress, mail_sub, mail_msg)

def local_time():  # 获取当前时间
    now_str = time.strftime("%Y-%m-%d %H-%M-%S")  # 时间字符串
    now = datetime.datetime.now()  # 时间
    day = now_str[0:10]  # 日期X号
    return now, now_str, day

def Use_Time(start, end):  # 计算时间差
    temp_time = (end - start).seconds  # 得到相差 秒
    hours = temp_time // 3600  # 时
    minuts = (temp_time - hours * 3600) // 60  # 分
    second = temp_time - hours * 3600 - minuts * 60  # 秒
    use = "%s Hour %s Min %s Sec" % (hours, minuts, second)
    return use

def end_log(copy_time, start, end, errlog, to_mail_address):  # 写入log和err到文件
    print('开始写入日志文件！')
    to_mail_address_str = ''
    for x in to_mail_address:
        to_mail_address_str += (x + ',')
    to_mail_address_str = to_mail_address_str.rstrip(',')
    if mail_number == True:
        tomail = '邮件已成功发送至: %s' % to_mail_address_str
    else:
        tomail = '邮件发送至 %s 失败！' % to_mail_address_str
    if err != 'LOGERROR':
        logfile = open('%s\\log\\backup_file_log-%s.txt' % (os.getcwd(), start), mode='a')
        logfile.write('\n' + '-' * 75 + '\n')
        if errinfo:
            logfile.writelines('累计的错误信息如下\n')
            for templog in errlog:
                logfile.writelines('错误：%s\n' % templog)
        logfile.write('\nStart: %s \nEnd: %s\n本次运行累计耗时: %s\n%s\n' % (start, end, copy_time, tomail) + '-' * 75)
        logfile.close()

def one_or_to(temptime):
    Hour = int(temptime[11:13])  #读取时间字符串 ‘小时’
    if Hour > 0 and Hour < 12:  #上午的备份
        time_point = True
    else:time_point = False     #否则为下午
    return time_point

if __name__ == '__main__':
    temp = 0
    SIZE = []
    sou = []
    tar = []
    errinfo = []
    Disk_Total_str = ''
    start_time, start_time_str, day_start = local_time()  # 确定任务开始时间
    time_point = one_or_to(start_time_str)      # 得到上下午
    if time_point:
        sou = [soulist1]
        tar = [target1]
    else:
        sou = [soulist1]
        tar = [target2]
    for soulist in sou:     # 可进行多目标路径循环复制
        target = tar[sou.index(soulist)]
        filter_srt(soulist)  # 检查并删除无效的路径
        converre = targetconver(soulist)  # 取出要复制目标文件夹名字
        if len(converre) == 0:
            temp = 2
            # 直接跳过复制部分
        else:
            target_fold, sources_fold = targetlist(soulist, target, converre)  # 组合源文件夹与目标文件夹路径
            err = copyfile(sources_fold, target_fold, start_time_str)  # 复制文件
            print('文件复制结束...')
            SIZE += dirsize_total(target_fold)  # 计算文件夹大小
            if err:
                errinfo.append(err)
                if err == 'LOGERROR':
                    temp = 2
                else:
                    temp = 1
    print('复制任务已结束！\n')
    for disk in tar:
        free, total = disk_size(disk[0])  # 计算分区大小以及剩余空间
        Disk_Total_str += '<p></p><p>分区 {2} 剩余: {0:.2f} GB</p><p>分区 {2} 总计: {1:.2f} GB</p>'.format(free, total, disk[0])
        print(Disk_Total_str)
    print('获取结束时间')
    end_time, end_time_str, day_end = local_time()  # 任务结束时间
    print('计算消耗时间')
    copy_time = Use_Time(start_time, end_time)  # 计算消耗时间
    print('发送邮件')
    mail_number, mail_to = mail(temp, errinfo, SIZE, Disk_Total_str, copy_time)
    '''
    mail()          发送邮件
    temp:           任务完成类型  包含无错完成，出现一些错误，以及没有一个目录正确完成
    err:            错误信息
    SIZE:           文件夹大小
    Disk_Total:     分区空间信息 '''
    end_log(copy_time, start_time_str, end_time_str, errinfo, mail_to)