# -*- coding: utf-8 -*-
"""
dialog_reading 模块
定义目录选择弹窗 TocDialog 与打开文件弹窗 FileDialog
"""

import os
from urllib.parse import urlparse

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFileDialog,
                               QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QVBoxLayout)

from utils import local_path_from_url, RoundedDialog
from styles import toc_list_style_css, file_dialog_style_css


class TocDialog(QDialog):
    """目录选择弹窗 数据完全来自主窗口的本地书籍缓存"""

    def __init__(self, parent, toc_url):
        """初始化目录弹窗 载入章节列表并定位到当前章节"""
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("目录")
        self.resize(300, 150)
        self.setMinimumSize(200, 100)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 按目录快捷键可关闭弹窗
        self.close_shortcut = QShortcut(QKeySequence(parent.key_toc), self)
        self.close_shortcut.activated.connect(self.reject)

        # 监听全局事件 点击弹窗外部任意位置时关闭弹窗
        QApplication.instance().installEventFilter(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        # 创建章节列表并应用统一样式
        self.chapter_list = QListWidget()
        self.chapter_list.setAlternatingRowColors(False)
        self.chapter_list.setEditTriggers(QListWidget.EditTrigger.NoEditTriggers)
        self.chapter_list.setStyleSheet(toc_list_style_css())
        self.chapter_list.itemActivated.connect(self._open_chapter)
        layout.addWidget(self.chapter_list)

        # 逐个填充章节 并高亮当前章节
        for title, url in parent.get_cached_toc(toc_url) or []:
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, url)
            self.chapter_list.addItem(item)
            if url == parent.current_url:
                self.chapter_list.setCurrentItem(item)
                self.chapter_list.scrollToItem(item, QListWidget.ScrollHint.PositionAtCenter)

        # 没有匹配到当前章节时默认选中第一项
        if self.chapter_list.currentItem() is None and self.chapter_list.count():
            self.chapter_list.setCurrentRow(0)
        self.chapter_list.setFocus()

    def event(self, event):
        """弹窗失去焦点时自动关闭"""
        if event.type() == QEvent.Type.WindowDeactivate:
            self.reject()
            return True
        return super().event(event)

    def eventFilter(self, watched, event):
        """点击弹窗外部时自动关闭"""
        if self.isVisible() and event.type() == QEvent.Type.MouseButtonPress:
            if not self.frameGeometry().contains(event.globalPosition().toPoint()):
                self.reject()
        return super().eventFilter(watched, event)

    def _open_chapter(self, item):
        """跳转到选中的章节并关闭弹窗"""
        self.parent._force_reset_index = True
        self.parent.start_async_load(item.data(Qt.ItemDataRole.UserRole))
        self.accept()


class FileDialog(RoundedDialog):
    """我的书库：打开本地文件并管理最近阅读记录"""

    def __init__(self, parent):
        """初始化打开文件弹窗 构建历史记录映射"""
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("我的书库")
        self.resize(380, 130)
        self.setMinimumSize(380, 130)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.set_rounded_style(radius=5)

        # 把历史记录转成 显示文本到地址 的映射
        self.history_mapping = {
            f"{item.get('title', '本地文件')} - {path}": item.get('url', '')
            for item in parent.file_history
            if (path := local_path_from_url(item.get('url', '')))
        }
        self._init_ui()

    def _init_ui(self):
        """构建弹窗界面 标题栏 文件选择框与按钮"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        self.setStyleSheet(file_dialog_style_css())

        # 标题栏 左侧标题 右侧关闭按钮
        header = QHBoxLayout()
        header.setSpacing(0)
        title = QLabel("我的书库")
        title.setObjectName("dialogTitle")
        header.addWidget(title)
        header.addStretch()
        close_button = QPushButton("×")
        close_button.setObjectName("closeButton")
        close_button.setToolTip("关闭")
        close_button.clicked.connect(self.reject)
        header.addWidget(close_button)
        layout.addLayout(header)

        # 可编辑下拉框 既能选择历史也能直接输入路径
        self.file_combo = QComboBox()
        self.file_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.file_combo.setEditable(True)
        self.file_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.file_combo.setMinimumContentsLength(24)
        self.file_combo.addItems(self.history_mapping.keys())

        # 当前已有打开文件时预填当前文件
        if urlparse(self.parent.current_url).scheme in ("file", "localbook"):
            current = next((label for label, url in self.history_mapping.items()
                            if url == self.parent.current_url),
                           local_path_from_url(self.parent.current_url))
            self.file_combo.setCurrentText(current)
        self.file_combo.setPlaceholderText("选择 txt、epub 或 mobi 文件")
        layout.addWidget(self.file_combo)

        # 底部按钮区 浏览文件与打开并阅读
        buttons = QHBoxLayout()
        browse = QPushButton("添加书籍")
        browse.setObjectName("secondaryButton")
        browse.clicked.connect(self._choose_file)
        remove = QPushButton("删除记录")
        remove.setObjectName("secondaryButton")
        remove.clicked.connect(self._remove_selected)
        open_button = QPushButton("打开并阅读")
        open_button.setObjectName("primaryButton")
        open_button.clicked.connect(self._open_file)
        buttons.addWidget(browse)
        buttons.addWidget(remove)
        buttons.addStretch()
        buttons.addWidget(open_button)
        layout.addLayout(buttons)

    def _remove_selected(self):
        """从书库删除当前记录，不删除本地文件。"""
        value = self.file_combo.currentText().strip()
        target = self.history_mapping.get(value, "")
        if not target:
            return
        target_path = local_path_from_url(target)
        self.parent.file_history = [
            item for item in self.parent.file_history
            if local_path_from_url(item.get("url", "")) != target_path
        ]
        self.parent.save_current_config()
        index = self.file_combo.findText(value)
        if index >= 0:
            self.file_combo.removeItem(index)
        self.history_mapping.pop(value, None)
        if self.file_combo.count():
            self.file_combo.setCurrentIndex(0)

    def _choose_file(self):
        """弹出系统文件选择框 把选中的路径填入输入框"""
        path, _ = QFileDialog.getOpenFileName(
            self, "打开小说文件", "", "小说文件 (*.txt *.epub *.mobi)")
        if path:
            self.file_combo.setCurrentText(path)

    def _open_file(self):
        """校验并打开输入框中的文件"""
        value = self.file_combo.currentText().strip()
        target = self.history_mapping.get(value, value)
        from_history = value in self.history_mapping
        if not target:
            return

        # 解析目标路径 本地地址反解 普通路径做展开与绝对化
        is_local_url = urlparse(target).scheme in ("file", "localbook")
        path = local_path_from_url(target) if is_local_url else os.path.abspath(os.path.expanduser(target))
        if not os.path.isfile(path):
            QMessageBox.warning(self, "打开失败", "本地文件不存在，可能已被移动或删除。")
            return

        # 生成目标地址 历史记录沿用原地址 否则预加载后取第一章
        try:
            target_url = target if urlparse(target).scheme == "localbook" else self.parent.prepare_local_book(path)[0]
        except Exception as error:
            QMessageBox.warning(self, "打开失败", f"无法打开该文件：\n{error}")
            return

        # 从历史打开时保留进度 新打开时回到开头
        self.parent._force_reset_index = not from_history
        self.parent.start_async_load(target_url)
        self.accept()
