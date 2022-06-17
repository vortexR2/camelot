#  ============================================================================
#
#  Copyright (C) 2007-2016 Conceptive Engineering bvba.
#  www.conceptive.be / info@conceptive.be
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#      * Redistributions of source code must retain the above copyright
#        notice, this list of conditions and the following disclaimer.
#      * Redistributions in binary form must reproduce the above copyright
#        notice, this list of conditions and the following disclaimer in the
#        documentation and/or other materials provided with the distribution.
#      * Neither the name of Conceptive Engineering nor the
#        names of its contributors may be used to endorse or promote products
#        derived from this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#  ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#  WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
#  DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#  ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#  ============================================================================

""" Tableview """

import logging

from camelot.view.model_thread import object_thread
from ...core.qt import QtCore, QtGui, QtWidgets, Qt, variant_to_py


logger = logging.getLogger('camelot.view.controls.tableview')


class ColumnGroupsWidget(QtWidgets.QTabBar):
    """
    A tabbar the user can use to select a group of columns within an
    item view.

    :param table: a :class:`camelot.admin.table.Table` object, describing the
        column groups.
    :param table_widget: a :class:`QtWidgets.QTableView` widget of which
        columns will be hidden and shown depending on the selected tab.
    :param parent: a :class:`QtWidgets.QWidget`
    """

    def __init__(self, table, table_widget, parent=None):
        from camelot.admin.table import ColumnGroup
        super(ColumnGroupsWidget, self).__init__(parent)
        assert object_thread(self)
        self.setShape(QtWidgets.QTabBar.Shape.RoundedSouth)
        self.groups = dict()
        self.table_widget = table_widget
        column_index = 0
        tab_index = 0
        for column in table.columns:
            if isinstance(column, ColumnGroup):
                self.addTab(str(column.verbose_name))
                previous_column_index = column_index
                column_index = column_index + len(column.get_fields())
                self.groups[tab_index] = (previous_column_index,
                                          column_index)
                tab_index += 1
            else:
                column_index += 1
        self.currentChanged.connect(self._current_index_changed)

    @QtCore.qt_slot(QtCore.QModelIndex, int, int)
    def columns_changed(self, index, first_column, last_column):
        assert object_thread(self)
        self._current_index_changed(self.currentIndex())

    @QtCore.qt_slot()
    def model_reset(self):
        assert object_thread(self)
        self._current_index_changed(self.currentIndex())

    @QtCore.qt_slot(int)
    def _current_index_changed(self, current_index):
        assert object_thread(self)
        for tab_index, (first_column,
                        last_column) in self.groups.items():
            for column_index in range(first_column, last_column):
                self.table_widget.setColumnHidden(column_index,
                                                  tab_index != current_index)


class TableWidget(QtWidgets.QTableView):
    """
    A widget displaying a table, to be used within a TableView.  But it does
    not rely on the model being Camelot specific, or a Collection Proxy.

    .. attribute:: margin

    margin, specified as a number of pixels, used to calculate the height of a
    row in the table, the minimum row height will allow for this number of
    pixels below and above the text.

    :param lines_per_row: the number of lines of text that should be viewable
        in a single row.
    """

    margin = 5
    keyboard_selection_signal = QtCore.qt_signal()

    def __init__(self, lines_per_row=1, parent=None):
        QtWidgets.QTableView.__init__(self, parent)
        logger.debug('create TableWidget')
        assert object_thread(self)
        self._columns_changed = dict()
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.SelectedClicked |
                             QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked |
                             QtWidgets.QAbstractItemView.EditTrigger.CurrentChanged)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)
        try:
            self.horizontalHeader().setClickable(True)
        except AttributeError:
            self.horizontalHeader().setSectionsClickable(True)
        self._header_font_required = QtWidgets.QApplication.font()
        self._header_font_required.setBold(True)
        line_height = QtGui.QFontMetrics(QtWidgets.QApplication.font()
                                         ).lineSpacing()
        self._minimal_row_height = line_height * lines_per_row + 2*self.margin
        self.verticalHeader().setDefaultSectionSize(self._minimal_row_height)
        self.setHorizontalScrollMode(
            QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.horizontalHeader().sectionClicked.connect(
            self.horizontal_section_clicked)
        self.horizontalHeader().sectionResized.connect(
            self._save_section_width)
        self.verticalScrollBar().sliderPressed.connect(self._slider_pressed)
        self.horizontalScrollBar().sliderPressed.connect(self._slider_pressed)

    @QtCore.qt_slot()
    def selectAll(self):
        """
        Reimplement `QtWidgets.QAbstractItemView.selectAll` to add the
        option of selecting nothing.
        """
        selection_model = self.selectionModel()
        if selection_model is not None:
            if selection_model.hasSelection():
                selection_model.clear()
            else:
                super(TableWidget, self).selectAll()

    def timerEvent(self, event):
        """ On timer event, save changed column widths to the model """
        assert object_thread(self)
        for logical_index, new_width in self._columns_changed.items():
            if self.horizontalHeader().isSectionHidden(logical_index):
                # don't save the width of a hidden section, since this will
                # result in setting the width to 0
                continue
            old_size = variant_to_py(self.model().headerData(logical_index,
                                                             Qt.Orientation.Horizontal,
                                                             Qt.ItemDataRole.SizeHintRole))
            # when the size is different from the one from the model, the
            # user changed it
            if (old_size is not None) and (old_size.width() != new_width):
                new_size = QtCore.QSize(new_width, old_size.height())
                self.model().setHeaderData(logical_index,
                                           Qt.Orientation.Horizontal,
                                           new_size,
                                           Qt.ItemDataRole.SizeHintRole)
        self._columns_changed = dict()
        super(TableWidget, self).timerEvent(event)

    @QtCore.qt_slot()
    def _slider_pressed(self):
        """
        Close the editor when scrolling starts, to prevent the table from
        jumping back to the open editor, or to prevent the open editor from
        being out of sight.
        """
        self.close_editor()

    @QtCore.qt_slot(int, int, int)
    def _save_section_width(self, logical_index, _old_size, new_width):
        # instead of storing the width immediately, a timer is started to store
        # the width when all event processing is done.  because at this time
        # we cannot yet determine if the section at logical_index is hidden
        # or not
        #
        # there is no need to start the timer, since this is done by the
        # QAbstractItemView itself for doing the layout, here we only store
        # which column needs to be saved.
        assert object_thread(self)
        self._columns_changed[logical_index] = new_width

    @QtCore.qt_slot(int)
    def horizontal_section_clicked(self, logical_index):
        """Update the sorting of the model and the header"""
        assert object_thread(self)
        header = self.horizontalHeader()
        order = Qt.SortOrder.AscendingOrder
        if not header.isSortIndicatorShown():
            header.setSortIndicatorShown(True)
        elif header.sortIndicatorSection() == logical_index:
            # apparently, the sort order on the header is already switched
            # when the section was clicked, so there is no need to reverse it
            order = header.sortIndicatorOrder()
        header.setSortIndicator(logical_index, order)
        self.model().sort(logical_index, order)

    def close_editor(self):
        """
        Close the active editor, this method is used to prevent assertion
        failures in QT when an editor is still open in the view for a cell
        that no longer exists in the model

        those assertion failures only exist in QT debug builds.
        """
        assert object_thread(self)
        current_index = self.currentIndex()
        if not current_index.isValid():
            return
        self.closePersistentEditor(current_index)

    def setModel(self, model):
        assert object_thread(self)
        #
        # An editor might be open that is no longer available for the new
        # model.  Not closing this editor, results in assertion failures
        # in qt, resulting in segfaults in the debug build.
        #
        self.close_editor()
        #
        # Editor, closed. it should be safe to change the model
        #
        QtWidgets.QTableView.setModel(self, model)
        model.setParent(self)
        # assign selection model to local variable to keep it alive during
        # method call, or PySide segfaults
        selection_model = self.selectionModel()
        selection_model.currentChanged.connect(self._current_changed)
        model.modelReset.connect(self.update_headers)
        self.update_headers()

    @QtCore.qt_slot()
    def update_headers(self):
        """
        Updating the header size seems to be no default Qt function, so, it's
        managed here
        """
        model = self.model()
        for i in range(model.columnCount()):
            size_hint = variant_to_py(model.headerData(i,
                                                       Qt.Orientation.Horizontal,
                                                       Qt.ItemDataRole.SizeHintRole))
            if size_hint is not None:
                self.setColumnWidth(i, size_hint.width())
        # dont save these changes, since they are the defaults
        self._columns_changed = dict()

    @QtCore.qt_slot(QtCore.QModelIndex, QtCore.QModelIndex)
    def _current_changed(self, current, previous):
        """ This slot is called whenever the current cell is changed """
        editor = self.indexWidget(current)
        header_data = self.model().headerData
        # if there is an editor in the current cell, change the column and
        # row width to the size hint of the editor
        if editor is not None:
            column_size_hint = variant_to_py(header_data(current.column(),
                                                         Qt.Orientation.Horizontal,
                                                         Qt.ItemDataRole.SizeHintRole))
            row_size_hint = variant_to_py(header_data(current.row(),
                                                      Qt.Orientation.Vertical,
                                                      Qt.ItemDataRole.SizeHintRole))
            editor_size_hint = editor.sizeHint()
            self.setRowHeight(current.row(), max(row_size_hint.height(),
                                                 editor_size_hint.height()))
            self.setColumnWidth(current.column(),
                                max(column_size_hint.width(),
                                    editor_size_hint.width()))
        if current.row() != previous.row():
            if previous.row() >= 0:
                row_size_hint = variant_to_py(header_data(previous.row(),
                                                          Qt.Orientation.Vertical,
                                                          Qt.ItemDataRole.SizeHintRole))
                self.setRowHeight(previous.row(), row_size_hint.height())
        if current.column() != previous.column():
            if previous.column() >= 0:
                column_size_hint = variant_to_py(header_data(previous.column(),
                                                             Qt.Orientation.Horizontal,
                                                             Qt.ItemDataRole.SizeHintRole))
                self.setColumnWidth(previous.column(),
                                    column_size_hint.width())
        # whenever we change the size, sectionsResized is called, but these
        # changes should not be saved.
        self._columns_changed = dict()

        self.model().change_selection_v2([current.row(), current.row()], current.row(), current.column())

    def keyPressEvent(self, e):
        assert object_thread(self)
        if self.hasFocus() and e.key() in (QtCore.Qt.Key.Key_Enter,
                                           QtCore.Qt.Key.Key_Return):
            self.keyboard_selection_signal.emit()
        else:
            super(TableWidget, self).keyPressEvent(e)


class AdminTableWidget(QtWidgets.QWidget):
    """
    A table widget that inspects the admin class and changes the behavior
    of the table as specified in the admin class
    """

    def __init__(self, parent=None):
        super(AdminTableWidget, self).__init__(parent)
        assert object_thread(self)
        table_widget = TableWidget(parent=self)
        table_widget.setObjectName('table_widget')
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(table_widget)
        self.setLayout(layout)

    def __getattr__(self, name):
        table_widget = self.findChild(QtWidgets.QWidget, 'table_widget')
        if table_widget is not None:
            return getattr(table_widget, name)

    def setModel(self, model):
        assert object_thread(self)
        table_widget = self.findChild(QtWidgets.QWidget, 'table_widget')
        if table_widget is not None:
            table_widget.setModel(model)
