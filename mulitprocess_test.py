# coding=utf8
__author__ = 'jacky'

import multiprocessing
import datetime

def some_test(num):
    final = 0
    for i in xrange(num):
        final += i

    return final,datetime.datetime.now()

if __name__ == '__main__':
    pool = multiprocessing.Pool()
    result_list = []
    for i in range(8):
        result = pool.apply_async(some_test, (i,))
        result_list.append(result)

    for result in result_list:
        print result.get(1)
