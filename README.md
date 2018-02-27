# Overview
一些工作中编写的脚本

| script name                                            | language | description                                                  |
| ------------------------------------------------------ | -------- | ------------------------------------------------------------ |
| [copy-file](python/copy-file.py)                       | Python   | 一个带过滤器的增强文件复制脚本                               |
| [get-region-route-acl](python/get-region-route-acl.py) | Python   | 从apnic站点获取路由信息并转换为Cisco的ACL，可用于基于IP的国内外流量分离，或转换为ip mask格式 |
| [multi-gw-monitor](python/multi-gw-monitor.py)         | Python   | 通过轮询检测与本机同一子网内多个网关的网络连通状况，用于监测网关状态 |
| [dhcp-backup](python/dhcp-backup.py)                   | Python   | 将windown server dhcp数据备份并邮件通知                      |
| [windows_log_analysis](python/windows-log-analysis.py) | Python   | window日志提取格式化为excel                                  |
| [switch-nginx-kong](python/switch-nginx-kong)          | Python   | 在应用nginx与kong之间转换配置，用于作为API网关场景           |
| [oc-to-k8s](python/oc-to-k8s.py)                       | Python   | 将运行于OpenShift中的应用部署到kubernetes中                  |
| [monitor_folder](shell/monitor_folder.sh)              | Shell    | 轮询文件夹，监控其变化做出自定义动作，如发生改变就执行复制动作 |
| [osx-mount-bitlocker](shell/osx-mount-bitlocker.sh)    | Shell    | OSX下挂载/卸载 bitlocker加密卷，使用dislocker方案            |
| [deploy](shell/deploy/deploy.sh)                       | Shell    | 从openshift或k8s获取java微服务应用镜像部署到裸机。完成自动运行、自动更新API路由、自动更新DNS、健康检查、故障恢复等功能。用于临时测试或者临时业务迁移。 |