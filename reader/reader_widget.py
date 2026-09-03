# -*- coding: utf-8 -*-
"""
reader_widget 模块
定义阅读区文本控件与文本排版函数
文本换行 分页计算与绘制逻辑集中在此 与主窗口解耦
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QWidget


def layout_text(text, metrics, max_width, max_lines):
    """对文本做一次排版 返回消费到的字符数与排好的行列表

    该函数同时用于分页计算和绘制 保证两者使用完全相同的换行结果
    返回的 consumed 表示按当前尺寸能容纳的字符数 lines 是排好的每行文本
    """
    if not text or max_lines < 1:
        return 0, []

    lines = [""]
    line_width = 0
    consumed = 0
    for index, character in enumerate(text):
        # 回车符不占显示宽度 仅更新已消费位置
        if character == '\r':
            consumed = index + 1
            continue
        # 换行符强制开启新行 行数已满则直接返回
        if character == '\n':
            consumed = index + 1
            if len(lines) >= max_lines:
                return consumed, lines
            lines.append("")
            line_width = 0
            continue

        # 制表符展开为四个空格 其余字符原样显示
        displayed = "    " if character == '\t' else character
        character_width = max(1, metrics.horizontalAdvance(displayed))
        # 当前行已放不下该字符时换行 行数已满则返回当前字符位置
        if line_width and line_width + character_width > max_width:
            if len(lines) >= max_lines:
                return index, lines
            lines.append("")
            line_width = 0
        lines[-1] += displayed
        line_width += character_width
        consumed = index + 1
    return consumed, lines


class ReaderTextWidget(QWidget):
    """阅读区的文本显示控件 负责按当前设置绘制文字"""

    # 文本内容四周的留白 保证文字不贴边
    HORIZONTAL_PADDING = 12
    VERTICAL_PADDING = 12

    def __init__(self, text="", parent=None):
        """初始化控件 设置透明背景与默认显示参数"""
        super().__init__(parent)
        # 使用透明背景 由主窗口统一绘制背景色
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAutoFillBackground(False)
        self._text = text
        self._line_height = 1
        self._text_color = QColor(Qt.GlobalColor.black)
        self._text_alpha = 1.0

    def setText(self, text):
        """设置要显示的文本并请求重绘"""
        self._text = text
        self.update()

    def text(self):
        """返回当前显示的文本"""
        return self._text

    def set_display_options(self, line_height, color, alpha):
        """更新显示参数 行高 颜色与不透明度"""
        self._line_height = max(1, line_height)
        self._text_color = QColor(color)
        self._text_alpha = max(0.0, min(1.0, alpha))
        self.update()

    def paintEvent(self, event):
        """绘制文本内容 先排版再逐行绘制"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # 根据当前不透明度生成画笔颜色
        color = QColor(self._text_color)
        color.setAlphaF(self._text_alpha)
        painter.setPen(color)
        painter.setFont(self.font())

        # 计算除去留白后的可用区域与最多行数
        metrics = QFontMetrics(self.font())
        content_width = max(1, self.width() - self.HORIZONTAL_PADDING * 2)
        content_height = max(1, self.height() - self.VERTICAL_PADDING * 2)
        max_lines = max(1, content_height // self._line_height)

        # 按窗口高度逐行绘制
        _, lines = layout_text(self._text, metrics, content_width, max_lines)
        baseline = self.VERTICAL_PADDING + metrics.ascent()
        for index, line in enumerate(lines):
            painter.drawText(self.HORIZONTAL_PADDING, baseline + index * self._line_height, line)
