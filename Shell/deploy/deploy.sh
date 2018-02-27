#!/usr/bin/env bash
# by: Sonny Yang
# 1.3.1

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/bin:/root/bin"
cd `dirname $0` &>/dev/null


# ------------- user config start -------------
remote_workdir='~/vpclub'
inventory=hosts.conf

oc_user=admin
oc_passwd='********'
oc_url='https://devops.xxx.xxx.cn:8443'
src=stage
loacl_src_dir=apps

# java env
app_env='-Xmx512m -Xss256k -Djava.net.preferIPv4Stack=true -Dspring.profiles.active=prod'

# 部署信息 ansible inventory
deployconfig=java-apps

# dns server
dns_server='10.108.78.146'

# nginx ---------------
## 附加https配置
anc='nginx-conf-head/nginx-attached-redirect-https-conf'
## 附加http https配置
nattc='nginx-conf-head/nginx-attached-http-https-conf'
## location 下的附加选项
nao='nginx-conf-head/nginx-attached-location-option'
## nginx主机ansible inventory
nginxhost='nginx-conf-head/nginx-host'
## 自动生成的站点配置
nginx_site_conf='nginx-hsh.conf'

# 外挂模块
check_module='monitor-rule'

system_env='
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/bin:/root/bin && \
export JAVA_HOME=/root/jdk1.8.0_144 && \
export JRE_HOME=/root/jdk1.8.0_144/jre && \
export CLASSPATH=.:$JAVA_HOME/lib/dt.jar:$JAVA_HOME/lib/tools.jar && \
export PATH=$JAVA_HOME/bin:$PATH'

# -------------user config end -----------

# 读取 nginx 附加配置
ANC=$(cat ${anc} 2>/dev/null)
NATTC=$(cat ${nattc} 2>/dev/null)
NSC=$(printf "$(cat nginx-conf-head/nginx-site-config)" "${NATTC}") # Simultaneously add http configure
NAO=$(cat ${nao} 2>/dev/null)


# nginx config build
    NGINX_CONFIG="
${NSC}

    # -- nginx-attached-http-https-conf start ----
${NATTC}
    # -- nginx-attached-http-https-conf end ------

    # -- nginx-attached-redirect-https-conf start ----
${ANC}
    # -- nginx-attached-redirect-https-conf end ------
"

# ------------- args ---

for x in $@
do
    # 至少六位数密码
    echo "$x" | grep -q -P "update=.{4,}" && update=$(echo "$x" | awk -F= '{print $2}')
    echo "$x" | grep -q -P "src=.{2,}" && src=$(echo "$x" | awk -F= '{print $2}')
    echo "$x" | grep -q -P "dc=.{2,}" && deployconfig=$(echo "$x" | awk -F= '{print $2}')
done
# --------------

URLS=$(cat ${deployconfig})
IFS=$'\n'

logs(){
    msg="$@"
    show=false

    for x in $@
    do
        echo "$x" | grep -q -E "^show=true$" && show="true" && \
        msg=$(echo "$@" | sed 's/show=true//g')
    done

    if [ "${show}" == "true" ];then
        echo "$(date '+%Y-%m-%d %H:%M:%S'): ${msg}"  | tee -a monitor-$(date '+%Y-%m-%d').log
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S'): ${msg}" >> monitor-$(date '+%Y-%m-%d').log
    fi
}

end(){
    logs ++++++++++++++++++++ end
    exit $1
}

updns(){
    logs start update dns
    # clear
    ssh ${dns_server} "sed  -i '/AUTO---DEPLOY--START/,/AUTO---DEPLOY--END/d' /etc/named/hsh.io" >/dev/null

    # add
    ssh ${dns_server} "echo -e \"AUTO---DEPLOY--START\tIN\tA\t0.0.0.0\" >> /etc/named/hsh.io && \
    echo \"${URLS}\"  | awk '{printf \"%s\tIN\tA\t%s\n\",\$2,\$5}' >> /etc/named/hsh.io && \
    echo -e \"AUTO---DEPLOY--END\tIN\tA\t0.0.0.0\" >> /etc/named/hsh.io 
    " >/dev/null
    # lod_num=$(ssh ${dns_server} "cat /etc/named/hsh.io  | grep serial | awk '{print \$1}'")

    ssh ${dns_server} "\
    lod_num=\`cat /etc/named/hsh.io  | grep serial | awk '{print \$1}'\` && \
    new_num=\$(expr 1 +  \`cat /etc/named/hsh.io  | grep serial | awk '{print \$1}'\`) && \
    sed -i \"s/            \${lod_num}  ;serial/            \${new_num}  ;serial/\" /etc/named/hsh.io && \
    systemctl restart named
    " >/dev/null
}

upnginx(){
    app_name=$1
    http_port=$2
    target_host=$3
    url=$4
    types=$5


    if [ "${types}" == 'upstream' ];then
        echo"

upstream ${app_name} {
    server ${target_host}:${http_port} max_fails=3 fail_timeout=10s
}"

    elif [ "${types}" == 'location' ];then
        # 处理额外的location参数
        nginx_option=$(echo "${NAO}"  |  sed -n  "s/^${app_name}\s*\(.*\)/\n        \1;/p" | sed '2,${/^$/d'})


        echo "

    location ${url} {${nginx_option}
        proxy_pass http://${target_host}:${http_port}/;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }"
    fi

}

up_file(){
    _ip=$1
    _app_name=$2
    ansible -i ${inventory} ${_ip} -m copy -a "src=${loacl_src_dir}/${_app_name} dest=${remote_workdir}"
    return $?
}

get(){
    
    oc_app=$1
    project=$2
    app=$3

    container=$(oc get pod -n ${project} 2>/dev/null | grep -v build | grep Running |grep ${oc_app} | head -n 1 | awk '{print $1}')

    # 多出一个

    if [ -n "${container}" ]; then
        oc project ${project} && \
        mkdir -p tmp && \
        mkdir -p ${loacl_src_dir}/${app}/app && \
        oc rsync ${container}:/opt/openshift/ tmp

        if [ $? -eq 0 ];then
            logs "Get the jar from ${oc_app} pod success!" show=true
            mv  tmp/app.jar ${loacl_src_dir}/${app}/app/${app}.jar || logs move ${oc_app} jar file faild! show=true
        else
            logs "Get the jar from ${oc_app} pod faild!" show=true
        fi
        rm -rf tmp
    fi
}

fire_walld(){
    dest_ip=$1
    port=$2
    method=$3
    # 
    method=${method:="add"}

    if [ "${method}" == "add" ];then
        # 判断是否存在
        ssh ${dest_ip} "iptables  -L INPUT -nv --line |  grep ${port}" &>/dev/null
        # 不存在
        if [ $? -ne 0 ];then
            set -e
            insert_line=$(ssh ${dest_ip} "iptables  -L INPUT -nv --line | tail -n +3 | tail -n 2 | head -n 1 | awk '{print \$1}'")
            [ -n "${insert_line}" ] && ssh ${dest_ip} "iptables -I INPUT ${insert_line}  -p tcp --dport ${port} -m state --state NEW -j ACCEPT" && \
            logs "added open ${dest_ip} ${port} firewalld rule"
            set +e
        fi
    elif [ "${method}" == "clear" ];then
        ssh ${dest_ip} "iptables  -L INPUT -nv --line |  grep ${port} | awk '{print \$1}'| xargs iptables -D INPUT 2>/dev/null || true"
    fi
   
}


ssh_sh(){
    dest_ip=$1
    app_name=$2
    app_port1=$3
    app_port2=$4
    ssh_option=$5

    log_dir="${remote_workdir}/${app_name}/logs"

    # stop
    if [ "${ssh_option}" == "stop" ];then
        ssh ${dest_ip} "ps aux | grep ${app_name} | grep -v grep | awk '{print \$2}' | xargs kill -9 2>/dev/null "
        return 0
    fi

    logs "-----------------------------"
    logs restart .... show=true
    logs dest ip = ${dest_ip} show=true
    logs app name: ${app_name} show=true


    if [ "${update}" == "true" -o "${option}" == "update" ];then
        up_file ${dest_ip} ${app_name}
        if [ $? -ne 0 ];then
            logs  ${dest_ip} ${app_name} copy fiald show=true
        fi
    fi

    log_path="${log_dir}/${app_name}-$(date '+%Y-%m-%d').log"


    # echo " ${system_env} && \
    #         cd ${remote_workdir}/${app_name}/app && \
    #         ps aux | grep ${app_name} | grep -v grep | awk '{print \$2}' | xargs kill -9 2>/dev/null ; \
    #         mkdir -p ${log_dir}; \

    #         echo '$(date '+%Y-%m-%d %H:%M:%S'): ------------- now restart ------------' >> ${log_path}; \
    #         echo \"$(date '+%Y-%m-%d %H:%M:%S'): JAVA_HOME = \$JAVA_HOME\" >> ${log_path} ; \
    #         echo \"$(date '+%Y-%m-%d %H:%M:%S'): PATH = \$PATH\" >> ${log_path} ; \

    #         java ${app_env} -jar ${app_name}.jar  &>>${log_path} " > ${dest_ip}.sh

    # ansible -i ${inventory} ${dest_ip} -m copy -a "src=${dest_ip}.sh dest=/tmp"
    # ssh ${dest_ip} "nohup bash /tmp/${dest_ip}.sh &>/dev/null &"

    ssh ${dest_ip} "
            cd ${remote_workdir}/${app_name}/app && \
            ps aux | grep ${app_name} | grep -v grep | awk '{print \$2}' | xargs kill -9 2>/dev/null ; \
            mkdir -p ${log_dir}; \

            echo '$(date '+%Y-%m-%d %H:%M:%S'): ------------- now restart ------------' >> ${log_path}; \
            echo \"$(date '+%Y-%m-%d %H:%M:%S'): JAVA_HOME = \$JAVA_HOME\" >> ${log_path} ; \
            echo \"$(date '+%Y-%m-%d %H:%M:%S'): PATH = \$PATH\" >> ${log_path} ; \

            nohup bash -c '${system_env} && \
            echo pwd=\$(pwd) >> ${log_path} && \
            java ${app_env} -jar ${app_name}.jar  &>>${log_path}' &>/dev/null &
            " &>/dev/null

    fire_walld ${dest_ip} ${app_port1}
    fire_walld ${dest_ip} ${app_port2}

    logs "-----------------------------" show=true
}

clear(){
    host=$1
    app_name=$2
    port1=$3
    port2=$4
    args=$5
    
    if [ -n "${remote_workdir}" -a -n "${app_name}" ];then
        logs "start clear ${app_name} in ${host}" show=true
        ssh ${host} "rm -rf ${remote_workdir}/${app_name}/" >/dev/null
        ssh ${host} "ps aux | grep ${app_name} | grep -v grep | awk '{print \$2}' | xargs kill -9 2>/dev/null" >/dev/null

        fire_walld ${host} ${port1} ${args}
        fire_walld ${host} ${port2} ${args}
    else
        logs CLEAR ERROR!!!
    fi
}


update(){
    app_name=$2

    for _line in  ${URLS}
    do
        echo "${_line} "| grep -P "${app_name}" -q
        if [ $? -eq 0 ];then
            logs "start update ${app_name}..." show=true
            update=true
            ssh_sh $@
            return $?
        fi
    done
}

login_openshift(){
    oc login -u ${oc_user} -p ${oc_passwd} ${oc_url} &>/dev/null || (echo "openshift login faild!" ;exit -1)
}

restart_nginx(){
    ansible -i ${nginxhost} all -m shell -a 'nginx -t'
    if [ $? -ne 0 ];then
        logs "nginx配置文件语法错误，停止应用配置，请检查${anc}文件是否有误" show=true
        end 1
    fi
    logs "start restart nginx gateway"
    ansible -i ${nginxhost} all -m shell -a "nginx -s reload || \
    (       kill -9 \$(netstat -nltp | grep ':80' | awk '{print \$7}' | awk -F/ '{print \$1}') &>/dev/null;
            ps aux | grep nginx | grep -v nobody | grep -v grep | grep -v kong | awk '{print \$2}' | xargs kill -9 &>/dev/null ;
        sleep 1;
        (nginx >/dev/null &)
    )"
    end $?
}

main(){
    option=$1
    args=$2
    args2=$3
    

    echo "# ------------------------------------------------"
    echo "# start..."
    echo "# 如有疑问请先直接运行以查看帮助"
    echo "# ---------报告bug ---> Yang.siyi@vpclub.cn ------ "
    echo ""

    # get must login to openshift
    if [ "${option}" == "get" -o "${args}" == "update=true" ];then
        login_openshift
    elif [ "${option}" == "run" ];then
        # 检查 monitor rule
        for iter in $(ls -l ${check_module} | awk 'NR>1 {print $NF}')
        do
            logs "start run ${iter} check"
            nohup monitor-rule/${iter}/main.sh $@ &>/dev/null &
        done
    fi
    # start process option

    for line in ${URLS}
    do
        # echo '### next line ###'
        _ns=$(echo ${line}  | awk '{print $1}')
        _project=${_ns}-${src}
        _app=$(echo ${line}  | awk '{print $2}')
        _oc_app=$(echo ${_app} | sed "s/${_ns}-//g")
        _port1=$(echo ${line} | awk '{print $3}')
        _port2=$(echo ${line} | awk '{print $4}')
        _ip=$(echo ${line}  | awk '{print $5}')
        _location=$(echo ${line}  | awk '{print $6}')

        _healthurl=${_ip}:${_port1}/health

        # get 下载文件
        if [ "${option}" == "get" ];then
            ${option} ${_oc_app} ${_project} ${_app}
            continue
        fi

        # build nginx config
        if [ "${option}" == 'upnginx' ];then
            # 查看nginx进程状态
            if [ "${args}" == "status" ];then
                ansible -i ${nginxhost} all -m shell -a 'ps aux | grep nginx | grep -P "^nginx" | grep -v grep'
                end 0
            # 重启nginx
            elif [ "${args}" == "restart" ];then
                restart_nginx
                end 0
            # 同步nginx主配置与日志配置
            elif [ "${args}" == "sync" ];then
                ansible -i ${nginxhost} all -m copy -a 'src=nginx-conf-head/nginx-logrotate.sh dest=/etc/nginx/' && \
                ansible -i ${nginxhost} all -m shell -a "chmod a+x /etc/nginx/nginx-logrotate.sh; \
                sed -i '/nginx-logrotate.sh/d' /etc/crontab;\
                echo '59 23 * * *  root /etc/nginx/nginx-logrotate.sh' >> /etc/crontab"
                ansible -i ${nginxhost} all -m copy -a 'src=nginx-conf-head/nginx.conf dest=/etc/nginx/' && restart_nginx
                end $?
            fi

            if [ -n "${_location}" ];then
                _location=$(${option} ${_app} ${_port1} ${_ip}  ${_location} 'location')
                NGINX_CONFIG="${NGINX_CONFIG}${_location}"
            fi
            continue
        fi

        # update 更新文件
        if [ "${option}" == "update" ];then
            if [ -z "${args}" ];then
                echo "缺少应用名参数" >&2
                end -1
            elif [ "${args}" == "all" ];then
                login_openshift
                get ${_oc_app} ${_project} ${_app}
                update=true
                ssh_sh ${_ip} ${_app} ${_port1} ${_port2} ${option}
                continue
            elif [ "${_app}" == "$args" ];then
                login_openshift
                get ${_oc_app} ${_project} ${_app}
                update=true
                ssh_sh ${_ip} ${_app} ${_port1} ${_port2} ${option}
                end $?
            else
                continue
            fi
        fi

        # clear 
        if [ "${option}" == "clear" ];then
            if [ "$args" == "" ];then
                helper
            elif [ "${args}" == "all" ];then
                ${option} ${_ip} ${_app} ${_port1} ${_port2} ${option}
                continue
            elif [ -n "${args}" -a "${args}" == "${_app}" ];then
                ${option} ${_ip} ${_app} ${_port1} ${_port2} ${option}
                end $?
            else
                continue 
            fi
        fi

        # check & restart
        if [ "${option}" == "check" -o "${option}" == "restart" ];then
            if [ -z "${args}" ];then
                echo "缺少应用名参数" >&2
                exit -1
            elif [ "${args}" == "${_app}" ];then
                # restart 
                if [ "${option}" == "restart" ];then
                    ssh_sh ${_ip} ${_app} ${_port1} ${_port2} ${option}
                    end $?
                fi
                # check
                logs "start check ${_app} health status..." show=true
                timeout 2 curl --connect-timeout 3 -s ${_healthurl}  | grep -q -e 'UP' &>/dev/null
                if [ $? -eq 0 ];then
                    logs "ok, ${_app} health check result is UP!" show=true
                else
                    logs "bad, ${_app} health check result is DOWN!" show=true
                    logs "plause login host ${_ip} check ${_app} app status!" show=true
                fi
                end 0
            else
                continue
            fi

        fi

        # run 检查
        if [ "${option}" == "run" ];then
            if [ "${args}" == "" -o "${args}" == "norestart" -o "${args}" == "update=true" -o "${args}" == "forcereset"  -o "${args}" == "stop" ];then
                if [ "${args}" == "stop" ];then
                    logs "stop ${_app}" show=true 
                    ssh_sh ${_ip} ${_app} ${_port1} ${_port2} ${args}
                    continue
                fi
                # 不检查直接重启
                if [ "${args}" == "forcereset" ];then
                        false
                else
                        timeout 2 curl --connect-timeout 3 -s ${_healthurl}  | grep -q -e 'UP'  &>/dev/null
                fi
                if [ $? -ne 0 ];then
                    logs check ${_ip} ${_app} ${_port1} ${_port2} faild! show=true
                    if [ "${args}" == "norestart" ];then
                        logs usage norestart option, not restart ${_app}
                    else
                        [ "${args}" == "update=true" ] && get ${_oc_app} ${_project} ${_app}
                        logs try restart ${_app} show=true
                        ssh_sh ${_ip} ${_app} ${_port1} ${_port2} ${option}
                    fi
                else
                    logs ${_ip} ${_app} ${_port1} ${_port2} ok
                fi
            else
                logs 参数错误 ${args} show=true >&2
                end -1
            fi
        fi

    done

    # 循环外独立事件
    
    if [ "${option}" == 'upnginx' ];then
        echo -e "${NGINX_CONFIG}\n}" > ${nginx_site_conf}
        [ "${args}" == "build" ] && echo "Nginx Configure File ${nginx_site_conf} Build Success!" && end 0
        logs start update nginx
        ansible -i ${nginxhost} all -m copy -a "src=${nginx_site_conf} dest=/etc/nginx/conf.d/"
        restart_nginx
    fi
    end 0
}

helper(){
    logs "show help info"
    cat >&2 <<EOF
    Usage:
        "[ ]"内为可选参数，"< >"内为必需参数，"|"表示参数只能选其一
        Example:
            # 手动更新应用，从pod拉取文件+更新文件+重启
            ${BASH_SOURCE[0]}  update <all|a-app-name>

            # 手动检查或重启某应用
            ${BASH_SOURCE[0]}  <check|restart>  a-app-name

            # 对所有应用健康检查，失败默认restart, norestart失败不重启，forcereset不管结果强制重启，stop停止应用运行
            ${BASH_SOURCE[0]}  run  [ norestart|forcereset|stop ]

            # 健康检查，在触发重启时尝试更新文件
            ${BASH_SOURCE[0]}  run  update=true

            # 从openshift下载所有jar
            ${BASH_SOURCE[0]}  get

            # 清理资源,删除某部署的应用
            ${BASH_SOURCE[0]}  clear <all|a-app-name>

            # 更新dns，基于文件${deployconfig}
            ${BASH_SOURCE[0]}  updns

            # 更新nginx，build 仅生成nginx站点配置不应用生效，基于文件${deployconfig}和nginx-conf-head目录下配置文件
            ${BASH_SOURCE[0]}  upnginx [ build ]

    more Option:
        # 指定openshift源环境, 在update或get选项中有意义，默认${src}
            ${BASH_SOURCE[0]} get src=<prod|stage>
        # 指定配置来源，默认是${deployconfig}
            ${BASH_SOURCE[0]} run dc=a-description-file
    tips:
        添加应用部署信息写入${deployconfig}，然后updns，upnginx，update
        如需要修改部署服务器IP或端口请先clear删除现有信息，然后修改${deployconfig}记录，再updns与update
        只要${deployconfig}有url变动均要upnginx，只有要服务器地址变动均要updns
        ${anc}文件为nginx server部分附加参数，在${deployconfig}之外的信息可以手动添加配置到这里，upnginx应用更新

EOF
    end 1
}

logs  ++++++++++++++++++++ start...
logs args: $@

case "$1" in
    run|update|clear|upnginx|get|check|restart)
        main $@
        ;;
    updns)
        $@
        ;;
    *)
        helper
        ;;
esac