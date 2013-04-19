'''
Created on Nov 7, 2012

@author: mconstantin
'''
def singleton(cls):
    instances = {}
    def getinstance():
        if cls not in instances:
            instances[cls] = cls()
        return instances[cls]
    return getinstance
