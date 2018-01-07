#!/usr/bin/env bash
# by: Sonny Yang
# 1.0



export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/bin:/root/bin
cd `dirname $0` &>/dev/null

remote_workdir='~/vpclub'
inventory=hosts.conf

oc_user=admin
oc_passwd='sc@hsh2018'
oc_url='https://devops.hsh.vpclub.cn:8443'
src=prod
loacl_src_dir=app
app_env='--spring.profiles.active=prod'

URLS=$(cat ./host)
IFS=$'\n'

logs(){
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $@" >> monitor-$(date '+%Y-%m-%d').log
}


up_file(){
    ansible -i ${inventory} $1 -m copy -a "src=${loacl_src_dir}/$2 dest=${remote_workdir}"
}

get_jar(){

    oc_app=$1
    project=$2
    app=$3

    container=$(oc get pod -n  ${project} 2>/dev/null | grep -v build | grep Running |grep ${oc_app} | head -n 1 | awk '{print $1}')

    if [ -n "${container}" ];then
        set -x
        oc project ${project}
        mkdir -p ${project}/${oc_app}
        oc rsync ${container}:/opt/openshift/ ${project}/${oc_app}
        mkdir -p ${loacl_src_dir}/${app} && mv ${project}/${oc_app}/app.jar ${loacl_src_dir}/${app}/${app}.jar && rm -rf ${project}
        set +x
    fi
}

fire_walld(){
    dest_ip=$1
    port=$2

    # 判断是否存在
    ssh ${dest_ip} "iptables  -L INPUT -nv --line |  grep ${port}" &>/dev/null
    # 不存在
    if [ $? -ne 0 ];then
        set -e
        insert_line=$(ssh ${dest_ip} "iptables  -L INPUT -nv --line | tail -n +3 | tail -n 2 | head -n 1 | awk '{print \$1}'")
        [ -n "${insert_line}" ] && ssh ${dest_ip} "iptables -I INPUT ${insert_line}  -p tcp --dport ${port} -m state --state NEW -j ACCEPT"
        set +e
    fi
    # iptables  -L INPUT -nv --line |  grep 7575 | awk '{print $1}'| xargs iptables -D INPUT 2>/dev/null || true
}


ssh_sh(){
    dest_ip=$1
    app_name=$2
    app_port1=$3
    app_port2=$4
    option=$5

    log_dir=${remote_workdir}/${app_name}/logs
    jar_file=${remote_workdir}/${app_name}/app.jar

    logs "-----------------------------"
    logs dest ip = ${dest_ip}
    logs app name: ${app_name}

    # exec_name=run_$(date '+%Y-%m-%d').sh

    # echo "ssh ${dest_ip} \"ps aux | grep ${file_name} | grep -v grep | awk '{print \$2}' | xargs kill -9 2>/dev/null ; \
    # nohup java -jar $2 &>>$2.log &\" " > ${exec_name}

    # sed -i 's/\$/\\\$/g' ${exec_name}
    # asi_exec ${exec_name}
    # rm -rf ${exec_name}

    if [ "${update}" == "true" ];then
        up_file ${dest_ip} ${app_name}
    fi

    log_path=${log_dir}/${app_name}-$(date '+%Y-%m-%d').log

    ssh ${dest_ip} "cd ${remote_workdir}/${app_name} && \
                    ps aux | grep ${app_name} | grep -v grep | awk '{print \$2}' | xargs kill -9 2>/dev/null ; \
                    mkdir -p ${log_dir}; \
                    echo '$(date '+%Y-%m-%d %H:%M:%S'): ------------- now restart ------------' >> ${log_path}; \
                    nohup java -jar ${app_name}.jar ${app_env} &>>${log_path} &"

    fire_walld ${dest_ip} ${app_port1}
    fire_walld ${dest_ip} ${app_port2}

    logs "-----------------------------"
}

update(){
    app_name=$1
    for _ip in $(cat ${URLS} | grep ${app_name} | awk '{print $4}')
    do
        update=true
        ssh_sh ${_ip} ${app_name}
    done
}

main(){
    option=$1
    logs start...

    for line in ${URLS}
    do
        # echo '### next line ###'
        _ns=$(echo ${line}  | awk '{print $1}')
        _project=${_ns}-${src}
        _app=$(echo ${line}  | awk '{print $2}')
        _oc_app=$(echo ${_app} | sed "s/${_ns}-//g")
        _port1=$(echo ${line} | awk '{print $3}')
        _port2=$(echo ${line} | awk '{print $4}')
        _ip=$(echo ${line}  | awk '{print $NF}')

        _healthurl=${_ip}:${_port1}/${_ns}/${_oc_app}/health

        # 下载文件
        if [ "${option}" == "get_jar" ];then
            ${option} ${_oc_app} ${_project} ${_app}
            continue
        fi

        curl --connect-timeout 3 -s ${_healthurl}  | grep -q -e 'UP'  &>/dev/null

        if [ $? -ne 0 ];then
            ssh_sh ${_ip} ${_app} ${_port1} ${_port2} ${option}
        fi
    done

    logs end
}

helps(){
    cat >&2 <<EOF
    Usage：
        Example：
            手动更新应用，更新文件+重启
            ${BASH_SOURCE[0]}  update  a-app-name

            # 监控模式，启用健康检查，失败自动重启
            ${BASH_SOURCE[0]}  run

            # 监控模式，在触发重启时尝试更新文件
            ${BASH_SOURCE[0]}  run  update=true

            # 从openshift下载jar
            ${BASH_SOURCE[0]}  get
EOF
    exit 1
}


for x in $@
do

    # 至少六位数密码
    echo "$x" | grep -q -P "update=.{4,}" && update=$(echo "$x" | awk -F= '{print $2}')
done




case "$1" in
    update)
       update $2
       ;;
    run)
        main
        ;;
    get)
        oc login -u ${oc_user} -p ${oc_passwd} ${oc_url} || exit -1
        main get_jar $2
        ;;
    *)
        helps
        ;;
esac