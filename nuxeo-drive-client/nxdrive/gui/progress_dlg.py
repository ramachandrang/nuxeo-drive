'''
Created on Dec 13, 2012

@author: mconstantin
'''

from PySide.QtGui import QDialog, QImage, QPushButton, QLabel, QMovie
from PySide.QtCore import QTimer, Qt, QRectF, QPointF

from nxdrive.logging_config import get_logger

log = get_logger(__name__)


class ProgressDialog(QDialog):
    WINDOW_WIDTH = 120
    WINDOW_HEIGHT = 110
    OK_AND_RESTART = 1
    OK_AND_NO_RESTART = 2
    CANCELLED = 3
    PROGRESS_DLG_RESULT = {QDialog.Accepted: OK_AND_RESTART,
                           QDialog.Rejected: CANCELLED,
                           }
    
    def __init__(self, frontend, parent=None, cancel=True):
        super(ProgressDialog, self).__init__(parent=parent, f=Qt.FramelessWindowHint)
        
        self.frontend = frontend
        self.setFixedSize(ProgressDialog.WINDOW_WIDTH, ProgressDialog.WINDOW_HEIGHT)
        self.btn = QPushButton('Cancel', self)
        sizeBtn = self.btn.size()
        self.btn.setEnabled(cancel)
        
        self.lblMov = QLabel(self)
        self.movie = QMovie(':/wheel.gif')
        self.lblMov.setMovie(self.movie)
        self.lblMsg = QLabel("Stopping syncing...", self)
        self.lblMsg.setStyleSheet("QLabel { font-family : arial; font-size : 10px; color : DarkBlue }")
        
        image = QImage(':/wheel.gif')
        sizeImg = image.size()
        sizeImg.setWidth(sizeImg.width() + 2)
        sizeImg.setHeight(sizeImg.height() + 2)
        sizeClient = self.rect()
        sizeMsg = self.lblMsg.size()
        
        dy = (sizeClient.height() - sizeImg.height() - sizeBtn.height() - sizeMsg.height()) / 3
        ix = (sizeClient.width() - sizeImg.width()) / 2
        iy = dy
        if iy < 2: iy = 2
        mx = (sizeClient.width() - sizeMsg.width()) / 2
        my = iy + sizeImg.height() + dy
        bx = (sizeClient.width() - sizeBtn.width()) / 2
        by = my + sizeMsg.height() + dy 
        self.rectImg = QRectF(QPointF(ix, iy), sizeImg)

        # x-position doesn't add up!?
        bx += 8; mx += 8
        self.btn.move(bx, by)
        self.lblMov.setGeometry(ix, iy, sizeImg.width(), sizeImg.height())
        self.lblMsg.setGeometry(mx, my, sizeMsg.width(), sizeMsg.height())
        
        #Looks better with background
#        self.setAttribute(Qt.WA_TranslucentBackground)
        self.btn.clicked.connect(self.cancel)
        
        # start a timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.timeout)
        self.timer.setInterval(500)
        self.timer.start()
        
        self.movie.start()
        
        
    def cancel(self):
        self.timer.stop()
        self.reject()
        
    def ok(self):
        self.timer.stop()
        self.accept()
        
    @classmethod
    def stopServer(self, frontend, parent = None, cancel = True):
        if frontend.worker is not None and frontend.worker.isAlive():
            # Ask the controller to stop: the synchronization loop will in turn
            # call notify_sync_stopped and finally handle_stop (without quitting the app)
            frontend.controller.stop()
        
            # wait in a loop while displaying a message...
            dlg = ProgressDialog(frontend, parent = parent, cancel = cancel)
            return ProgressDialog.PROGRESS_DLG_RESULT[dlg.exec_()]
        else:
            return ProgressDialog.OK_AND_NO_RESTART

    def timeout(self):
        if self.frontend.worker is None or not self.frontend.worker.isAlive():
            super(ProgressDialog, self).accept()
