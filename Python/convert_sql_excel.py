"""
自动从数据库中抓取的数据生成excel文件并邮件到目标
"""
import pymssql
import xlsxwriter
import time
from email import encoders
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.utils import parseaddr, formataddr
import smtplib
import logging
import os


"""
在此处修改参数
"""
variable = {

    # database parameter
    'host': '127.0.0.1',
    'user': 'sonny',
    'pwd': 'xxx.123',
    'db': 'WuHanPingAnBank',
    # email parameter
    'smtp_server': 'smtp.exmail.qq.com',
    'from_address': 'xx@x.cn',
    'password': 'xxx',
    # 收件人信息
    'to_address': 'xxx@xx.cn',
    'cc_address': '',
    'mail_text': 'The Excel in the attachment is automatically generated by the Python program\n'
                 'from "[WuHanPingAnBank].[dbo].[ApplyLoanInfo]"',
    'title': 'Daily analysis'
}


class init_log():
    """
    初始化日志
    """
    def __init__(self, lev=1, levels='DEBUG'):
        """
        记录日志，输出到控制台和文件
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

    def get_logging(self):
        return self.logs

class MSSQL:
    """
    对pymssql的简单封装
    """
    def __init__(self, host, user, pwd, db):
        self.host = host
        self.user = user
        self.pwd = pwd
        self.db = db

    def __GetConnect(self):
        """
        得到连接信息
        返回: conn.cursor()
        """
        if not self.db:
            raise(NameError, "没有设置数据库信息")
        self.conn = pymssql.connect(host=self.host, user=self.user, password=self.pwd, database=self.db, charset="utf8")
        cur = self.conn.cursor()
        if not cur:
            raise(NameError, "连接数据库失败")
        else:
            return cur

    def ExecQuery(self, sql):
        """
        执行查询语句
        返回的是一个包含tuple的list，list的元素是记录行，tuple的元素是每行记录的字段

        调用示例：
                ms = MSSQL(host="localhost",user="sa",pwd="123456",db="PythonWeiboStatistics")
                resList = ms.ExecQuery("SELECT id,NickName FROM WeiBoUser")
                for (id,NickName) in resList:
                    print str(id),NickName
        """
        cur = self.__GetConnect()
        try:
            cur.execute(sql)
            resList = cur.fetchall()
        except:
            raise ('查询失败！')
        else:
            return resList
        finally:
            # 查询完毕后关闭连接
            self.conn.close()

    def ExecNonQuery(self, sql):
        """
        执行非查询语句
        调用示例：
            cur = self.__GetConnect()
            cur.execute(sql)
            self.conn.commit()
            self.conn.close()
        """
        cur = self.__GetConnect()
        cur.execute(sql)
        self.conn.commit()
        self.conn.close()


def get_sql_date():
    sql = MSSQL(host=variable['host'], user=variable['user'], pwd=variable['pwd'],
                db=variable['db'])
    relist = sql.ExecQuery('select * from dbo.ApplyLoanInfo')
    return relist


def str_len(strs):
    """计算字符串长度"""
    try:
        row_l = len(strs)
        utf8_l = len(strs.encode('utf-8'))
        return (utf8_l - row_l) / 2 + row_l
    except BaseException:
        return len(strs)


def init_xlsx(add_sql_title=False):
    column_list = []
    filename = '%s_sql_excel.xlsx' % time.strftime('%Y_%m_%d-%H_%M')
    filename = os.path.join('./history/', filename)
    if not os.path.isdir('history'):
        os.mkdir('history')
    book = xlsxwriter.Workbook(filename=filename)
    worksheet = book.add_worksheet(name='Total')

    title_cn = 'ID	姓名	教育程度	婚姻状况	有无子女	身份证号	证件到期日	发证机关所在地	户别	户口所在地	有无本地房产	居住情况	居住' \
               '地址(省市区)	居住地址(街道地址)	电子邮箱	手机号	备用手机号	近三个月申请贷款	近三个月申请过信用卡	单位名称	' \
               '部门	单位性质	单位地址(省市区)	单位地址(街道地址)	人事联系人姓名	人事联系人电话	职务名称	职务类型	雇佣类型' \
               '    企业成立年限	月收入	现单位工作年限	邮寄地址	紧急联系人姓名	与您关系	宅电	手机号	亲属联系人姓名	' \
               '与您的关系	宅电	手机号	亲属联系人姓名	与您的关系	宅电	手机号	申请金额	贷款期限	贷款用途    添加日期'
    title_sql = 'ID UserName	Education	IsMarried 	HaveChildren	IdCard	IdCardEndTime	IdCardProductAddress	' \
                'ResidenceType	ResidenceAddress	HaveLocalHouse	LiveCondition	LiveAddressMain	LiveAddressStreet	' \
                'Email	MobileCode	SpareMobileCode	HaveLoan	HaveCreditCard	UnitName	Department	UnitNature	' \
                'UnitAddressMain	UnitAddressStreet	UnitUserName	UnitUserMobileCode	JobName	JobType	EmployType' \
                '	CompanyFoundYear	MonthIncome	WorkYears	PostAddress	CriticalUserName	RelationShip	' \
                'HomePhone	ContactMobileCode	FamilyUserName1	FamilyRelationShip1	FamilyHomePhone1	FamilyMobileCode1' \
                '	FamilyUserName2	FamilyRelationShip2	FamilyHomePhone2	FamilyMobileCode2	ApplyMoney 	LoanLimit	' \
                'LoanUserType   AddTime'

    def add_book_head(data1='', row=0, col=0, set_col=False):
        """
        :param data: 
        :param row: 行号
        :param col: 列号
        :return: 
        """

        bold = book.add_format({'bold': True})
        location = 0
        for x in data1.split():
            worksheet.write(row, col, x, bold)
            if set_col:
                """ 自动计算并设置列宽 """
                x_len = str_len(x)
                cn_len = str_len(title_cn.split()[location])
                if x_len > cn_len:
                    set_column = x_len + 2
                else:
                    set_column = cn_len + 2
                worksheet.set_column(col, col, set_column)
                column_list.append(set_column)

            col += 1
            location += 1
    if not add_sql_title:
        add_book_head(title_cn, set_col=True)
    else:
        add_book_head(title_cn)
    if add_sql_title:
        add_book_head(title_sql, row=1, set_col=True)
    return book, worksheet, column_list, filename


def __Pretreatment_sql(sql):
    """最后一列日期处理"""
    post_sql = []
    for x in sql:
        x = list(x)
        x[-1] = x[-1].strftime('%Y-%m-%d %H:%M:%S')
        post_sql.append(x)
    return post_sql


def write_sql_to_xlsx(worksheet, sql_list, add_sql_title, column):
    row = 1
    if add_sql_title:
        row = 2
    col = 0
    for cow in sql_list:
        for value in cow:
            if value is not None:
                worksheet.write(row, col, value)
                value_len = str_len(str(value))
                if value_len > column[col]:
                    worksheet.set_column(col, col, value_len)
                    column[col] = value_len                     # 更新列表宽度值
            col += 1
        row += 1    # 下一行
        col = 0     # 回到行首


class Send_email():
    def __init__(self, text='', title='', to_addr='', cc_addr='', filename=''):
        # 发件人
        self.from_addr = variable['from_address']
        # 发件人密码
        self.password = variable['password']
        # 收件人列表
        self.to_addr = [x.strip() for x in to_addr.split(';')]
        self.Cc_addr = [x.strip() for x in cc_addr.split(';')]
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


def work_process():
    """
    工作流程
    :return: 
    """
    # 从数据库读取数据
    sql_data = get_sql_date()
    sql_data = __Pretreatment_sql(sql_data)
    # 生成excel
    add_sql_title = False
    xlsbook, worksheet, column_list, xlsxname = init_xlsx(add_sql_title)
    write_sql_to_xlsx(worksheet, sql_data, add_sql_title, column_list)
    xlsbook.close()
    # 以附件形式发出生成的Excel
    email = Send_email(text=variable['mail_text'], title=variable['title'], to_addr=variable['to_address'],
                       cc_addr=variable['cc_address'], filename=xlsxname)
    email.send()

if __name__ == '__main__':
    init_logs = init_log(lev=2)
    logs = init_logs.get_logging()
    work_process()
