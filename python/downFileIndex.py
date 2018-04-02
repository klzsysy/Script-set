#!/usr/bin/env python3

# 递归下载文件和目录

import requests
import re
import os
from sys import exit

URL = 'http://dl.bintray.com/nodeclipse/nodeclipse/1.0.2f/'
keep_structure = True
download_path = '.'


class Downloads(object):
    def __init__(self, root_url, down_folder, keepstructure=True):
        self.root_url = root_url
        self.down_folder = down_folder
        self.keep = keepstructure
        self.re_try_count = 5
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, '
                                      'like Gecko) Chrome/57.0.2987.133 Safari/537.36'
                        }
        self.__check_path(folder=down_folder)
        self.start()

    def __retry(self, *args):
        functions = args[0]
        url = args[1]
        count = args[-1]
        if count < self.re_try_count:
            print('retry %s' % url)
            return functions(url, count + 1)
        else:
            print('download fail %s' % url)
            return None

    def __request_url(self, url, try_count=0, stream=False):
        try:

            r = requests.get(url=url, headers=self.headers, timeout=10, allow_redirects=True, stream=stream)
            status_code = r.status_code
            if status_code >= 400:
                r.close()
                return self.__retry(self.__request_url, url, try_count)
        except requests.Timeout:
            return self.__retry(self.__request_url, url, try_count)
        except requests.exceptions.ConnectionError:
            return self.__retry(self.__down_url, url, try_count)
        else:
            print('get successful %s' % url)
            return r

    @staticmethod
    def __merge_path(path1, path2):
        return os.path.join(path1, path2)

    @staticmethod
    def __check_path(folder):
        if not os.path.exists(folder):
            try:
                os.makedirs(folder)
            except OSError as err:
                print("无法保存到选定的目录 退出\n" + str(err))
                exit(-1)

    def __keep_structure(self, url):
        if self.keep:
            f = url.replace(self.root_url, '').split('/')
            if len(f) == 1:
                file_path = self.__merge_path(self.down_folder, url.split('/')[-1])
            else:
                folder = os.path.join(self.down_folder, '/'.join(f[:-1]))
                self.__check_path(folder)
                file_path = os.path.join(folder, url.split('/')[-1])
        else:
            file_path = self.__merge_path(self.down_folder, url.split('/')[-1])

        return file_path

    def __down_url(self, file_url):
        file_path = self.__keep_structure(file_url)
        r = self.__request_url(file_url, stream=True)

        if r:
            print('download download successful %s' % file_url)
            with open(file_path, "wb") as code:
                for block in r.iter_content(chunk_size=1024):
                    if block:
                        code.write(block)
                r.close()

    def __combination_url(self, re_obj, url):
        if re_obj is None:
            return
        obj_text = str(re_obj.text)
        obj_text_list = obj_text.split()
        for line in obj_text_list:
            search = re.match('^rel="nofollow">(.*?)</a></pre>$', line)
            if search:
                file = search.group(1)
                file_url = url.strip('/') + '/' + file
                if '/' in file:
                    self.__combination_url(self.__request_url(file_url), file_url)
                else:
                    self.__down_url(file_url=file_url)

    def start(self):
        re_obj = self.__request_url(self.root_url)
        self.__combination_url(re_obj, self.root_url)


if __name__ == '__main__':
    Downloads(URL, download_path, keep_structure)
