'''
Created on Feb 15, 2013

@author: mconstantin
'''

from dateutil import tz
from datetime import datetime
from PySide.QtGui import QDialog, QIcon, QVBoxLayout, QHBoxLayout
from PySide.QtGui import QTableView, QDialogButtonBox, QPushButton
from PySide.QtGui import QStandardItemModel, QStandardItem
from PySide.QtCore import Qt

import nxdrive.gui.qrc_resources
from nxdrive.model import ServerEvent

SQLID_ROLE = Qt.UserRole + 1


class InfoDlg(QDialog):
    def __init__(self, frontend=None, parent=None):
        super(InfoDlg, self).__init__(parent)

        self.frontend = frontend
        self.table = QTableView()
        buttonbox = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok, parent=self)
        self.btn_select = QPushButton(self.tr("Select All"))
        self.btn_clear = QPushButton(self.tr('Clear All'))
        self.btn_delete = QPushButton(self.tr('Delete'))
        self.btn_delete.setEnabled(False)
        buttonbox.addButton(self.btn_select, QDialogButtonBox.ActionRole)
        buttonbox.addButton(self.btn_clear, QDialogButtonBox.ActionRole)
        buttonbox.addButton(self.btn_delete, QDialogButtonBox.ActionRole)
        
        hlayout = QHBoxLayout()
        hlayout.addStretch(10)
        hlayout.addWidget(buttonbox)
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.table)
        vlayout.addLayout(hlayout)
        self.setLayout(vlayout)
        
        self.btn_select.clicked.connect(self.select_all)
        self.btn_clear.clicked.connect(self.clear_all)
        self.btn_delete.clicked.connect(self.delete)
        btn_ok = buttonbox.button(QDialogButtonBox.Ok)
        btn_ok.clicked.connect(self.accept)
        btn_cancel = buttonbox.button(QDialogButtonBox.Cancel)
        btn_cancel.clicked.connect(self.reject)
        
        if self.frontend is None:
            return 
        
        self.session = self.frontend.controller.get_session()
        server_events = self.session.query(ServerEvent).\
                        filter(ServerEvent.local_folder == frontend.local_folder).all()

        self.model = QStandardItemModel(len(server_events), 4)
        row_count = len(server_events)
        
        for row in xrange(0, row_count):
            item0 = QStandardItem()
            item0.setCheckable(True)
            if server_events[row].message_type == 'maintenance':
                icon = QIcon(':/maintenance.png')
            elif server_events[row].message_type == 'quota':
                icon = QIcon(':/gauge.png')
            else:
                icon = QIcon(':/unknown.png')
            item1 = QStandardItem(icon, None) 
            item1.setToolTip(server_events[row].message_type)
            # TODO convert to local time
            from_tz = tz.tzutc()
            to_tz = tz.tzlocal()
            event_time_utc = server_events[row].utc_time.replace(tzinfo=from_tz)
            event_time_local = event_time_utc.astimezone(to_tz)
            item2 = QStandardItem(event_time_local.strftime('%x %X'))

            info = server_events[row].message
            item3 = QStandardItem(info)
            item3.setToolTip(info)
            
            self.model.setItem(row, 0, item0)
            self.model.setItem(row, 1, item1)
            self.model.setItem(row, 2, item2)
            self.model.setItem(row, 3, item3)
            
            item2.setData(server_events[row].id, SQLID_ROLE)
            
        self.model.setHorizontalHeaderItem(0, QStandardItem(''))
        self.model.setHorizontalHeaderItem(1, QStandardItem(self.tr('Type')))
        self.model.setHorizontalHeaderItem(2, QStandardItem(self.tr('Created')))
        self.model.horizontalHeaderItem(2).setTextAlignment(Qt.AlignLeft)
        self.model.setHorizontalHeaderItem(3, QStandardItem(self.tr('Information')))
        self.model.horizontalHeaderItem(3).setTextAlignment(Qt.AlignLeft)

        self.model.sort(2, Qt.DescendingOrder)
        self.table.setModel(self.model)
        
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(3, 700)
        self.table.clicked.connect(self.select)
        self.resize(900, 250)
        
    def select(self, index):
        item_clicked = self.model.itemFromIndex(index)
        self._update_btn_delete()
    
    def select_all(self):
        row_count = self.model.rowCount()
        for i in xrange(0, row_count):
            item = self.model.item(i, 0)
            item.setCheckState(Qt.Checked)
        self.btn_delete.setEnabled(True)
    
    def clear_all(self):
        row_count = self.model.rowCount()
        for i in xrange(0, row_count):
            item = self.model.item(i, 0)
            item.setCheckState(Qt.Unchecked)
        self.btn_delete.setEnabled(False)
    
    def delete(self):
        items_deleted = []
        row_count = self.model.rowCount()
        col_count = self.model.columnCount()
        topleft = self.model.indexFromItem(self.model.item(0, 0))
        bottomright = self.model.indexFromItem(self.model.item(row_count - 1, col_count - 1))
        for i in xrange(row_count, 0, -1):
            item0 = self.model.item(i - 1, 0)
            if item0.checkState():
                item2 = self.model.item(i - 1, 2)
                item_id = item2.data(SQLID_ROLE)
                items_deleted.append(item_id)
                self.model.removeRow(i - 1)
                
        if len(items_deleted) > 0:
            self.session.query(ServerEvent).\
                    filter(ServerEvent.id.in_(items_deleted)).\
                    delete(synchronize_session=False)
            self.model.dataChanged.emit(topleft, bottomright)
            
    def _update_btn_delete(self):
        row_count = self.model.rowCount()
        for i in xrange(0, row_count):
            item = self.model.item(i, 0)
            if item.checkState():
                self.btn_delete.setEnabled(True)
                break
        else:
            self.btn_delete.setEnabled(False)
            
    def accept(self):
        self.session.commit()
        super(InfoDlg, self).accept()
        
    def reject(self):
        self.session.rollback()
        super(InfoDlg, self).reject()
        
