#!/usr/bin/env bash
# OSX mount bitlocker volume
# __author__='Sonny Yang'


install_program(){
    which brew &>/dev/null || /usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
    brew update && \
    brew intall wget && \
    brew install cmake && \
    brew install PolarSSL && \
    brew install Caskroom/cask/osxfuse && \
    wget https://github.com/Aorimn/dislocker/archive/v0.7.1.tar.gz && \
    tar -xzf v0.7.1.tar.gz && \
    cd dislocker-0.7.1 && \
    brew install src/dislocker.rb
}


# check install
which dislocker-fuse &>/dev/null
[ $? -ne 0 ] && install_program


show_ntfs(){
    msg=$(diskutil list | sed -n '/external/,/^$/p' | sed '$d')
    line=$(echo -n "${msg}" | wc -l)

    if [ ${line} -eq 0 ];then
        echo 'not bitclockrt device'
    else
        echo "${msg}"
    fi
}


mount_disk(){
    set -e
    mkdir -p /tmp/bitlocker-entrypoint

    pat=$1
    pwd=$2

    if [ $1 -gt 0 ] 2>/dev/null;
    then
        bit_dev=$(show_ntfs | grep "$1:" | awk '{print $NF}')
        if [ -z "${bit_dev}" ];then
            echo "not bitclockrt device" >&2
            exit -1
        fi
        pat="/dev/$(show_ntfs | grep "$1:" | awk '{print $NF}')"
    elif [ ! -b "$disk}" ];then
        echo "the $1 is not block device"
        exit 1
    fi

    args=$(echo $@ | awk '{$1="";$2="";print $0}')
    disk=$(echo ${pat} | awk -F/ '{print $NF}')

    # 解密
    sudo dislocker-fuse -v -V ${pat} -u${pwd} ${args} -- /tmp/bitlocker-entrypoint/${disk}
    if [ $? -ne 0 ];then
        echo 'Password Error'
        exit 3
    else
        # 虚拟挂载点
        sudo hdiutil attach -imagekey diskimage-class=CRawDiskImage /tmp/bitlocker-entrypoint/${disk}/dislocker-file
        if [ $? -eq 0 ];then
            echo 'mount success!'
        else
            echo 'mount fail'
            exit 4
        fi
    fi

}


umount_disk(){
    set -e
    # 记录执行卸载一个卷时的原始名
    umount_vol=

    [ "$3" == "-force" -o "$3" == "-f" ] && force='-force'


    detach_volume(){
        if [ -n "$1" ];then
            sudo hdiutil detach /tmp/bitlocker-entrypoint/${1} ${2}
            rm -rf /tmp/bitlocker-entrypoint/${1}
        else
            for x in $(ls -l /tmp/bitlocker-entrypoint/  | awk 'NR>1 {print $NF}')
            do
                sudo hdiutil detach /tmp/bitlocker-entrypoint/${x} ${2}
                rm -rf /tmp/bitlocker-entrypoint/${x}
            done
        fi
    }

    bit_mount=$(echo "$(hdiutil info | grep dislocker-file -A 15 | grep /dev/)" | nl -n ln)
    stats=$(echo "${bit_mount}" | awk '{print NF}')

    if [ $# -eq 0 ];then
        echo 'Current Mount Bitlocker Volume'
        echo "${bit_mount}"
        exit 0

    elif [ "$2" == "-h" ];then
        script_help

    elif [ "$2" == "all" ];then
        set +e
        while read d
        do
            diskutil umount "$(echo "${d}" | awk '{print $NF}')"
        done < <(echo "${bit_mount}")
        detach_volume

    elif [ $2 -gt 0 ] 2>/dev/null ;then
        volume_name=$(echo "${bit_mount}" | grep "^$2" | awk '{print $NF}')
        umount_vol=$(hdiutil info | grep ${volume_name} -B 15 | head -n 1 | awk -F/ '{print $(NF-1)}')
        # stats != 3 时虚拟硬盘没有挂载
        [ ${stats} -eq 3 ] && diskutil umount "$(echo "${bit_mount}" | grep "^$2" | awk '{print $NF}')"
        detach_volume "${umount_vol}" "${force}"

    elif [ -d "$2" ];then
        umount_vol=$(hdiutil info | grep ${2} -B 15 | head -n 1 | awk -F/ '{print $(NF-1)}')
        [ ${stats} -eq 3 ] && diskutil umount "$2"
        detach_volume "${umount_vol}" "${force}"

    else
        script_help
	exit 1
    fi

    set +e
}



script_help(){
    SCRIPTS_MAME=$(echo $BASH_SOURCE)
    cat <<EOF
    Instructions:
    Mount
        Syntax
            $ $SCRIPTS_MAME <dev|number> <password> <more_args>
        Example:
          mount
            $ $SCRIPTS_MAME /dev/disk2s2 12345
          show external ntfs volumes
            $ $SCRIPTS_MAME
    Umount
        Syntax
            $ $SCRIPTS_MAME um [dev|number|volume|all] [-force|-f]
        Example:
          show bitlocker volume mount status
            $ $SCRIPTS_MAME um
          Umount sigin Volume
            $ $SCRIPTS_MAME um  /Volumes/Data
          or
            $ $SCRIPTS_MAME um  /dev/disk2
          or (Get the number via "$SCRIPTS_MAME um")
            $ $SCRIPTS_MAME um  1
EOF
}


# 0个参数
if [ $# -eq 0 ];then
    show_ntfs

# 一个参数
elif [ $# -eq 1 ];then

    if [ "$1" == "um" ];then
        umount_disk
    elif  [ "$1" == "-h" ];then
        script_help
    else
        script_help
	exit 1
    fi
# 两个或更多参数
else
    if [ "$1" == "um" ];then
        umount_disk $@
    else
        mount_disk $@
    fi
fi
