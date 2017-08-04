#!/usr/bin/env bash
#
# __author__='Sonny Yang'
#
export PATH=$PATH:/bin:/sbin:/usr/bin:/usr/sbin:/root/bin:/usr/local/sbin:/usr/local/bin
# ------------自定义参数开始---------------
folder="/var/log"
types="*.log"
# --- 动作开关
action_main_switch='true'
add_event='true'
update_event='true'
delete_event='false'

# [新增事件]动作定义
add_action='cp'
add_first_para=''
add_last_para='/tmp/${key}_$(date +%m-%d_%H:%M:%S-%s)'
add_send_mail='true'

#add_attached_para='/${key}_$(date +%m-%d_%H:%M:%S-%s)'
# [修改事件]动作定义
update_action='cp'
update_first_para=''
update_last_para='/tmp/${key}_$(date +%m-%d_%H:%M:%S-%s)'
update_send_mail='true'
# [删除事件]动作定义
delete_action=''
delete_first_para=''
delete_last_para=''
delete_send_mail='true'
# ----邮件相关----
# 邮件总开关
mail_switch='true'
# 使用以下的mail_server_info 定义的账户信息，设置为非 true将使用系统默认配置
use_customize_config="true"
mail_server_info="
set from=Yang.Siyi@vpclub.cn
set smtp=smtp.exmail.qq.com
set smtp-auth-user=Yang.Siyi@vpclub.cn
set smtp-auth-password=password
set smtp-auth=login
"
#  收件人 邮件标题 邮件文本
mail_to_address="Yang.Siyi@vpclub.cn"
mail_title="this mail from Shell Program"
mail_text="this is mail text ...... "
# ---
# 间隔 秒
sleep_time=5
# ------------自定义参数结束---------------



# 全局变量
declare -A new_dict
declare -A last_dict
declare -A update_dict
declare -A mail_dict
number=0


logs(){
    # 将日志输出到标准输出 > /dev/stdout
    logs_text=$1
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ${logs_text}" >> monitor.log
}

exec_action(){
    # key 完整路径的文件名
    key=$1
    action=$2
    action_first_para=$3
    action_last_para=$4
    info=$5
    # logs
    logs "exec action # ${action} ${action_first_para} ${key} ${action_last_para}"
    # exec action
    bash -c "key=$(echo ${key} | awk -F/ '{print $NF}'); ${action} ${action_first_para} ${key} ${action_last_para} "
    # save exec result
    [ $? -eq 0 ] && logs "{info} action Correctly completed" || logs "${info} action An error occurred"
}


send_mail(){
    title="${mail_title}"
    text="${mail_text}"


    # 判断要不要发邮件
    [ "${mail_switch}" != 'true' ] && return 0

    mail_dict_key=$(echo ${!mail_dict[*]})
    [ -z "${mail_dict_key}" ] &&  return 0

    # 修改系统配置文件，修改失败停止发送
    if [ "${use_customize_config}" == "true" ];then
        cp -f /etc/mail.rc /tmp/mail.rc.origin &>/dev/null
        if [ $? -eq 0 ];then        # 执行成功
            echo "${mail_server_info}" 2>/dev/null >>/etc/mail.rc
            if [ $? -ne 0 ];then    # 执行失败
                logs "not Permission change mail configure, stop send mail"
            fi
        else
           logs "not Permission backup mail configure, stop send mail"
           return 1
        fi
    else
        return 1
    fi

    # 组合邮件正文内容
    for key in $(echo ${!mail_dict[*]})
    do
        text="${text}\n file ${mail_dict["${key}"]}: ${key}"
    done

    echo -e "${text}" | mail -s "${title}" ${mail_to_address}  && logs "Message has been sent"

    # 恢复系统配置
    [ "${use_customize_config}" == "true" ] &&  mv -f /tmp/mail.rc.origin /etc/mail.rc
}

action_select(){
    key=$1                  # 包含路径的完整文件名
    action_type=$2          # 动作类型

    case ${action_type} in
    "add" )
    [ "${add_event}" == "true" -a "${action_main_switch}" == "true" ] && \
    exec_action "${key}" "${add_action}" "${add_first_para}" "${add_last_para}" "add event"

    [ "${add_send_mail}" == "true" ] && mail_dict["${key}"]="${action_type}"
    ;;
    "update")
    [ "${update_event}" == "true"  -a "${action_main_switch}" == "true" ] && \
    exec_action "${key}" "${update_action}" "${update_first_para}" "${update_last_para}" "update event"

    [ "${update_send_mail}" == "true" ] && mail_dict["${key}"]="${action_type}"
    ;;
    "delete")
    [ "${delete_event}" == "true" -a "${action_main_switch}" == "true" ] && \
    exec_action "${key}" "${delete_action}" "${delete_first_para}" "${delete_last_para}" "delete event"

    [ "${delete_send_mail}" == "true" ] && mail_dict["${key}"]="${action_type}"
    ;;
    esac

}


check_action(){
    [ ${number} -eq 0 ] && number=$((${number}+1)) && return 0          # 第一次执行

    for key in $(echo ${!update_dict[*]})
        do
            # 新增文件 在旧字典没有找到匹配
            last_value=${last_dict["${key}"]}
            if [ -z "${last_value}" ];then
                echo "$(date '+%Y-%m-%d %H:%M:%S') - new file ${key}" >> monitor.log
                action_select ${key} "add"
            else
             #      发生变更
                    logs "change file: ${key}  ${new_dict["${key}"]} != ${last_dict["${key}"]}"
                   action_select ${key} "update"
            fi
        done

    # 找出删除的文件
    for key in $(echo ${!last_dict[*]})
    do
        new_value=${new_dict["${key}"]}
        if [ -z "${new_value}" ];then
            # 发生删除
            logs "delete file  ${key}"
            action_select ${key} "delete"
        fi
    done

    # 找出不变的文件
    for key in $(echo ${!new_dict[*]})
    do
        update_value=${update_dict[${key}]}
        if [ -z "${update_value}" ];then
            # 没有发生变化
            logs "file not change  ${key}"
        fi
    done

}

dict_loop(){
    for key in $(echo ${!new_dict[*]})
    do
       last_dict[${key}]=${new_dict[${key}]}
    done
}

convert_to_dict(){
# 拆分输出文本为 文件名和unix时间的字典
# 得到发送变化的文件字典 与 所有文件字典

    IFS=$'\n'
    now_date=$(expr $(date '+%s') - ${sleep_time})
    for x in ${new_names}
        do
            filename=$(echo "${x}" | awk -F"|" '{print $NF}')
            unix_time=$(echo "${x}" | awk -F"|" '{print $1}'  | xargs  -I {} date -d '{}' +%s)

            if [ ${now_date} -le ${unix_time} ] ; then
                       update_dict[${filename}]="${unix_time}"
            fi

            new_dict[${filename}]="${unix_time}"
        done
    IFS=$' \t\n'
}

get_filename_path(){
    new_names=$(find ${folder} -name "${types}" 2>/dev/null | xargs -I {} ls -l --full-time {}| awk '{printf "%s %s|%s\n", $6,$7,$9}')
}

process(){
    # 扫描文件
    get_filename_path
    # 转换为字典
    convert_to_dict
    # 检查结果与链接动作
    check_action
    # 处理邮件
    send_mail
}

while [ "-" == "-" ]
do
    process
    # 清空旧字典并设置新字典
    unset last_dict
    declare -A last_dict
    # 将当前字典作为下一次的对比参考并的旧字典
    dict_loop

    # 清空当前字典并新建
    unset new_dict
    unset update_dict
    unset mail_dict
    declare -A new_dict
    declare -A update_dict
    declare -A mail_dict
    # 刷新变量
    new_names=
    #
    logs "end--------------"
    sleep ${sleep_time}
done
