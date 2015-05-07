#!/usr/bin/env python
import select
import threading
import socket
import argparse
import datetime

#class MyBaseRequsetHandler(object):
    #TODO:add the http handle in this class
#    '''the class is use to handle the request'''
#
#    def __init__(self):
#        '''the init function'''
#        pass

#    def handle(self):
#        '''use to handle the request'''
#        pass

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

    def __init__(self,request_socket,client_address,client_port,server):
        '''init the handle'''
        #define the request,which usual is the connect socket
        self.request_socket = request_socket
        self.client_address = client_address
        self.client_port = client_port
        self.server = server
        
        try:
            self.handle()
        finally:
            self.finish()

    def handle(self):
        '''the handler to proccess the request'''                
        #TODO:add the header ananlysis here
        print '%s : visit from %s' % (datetime.datetime.now(),self.client_address)
        print 'process in thread : %s ' %(threading.current_thread().ident)
        self.request_socket.sendall('hello world\n')

    def finish(self):
        #TODO:add the action in finish       
        #close the request
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

def main():
    #get the address and port 
    address,port = trans_arg()
    #init the server
    server = ThreadTcpServer(address,port,TcpHandler)
    #run it
    try: 
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        print '\nbye~'
if __name__ == '__main__':
    main()

