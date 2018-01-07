#!/usr/bin/env python3

import sys
import requests
import re
import os
import subprocess
import argparse


DEFAULT = {
    'KONG_ADMIN': 'http://kong-admin-gateway-stage.apps.hsh.vpclub.cn/apis/',
    'nginx_cm_name': 'nginx-api',
    'nginx_project': 'gateway-nginx-prod',
    'openshift_url': 'https://devops.hsh.vpclub.cn:8443',
}

def split_raw(text):
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

            # upstream IP与域名判断
            if re.match('\S+?\d+\.\d+.\d+.\d+', upstream):
                name = '-'.join(location.split('/')).strip('-')
            else:
                name = upstream.split('.')[0].replace('http://', '', 1)
            tag += 1
        else:
            pass
        if tag == 2:
            create_api(location=location, upstream=upstream, name=name)
            tag = 0


def create_api(**kw):

    r = requests.post(DEFAULT['KONG_ADMIN'], data={'name': kw['name'], 'uris': kw['location'], 'upstream_url': kw['upstream'],
                                        'http_if_terminated': 'true'})
    print(r.status_code, r.reason)
    if r.status_code == 409:
        print(kw['name'], ' 已存在')
    elif r.status_code == 201:
        print('name: %s Created!' % kw['name'])
    else:
        print('name: %s error!' % kw['name'])


def conver_to_nginx(to_prod=True):

    raw_text = requests.get(DEFAULT['KONG_ADMIN'])
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

        if to_prod:
            upstream_url = upstream_url.replace('-stage', '-prod')

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

    return _cm_json.format(nginx_api, DEFAULT['nginx_cm_name'], DEFAULT['nginx_project'])


def import_cm(_json):
    oc_status = subprocess.check_output('oc project', shell=True).decode()
    if DEFAULT['openshift_url'] not in oc_status:
        login = subprocess.call('oc login %s' % DEFAULT['openshift_url'],  shell=True)
        if login != 0:
            print('login failed!')
            exit(-1)

    cm_re = subprocess.call('oc get cm %s -n %s' % (DEFAULT['nginx_cm_name'], DEFAULT['nginx_project']),  shell=True)
    if cm_re != 0:
        print('config maps不存在，需要手动创建')
        exit(-1)

    exec_import = os.system('oc apply -f - <<\'EOF\'\n%s\nEOF' % _json)
    if exec_import == 0:
        os.system('oc rollout latest dc/nginx -n gateway-nginx-prod')


def args_parser():
    parse = argparse.ArgumentParser(prog='nginx-switch-kong', description='Nginx与Kong网关配置相互转换',
                                    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parse.add_argument('-src', choices=['nginx', 'kong'], help="选择转换来源", required=True)
    parse.add_argument('-kong', type=str, default=DEFAULT['KONG_ADMIN'])
    parse.add_argument('-ocurl',  default=DEFAULT['openshift_url'])
    parse.add_argument('--switch',  nargs=2, default=['stage', 'prod'], help='关键字替换')
    parse.add_argument('--version', action='version', version='%(prog)s-1.0', help='输出版本号(prog)表示文件名或ArgumentParser中定义的prog值')

    args = parse.parse_args()
    print(args.src)
    print(args.switch)
    print(args.kong)
    print(args.ocurl)



    return parse.parse_args()


def main():
    args = args_parser()
    exit(0)

    if args.src == "nginx":
        split_raw(sys.stdin.read())
    else:
        import_cm(conver_to_nginx(to_prod=False))

if __name__ == '__main__':
    main()
