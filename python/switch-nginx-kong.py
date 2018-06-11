#!/usr/bin/env python3
# 实现Nginx与Kong配置相互转换
# Author: Sonny Yang
# Email: klzsysy@gmail.com

import sys
import re
import os
import subprocess
import argparse

try:
    import requests
except ImportError:
    print('not find requests module, try install...')
    requests_re = os.system('pip3 install requests')
    if requests_re == 0:
        import requests
    else:
        print('requests install failure!, please manually install')


# ---

DEFAULT = {
    'KONG_ADMIN': 'http://kong-admin-gateway-stage.apps.hsh.vpclub.cn/apis/',
    'nginx_cm_name': 'nginx-api',
    'project': 'gateway-nginx-prod',
    'openshift_url': 'https://devops.hsh.vpclub.cn:8443',
    'k8s_kc': 'kubectl --kubeconfig /root/work/config'
}

# ---------


def build_svc(upstream, svc_port):
    """
    将upstream转换为k8s内部地址
    :param upstream: http://app-name-namespace-env.apps.xx.com
    :param svc_port: default is 8080
    :return: http://app_name.namespace-env:8080
    """
    _url = upstream.split('.')
    try:
        url_prefix = _url[0]
        i = re.match('(.*?)-(\w+-\w+)$', url_prefix)
        _name = i.group(1)
        _ns = i.group(2)
    except IndexError:
        return upstream
    except AttributeError:
        return upstream
    else:
        return _name + '.' + _ns + ':{}'.format(svc_port)


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
            upstream = upstream.replace('{}'.format(args.rep_up[0]), '{}'.format(args.rep_up[1]))
            name = name.replace('{}'.format(args.rep_name[0]), '{}'.format(args.rep_name[1]))

            if filter_process(args, uris=location):
                if args.svc:
                    upstream = build_svc(upstream, svc_port=args.svc_port)

                create_kong_api(url=args.dkong, uris=location, upstream_url=upstream, name=name, hosts=args.hosts)
            tag = 0


def create_kong_api(url, method='POST', **kw):

    r = requests.request(method=method, url=url, data=kw)

    print(r.status_code, r.reason)
    if r.status_code == 409:
        print(kw['name'], ' 已存在')
    elif r.status_code == 201:
        print('name: %s Created!' % kw['name'])
    elif r.status_code == 200:
        print('name: %s Updated!' % kw['name'])
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

        # --
        upstream_url = upstream_url.replace('{}'.format(args.rep_up[0]), '{}'.format(args.rep_up[1]))

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

    return _cm_json.format(nginx_api, args.nginxcm, args.project)


def import_cm(_json, args):
    oc_status = subprocess.check_output('oc project', shell=True).decode()
    if DEFAULT['openshift_url'] not in oc_status:
        login = subprocess.call('oc login %s' % DEFAULT['openshift_url'],  shell=True)
        if login != 0:
            print('login failed!')
            exit(-1)

    cm_re = subprocess.call('%s get cm %s -n %s' % (args.kc, args.nginxcm, args.project),  shell=True)
    if cm_re != 0:
        print('config maps不存在，需要手动创建')
        exit(-1)

    exec_import = os.system('oc apply -f - <<\'EOF\'\n%s\nEOF' % _json)
    if exec_import == 0:
        os.system('oc rollout latest dc/nginx -n gateway-nginx-prod')


def filter_process(args, uris):
    if re.match(args.filter, uris):
        if args.reverse is False:
            return True
        else:
            print(uris, 'is match filter, but reverse=true, discard!')
            return False
    else:
        if args.reverse is True:
            return True
        else:
            print(uris, 'is not match filter, discard!')
            return False


class ChangeKong(object):
    def __init__(self, args):
        self.args = args

        self.raw_text = requests.get(self.args.skong, params='size=1000')
        self.json_data = self.raw_text.json()['data']
        self.change_mode = self.args.change
        self._action()

    def _action(self):
        if self.change_mode == 'update':
            self.change_attrib = self._read_update_args()
            self._update_host()

    def _read_update_args(self):
        x = {}
        for _attribute in self.args.update:
            try:
                _key, _value = _attribute.split('=')

            except ValueError:
                print('Error value %s' % _attribute)
            else:
                x[_key] = _value
        return x

    def _update_host(self):
        update_data = {}
        for _api in self.json_data:
            # 过滤
            if filter_process(self.args, _api['uris'][0]):
                for _key, _value in self.change_attrib.items():
                    update_data['name'] = _api['name']
                    update_data[_key] = _value

                    # update api
                    create_kong_api(url=self.args.skong+'/%s' % _api['id'], method='PATCH', **update_data)
                    update_data.clear()


def kong_to_kong(args):
    raw_text = requests.get(args.skong, params='size=1000')
    json_data = raw_text.json()['data']

    # if args.svc:
    #     svc_list = get_svc_upstream(args)

    for _api in json_data:
        _api['uris'] = _api['uris'][0]

        # 应用 --replace 参数

        _api['upstream_url'] = _api['upstream_url'].replace('{}'.format(args.rep_up[0]), '{}'.format(args.rep_up[1]))
        _api['name'] = _api['name'].replace('{}'.format(args.rep_name[0]), '{}'.format(args.rep_name[1]))
        _api['hosts'] = args.hosts

        _api.pop('id')
        _api.pop('created_at')

        if filter_process(args, uris=_api['uris']):
            if args.svc:
                _api['upstream_url'] = build_svc(_api['upstream_url'], args.svc_port)
            create_kong_api(url=args.dkong, **_api)


def args_parser():
    parse = argparse.ArgumentParser(prog='switch-nginx-kong', description='Nginx与Kong网关配置相互转换',
                                    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                    epilog='nginx转kong时，从标准输入读取nginx配置')

    parse.add_argument('-src', choices=['nginx', 'kong'], help="选择转换来源", required=True)
    parse.add_argument('-dest', choices=['nginx', 'kong'], help="选择转换到目标", required=True)
    parse.add_argument('-skong', type=str, default=DEFAULT['KONG_ADMIN'], help='源KongAPI接口地址')
    parse.add_argument('-dkong', type=str, default=DEFAULT['KONG_ADMIN'], help='目标KongAPI接口地址')
    parse.add_argument('-change', type=str, choices=['update', 'delete'], help='修改的动作模式')
    parse.add_argument('--update', type=str, nargs='+', help='更新特定属性，change参数使用时有效, 更新skong目标')
    parse.add_argument('--svc', action='store_true', help='dest为kong时，使用svc作为upstream地址')
    parse.add_argument('--svc-port', dest='svc_port', type=str, default='8080', help='使用svc作为upstream地址时默认后端端口')
    parse.add_argument('--kc', type=str, default=DEFAULT['k8s_kc'], help='使用svc作为upstream地址时候使用的kubectl命令行, 调用目标集群')
    parse.add_argument('-nginxcm', type=str, default=DEFAULT['nginx_cm_name'], help='nginx configmaps name，转换到nginx时必需提供')
    parse.add_argument('-project', type=str, default=DEFAULT['project'], help='project name，转换到nginx时必需提供')
    parse.add_argument('--hosts', type=str, default='', help='目标API hosts参数')
    parse.add_argument('-ocurl',  default=DEFAULT['openshift_url'], help='openshift 管理地址，转换到nginx时必需提供')
    parse.add_argument('--filter', type=str, default='.*', help="对URL部分进行正则过滤")
    parse.add_argument('--filter-reverse', dest='reverse', action='store_true', help='反转正则匹配')
    parse.add_argument('--replace-name', dest='rep_name', nargs=2, default=['-stage', '-stage'], help='关键字替换，替换name')
    parse.add_argument('--replace-upstream', dest='rep_up', nargs=2, default=['cn', 'cn'], help='关键字替换，替换upstream')
    parse.add_argument('--version', action='version', version='%(prog)s 1.1', help='输出版本号')

    # debug_args = "-src kong -dest kong --hosts h5.xxx.xxx.com " \
    #              "-skong http://h5.sd.chinamobile.com/admin-api/apis/ " \
    #              "-project cmbs-test   -change update --update hosts=h5.sd.chinamobile.com".split()
    # debug_args = "-src=nginx  -dest=kong --svc --filter=/moses".split()
    debug_args = None

    return parse.parse_args(debug_args)


def main():
    args = args_parser()

    if args.src == "nginx" and args.dest == 'kong':
        nginx_to_kong(sys.stdin.read(), args)
    elif args.src == 'kong' and args.dest == 'nginx':
        import_cm(kong_to_nginx(args), args)
    elif args.src == args.dest == 'kong':
        if args.change is not None:
            ChangeKong(args)
        else:
            kong_to_kong(args)
    else:
        print("不支持的转换方式")


if __name__ == '__main__':
    main()
