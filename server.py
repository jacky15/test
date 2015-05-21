#!/usr/bin/env python
#coding=utf8
import select
import threading
import socket
import argparse
import datetime
import json
import re

def _EINTER_retry(fun,*args):
    '''if the function is stop for EINTR,try continue'''
    while True:
        try:
            return fun(*args)
        except (OSError, select.error) as e:
            if e.args[0] != errno.EINTR:
                raise

class TcpServer(object):
    '''the socket server class'''

    #define the family of the server
    __address_famliy = socket.AF_INET

    def __init__(self,address,port,handler_class,address_famliy=None,reuse_address=True,max_queue_size=1,poll_gap=0.5):
        '''init the class'''
        if address_famliy:
            self.__address_famliy = address_famliy
        
        self.__socket = socket.socket(self.__address_famliy,socket.SOCK_STREAM)
        #set to reuse the address
        if reuse_address:
            self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.__socket.bind((address,port))
        #the max queue size use for listen
        self.__max_queue_size = max_queue_size
        self.handler_class = handler_class
        #the poll_gap use for select
        self.__poll_gap = poll_gap

        #support the server is run in mulit thread 
        self.__has_shutdown = threading.Event()
        #the flag for server is serving 
        self.__is_serving = False
        #the flag whether the server is request to shutdown
        self.__is_request_shutdown = False

    def serve_forever(self):
        '''the main loop in the '''   
        #active the socket for the server
        self.__socket.listen(self.__max_queue_size)
        #to clear the internal flag
        #set this to support the server running in mulit thread
        self.__has_shutdown.clear()     
        #set the serving flag         
        self.__is_serving = True

        #loop until the server is request to shutdown 
        try:
            while not self.__is_request_shutdown:
                #TODO:define the loop

                _ready_list = _EINTER_retry(select.select,[self],[],[],self.__poll_gap) 
               
                #if the socket in the ready list
                #the first element of the ready_list is the wfile
                if self in _ready_list[0]:
                    #print 'select work' 
                    #get the peer socket
                    _peer_socket,_peer_info = self.__socket.accept()
                    
                    self.process_request(_peer_socket,_peer_info)
        finally:
            #make sure the loop can always set the internal flag
            #or it may make the deadblock when call shutdown() in single thread
            
            #set the flag
            self.__is_serving = False
            #set the internal flag
            self.__has_shutdown.set()
            #close the server socket
            self.__socket.close()
            
    def shutdown(self):
        self.__is_requeset_shutdown = True
        self.__has_shutdown.wait()
            
    def fileno(self):
        '''define this function to make the class can use for select()'''
        return self.__socket.fileno()   

    def process_request(self,request_socket,request_info):
        #the server just instant the handle class
        #what is done in the class is ignored
        self.handler_class(request_socket,request_info[0],request_info[1],self)

class TcpHandler(object):
    '''define the class to handler the request'''

    rbufsize = -1
    wbufsize = 0

    def __init__(self,request_socket,client_address,client_port,server):
        '''init the handle'''
        #define the request,which usual is the connect socket
        self.request_socket = request_socket
        self.client_address = client_address
        self.client_port = client_port
        self.server = server
        
        try:
            self.setup()
            self.handle()
        finally:
            self.finish()

    def setup(self):
        self.rfile = self.request_socket.makefile('rb', self.rbufsize)
        self.wfile = self.request_socket.makefile('wb', self.wbufsize)

    def handle(self):
        '''
        the handler to proccess the request,
        subclass should do some work in this function
        '''                
        pass

    def finish(self):
        #TODO:add the action in finish       
        #close the request
        if not self.wfile.closed:
            self.wfile.flush
        self.rfile.close()
        self.wfile.close()
        self.request_socket.close()

class ThreadingMixIn(object):
    '''overwrite the function for TCPServer'''

    #the thread will keep running when the main process is exit
    set_daemon = True

    def process_request_in_thread(self,request_socket,request_info):
        '''where the process is real process'''
        self.handler_class(request_socket,request_info[0],request_info[1],self)

    def process_request(self,request_socket,request_info):
        '''make a new thread '''
        new_thread = threading.Thread(target=self.process_request_in_thread,
                                      args=(request_socket,request_info))

        if self.set_daemon:
            new_thread.setDaemon(1)

        new_thread.start()


class ThreadTcpServer(ThreadingMixIn,TcpServer):
    pass

def trans_arg():
    '''this function is use to analysis the arg'''
    arg_parse = argparse.ArgumentParser()
    
    #add some args
    arg_parse.add_argument('--add','-a',required=True,help='the address the server listen on')
    arg_parse.add_argument('--port','-p',type=int,required=True,help='the port the server listen on')

    result = arg_parse.parse_args()

    return result.add,result.port

class MyTcpHandler(TcpHandler):

    def handle(self):
        #TODO:add the header ananlysis here
        print '%s : visit from %s' % (datetime.datetime.now(),self.client_address)
        print 'process in thread : %s ' %(threading.current_thread().ident)
        
class BaseHttpHandler(MyTcpHandler):
    '''此类内部为单线程处理，线程安全'''
    #可以被映射的方法
    ALLOW_METHOD = ['GET','POST']
    #解析用户请求
    PATH_RE = re.compile('(?P<path>(/.*?))(\?(?P<params>(.*)))?')
    #PARAM_RE = re.compile('((.*?)=(.*?))&?*')
    command = ''
    request_path = ''
    request_param = {
        'GET' : {},
        'POST' : {}
    }
    head_info = {}

    def handle(self):
        '''此函数用于解析http请求首行，用于分发各个方法进行处理，不关心详细处理细节'''
        #父类的处理，可以去除
        super(BaseHttpHandler,self).handle()

        raw_request_line = self.rfile.readline(65535)

        if not self.analysis_request(raw_request_line):
            return self.request_error('request error')

        
        #判断这个请求是何种请求
        method = getattr(self,self.command.lower())
        method()
        self.wfile.flush()

    def analysis_request(self,raw_request_line):
        '''解析用户的请求'''
        raw_request_list = raw_request_line.split()
        command,request_path = raw_request_list[0],raw_request_list[1]

        if not command.upper() in self.ALLOW_METHOD:
            return False
        
        self.command = command
        self.request_path = request_path

        #过滤请求路径异常的请求
        _result = self.PATH_RE.match(self.request_path)

        if not _result:
            return False

        self.request_path = _result.groupdict()['path']
        _request_param = _result.groupdict()['params']

        #解析头部
        self.analysis_head()

        if _request_param:
            analysis_param('GET',_request_param)

        self.analysis_body()

        return True

    def analysis_param(self,method,request_str):
        
        _request_param_list = request_str.split('&')
        for param in _request_param_list:
            name,value = param.split('=')
            self.request_param[method][name] = value

    def analysis_head(self):
        #读取浏览器的所有头信息
        re_space = re.compile('^\s+$')
        while True:
            info = self.rfile.readline()
            #判断是否已经完全接收了头部，读到了空白行
            _result = re_space.match(info)
            if _result :
                return
            #TODO:头部处理
            info = info.split(':')
            self.head_info[info[0].lower()] = info[1]

    def analysis_body(self):
        #读取浏览器的所有body信息
        _content_length = self.head_info.get('content-length',None)
        
        if _content_length:
            _request_param = self.rfile.read(int(_content_length))
            print _request_param,int(_content_length)
            self.analysis_param('POST',_request_param)

    def request_error(self,message):
        '''返回错误信息'''
        return self.wfile.write(json.dumps({'result' : False}))

class HttpHandler(BaseHttpHandler):
    
    def get(self):
        print 'In GET function.'
        print 'request path : %s' % (self.request_path)
        print self.head_info
        self.wfile.write('hello world\n')
        result = json.dumps(self.request_param['GET'])
        self.wfile.write(result + '\n')


    def post(self):
        print 'In POST function.'
        print 'request path : %s' % (self.request_path)
        self.wfile.write('hello world\n')
        self.request_param['POST']['time'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        result = json.dumps(self.request_param['POST'])
        self.wfile.write(result + '\n')


def main():
    #get the address and port 
    address,port = trans_arg()
    #init the server
    server = ThreadTcpServer(address,port,HttpHandler)
    #run it
    try: 
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        print '\nbye~'

if __name__ == '__main__':
    main()

