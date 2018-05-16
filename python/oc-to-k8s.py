#!/usr/bin/env python3
# sync openshift app to k8s
# by:Sonny Yang

import os
import subprocess
import re
from locale import getpreferredencoding as local_code
import argparse
import textwrap
import copy
import logging
import logging.handlers

# -------------------------------
# run in openshift cluster

development_registry = 'registry.xxxx.cn:5000'
openshift = 'https://registry.xxxx.cn:8443'
#
prod_registry = 'registry.paas'
prod_registry_user = 'admin'
prod_registry_token = '123456Dcos'
prod_registry_prefix = '/library'
prod_registry_port = ':80'

default_project = 'moses-test'
k8s_login_env = 'kubectl --kubeconfig /root/work/config'

#
# deployment template default value
default_replicas = 1
# add pod env var
# inject_variables = {"HTTP_PROXY": "http://192.195.20.5:8080"}
inject_variables = {}

# variables replace
replace_app_options_variables = {'-DMASTER_URL': 'https://10.254.0.1:443'}
replace_spring_profiles_active_variables = {'test': 'prod', 'dev': 'prod'}

# config maps volume
mount_config = {'external-config': '/opt/openshift/config/'}

# -------------------------------

# 日志配置
log_output_file = True  # 保存到文件
log_output_terminal = True  # 输出到屏幕

#
vp_club = True

logging_level = 'debug'


class Logger(object):
    def __init__(self, level):
        self.log_stats = True
        self.formatter = logging.Formatter('%(asctime)s - %(levelname)-7s : %(message)s')
        try:
            if not os.path.exists(os.path.join(os.getcwd(), 'logs')):
                os.mkdir('logs')
        except IOError:
            self.log_stats = False

        self.logging_level_def = {
            'debug':    logging.DEBUG,
            'info':     logging.INFO,
            'warn':     logging.WARNING,
            'error':    logging.ERROR,
            'critical': logging.CRITICAL
        }
        self.logging_level = self.logging_level_def[level]

        self.__write_file_logger()
        self.__terminal_file_logger()

    def __write_file_logger(self):
        """只写入文件"""
        self.write_log = logging.getLogger('file')
        self.write_log.setLevel(self.logging_level)
        if self.log_stats and log_output_file:
            of = logging.handlers.RotatingFileHandler("./logs/%s.log" % str('run_log'), mode='a',
                                                      maxBytes=1024 * 1024 * 10, backupCount=10)
            of.setLevel(self.logging_level)
            of.setFormatter(self.formatter)
            self.write_log.addHandler(of)
            self.write_log.debug('日志写入模块初始化成功!')

    def __terminal_file_logger(self):
        """输出到终端，并继承写入行为"""
        self.terminal_log = logging.getLogger('file.terminal')
        ot = logging.StreamHandler()
        ot.setLevel(self.logging_level)
        ot.setFormatter(self.formatter)
        if log_output_terminal:
            self.terminal_log.addHandler(ot)
            self.terminal_log.debug('日志终端输出模块初始化成功')
            if not self.log_stats:
                self.terminal_log.error('因为没有写入权限，日志无法写入到文件')

    def get_logger(self):
        return self.terminal_log


class Messages(object):
    """
    some messages
    """
    @staticmethod
    def login_dev_info(msg=None):
        logs.info('- ' * 40)
        logs.info('----- login development env %s -----' % msg)

    @staticmethod
    def pull_info():
        logs.info('- ' * 40)
        logs.info('----- pull development images -----')

    @staticmethod
    def push_info(msg=None):
        logs.info('- ' * 40)
        logs.info('----- push development images to %s -----' % msg)

    @staticmethod
    def kc_info():
        logs.info('- ' * 40)
        logs.info('----- exec kubernetes command -----')


class Check(Messages):
    def __init__(self, **kwargs):
        super().__init__()
        self.k8s_env = k8s_login_env
        self.dev_registry = development_registry
        self.prod_registry = prod_registry
        self.project = kwargs['project']
        self.dproject = kwargs['dproject']
        self.openshift = openshift
        self.timeout = 3000

    @staticmethod
    def __login_registry(registry, user, token):
        logs.info('login registry: %s' % registry)
        docker_login_command = 'docker login -u {} -p {} {}'.format(user, token, registry)
        if os.system(docker_login_command):
            logs.info('%s registry login failed' % registry)
            exit(2)

    def __oc(self):
        def login():
            if not os.system('oc login %s' % self.openshift):
                logs.info('Login Successful!')
            else:
                logs.error('%s Login Failed!' % self.openshift)
                exit(-1)

        proc = subprocess.Popen('oc project %s' % self.project, shell=True, stdout=subprocess.PIPE)
        proc.wait()
        re_code = proc.returncode

        if re_code == 0:
            out = proc.communicate()[0].decode()
            if self.openshift not in out:
                # login到其他位置 logout
                os.system('oc logout')
                login()
            else:
                logs.info('Has logged')
        else:
            login()

        token = subprocess.check_output('oc whoami -t', shell=True).decode().strip()
        username = subprocess.check_output('oc whoami', shell=True).decode().strip()
        return username, token

    def __switch_project(self):
        re_code = subprocess.call('oc project {}'.format(self.project), shell=True)
        if re_code != 0:
            logs.error('Porject %s 不存在' % self.project)
            exit(-1)

    def kubectl(self):
        if subprocess.call('%s  get node' % self.k8s_env, shell=True, stdout=subprocess.PIPE):
            logs.info('Error:  not working,  Unable to deploy!!!')
            return False
        else:
            logs.info('kubectl Working properly')
            return True

    def login_dev(self):
        self.login_dev_info(self.dev_registry)
        username, oc_token = self.__oc()
        self.__login_registry(self.dev_registry, username, oc_token)
        self.__switch_project()

    def login_prod(self, **kwargs):
        self.__login_registry(self.prod_registry + prod_registry_port, **kwargs)

    def logout(self):
        os.system('oc logout')
        os.system('docker logout %s' % self.dev_registry)
        os.system('docker logout %s' % self.prod_registry)

    @staticmethod
    def oc_login_status():
        if subprocess.call('oc project', shell=True):
            return False
        else:
            return True


class ImagesOperating(Check):
    def __init__(self, **kwargs):
        # ns = --project
        super().__init__(**kwargs)
        self.dev_images = []            # 开发库的所有image
        self.dev_update_images = []     # 本次从开发库更新的image
        self.push_list = []             # 执行push的image
        self.pushd_list = []            # push了实际内容的images

        self.prod_images_name = ''
        self.push_flag = True
        self.kwargs = kwargs

    def __clear_local_image(self, image_name):
        """
        清理无效的images
        : param image_name: 镜像名+tag ,不包含registry地址

        """
        def delete_image(image):
            logs.info('--- clear ' + image)
            os.system('docker rmi -f {image}'.format(image=image))

        try:
            local_images = subprocess.check_output('docker images | grep "{registry}/{project}"'.
                                                   format(registry=self.prod_registry, project=self.project),
                                                   shell=True).decode().splitlines()
        except subprocess.CalledProcessError:
            pass
        else:
            for line in local_images:
                match = re.match('^(\S+)\s+(\S+)\s+(\S+)', line)
                repository = match.group(1)
                tag = match.group(2)
                image_id = match.group(3)
                if tag == '<none>':
                    # delete 旧 image
                    delete_image(image_id)
                    continue

                # t = moses/app-xxx:latest
                t = '/'.join(repository.split('/')[1:]) + ':' + tag
                if t not in image_name:
                    # delete 开发库不存在的image
                    delete_image('/'.join([self.prod_registry, t]))
                    delete_image('/'.join([self.dev_registry, t]))

    def pull(self):

        self.pull_info()

        # 开发库镜像列表
        pull_command = "oc get is %s -n %s| awk 'NR>1 {print $0}'" % (*self.kwargs.get('update', ''), self.project)
        logs.debug(pull_command)
        image_streams_line = subprocess.check_output(pull_command, shell=True).decode().splitlines()

        # -------- 删除deployment不存在但images存在的对象
        if self.kwargs['all'] is False:
            dc_name = subprocess.check_output("oc get dc %s -n %s| awk 'NR>1 {print $1}'" %
                                              (self.kwargs.get('update', ''), self.project),
                                              shell=True).decode().splitlines()
            is_name = subprocess.check_output("oc get is %s -n %s| awk 'NR>1 {print $1}'" %
                                              (self.kwargs.get('update', ''), self.project),
                                              shell=True).decode().splitlines()
            image_mixed = set(dc_name) & set(is_name)

            def __drop_img(_name):
                if _name.split()[0] not in image_mixed:
                    image_streams_line.pop(image_streams_line.index(_name))

            list(map(__drop_img, image_streams_line))
        # --------- end

        logs.debug('Get images len()=%s' % len(image_streams_line))
        for line in image_streams_line:
            line_re = re.match('^(\S+)\s+(\S+)\s+(\S+)', line)
            name = line_re.group(1)
            repo = line_re.group(2).split('5000')[1]

            # 命令中tag位置会随机变化，首选latest
            m3 = line_re.group(3)
            if 'latest' in m3:
                tag = 'latest'
            else:
                tag = m3.split(',')[0]

            self.dev_images.append((name, repo, tag))

        # 尝试拉取开发库的所有镜像
        for line in self.dev_images:
            name, image, tag = line
            logs.info('--- Pull image: %s:%s ...' % (self.dev_registry, name))
            proc = subprocess.call('docker pull %s%s:%s' % (self.dev_registry, image, tag), shell=True)
            if proc:
                logs.warning('--- pull image failed: %s\n' % name)
                if self.kwargs.get('update'):
                    logs.error('not update %s' % self.kwargs.get('update'))
                    exit(1)
            else:
                logs.info('--- Pull %s image complete\n' % name)
                self.dev_update_images.append(line)

        # update tag
        self.__update_tag()

        # clear local images
        # image_and_tag = [x[1].strip('/')+':'+x[2] for x in self.dev_images]
        # self.__clear_local_image(image_and_tag)

    def __update_tag(self):
        logs.debug('start update image tag...')
        line_number = 0
        for line in self.dev_update_images:
            name, image, tag = line
            line_number += 1
            origin_image = '{0}{1}'.format(self.dev_registry, image)
            dest_image = '{0}{1}{2}/{3}/{4}'.format(self.prod_registry, prod_registry_port, prod_registry_prefix,
                                                    self.dproject, name)

            command = 'docker tag {0}:{2}  {1}:{2}' .format(origin_image, dest_image, tag)

            logs.debug('%-3s: %s' % (str(line_number), command))

            tag_stats = os.system(command)
            if tag_stats == 0:
                logs.debug('update tag success:  %s' % origin_image)
            else:
                logs.debug('update tag failure:  %s' % origin_image)

            self.push_list.append((dest_image, tag))

        logs.debug('end update image tag')

    def push(self):
        """push to prod registry"""
        # 防止重复运行
        if self.push_flag is False:
            return []

        self.push_info(self.prod_registry)

        if not self.push_list and self.kwargs.get('active') != 'update':
            # 直接调用push
            try:
                # %s/ 以 namespace 名结尾
                command = 'docker images | grep -E "%s/" ' % (self.prod_registry + prod_registry_port +
                                                              prod_registry_prefix + '/' + self.dproject)
                logs.debug('push command: ' + command)
                local_info = subprocess.check_output(command, shell=True).decode().splitlines()
            except subprocess.CalledProcessError:
                self.push_flag = False
                return []
            else:
                for x in local_info:
                    match = re.match('^(\S+)\s+(\S+)', x)
                    repository = match.group(1)
                    tag = match.group(2)
                    self.push_list.append((repository, tag))
        logs.debug('push list len: %s' % len(self.push_list))
        for line in self.push_list:
            repository, tag = line
            name = repository.split('/')[-1]
            logs.info('--- push image: %s ...' % name)
            proc = subprocess.Popen('docker push %s:%s' % (repository, tag), shell=True,
                                    stdout=subprocess.PIPE)
            out_msg = ''
            with proc.stdout:
                for l in iter(proc.stdout.readline, b''):
                    out_msg += l.decode(local_code())
                    logs.debug(l.decode(local_code()).strip())

            proc.wait(timeout=self.timeout)
            if proc.returncode:
                logs.warning('--- push image failed: %s\n' % name)
            else:
                logs.info('--- push image complete: %s\n' % name)

            if 'Pushed' in out_msg:
                self.pushd_list.append(line)

        self.push_flag = False

    def sync(self):
        self.pull()
        self.push()


def decoration_env_replace(func):
    def replace(*args, **kwargs):
        # 修改pod环境变量
        value = kwargs['env']
        for _key, _value in replace_app_options_variables.items():
            try:
                _APP_OPTIONS = re.sub('{}=\S+'.format(_key), '{}={}'.format(_key, _value), value['APP_OPTIONS'])
            except KeyError:
                pass
            else:
                value['APP_OPTIONS'] = _APP_OPTIONS

        for _key, _value in replace_spring_profiles_active_variables.items():
            try:
                _SPRING_PROFILES_ACTIVE = re.sub(_key, _value, value['SPRING_PROFILES_ACTIVE'])
            except KeyError:
                pass
            else:
                value['SPRING_PROFILES_ACTIVE'] = _SPRING_PROFILES_ACTIVE
        kwargs['env'] = value

        return func(*args, **kwargs)
    return replace


def decoration_add_config_maps(func):
    def config_maps(*args, **kwargs):

        if len(mount_config) == 0:
            # None config maps
            volumes = ''
            volumemounts = ''
        else:
            volumemounts = '        volumeMounts:\n'
            volumes = '      volumes:\n'
            for _key, _value in mount_config.items():
                volumemounts += '        - mountPath: {}\n'.format(_value)
                volumemounts += '          name: {}\n'.format(_key)
                volumemounts += '          readOnly: true\n'

                volumes += '      - configMap:\n'
                volumes += '          defaultMode: 420\n'
                volumes += '          name: {}\n'.format(_key)
                volumes += '        name: {}\n'.format(_key)

        kwargs['volumemounts'] = volumemounts
        kwargs['volumes'] = volumes

        return func(*args, **kwargs)
    return config_maps


class Deploy(Check):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.io = kwargs['io']
        self.kwargs = kwargs

    def __namespace_check(self):
        if subprocess.call('{env}  get ns {ns}'.format(env=self.k8s_env, ns=self.dproject), shell=True,
                           stderr=subprocess.PIPE, stdout=subprocess.PIPE):
            os.system('{env}  create ns {ns}'.format(env=self.k8s_env, ns=self.dproject))

    @decoration_env_replace
    @decoration_add_config_maps
    def __deployment_yml(self, **kwargs):

        env_template = '''\
        - name: {name}
          value: {value}\n'''

        label_template = '        {label}: {value}\n'
        container_port = '        - containerPort: {port}\n'
        service_port = '''\
  - name: {port}-tcp
    protocol: TCP
    port: {port}
    targetPort: {port}\n'''

        dp = textwrap.dedent('''\
        ---
        apiVersion: apps/v1beta1 # for versions before 1.6.0 use extensions/v1beta1
        kind: Deployment
        metadata:
          name: {name}
        spec:
          replicas: {replicas}
          template:
            metadata:
              labels:
        {label_group}
            spec:
              containers:
              - name: {name}
                image: {image}:{tag}
                ports:
        {container_port_group}
        {volumemounts}
                env:
        {env_group}
                imagePullPolicy: Always
              restartPolicy: Always
        {volumes}
        
        ---
        kind: Service
        apiVersion: v1
        metadata:
          name: {name}
        spec:
          selector:
            app: {name}
          ports:
        {service_port_group}
        ''')

        # pre format
        env_group = ''
        for name, value in kwargs['env'].items():
            env_group += env_template.format(name=name, value=value)

        for _name, _value in self.kwargs['pod_env'].items():
            env_group += env_template.format(name=_name, value=_value)

        label_group = ''
        for label, value in kwargs['label'].items():
            label_group += label_template.format(label=label, value=value)

        container_port_group = ''
        service_port_group = ''

        for port in kwargs['port']:
            container_port_group += container_port.format(port=port)
            service_port_group += service_port.format(port=port)

        # add
        kwargs['label_group'] = label_group
        kwargs['env_group'] = env_group
        kwargs['container_port_group'] = container_port_group
        kwargs['service_port_group'] = service_port_group

        return dp.format(**kwargs)

    def __create_deployment(self, obj):
        self.kc_info()
        obj['replicas'] = default_replicas
        deploy_yml = self.__deployment_yml(**obj)
        # logs.debug(deploy_yml)

        return subprocess.call("echo '{yml}' |  {env}  create -f - -n {ns}".format
                               (yml=deploy_yml, ns=self.dproject, env=self.k8s_env), shell=True)

    def __update_deployment_obj(self, **kwargs):
        def check_tag(tag):
            if tag == 'latest':
                logs.debug('check %s tag' % kwargs.get('name'))
                _tag_check = subprocess.call('{env} get deploy  {name} -n {ns} -o yaml | grep "image:" | grep -q -E '
                                             '":latest$"'.format(env=self.k8s_env, ns=self.dproject, **kwargs),
                                             shell=True)
                logs.debug('_tag_check value:' + str(_tag_check))
                if _tag_check:
                    # 不存在，加上tag
                    return tag
                else:
                    return None
            else:
                return tag

        # update image
        logs.debug('start update deployment object %s' % kwargs.get('name'))

        # 有latest的去掉，没用的补上，触发更新
        if check_tag(kwargs['tag']):
            img_and_tag = '%s:%s' % (kwargs['image'], kwargs['tag'])
        else:
            img_and_tag = kwargs['image']

        _command = '{env}  set image deployment/{name} {name}={img_url} -n {ns}'.format(
            env=self.k8s_env, ns=self.dproject, img_url=img_and_tag, name=kwargs['name'])

        logs.debug(_command)
        os.system(_command)

    @staticmethod
    def __special_treatment(string, delete_string):
        # 针对这个仓库的特殊处理  集群里的images 地址删除registry的端口号
        if vp_club:
            return string.replace(delete_string, '')
        else:
            return string

    def __get_deployment_args(self):

        prod_deployment = subprocess.check_output("%s  get deployment  -n %s | awk 'NR>1 {print $1}'" %
                                                  (self.k8s_env, self.dproject), shell=True, stderr=subprocess.PIPE).\
            decode().splitlines()
        try:
            logs.debug('update = %s' % self.kwargs['update'])
            if self.kwargs['update'] != '':
                # update args , name 分隔，单镜像筛选
                command = "docker images |  grep -v '<none>' | grep -E '%s/%s\s' " % (
                    self.prod_registry + prod_registry_port + prod_registry_prefix + '/' + self.dproject,
                    # image name
                    self.kwargs['update'])
            else:
                # 多镜像筛选
                command = "docker images | grep -v '<none>' | grep -E '%s/'" % (self.prod_registry +
                                                                                prod_registry_port +
                                                                                prod_registry_prefix
                                                                                + '/' + self.dproject)

            logs.debug('deploy docker grep args: ' + command)
            docker_image = subprocess.check_output(command, shell=True).decode().splitlines()
        except subprocess.CalledProcessError:
            docker_image = []

        def match(string=''):
            for dp in prod_deployment:
                if dp == string:
                    logs.debug('%s in %s' % (dp, string))
                    logs.debug('已存在 跳过')
                    return False
            return True

        def check_exist(app_name):
            # 对源不存在的应用进行删除
            try:
                logs.debug('check %s' % app_name)
                subprocess.check_output('oc get dc %s -n %s' % (app_name, self.project), shell=True)
            except subprocess.CalledProcessError as err:
                logs.debug(str(err))
                logs.debug('%s 不存在 删除' % name)
                try:
                    subprocess.check_output("docker images | grep -E '%s/%s\s' | awk '{print $1}' | xargs docker rmi -f"
                                            % (self.project, name), shell=True)
                except subprocess.CalledProcessError as err:
                    logs.debug(str(err))

                return False
            else:
                return True

        def get_env():
            env_list = subprocess.check_output("oc env dc %s --list -n %s | grep -v '^#' | grep '='" %
                                               (name, self.project), shell=True).decode().splitlines()

            logs.debug('Get env: %s' % env_list)
            return {x.split('=', maxsplit=1)[0]: x.split('=', maxsplit=1)[1] for x in env_list}

        def get_label():
            label_list = subprocess.check_output("oc get dc %s -n %s --show-labels | awk 'NR==2 {print $NF}'" %
                                                 (name, self.project), shell=True).decode().strip().split(',')
            return {x.split('=')[0]: x.split('=')[1] for x in label_list}

        def get_port():
            return subprocess.check_output("oc get dc %s  -n %s -o yaml | grep containerPort | awk '{print $NF}'" %
                                           (name, self.project), shell=True).decode().strip().splitlines()

        deploy_args_list = []
        deploy_args = {}

        for line in docker_image:
            logs.debug('----------- process %s' % line)
            if match(line):
                image = line.split()[0]
                name = image.split('/')[-1]
                # check deployment object
                if not check_exist(name):
                    logs.warning(name + '将不会部署')
                    continue
                deploy_args['name'] = name
                deploy_args['image'] = self.__special_treatment(image, prod_registry_port)
                deploy_args['tag'] = line.split()[1]
                deploy_args['env'] = get_env()
                deploy_args['label'] = get_label()
                deploy_args['port'] = get_port()
                # add list
                _temp_dict = copy.deepcopy(deploy_args)

                deploy_args_list.append(_temp_dict)

        logs.debug(deploy_args_list)
        return deploy_args_list

    def __check_deployment_exist(self, name):
        if not subprocess.call('{env}  get deployment {name} -n {ns}'.format(
                env=self.k8s_env, name=name, ns=self.dproject), shell=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE):
            # 存在 deployment
            return True
        else:
            return False

    def deployment(self, status=True):
        """
        deploy images
        :return: 
        """
        logs.debug('start deployment process...')
        # 检查kubectl能否工作
        if self.kubectl() is False:
            exit(1)

        if self.oc_login_status() is False:
            logs.error('login token 失效，请重新登录再继续')
            exit(3)

        self.__namespace_check()

        if not self.io.pushd_list and status:
            '''尝试push一次'''
            self.io.push()

        for kwargs_obj in self.__get_deployment_args():
            # 构建deploy与svc对象
            if self.__create_deployment(kwargs_obj) == 1 and self.kwargs['active'] == 'update':
                # 如果处于update状态且已存在
                image, tag = self.kwargs['push_list'][0]
                name = image.split('/')[-1]
                self.__update_deployment_obj(
                    name=name, image=self.__special_treatment(image, prod_registry_port), tag=tag)


def show_config(project=default_project):
    info = textwrap.dedent('''\
    %-14s：%s
    %-14s：%s
    %-12s：%s
    %-12s：%s
    %-11s：%s\
    ''' % ('开发registry', development_registry,
           '生产registry', prod_registry,
           '当前项目', project,
           'k8s变量设定', k8s_login_env,
           '默认副本数', default_replicas
           ))
    logs.info(info)


def args_parser():
    parse = argparse.ArgumentParser(prog='Sync project', description=textwrap.dedent('''\
    部署OpenShift项目到k8s
    --------------------------------
        pull: 从开发库拉取image到本机
        push: 将本机镜像推送到k8s，并以本机image为参考k8s更新deployment，更新或创建
        sync: 合并pull与push，即从开发库拉取，推送到k8s并更新或创建deployment
        deploy: 创建deployment对象
        update xxx: 更新特定应用

    '''), formatter_class=argparse.RawDescriptionHelpFormatter, epilog='and more')

    parse.add_argument('active', nargs='?', choices=['sync', 'push', 'pull', 'deploy', 'update'], default='sync',
                       help='动作类型，默认为sync')
    parse.add_argument('update', nargs='?', metavar='update app-name', default='', help='更新应用')
    parse.add_argument('--project', type=str, default=default_project, help='要处理的源namespace')
    parse.add_argument('--dproject', type=str, default=None, help='部署到的目标namespace，默认与源相同')
    parse.add_argument('--debug', type=str, choices=['debug', 'info', 'warn', 'error', 'critical'],
                       default=logging_level, help='日志级别')
    parse.add_argument('--all', action='store_true', default=False,
                       help='拉取project下的所有镜像，包括未运行的，但不会进行部署。默认只拉取运行的中镜像')
    parse.add_argument('--show', action='store_true', help='显示配置信息')

    # debug_args = 'deploy --project moses-test'.split()
    debug_args = None
    _args = parse.parse_args(debug_args)
    if _args.dproject is None:
        _args.dproject = _args.project

    if _args.active == 'update' and _args.update is '':
        print('update 选项需要跟随应用名作为参数')
        exit(-1)
    else:
        return _args


def main(parse):

    parse_kwargs = vars(parse)

    if parse.show:
        show_config()
        return
    check = Check(**parse_kwargs)
    check.login_dev()
    check.login_prod(user=prod_registry_user, token=prod_registry_token)

    io = ImagesOperating(**parse_kwargs)

    if parse.active == 'pull':
        io.pull()
        return

    elif parse.active == 'push':
        io.push()

    elif parse.active == 'update' or parse.active == 'sync':
        io.sync()

    elif parse.active == 'deploy':
        deploy = Deploy(io=io, pod_env=inject_variables, **parse_kwargs)
        deploy.deployment(status=False)
        return

    #  最后对deploy对象进行操作
    deploy = Deploy(io=io, pod_env=inject_variables, push_list=io.push_list, **parse_kwargs)
    deploy.deployment()


if __name__ == '__main__':
    __args = args_parser()
    logger = Logger(level=__args.debug)
    logs = logger.get_logger()
    main(__args)
