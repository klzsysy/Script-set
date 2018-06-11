#!/usr/bin/env bash
# 转移OpenShift的资源到另一个OpenShift

origin_registry='docker-registry-default.apps.vpclub.io'
origin_openshift='https://devops.vpclub.io:8443'
origin_registry_token=
origin_openshift_id=sonny

shift_registry='new-registry-default.apps.vpclub.io'
shift_openshift='https://172.16.20.5:8443'
shift_openshift_id=admin
shift_registry_token=

# 排除的namespaces
exclude_namespace="default|openshift|cicd|databases"
#citic-mall-dev|citic-mall-stage|cmbs-dev|cmbs-stage
include_namespace="^doc|gateway-dev|gateway-stage|heshenghuo-dev|heshenghuo-stage|mcs-dev|mcs-stage|moses-dev|moses-stage|\
promotion-dev|promotion-stage|shm-dev|shm-stage|umall-dev|umall-stage|vpintl-dev|vpintl-stage|yingxiaobao-dev|yingxiaobao-stage|zuihebei-dev"

# remote exec
# 在远程执行导入 远程主机有oc 并已登录 $shift_openshift
exec_host='172.16.20.8'

#
intranet_registry="docker-registry.default.svc:5000"
# -----------------------------------

login_origin(){
    oc project 2>/dev/null | grep -P -q ${origin_openshift}
    if [ $? -ne 0 ];then
        oc login ${origin_openshift}
    fi
    set -e
    [ -z "${origin_openshift_id}" ] && origin_openshift_id=$(oc whoami)
    [ -z "${origin_registry_token}" ] && origin_registry_token=$(oc whoami -t)

    docker login -u ${origin_openshift_id} -p "${origin_registry_token}" ${origin_registry}
    set +e
}

login_shift(){
    if [ -z "${shift_openshift_id}" ] || [ -z "${shift_registry_token}" ];then
        oc project 2>/dev/null | grep -P -q ${shift_openshift}
        if [ $? -ne 0 ];then
            oc login ${shift_openshift}
        fi
    fi
    set -e
    [ -z "${shift_openshift_id}" ] && shift_openshift_id=$(oc whoami)
    [ -z "${shift_registry_token}" ] && shift_registry_token=$(oc whoami -t)
    docker login -u ${shift_openshift_id} -p "${shift_registry_token}" ${shift_registry}
    set +e
}


shift_svc(){
    origin_registry_svc=$(oc get svc --all-namespaces | grep -v -P "${exclude_namespace}" | grep -i -P "${include_namespace}")

    echo "${origin_registry_svc}" | while read line
    do
        _project=$(echo "${line}" | awk '{print $1}')
        _svc_name=$(echo "${line}" | awk '{print $2}')

        # 过滤heketi
        echo ${_svc_name} | grep -q -P 'heketi'
        if [ $? -ne 0 ];then
            oc get svc ${_svc_name} -o yaml -n ${_project} | head -n -2 | sed '/uid/d' | sed '/selfLink/d' | sed '/resourceVersion/d' | \
            sed '/creationTimestamp/d' | sed '/clusterIP/d' | ssh ${exec_host} 'oc create -f -'
        fi
    done
}

shift_dc(){
    origin_registry_dc=$(oc get dc --all-namespaces | grep -v -P "${exclude_namespace}" | grep -i -P "${include_namespace}")

    echo "${origin_registry_dc}" | while read line
    do
        _project=$(echo "${line}" | awk '{print $1}')
        _dc_name=$(echo "${line}" | awk '{print $2}')

        # build image url
        _images="${intranet_registry}\/${_project}\/${_dc_name}:latest"

        oc get dc ${_dc_name} -o yaml -n ${_project} | sed -n '1, /^status:/p'  | head -n -1 | sed '/uid/d' | sed '/selfLink/d' | sed '/resourceVersion/d' | \
        sed '/creationTimestamp/d' | sed '/generation/d' | sed "s/172.30.*$/${_images}/g" |  ssh ${exec_host} 'oc create -f -'
    done
}


shift_route(){
    origin_registry_route=$(oc get route --all-namespaces | grep -v -P "${exclude_namespace}" | grep -i -P "${include_namespace}")

    echo "${origin_registry_route}" | while read line
    do
        _project=$(echo "${line}" | awk '{print $1}')
        _route_name=$(echo "${line}" | awk '{print $2}')
#        oc expose service ${_route_name} --port=$(oc get  -n ${_project} route ${_route_name} -o jsonpath={.spec.port.targetPort})  -n ${_project}
        _route_port=$(oc get route ${_route_name} -n ${_project} | tail -n 1 | awk '{print $4}' | sed  's/-tcp//g')
        ssh ${exec_host} "oc expose service  ${_route_name} -n ${_project} --port=${_route_port}" < /dev/null

#        oc get route ${_route_name} -o yaml -n ${_project} | sed -n '1, /^status:/p'  | head -n -1 | sed '/uid/d' | sed '/selfLink/d' | sed '/resourceVersion/d' | \
#        sed '/creationTimestamp/d'  | ssh ${exec_host} 'oc create -f -'
    done
}

shift_confmap(){
    _IFS=${IFS}
    nss=$(echo "$include_namespace" | tr "|" " " | tr -d "^")
    for ns in ${nss};
    do
        oc get cm -n ${ns} 2>&1 | grep -q "found"
        if [ $? -ne 0 ];then
#            ssh ${exec_host} "oc delete cm --all -n ${ns}"
            IFS=$'\n\n'
            for line in $(oc get cm -n ${ns} | tail -n +2)
            do
                echo " -------------------"
                _confmap=$(echo "${line}" | awk '{print $1}')
                oc get cm ${_confmap} -n ${ns} -o yaml | sed '/creationTimestamp/d' |   sed '/uid/d' | sed '/selfLink/d' | sed '/resourceVersion/d' | ssh ${exec_host} 'oc create -f -'
            done
            echo " -------------------"
        fi
    done
    IFS=${_IFS}
}

shift_users(){
    origin_registry_users=$(oc get users | tail -n +2 | awk '{print $1}')
    for user in ${origin_registry_users}
    do
        oc get users ${user} -o yaml |  sed '/creationTimestamp/d' |   sed '/uid/d' | sed '/selfLink/d' | sed '/resourceVersion/d' | ssh ${exec_host} 'oc create -f -'
    done
    nss=$(echo "$include_namespace" | tr "|" " ")
    for ns in ${nss}
    do
        ns=$(echo ${ns} | tr -d '^')
        ns_role=$(oc get rolebindings -n ${ns})
        for user in ${origin_registry_users}
        do
            _role=$(echo "${ns_role}" | grep ${user} | awk '{print $1}' | head -n 1)
            if [ -n "${_role}" ];then
                ssh ${exec_host}  "oc policy add-role-to-user ${_role} ${user} -n ${ns}"
            fi
        done
    done
}

shift_images(){
    origin_registry_images=$(oc get is --all-namespaces | grep -v -P "/${exclude_namespace}/" | grep -i -P "${include_namespace}"| grep ':5000')

    if [ -z "${origin_registry_images}" ];then
            echo "没有image需要处理"
            return 0
    fi

    echo "${origin_registry_images}" | while read line
    do

#        echo "${line}"
        _project=$(echo "${line}" | awk '{print $1}')
        _app_name=$(echo "${line}" | awk '{print $2}')
        _tag=$(echo "${line}" | awk '{print $4}')

        if [ -z "${_tag}" ];then
            continue
        fi

        echo "${_tag}" | grep -q -E '^latest$'
        if [ $? -ne 0 ];then
            echo "${_tag}" | grep -q 'latest' && _tag=latest || _tag=$(echo ${_tag} | awk -F, '{print $1}')
        fi

#        echo "docker pull \"${origin_registry}/${_project}/${_app_name}:${_tag}\""
#        echo "docker tag  \"${origin_registry}/${_project}/${_app_name}:${_tag}" "${shift_registry}/${_project}/${_app_name}:${_tag}\""
#        echo "docker push \"${shift_registry}/${_project}/${_app_name}:${_tag}\""

        docker pull "${origin_registry}/${_project}/${_app_name}:${_tag}" && \
        docker tag  "${origin_registry}/${_project}/${_app_name}:${_tag}" "${shift_registry}/${_project}/${_app_name}:${_tag}" && \
        docker push "${shift_registry}/${_project}/${_app_name}:${_tag}"

    done
}

create_project(){
    oc get project | grep -v -P ${exclude_namespace} | grep -P ${include_namespace} | awk '{print $1}' | xargs -n 1 -I {} ssh ${exec_host} "oc new-project {}"
}


start(){
    # 有一个参数
    if [ -n "$2" ];then
        origin_include_namespace=${include_namespace}
        include_namespace=$2
    fi

    case $1 in
    dc|deploy)
    shift_dc
    ;;
    svc|service)
    shift_svc
    ;;
    route)
    shift_route
    ;;
    image|images)
    shift_images
    ;;
    cm|configmaps)
    shift_confmap
    ;;
    user|users)
    shift_users
    ;;
    *)
    login_shift
    login_origin
    create_project
    shift_images
    shift_dc
    shift_svc
    shift_route
    shift_confmap

    if [ -n "$2" ];then
        include_namespace=${origin_include_namespace}
    fi
    shift_users
    ;;
    esac
}

start $@