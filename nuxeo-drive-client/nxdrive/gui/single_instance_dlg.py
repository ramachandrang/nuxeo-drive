'''
Created on Mar 24, 2013

@author: mconstantin
'''
from PySide.QtGui import QIcon, QDialog
from PySide.QtGui import QApplication
import sys

from ui_single_instance import Ui_Dialog
from nxdrive import Constants

class SingleInstanceDlg(QDialog, Ui_Dialog):
    def __init__(self, parent=None):
        super(SingleInstanceDlg, self).__init__(parent)
        self.setupUi(self)
        self.setWindowIcon(QIcon(Constants.APP_ICON_DIALOG))
        self.setWindowTitle(Constants.APP_NAME)
        self.pushButton.clicked.connect(self.accept)
        self.label.setText(self.tr('Another instance of %s application is already running.') % Constants.APP_NAME)
        
def startDialog():
    app = QApplication([])
    i = SingleInstanceDlg()
    i.show()
    return app.exec_()

if __name__ == "__main__":
    sys.exit(startDialog())
    
