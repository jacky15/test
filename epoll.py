#   coding=utf8
__author__ = 'jacky'

import socket
import select
import sys
import re
import json

from urllib import unquote
from cStringIO import StringIO

PATH_RE = re.compile('/(?P<path>(.*))(\?(?P<params>(.*)))?')
ALLOW_METHOD = ['GET', 'POST']

URL_DISPATCH = ()


def start_server():
    """启动socket监听等初始化动作"""

    #  初始化socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('127.0.0.1', 8080))
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.listen(5)

    # 根据平台的区别，绑定不同的处理方法
    if sys.platform != 'linux2':
        poll_method = select_wapper
        remove_socket = remove_select_socket
        # 此处使用set,考虑到去除socket的时候，list的消耗过大
        socket_set = {server_socket}
    else:
        poll_method = epoll_wapper

    while 1:
        ready_socket_list = poll_method(socket_set)[0]
        if len(ready_socket_list) == 0:
            continue

        ready_socket = ready_socket_list[0]

        if ready_socket == server_socket:
            # 有新的用户请求,加入到set中
            select_accpect_handler(server_socket, socket_set)
            continue
        elif ready_socket in socket_set:
            handle_request(ready_socket)
            remove_socket(ready_socket, socket_set)


def remove_select_socket(socket_remove, socket_set):
    """移除该socket"""
    socket_set.remove(socket_remove)

def select_accpect_handler(server_socket, socket_set):
    """接受新的socket的方法"""
    _temp_socket = server_socket.accept()[0]
    socket_set.add(_temp_socket)


def ananlysis_param(raw_string):
    """解析传入的字符串,返回一个字典"""
    result = {}
    param_list = raw_string.split('&')
    for per_param in param_list:
        param_name, param_value = map(unquote, per_param.split('='))
        result[param_name] = param_value

    return result


def handle_request(client_socket):
    """解析用户请求"""
    global PATH_RE, ALLOW_METHOD
    # 限制用户的url为64K
    buffer_file = StringIO(client_socket.recv(65535))

    # 先读取用户的第一行
    raw_request_line = buffer_file.readline()

    raw_request_list = raw_request_line.split()
    request_command, request_path = raw_request_list[0], raw_request_list[1]

    if not request_command.upper() in ALLOW_METHOD:
        return False

    # 过滤请求路径异常的请求
    _result = PATH_RE.match(request_path)

    # 如果没有匹配成功，说明用户的请求异常
    if not _result:
        return False

    request_path = _result.groupdict()['path']
    request_param = _result.groupdict()['params']

    # 对url中的get参数进行解析
    if request_param:
        request_get_param = ananlysis_param(request_param)
    else:
        request_get_param = {}

    # 逐行的解析用户的剩余头部
    request_head = {}
    while 1:
        _temp_read = buffer_file.readline()
        # 如果这个行不是分隔行
        if _temp_read != '\r\n':
            _temp_head_name, _temp_head_value = _temp_read.split(': ')
            request_head[_temp_head_name] = _temp_head_value
        else:
            # 如果读到了指定的分割行了，跳出循环
            break

    #  如果是POST方法，对body进行解析
    request_post_param = {}
    if request_command.upper() == 'POST':
        # 暂时只考虑简单的一行传入
        requets_post_param = ananlysis_param(buffer_file.readline())

    #  对用户的请求进行分发
    find = False
    for per_dispatch in URL_DISPATCH:
        if re.match(per_dispatch[0], request_path):
            # 分发请求处理
            result = per_dispatch[request_command.upper()](request_head, request_get_param, request_post_param)

            find = True

    if not find:
        # 如果找不到处理该请求的
        result = handler_default_request(request_head, request_get_param, request_post_param)
        client_socket.sendall(result)

    # 发送response
    client_socket.sendall(result)
    # 关闭socket
    client_socket.close()
    return True


def handler_default_request(request_head, get_param, post_param):
    """默认的处理方式"""
    result = '\n'.join(['this is the default handler', json.dumps(get_param), json.dumps(post_param)])
    return result


def handler_jacky_get_request(request_head, request_get_param, request_post_param):
    """处理用户请求，相当于view"""
    result = json.dumps(request_get_param)
    return result


def handler_jacky_post_request(request_head, request_get_param, request_post_param):
    """处理用户请求,相当于view"""
    result = json.dumps(request_post_param)
    return result


def select_wapper(socket_set):
    """select方法的包装，返回结果是一个文件描述符"""
    return select.select(socket_set, [], [], 0.1)


def epoll_wapper():
    """epoll方法的包装，返回结果是一个文件描述符"""
    pass


if __name__ == '__main__':
    URL_DISPATCH += (
        ('^jacky/$', {'GET': handler_jacky_get_request, 'POST': handler_jacky_post_request}),
    )

    start_server()
