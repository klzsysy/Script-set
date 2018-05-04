#!/usr/bin/env bash
# install mysql
# by Sonny Yang
# email: klzsysy@gmail.com
#
# version 0.2.0
# 重新验证安装，添加同步设置
# 2017年 11月 26日 星期日 23:14:55 CST
# -------------------------------------

# ---------------------------------
# 可自定义的内容
default_dir='/usr/local/mysql'
default_root_password='1s_mysql@sonny'
default_rep_password='copy.file@0'

default_mysql_url='https://dev.mysql.com/get/Downloads/MySQL-5.7/mysql-5.7.22-linux-glibc2.12-x86_64.tar.gz'
# ---------------------------------

# 不要随意修改
prefix=$2
mysql_home=''
mysql_bin=''
sh_name=$(basename $0)

directory(){
    # 使用指定的目录
    default_dir=$(echo ${default_dir} | awk -F"/+$" '{print $1}')
    if [ -n "${prefix}" ];then
        echo ${prefix} | grep -q '^/'
        if [ $? -ne 0 ];then
            if [ "${prefix}" == "." -o  "${prefix}" == "./" ];then
                prefix=$(pwd)/mysql
            elif $(echo ${prefix} | grep -q -P '^./.+');then
                mkdir -p  ${prefix}
                cd ${prefix}
                prefix=$(pwd)
                cd - &>/dev/null
            else
                prefix=$(pwd)/${prefix}
            fi
        fi
        mkdir -p ${prefix}
        if [ ! -d ${prefix} ];then
            echo 'Invalid path'
            exit 1
        else
            mysql_home=${prefix}
            mysql_bin=${prefix}/bin
        fi
    else
        mysql_home=${default_dir}
        mysql_bin=${default_dir}/bin
        mkdir -p ${mysql_home}
    fi
}


configure_file2(){

    if [ ! -f ${mysql_conf} ]; then
        cat > ${mysql_conf}<<EOFF
[client]
port = 3306
socket = ${mysql_home}/mysql.sock


[mysqladmin]
# logrote log
password = ${default_root_password}
user= root


[mysqld]
# basic settings #
port = 3306

# 伪随机生成id
server-id = $(date +%s | tail -c 4 | grep -o -P '[1-9]\d+$')
datadir = ${mysql_home}/data
tmpdir  = ${mysql_home}/tmp
user = mysql
socket = ${mysql_home}/mysql.sock
basedir = ${mysql_home}
pid-file = ${mysql_home}/mysql.pid

sql_mode = "STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER"
autocommit = 1
character_set_server=utf8
transaction_isolation = READ-COMMITTED
explicit_defaults_for_timestamp = 1
max_allowed_packet = 268435456
event_scheduler = 1

# connection #
interactive_timeout = 1800
wait_timeout = 1800
lock_wait_timeout = 1800
# skip_name_resolve = 1
max_connections = 1024
max_connect_errors = 1000000

# table cache performance settings
table_open_cache = 4096
table_definition_cache = 4096

# session memory settings #
read_buffer_size = 16M
read_rnd_buffer_size = 32M
sort_buffer_size = 32M
tmp_table_size = 64M
join_buffer_size = 128M
thread_cache_size = 64

# log settings #
log_error = ${mysql_home}/log/mysqld.log
slow_query_log = 1
general_log    = 0
log_output     = table
slow_query_log_file = ${mysql_home}/log/slow.log
log_queries_not_using_indexes = 1
log_slow_admin_statements = 1
log_slow_slave_statements = 1
log_throttle_queries_not_using_indexes = 10
expire_logs_days = 15
long_query_time = 2
min_examined_row_limit = 100
binlog-rows-query-log-events = 1
log-bin-trust-function-creators = 1
log-slave-updates = 1

# innodb settings #
innodb_page_size = 16384
innodb_buffer_pool_size = 4G
innodb_buffer_pool_instances = 4
innodb_buffer_pool_load_at_startup = 1
innodb_buffer_pool_dump_at_shutdown = 1
innodb_lru_scan_depth = 4096
innodb_lock_wait_timeout = 5
innodb_io_capacity = 200
innodb_io_capacity_max = 400
innodb_flush_method = O_DIRECT
innodb_undo_logs = 128
innodb_undo_tablespaces = 3
innodb_log_group_home_dir = ${mysql_home}/log/relay_log/
innodb_undo_directory = ${mysql_home}/log/undo_log/
innodb_flush_neighbors = 1
innodb_log_file_size = 128M
innodb_log_files_in_group = 2
innodb_log_buffer_size = 4M
innodb_purge_threads = 4
innodb_large_prefix = 1
innodb_thread_concurrency = 8
innodb_print_all_deadlocks = 1
innodb_strict_mode = 1
innodb_sort_buffer_size = 67108864
innodb_write_io_threads = 4
innodb_read_io_threads = 4 
innodb_file_per_table = 1
innodb_stats_persistent_sample_pages = 64
innodb_autoinc_lock_mode = 2
innodb_online_alter_log_max_size=512M
innodb_open_files=4096

# replication settings #
master_info_repository = TABLE
relay_log_info_repository = TABLE
log_bin = ${mysql_home}/log/bin_log/bin.log
sync_binlog = 1
gtid_mode = on
enforce_gtid_consistency = 1
log_slave_updates = 1

relay_log = ${mysql_home}/log/relay/relay.log
relay_log_recovery = 1
slave_skip_errors = ddl_exist_errors
slave-rows-search-algorithms = 'INDEX_SCAN,HASH_SCAN'

# semi sync replication settings #
plugin_load = "validate_password.so;rpl_semi_sync_master=semisync_master.so;rpl_semi_sync_slave=semisync_slave.so"
rpl_semi_sync_master_enabled = 1
rpl_semi_sync_master_timeout = 3000
# rpl_semi_sync_slave_enabled = 1

# password plugin #
validate_password_policy=LOW
validate_password_length=6
validate_password_number_count=0
# validate-password=FORCE_PLUS_PERMANENT

[mysqld-5.6]
# metalock performance settings
metadata_locks_hash_instances=64

[mysqld-5.7]
# new innodb settings #
loose_innodb_numa_interleave=1
innodb_buffer_pool_dump_pct = 40
innodb_page_cleaners = 16
innodb_undo_log_truncate = 1
innodb_max_undo_log_size = 2G
innodb_purge_rseg_truncate_frequency = 128
# new replication settings #
slave-parallel-type = LOGICAL_CLOCK
slave-parallel-workers = 16
slave_preserve_commit_order=1
slave_transaction_retries=128
# other change settings #
binlog_gtid_simple_recovery=1
log_timestamps=system
show_compatibility_56=on
EOFF
        
    fi
}

Config_Permissions(){
    chown root:root ${mysql_conf} && chmod 644 ${mysql_conf}
    mkdir -p ${mysql_home}/data
    mkdir -p ${mysql_home}/log/
    mkdir -p ${mysql_home}/log/relay_log/
    mkdir -p ${mysql_home}/log/undo_log/
    mkdir -p ${mysql_home}/log/bin_log/
    mkdir -p ${mysql_home}/log/relay
    mkdir -p ${mysql_home}/tmp
    chown -R mysql.mysql ${mysql_home}
    chmod -R 755 ${mysql_home}
}

system_logrote(){
    
    # add logrote
    echo \
"# The log file name and location can be set in
# /etc/my.cnf by setting the \"log-error\" option
# in either [mysqld] or [mysqld_safe] section as
# follows:
#
# [mysqld]
# log-error=/usr/local/mysql/data/mysqld.log
#
# In case the root user has a password, then you
# have to create a /root/.my.cnf configuration file
# with the following content:
#
# [mysqladmin]
# password = <secret> 
# user= root
#
# where \"<secret>\" is the password. 
#
# ATTENTION: The /root/.my.cnf file should be readable
# _ONLY_ by root !

${mysql_home}/log/mysqld.log {
        # create 600 mysql mysql
        notifempty
        daily
        # size 10M
        rotate 15
        missingok
        compress
    postrotate
    # just if mysqld is really running
    if test -x ${mysql_bin}/mysqladmin && \
       ${mysql_bin}/mysqladmin ping &>/dev/null
    then
       ${mysql_bin}/mysqladmin flush-logs
    fi
    endscript
}
" >> /etc/logrotate.d/mysql-log-rotate
}

system_environment(){
    
    # add PATH
    echo "PATH=\$PATH:${mysql_bin}" >> /etc/profile.d/mysqld.sh
    echo "PATH=\$PATH:${mysql_bin}" >> /etc/profile.d/mysqld.zsh
    source /etc/profile

    # add share lib
    echo "${mysql_home}/lib" > /etc/ld.so.conf.d/mysql.conf
    #
    echo "d ${mysql_home} 0755 mysql mysql  -" > /usr/lib/tmpfiles.d/mysql.conf

}

open_remote_connect(){
    # 开启root远程访问
    source '/etc/profile'
    mysql -Dmysql -uroot -p${default_root_password} -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' IDENTIFIED BY '${default_root_password}' WITH GRANT OPTION;" 2>/dev/null
    if [ $? -eq 0 ];then
        echo "open root remote acccess ok!"
    else
        echo "open root remote acccess faild!"
        exit -1
    fi
    mysql -Dmysql -uroot -p${default_root_password} -e 'flush privileges;' 2>/dev/null
}

create_rep_id(){
    if [ -z "${slave}" ];then
        echo "slave 主机未定义"
        exit -1
    else
        ping -c 2 ${slave} -W 500 &>/dev/null
        if [ $? -ne 0 ];then
            echo "主机 ${slave} 不可达"
            exit -1
        else
            mysql -Dmysql -uroot -p${default_root_password} -e "GRANT REPLICATION SLAVE ON *.* to 'rep1'@'${slave}' identified by '${default_rep_password}';" 2>/dev/null
            if [ $? -eq 0 ];then
                mysql -Dmysql -uroot -p${default_root_password} -e 'flush privileges;' 2>/dev/null
                echo '复制账户创建成功！'
            else
                echo '创建复制账户失败'
            fi
        fi
    fi
}

config_slave(){

    if [ -z "${master}" ];then
        echo "master 主机未定义"
        exit -1
    else
        ping -c 2 ${master} -W 500 &>/dev/null
        if [ $? -ne 0 ];then
            echo "主机 ${master} 不可达"
            exit -1
        else
            set -e
            mysql -uroot -p${default_root_password} -e "CHANGE MASTER TO MASTER_HOST='${master}',\
            MASTER_PORT=3306,MASTER_USER='rep1',\
            MASTER_PASSWORD='${default_rep_password}',\
            master_auto_position=1;"
            
            mysql -uroot -p${default_root_password} -e 'start slave;'

            sleep 5
            mysql -uroot -p${default_root_password} -e 'show slave status \G;'
             
            echo -e "\n设置slave为只读模式, 可通过set global read_only=0; 恢复读写"
            mysql -uroot -p${default_root_password} -e 'set global read_only=1;'
            echo "查看slave状态： mysql -uroot -p${default_root_password} -e 'show slave status \G;'"
            set +e
        fi
    fi
}

configure_pasword(){

    temp_pass=$(grep 'temporary password' ${mysql_home}/log/mysqld.log  | awk '{print $NF}')
    echo " ------------------ install info --------------------"
    echo temp mysql password: ${temp_pass}
    echo "Now change temp password:
            source /etc/profile
            mysql -uroot -p'${temp_pass}'
            SET PASSWORD=PASSWORD('${default_root_password}');
            flush privileges;
            exit"

    [ -n "${password}" ] && note="password='${password}'"

    echo "After changing the password, you can turn on root remote access:
            ./${sh_name} option remote ${note} password='you_are_set_password'"
    echo " ------------------ end -----------------------------"
}

system_version(){
#    "7 Centos 7"
#    "6 Centos 6"
#    "5 Centos 5"
#    "uname -i"
    cat /etc/redhat-release 2>/dev/null | grep -P "7.\d" -q && return 7
    cat /etc/redhat-release 2>/dev/null | grep -P "6.\d" -q && return 6
    cat /etc/redhat-release 2>/dev/null | grep -P "5.\d" -q && return 5
    lsb_release -a 2>/dev/null | grep Descr | grep -i  'ubuntu' -q && \
    lsb_release -a 2>/dev/null | grep Descr |  grep -i ubuntu | grep -P -q '12.\d' && return 12
    lsb_release -a 2>/dev/null | grep Descr |  grep -i ubuntu | grep -P -q '14.04' && return 14
    lsb_release -a 2>/dev/null | grep Descr |  grep -i ubuntu | grep -P -q '16.04' && return 16
    return -1
}


download_bin(){
    if  $(ls -l | awk '{print $NF}' | grep -P 'mysql-.*.tar.gz' -q);then
        echo mysql bin package find
    else
        wget ${default_mysql_url} || exit 1
    fi
}

install(){
    directory

    download_bin

    binary_package=$(ls -l | grep -P "mysql.*\.tar\.gz" | awk '{print $NF}' | head -n 1)
    binary_folder=$(echo ${binary_package} | sed 's/.tar.gz$//g')

    if [ -n "${binary_package}" ];then
        if [ ! -d "${binary_folder}" ];then
            echo "解包ing..."
            tar -xzf ${binary_package} && cd ${binary_folder} || exit -1
        else
            cd ${binary_folder}
        fi
        currdir=$(pwd)
        if [ "${mysql_home}" != "${currdir}" ];then
            echo  'copy mysql file ...'
            mv -f ./* ${mysql_home}
            cd ${mysql_home}
            rm -rf ${currdir}
        fi
    else
        exit -1
    fi


    # add mysql account
    groupadd mysql && useradd -s /sbin/nologin -g mysql mysql -M 2>/dev/null
    
    
    # add my.cnf

    mysql_conf="/etc/my.cnf"

    mv /etc/my.cnf /etc/my.cnf.backup &>/dev/null
    # add config
    configure_file2
    #
    Config_Permissions

    # show log
    if [ "${debug}" == 'true' ];then
        touch ${mysql_home}/log/mysqld.log
        chown mysql:mysql ${mysql_home}/log/mysqld.log
        tail -f ${mysql_home}/log/mysqld.log &
        LOGPID=$!
    fi

    # initialize mysql
    echo init mysql...
    ${mysql_home}/bin/mysqld --initialize --user=mysql --basedir=${mysql_home} --datadir=${mysql_home}/data
    # kill log
    if [ "${debug}" == 'true' ];then
        kill -9 ${LOGPID}
    fi
    
    #
    system_environment
    system_logrote

    # add system service
    cd ${mysql_home}
    
    raw_mysql_home=$(echo ${mysql_home} | sed 's/\//\\\//g' )

    basedir="basedir=.*"
    datadir="datadir=.*"

    newbasedir="basedir=${raw_mysql_home}"
    newdatadir="datadir=${raw_mysql_home}\/data"

    cat support-files/mysql.server | sed "s/^$basedir/$newbasedir/g" > mysql.server
    sed -i "s/^$datadir/$newdatadir/g"  mysql.server
    mv -f mysql.server /etc/init.d/mysqld

    systemctl is-active firewalld &>/dev/null && firewall-cmd --add-port=3306/tcp --permanent 2>/dev/null && systemctl restart firewalld 
    systemctl is-active iptables &>/dev/null && iptables -I INPUT 4 -p tcp --dport 3306 -m state --state NEW -j ACCEPT && service iptables save

    chmod +x /etc/init.d/mysqld
    /etc/init.d/mysqld start

    if [ $? -ne 0 ];then
        echo 'Start mysql faild!'
        exit -1
    else
        chkconfig --add mysqld
        chkconfig --level 3 mysqld on
        
        # 显示密码信息
        configure_pasword
        exit 0
    fi
}


uninstall(){
    ps aux | grep mysqld | grep -v grep | awk '{print $2}' | xargs kill -9 &>/dev/null
    rm -rf /etc/init.d/mysqld
    # delete user
    userdel mysql &>/dev/null
    rm -rf /etc/profile.d/mysqld.sh
    rm -rf /etc/profile.d/mysqld.zsh
    rm -rf /etc/logrotate.d/mysql-log-rotate
    rm -rf /usr/lib/tmpfiles.d/mysql.conf

    chkconfig  mysqld off &>/dev/null
    chkconfig --del mysqld &>/dev/null

    mv -f /etc/my.cnf  /etc/my.cnf.backup 2>/dev/null
}

helps(){
    cat >&2 <<EOF
    安装：
        Usage: ${BASH_SOURCE[0]}    动作      <安装路径(可选)>   <root密码(可选)>
        Example：
               ${BASH_SOURCE[0]}    install     /data/mysql     password=xxxx.123

    卸载：
        删除系统配置，保留数据库目录

        Usage: ${BASH_SOURCE[0]} uninstall

    额外选项：
        需要在完成安装后修改了密码才有效，使用了password选项指定密码

        Usage: ${BASH_SOURCE[0]} option [action]

        开启root远程访问：
            ${BASH_SOURCE[0]} option remote password='you_are_set_password'

        设置为master角色（创建同步账户）：
            ${BASH_SOURCE[0]} option master slave=x.x.x.x password='you_are_set_password'

        设置为slave角色：
            ${BASH_SOURCE[0]} option slave master=x.x.x.x password='you_are_set_password'
EOF
    exit 1
}


option(){
    # 一些选项
    select=$1
    case "$1" in
    remote)
        open_remote_connect
        ;;
    master)
        create_rep_id
        ;;
    slave)
        config_slave
        ;;
    *)
        echo "Do not have this option!" >&2
        helps
        ;;
    esac
}




## 处理自定义选项

for x in $@
do
    # 至少六位数密码
    echo "$x" | grep -q -P "password=.{6,}" && default_root_password=$(echo "$x" | awk -F= '{print $2}') && password=${default_root_password}
    echo "$x" | grep -q -P "slave=.{3,}" && slave=$(echo "$x" | awk -F= '{print $2}')
    echo "$x" | grep -q -P "master=.{3,}" && master=$(echo "$x" | awk -F= '{print $2}')
    echo "$x" | grep -q -P "debug=.{3,}" && debug=$(echo "$x" | awk -F= '{print $2}')
    
done


#############################
#############################
## start process

system_version
version=$?

case "$1" in
 install)
       install $2
       ;;
uninstall)
        uninstall
        ;;
option)
        option $2
        ;;
    *)
        helps
        ;;
esac