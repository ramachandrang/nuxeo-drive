'''
Created on Dec 12, 2012

@author: mconstantin
'''

from PySide.QtGui import QFileSystemModel
from PySide.QtCore import QDir, Qt
from collections import defaultdict, Iterable
import os
from pprint import pprint
from logging_config import get_logger, configure

log_file = os.path.join(os.getcwd(), 'log.txt')
configure(log_file, console_level='DEBUG')
log = get_logger(__name__)

class CheckedFileSystem(QFileSystemModel):
    VALUE = '>'
    
    def __init__(self, root=None, parent=None):
        super(CheckedFileSystem, self).__init__(parent)
        self.setRootPath(root)
        # show only directories
        self.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot)
        self.directories = self.tree()
        
    def tree(self):
        return defaultdict(self.tree)
    
    def pathsplit(self, pathstr, maxsplit=100):
        """split relative path into list"""
        path = [pathstr]
        while True:
            oldpath = path[:]
            path[:1] = list(os.path.split(path[0]))
            if path[0] == '':
                path = path[1:]
            elif path[1] == '':
                path = path[:1] + path[2:]
            if path == oldpath:
                return path
            if maxsplit is not None and len(path) > maxsplit:
                return path
            
    def dicts(self, t): 
        if isinstance(t, Iterable):
            return {k: self.dicts(t[k]) for k in t}
        else:
            return t
        
    def set_checked(self, path, checked):
        segs = self.pathsplit(path)
        t = self.directories
        for seg in segs:
            t = t[seg]
        t[CheckedFileSystem.VALUE] = checked
    
    def is_checked(self, path):
        segs = self.pathsplit(path)
        t = self.directories
        for seg in segs:
            t = t[seg]
        return t[CheckedFileSystem.VALUE]        
        
    def flags(self, index):
        f = super(CheckedFileSystem, self).flags(index)
        if index.column() == 0:
            f |= Qt.ItemIsUserCheckable
            
        return f
    
    def data(self, index, role):
        if index.isValid() and index.column() == 0 and role == Qt.CheckStateRole:
            return Qt.Checked if self.is_checked(self.filePath(index)) else Qt.Unchecked
        return super(CheckedFileSystem, self).data(index, role)
        
    def setData(self, index, value, role):
        if index.isValid() and index.column() == 0 and role == Qt.CheckStateRole:
            if self.isDir(index):
                # set all the children as well. The model shows only directories anyway
                self.set_checked(self.filePath(index), value)
                self.fetchMore(index)
                top_left, bottom_right = self._fetch(index, value)
                self.dataChanged.emit(top_left, bottom_right)
                
            log.debug('folder %s %schecked', self.filePath(index), '' if value == Qt.Checked else 'un')
            pprint(self.dicts(self.directories))
            
            return True
        return super(CheckedFileSystem, self).setData(index, value, role)
    
    def _fetch(self, index, value):
        if self.hasChildren():
            for i in range(0, self.rowCount(index)):
                child = self.index(i, 0, index)
                if child.isValid():
                    self.setData(child, value, Qt.CheckStateRole)
                    log.debug('subfolder %s %schecked', self.filePath(child), '' if value == Qt.Checked else 'un')
                    
            return self.index(0, 0, index), self.index(self.rowCount(index), 0, index)
                
    def canFetchMore(self, parent):
        return True
                
                
    