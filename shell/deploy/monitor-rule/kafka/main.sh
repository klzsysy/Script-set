#!/usr/bin/env sh
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/bin:/root/bin"
cd `dirname $0` &>/dev/null

zookeeper_host=$(cat zookeeper)
kafka_host=$(cat kafka)

IFS=$'\n'

port_test(){
    timeout 2 bash -c "cat < /dev/null > /dev/tcp/$1/$2" &>/dev/null
    return $?
}

check_zookeeper(){
    for line in ${zookeeper_host}
    do
        ip=$(echo "${line}" | awk '{print $1}')
        port=$(echo "${line}" | awk '{print $2}')
        
        port_test ${ip} ${port}
        if [ $? -ne 0 ];then
            echo "restart zookeeper in ${ip} " >> main.log
            ssh ${ip} '/opt/kafka/config/zkServer.sh start'
        fi
    done
}

check_kafka(){
    for line in ${kafka_host}
    do
        ip=$(echo "${line}" | awk '{print $1}')
        port=$(echo "${line}" | awk '{print $2}')
        
        port_test ${ip} ${port}
        if [ $? -ne 0 ];then
            echo "restart kafka in ${ip} " >> main.log
            ssh ${ip} '/opt/kafka/bin/kafka-server-start.sh -daemon /opt/kafka/config/server.properties'
        fi
    done
}

run(){
    check_zookeeper
    check_kafka
}

$@