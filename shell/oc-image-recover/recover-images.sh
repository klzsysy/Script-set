#!/usr/bin/env bash
# 回收所有正在运行pod使用的image， 用于registry故障恢复

registry_svc='172.30.53.243:5000'
registry_route='docker-registry-default.apps.vpclub.cn'
saveFolder=pod-image

# ---------------------------------------------------------

oc project || oc login
allNamespaces=$(oc get ns | awk 'NR>1 {print $1}')
mkdir -p ${saveFolder}

pushImage(){
    getImagePid=$1
    sleep 3
    echo pushImage pid: $$
    echo getImagePid pid: $getImagePid

    docker login -u admin -p `oc whoami -t` ${registry_route}
    mv Success.log  Success-$(date '+%m-%d_%H_%M_%S').log 2>/dev/null
    clearLog=''
    _page=0

    IFS=$'\n'
    while true;
    do
        echo "check text..."
        textNum=$(cat stateStorage.log| wc -l)
        text=$(cat stateStorage.log)

        if [ ${textNum} == ${_page} -o ${textNum} == 0 ];then
            ps -p ${getImagePid} &> /dev/null || exit 0
            echo "not new text ,waiting 10s ..."
            sleep 10

        else
            nextPage=$((${_page} + 1))
            for line in $(echo "${text}" | sed -n "${nextPage},\$p")
            do
               echo "Process Line: ${_page} ${line}"

                _imageID=$(echo ${line} | cut -d ' ' -f 1 )
                _newTag=$(echo ${line} | cut -d ' ' -f 2 ) || (echo Error "$line" && _page=$((${page} + 1)) && continue)
                _imageTar=$(echo ${line} | cut -d ' ' -f 3) ||  (echo Error "$line" && _page=$((${page} + 1)) && continue)
                _pid=$(echo ${line} | cut -d ' ' -f 4) || (echo Error "$line" && _page=$((${page} + 1)) && continue)
                _host=$(echo ${line} | cut -d ' ' -f 5) || (echo Error "$line" && _page=$((${page} + 1)) && continue)

                _count=0
                while ps -p ${_pid} &> /dev/null;
                do
                    echo ${_imageTar} "load ing... waiting"
                    _count=$(( ${_count} + 1 ))
                    if [ ${_count} -gt 10 ];then
                        echo "忽略${_imageTar}继续"
                        break
                    fi
                    sleep 10
                done

                docker tag ${_imageID} ${_newTag}  && docker push ${_newTag}
                echo $line >> Success.log
                clearLog="${_imageTar} ${_host}\n${clearLog}"
                _page=$((${_page} + 1))
            done
        fi
    done

    for _line in ${clearLog}
    do
        _imageTar=$(echo ${_line} | cut -d ' ' -f 1 )
        _host=$(echo ${_line} | cut -d ' ' -f 2)
        ssh ${_host} "rm ${_imageTar}" 2>/dev/null
    done
}

getImage(){
    mv stateStorage.log stateStorage-$(date '+%m-%d_%H_%M_%S').log
    touch stateStorage.log

    for ns in ${allNamespaces}
    do
        ns_dc=$(oc get dc -n ${ns}| awk 'NR>1 && $4!=0 {print $1}')
        for dc in ${ns_dc}
        do
            _pod=$(oc get pod -n ${ns} -o wide | grep -E "^${dc}" | grep 'Running' |  head -n 1 )
            podName=$(echo ${_pod} | awk '{print $1}')
            podHost=$(echo ${_pod} | awk '{print $NF}')

            oc get pod ${podName} -n ${ns} -o yaml | grep 'image:' | grep "${registry_svc}" -q

            if [ $? -eq 0 ];then
                scp execCommand.sh ${podHost}:/tmp/ &>/dev/null
                echo "Start Get ${ns} ${dc} Image ...."
                _ssh=$(ssh ${podHost} "bash /tmp/execCommand.sh ${podName}" 2>/dev/null)
                [ $? -ne 0 ] && echo ${ns} ${dc} ${podName} ${podHost} save image faild && continue

                imageTar=`echo "${_ssh}" | head -n 1`
                imageTag=`echo "${_ssh}" | awk 'NR==2 {print $0}'`
                imageID=`echo "${_ssh}" | awk 'NR==3 {print $0}'`
                imageNs=`echo "${_ssh}" | awk 'NR==4 {print $0}'`   # A namespace deploymentconfig may use B namespace image

                # 仓库里的镜像tag优先
                _is_tag=$(oc get is -n ${ns} ${dc} | awk 'NR==2 {print $3}')
                if [ "${_is_tag}" != "" ];then
                    echo ${_is_tag} | grep -q latest || imageTag=$(echo ${_is_tag} | awk -F, '{print $1}')
                fi

                if [ -f "${saveFolder}/${imageTar}" ];then
		    echo "${dc} is exist"
		else
                    scp ${podHost}:${imageTar} ${saveFolder} 2>/dev/null && ssh ${podHost} "rm -rf ${imageTar}" 2>/dev/null && \
                    (docker images | grep ${imageID} -q || docker load -i ${saveFolder}/${imageTar} >/dev/null ) &
                fi
                imagePid=$!
                echo "${imageID} ${registry_route}/${imageNs}/${dc}:${imageTag} ${imageTar} ${imagePid} ${podHost}" >> stateStorage.log
                echo "Success Load Image: ${ns} ${dc}"
            fi
        done
    done
}


getImage &
getImagePid=$!
pushImage ${getImagePid}