#!/usr/bin/env bash
# 使用tcping测试端口联通率
#
# by: Sonny@forchange.tech
#     klzsysy@gmail.com
#

if [ -z "$1"  -o -z "$2" ];then
    echo -e "Usage:\n    $BASH_SOURCE example.com 443" >&2
    exit 1
fi

if ! which tcping &>/dev/null ;then
    echo -e "you must install tcping
    macos:  brew install tcping
    centos: yum install -y tcping" >/dev/null
    exit 1
fi

function handle_TERM()
{
    kill -9  $process
    declare total=$(echo $(cat /tmp/tcpings.tmp | wc -l))
    declare ok=$(echo $(cat /tmp/tcpings.tmp | grep -e 'open' | wc -l))
    echo $(date '+%Y-%m-%d %H:%M:%S.%s') "- 成功率:" $(awk -v total=${total} -v ok=${ok} 'BEGIN {printf "%.2f\n", ok/total * 100}')
    exit 0

}

trap 'handle_TERM' 15 2

rm -rf  /tmp/tcpings.tmp &>/dev/null || true
number=1
while true;do
    echo "$(date '+%Y-%m-%d %H:%M:%S.%s') - sep $number: $(tcping -t 1 $1 $2)" | tee -a /tmp/tcpings.tmp &
    process=$!
    wait $process
    number=$[number+1]
    sleep 0.02
done