#!/usr/bin/env python3
# 实现Nginx与King配置相互转换
# Author: Sonny Yang
# Email: klzsysy@gmail.com

import sys
import re
import os
import subprocess
import argparse

try:
    import requests
except ModuleNotFoundError:
    print('not find requests module, try install...')
    requests_re = os.system('pip install requests')
    if requests_re == 0:
        import requests
    else:
        print('requests install failure!, please manually install')

DEFAULT = {
    'KONG_ADMIN': 'http://kong-admin-gateway-stage.apps.hsh.vpclub.cn/apis/',
    'nginx_cm_name': 'nginx-api',
    'nginx_project': 'gateway-nginx-prod',
    'openshift_url': 'https://devops.hsh.vpclub.cn:8443',
}


def nginx_to_kong(text, args):
    tag = 0
    location = ''
    upstream = ''
    name = ''

    for line in text.splitlines():
        if 'location' in line:
            location = line.split()[1].strip('\{')
            # 上个location不是反代
            if tag == 1:
                tag -= 1
            tag += 1
        elif 'proxy_pass' in line:
            upstream = line.split()[1].strip(';')

            # upstream IP与域名判断，提取应用名
            if re.match('\S+?\d+\.\d+.\d+.\d+', upstream):
                name = '-'.join(location.split('/')).strip('-')
            else:
                name = upstream.split('.')[0].replace('http://', '', 1)
            tag += 1
        else:
            pass
        if tag == 2:
            upstream = upstream.replace('{}'.format(args.switch[0]), '{}'.format(args.switch[1]))
            name = name.replace('{}'.format(args.switch[0]), '{}'.format(args.switch[1]))

            create_kong_api(args, uris=location, upstream_url=upstream, name=name)
            tag = 0


def create_kong_api(args, **kw):

    kw['strip_uri'] = kw.get('strip_uri', 'true')

    kw['http_if_terminated'] = kw.get('http_if_terminated', 'true')

    # r = requests.post(args.dkong, data={'name': kw['name'], 'uris': kw['uris'], 'upstream_url': kw['upstream_url'],
    #                                     'http_if_terminated': kw['http_if_terminated'], 'strip_uri': kw['strip_uri']})
    r = requests.post(args.dkong, data=kw)

    print(r.status_code, r.reason)
    if r.status_code == 409:
        print(kw['name'], ' 已存在')
    elif r.status_code == 201:
        print('name: %s Created!' % kw['name'])
    else:
        print('name: %s error!' % kw['name'])


def kong_to_nginx(args):

    raw_text = requests.get(args.skong, params='size=1000')
    json_data = raw_text.json()['data']

    nginx_api = '''
server {
    listen      80;
    server_name _;

    access_log  /dev/stdout  main;
    error_log   /dev/stderr;
    
    '''

    for api in json_data:
        location = api['uris'][0]
        upstream_url = api['upstream_url']

        # --switch
        upstream_url = upstream_url.replace('{}'.format(args.switch[0]), '{}'.format(args.switch[1]))

        _nginx_api = '''
    location {} {{
        proxy_pass {}/;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }}
        '''.format(location, upstream_url.strip('/'))

        nginx_api += _nginx_api

    nginx_api += '\n}\n'
    nginx_api = nginx_api.replace('\n', '\\n')
    # print(nginx_api)

    _cm_json = '''
{{
    "apiVersion": "v1",
    "data": {{
        "default.conf": "{}"
    }},
    "kind": "ConfigMap",
    "metadata": {{
        "name": "{}",
        "namespace": "{}"
        }}
}}
    '''

    return _cm_json.format(nginx_api, args.nginxcm, args.nginxproject)


def import_cm(_json, args):
    oc_status = subprocess.check_output('oc project', shell=True).decode()
    if DEFAULT['openshift_url'] not in oc_status:
        login = subprocess.call('oc login %s' % DEFAULT['openshift_url'],  shell=True)
        if login != 0:
            print('login failed!')
            exit(-1)

    cm_re = subprocess.call('oc get cm %s -n %s' % (args.nginxcm, args.nginxproject),  shell=True)
    if cm_re != 0:
        print('config maps不存在，需要手动创建')
        exit(-1)

    exec_import = os.system('oc apply -f - <<\'EOF\'\n%s\nEOF' % _json)
    if exec_import == 0:
        os.system('oc rollout latest dc/nginx -n gateway-nginx-prod')


def kong_to_kong(args):
    raw_text = requests.get(args.skong, params='size=1000')
    json_data = raw_text.json()['data']

    for _api in json_data:
        _api['uris'] = _api['uris'][0]

        # 应用 --switch 参数
        _api['upstream_url'] = _api['upstream_url'].replace('{}'.format(args.switch[0]), '{}'.format(args.switch[1]))
        _api['name'] = _api['name'].replace('{}'.format(args.switch[0]), '{}'.format(args.switch[1]))

        _api.pop('id')
        _api.pop('created_at')

        # 处理正则
        if re.match(args.filter, _api['uris']):
            if args.reverse is False:
                create_kong_api(args, **_api)
            else:
                print(_api['uris'], 'is match filter, but reverse=true, discard!')

        else:
            if args.reverse is True:
                create_kong_api(args, **_api)
            else:
                print(_api['uris'], 'is not match filter, discard!')


def args_parser():
    parse = argparse.ArgumentParser(prog='switch-nginx-kong', description='Nginx与Kong网关配置相互转换',
                                    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                    epilog='nginx转kong时，从标准输入读取nginx配置')

    parse.add_argument('-src', choices=['nginx', 'kong'], help="选择转换来源", required=True)
    parse.add_argument('-dest', choices=['nginx', 'kong'], help="选择转换到目标", required=True)
    parse.add_argument('-skong', type=str, default=DEFAULT['KONG_ADMIN'], help='源KongAPI接口地址')
    parse.add_argument('-dkong', type=str, default=DEFAULT['KONG_ADMIN'], help='目标KongAPI接口地址')
    parse.add_argument('-nginxcm', type=str, default=DEFAULT['nginx_cm_name'], help='nginx configmaps name，转换到nginx时必需提供')
    parse.add_argument('-nginxproject', type=str, default=DEFAULT['nginx_project'], help='nginx project name，转换到nginx时必需提供')
    parse.add_argument('-ocurl',  default=DEFAULT['openshift_url'], help='openshift 管理地址，转换到nginx时必需提供')

    parse.add_argument('--filter', type=str, default='.*', help="对URL部分进行正则过滤")
    parse.add_argument('--filter-reverse', dest='reverse', action='store_true', help='反转正则匹配')
    parse.add_argument('--switch', nargs=2, default=['-stage', '-stage'], help='关键字替换，替换name及uris')
    parse.add_argument('--version', action='version', version='%(prog)s 1.0', help='输出版本号')

    # debug_args = '-src kong -dest kong --filter /moses/.*|/cmbs/.* ' \
    #              '--switch vpclub.io ek.vpclub.cn ' \
    #              '-dkong http://kong-admin-kong-gateway-dev.apps.ek.vpclub.cn/apis/  ' \
    #              '-skong http://kong-admin-kong-gateway-dev.apps.vpclub.io/apis/'.split()

    # debug_args = None

    return parse.parse_args()


def main():
    args = args_parser()

    if args.src == "nginx" and args.dest == 'kong':
        nginx_to_kong(sys.stdin.read(), args)
    elif args.src == 'kong' and args.dest == 'nginx':
        import_cm(kong_to_nginx(args), args)
    elif args.src == args.dest == 'kong':
        kong_to_kong(args)
    else:
        print("不支持的转换方式")


if __name__ == '__main__':
    main()
