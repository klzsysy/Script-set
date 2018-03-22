#!/usr/bin/env bash
# 通过pod名得到镜像信息

export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/root/bin

set -e

podName=$1

[ -z "${podName}" ] && exit 1

_img=$(docker inspect `docker ps | grep ${podName} | grep -v POD | cut -d' ' -f1` | grep '"Image": "sha256' | awk 'NR==1 {print $2}')
imageId=${_img:8:12}
_iamge=$(docker images | grep ${imageId})
_imageName=$(echo ${_iamge} | awk '{print $1}')

imageNs=$(echo ${_imageName} | cut -d '/' -f 2)
imageTag=$(echo ${_iamge} | awk '{print $2}')

[ "${imageTag}" == "<none>" ] && imageTag='latest'

tarName=`echo ${_imageName} | awk -F/ '{print $NF}'`-${imageId}.tar
[ -f "${tarName}" ] || docker save ${imageId} >  ${tarName}

echo ${tarName}         # 压缩包名
echo ${imageTag}        # image tag
echo ${imageId}         # image sha256
echo ${imageNs}         # image url prefix

set +e