'''
Created on Dec 13, 2012

@author: mconstantin
'''

from PySide.QtGui import QDialog

from nxdrive.CheckedFileSystem import CheckedFileSystem
from ui_sync_folders import Ui_Dialog


class SyncFoldersDlg(QDialog, Ui_Dialog):
    def __init__(self, frontend=None, parent=None):
        super(SyncFoldersDlg, self).__init__(parent)
        self.setupUi(self)
        self.frontend = frontend
        
        cfs = CheckedFileSystem('/Users/mconstantin')
        self.treeView.setModel(cfs)
        
        # hide header and all columns but first one
        self.treeView.setHeaderHidden(True)
        self.treeView.resizeColumnToContents(0)
        for i in range(1,cfs.columnCount()):
            self.treeView.setColumnHidden(i, True)
        
        self.treeView.setRootIndex(cfs.index(cfs.rootPath()))