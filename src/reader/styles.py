# -*- coding: utf-8 -*-
"""
styles 模块
集中管理整个阅读器的界面样式与配色
所有颜色常量和 Qt 样式表统一在此定义
避免样式散落在各处 便于统一维护与后续换肤
"""

import os
import tempfile
from string import Template

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap


# ---------------------------------------------------------------------------
# 基础配色常量
# 界面里重复出现的颜色统一用下面的常量引用 修改一处即可全局生效
# ---------------------------------------------------------------------------

# 文字颜色
COLOR_TEXT_PRIMARY = "#2f302f"
COLOR_TEXT_SECONDARY = "#39434d"
COLOR_TEXT_BODY = "#26313b"
COLOR_TEXT_DARK = "#222222"
COLOR_TEXT_MUTED = "#334555"
COLOR_TEXT_BUTTON = "#2b3945"
COLOR_TEXT_DIALOG = "#2d3740"

# 主题蓝色
COLOR_ACCENT = "#3978b7"
COLOR_ACCENT_HOVER = "#2f6da9"
COLOR_ACCENT_FOCUS = "#4f88bd"
COLOR_ACCENT_SOFT = "#82a9cc"
COLOR_ACCENT_FOCUS_ALT = "#5b91c8"

# 边框与分隔线
COLOR_BORDER = "#cbd2d9"
COLOR_BORDER_LIGHT = "#e4e7eb"
COLOR_BORDER_FAINT = "#eceef2"
COLOR_BORDER_INPUT = "#c9ced4"
COLOR_BORDER_BUTTON = "#c5cdd5"

# 面板与交互背景
COLOR_PANEL = "#f9fafb"
COLOR_HOVER_BG = "#eaf2f9"
COLOR_PRESSED_BG = "#dceaf6"
COLOR_SELECTION_BG = "#b9d7f5"
COLOR_SELECTION_BG_SOFT = "#eef1f5"
COLOR_SELECTION_TEXT = "#14283d"

# 标题 滚动条与关闭按钮
COLOR_SECTION_TITLE = "#1d4f7a"
COLOR_SCROLLBAR = "#b8c1ca"
COLOR_CLOSE_HOVER_TEXT = "#a72f2f"
COLOR_CLOSE_HOVER_BG = "#f3d8d3"

# 微调器上翻下翻按钮的箭头颜色
COLOR_CHEVRON = "#6483a0"


# ---------------------------------------------------------------------------
# 样式表颜色映射
# 下面的字典把模板里的占位符映射到真实颜色 供 Template 替换使用
# ---------------------------------------------------------------------------

_PALETTE = {
    "text_primary": COLOR_TEXT_PRIMARY,
    "text_secondary": COLOR_TEXT_SECONDARY,
    "text_body": COLOR_TEXT_BODY,
    "text_dark": COLOR_TEXT_DARK,
    "text_muted": COLOR_TEXT_MUTED,
    "text_button": COLOR_TEXT_BUTTON,
    "text_dialog": COLOR_TEXT_DIALOG,
    "section_title": COLOR_SECTION_TITLE,
    "accent": COLOR_ACCENT,
    "accent_hover": COLOR_ACCENT_HOVER,
    "accent_focus": COLOR_ACCENT_FOCUS,
    "accent_soft": COLOR_ACCENT_SOFT,
    "accent_focus_alt": COLOR_ACCENT_FOCUS_ALT,
    "border": COLOR_BORDER,
    "border_light": COLOR_BORDER_LIGHT,
    "border_faint": COLOR_BORDER_FAINT,
    "border_input": COLOR_BORDER_INPUT,
    "border_button": COLOR_BORDER_BUTTON,
    "panel": COLOR_PANEL,
    "hover_bg": COLOR_HOVER_BG,
    "pressed_bg": COLOR_PRESSED_BG,
    "selection_bg": COLOR_SELECTION_BG,
    "selection_bg_soft": COLOR_SELECTION_BG_SOFT,
    "selection_text": COLOR_SELECTION_TEXT,
    "scrollbar": COLOR_SCROLLBAR,
    "close_hover_text": COLOR_CLOSE_HOVER_TEXT,
    "close_hover_bg": COLOR_CLOSE_HOVER_BG,
}


# ---------------------------------------------------------------------------
# 样式表模板
# 每个模板对应一个界面区域 通过 Template 替换颜色占位符
# ---------------------------------------------------------------------------

# 偏好设置对话框的通用样式
_DIALOG_STYLE_TEMPLATE = Template("""
        QDialog {
            color: $text_primary;
            font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
            font-size: 13px;
        }
        QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
        QLabel { color: $text_secondary; }
        QLabel#dialogTitle { color: $text_primary; font-size: 15px; font-weight: 600; }
        QLabel#sectionTitle {
            color: $section_title;
            font-size: 15px;
            font-weight: 600;
            padding: 8px 0 4px 0;
            border-bottom: 1px solid $border_faint;
        }
        QCheckBox { color: $text_dialog; spacing: 8px; padding: 3px 0; }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border: 1px solid $border;
            border-radius: 3px;
            background: #ffffff;
        }
        QCheckBox::indicator:hover { border-color: $accent_soft; }
        QCheckBox::indicator:checked {
            background: $accent;
            border-color: $accent;
            image: url(__CHECK__);
        }
        QCheckBox::indicator:checked:hover { background: $accent_hover; border-color: $accent_hover; }
        QComboBox, QFontComboBox, QSpinBox, QDoubleSpinBox, QKeySequenceEdit {
            min-height: 28px;
            padding: 0 7px;
            color: $text_body;
            background: #ffffff;
            border: 1px solid $border;
            border-radius: 4px;
            selection-background-color: $selection_bg;
            selection-color: $selection_text;
        }
        QComboBox:focus, QFontComboBox:focus, QSpinBox:focus,
        QDoubleSpinBox:focus, QKeySequenceEdit:focus { border-color: $accent_focus; }
        QComboBox QAbstractItemView, QFontComboBox QAbstractItemView {
            background: #ffffff; color: $text_body; border: 1px solid $border_light;
            selection-background-color: $selection_bg_soft; selection-color: $selection_text;
        }
        QPushButton {
            min-height: 30px;
            padding: 0 14px;
            border: 1px solid $border_button;
            border-radius: 4px;
            background: #ffffff;
            color: $text_button;
        }
        QPushButton:hover { border-color: $accent_soft; background: $hover_bg; }
        QPushButton:pressed { background: $pressed_bg; }
        QPushButton#primaryButton {
            color: #ffffff; background: $accent; border-color: $accent; font-weight: 600;
        }
        QPushButton#primaryButton:hover { background: $accent_hover; border-color: $accent_hover; }
        QPushButton#secondaryButton { color: $text_muted; background: $panel; }
        QPushButton#closeButton {
            min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px;
            padding: 0; border: none; background: transparent; font-size: 18px; font-weight: 400;
        }
        QPushButton#closeButton:hover { color: $close_hover_text; background: $close_hover_bg; }
        QScrollBar:vertical { width: 9px; background: transparent; margin: 2px; }
        QScrollBar::handle:vertical { min-height: 28px; background: $scrollbar; border-radius: 4px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    """)

# 打开文件对话框的样式
_FILE_DIALOG_STYLE_TEMPLATE = Template("""
            QDialog {
                font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
                font-size: 13px;
            }
            QLabel#dialogTitle { color: $text_primary; font-size: 14px; font-weight: 600; }
            QComboBox {
                min-height: 32px;
                padding: 0 9px;
                color: $text_dark;
                background: rgba(255, 255, 255, 225);
                border: 1px solid $border_input;
                border-radius: 4px;
            }
            QComboBox:focus { border-color: $accent_focus_alt; }
            QComboBox QAbstractItemView {
                background: #ffffff; color: $text_primary; border: 1px solid $border_light;
                selection-background-color: $selection_bg_soft; selection-color: $text_primary;
            }
            QPushButton {
                min-height: 30px;
                padding: 0 14px;
                color: #263544;
                background: rgba(255, 255, 255, 220);
                border: 1px solid $border_input;
                border-radius: 4px;
            }
            QPushButton:hover { background: #e8f1fa; border-color: #8eb5da; }
            QPushButton#primaryButton { color: white; background: $accent; border-color: $accent; }
            QPushButton#primaryButton:hover { background: $accent_hover; }
            QPushButton#closeButton {
                min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px;
                padding: 0; border: none; background: transparent; font-size: 18px;
            }
            QPushButton#closeButton:hover { color: $close_hover_text; background: rgba(220, 80, 80, 35); }
            QScrollBar:vertical { width: 9px; background: transparent; margin: 2px; }
            QScrollBar::handle:vertical { min-height: 28px; background: $scrollbar; border-radius: 4px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

# 目录弹窗章节列表的样式
_TOC_LIST_STYLE_TEMPLATE = Template("""
            QListWidget {
                background-color: rgba(248, 249, 250, 238);
                border: 1px solid rgba(190, 195, 200, 210);
                border-radius: 4px;
                color: $text_dark;
                outline: none;
                padding: 2px;
            }
            QListWidget::item {
                min-height: 28px;
                padding: 3px 6px;
                border-radius: 2px;
            }
            QListWidget::item:selected {
                background-color: #B9D7F5;
                color: #14283D;
            }
            QListWidget::item:hover:!selected {
                background-color: rgba(225, 235, 245, 210);
            }
            QScrollBar:vertical { width: 9px; background: #f8f9fa; margin: 2px; }
            QScrollBar::handle:vertical { min-height: 28px; background: $scrollbar; border-radius: 4px; }
            QScrollBar::groove:vertical,
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical { background: #f8f9fa; border: none; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal { height: 0; }
        """)

# 右键菜单的样式
_MENU_STYLE_TEMPLATE = Template("""
            QMenu { background: #ffffff; color: $text_primary; border: 1px solid $border_light;
                    padding: 5px; font-size: 13px; }
            QMenu::item { padding: 7px 22px; border-radius: 3px; }
            QMenu::item:selected { background: $selection_bg_soft; color: $text_primary; }
            QMenu::separator { height: 1px; background: $border_faint; margin: 5px 8px; }
        """)

# 主界面浮窗提示的样式
_TOAST_STYLE_TEMPLATE = Template("""
            background-color: rgba(0, 0, 0, 150); color: rgba(255, 255, 255, 235);
            border-radius: 6px; padding: 4px 14px;
        """)

# 微调器与下拉框的自绘箭头样式 图标路径在运行时填充
_ARROW_CSS = """
    QComboBox, QFontComboBox { padding-right: 20px; }
    QComboBox::drop-down, QFontComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: center right;
        width: 20px;
        border: none;
        background: transparent;
    }
    QComboBox::down-arrow, QFontComboBox::down-arrow {
        image: url(__DOWN__);
        width: 12px;
        height: 8px;
    }
    QSpinBox, QDoubleSpinBox { padding-right: 18px; }
    QSpinBox::up-button, QDoubleSpinBox::up-button {
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 18px;
        border: none;
        border-left: 1px solid #cbd2d9;
        background: transparent;
    }
    QSpinBox::down-button, QDoubleSpinBox::down-button {
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        width: 18px;
        border: none;
        border-left: 1px solid #cbd2d9;
        background: transparent;
    }
    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
        background: #e2edf8;
    }
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
        image: url(__UP__);
        width: 12px;
        height: 8px;
    }
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
        image: url(__DOWN__);
        width: 12px;
        height: 8px;
    }
"""

# 箭头图标路径缓存 避免每次重复生成 PNG
_ARROW_PATHS = None

# 勾选图标路径缓存 避免每次重复生成 PNG
_CHECK_PATH = None


# ---------------------------------------------------------------------------
# 箭头图标生成
# ---------------------------------------------------------------------------

def _arrow_icon_paths():
    """生成一组小箭头 PNG 图标 返回向下和向上两个文件的路径"""
    global _ARROW_PATHS
    if _ARROW_PATHS is not None:
        return _ARROW_PATHS

    # 图标统一放在系统临时目录的固定子目录里
    icon_dir = os.path.join(tempfile.gettempdir(), "reader_style_icons")
    os.makedirs(icon_dir, exist_ok=True)

    def _paint(up):
        """绘制一个 12x8 的折线箭头 pixmap up 为真表示向上"""
        pixmap = QPixmap(12, 8)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(COLOR_CHEVRON), 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        if up:
            painter.drawPolyline([QPointF(2, 6), QPointF(6, 2), QPointF(10, 6)])
        else:
            painter.drawPolyline([QPointF(2, 2), QPointF(6, 6), QPointF(10, 2)])
        painter.end()
        return pixmap

    # 生成并保存两个方向的箭头图标
    down_path = os.path.join(icon_dir, "chevron_down.png")
    up_path = os.path.join(icon_dir, "chevron_up.png")
    _paint(False).save(down_path)
    _paint(True).save(up_path)
    # 统一使用正斜杠 便于 Qt 样式表里的 url 使用
    _ARROW_PATHS = (down_path.replace("\\", "/"), up_path.replace("\\", "/"))
    return _ARROW_PATHS


def _check_icon_path():
    """生成白色对勾 PNG 图标并返回其路径 用于勾选框选中态"""
    global _CHECK_PATH
    if _CHECK_PATH is not None:
        return _CHECK_PATH

    # 图标统一放在系统临时目录的固定子目录里
    icon_dir = os.path.join(tempfile.gettempdir(), "reader_style_icons")
    os.makedirs(icon_dir, exist_ok=True)

    # 在透明画布上绘制一个白色对勾
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor("#ffffff"), 2.2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawPolyline([QPointF(3.5, 8.5), QPointF(6.8, 11.8), QPointF(12.8, 4.2)])
    painter.end()

    # 保存图标并缓存路径 统一使用正斜杠
    check_path = os.path.join(icon_dir, "check.png")
    pixmap.save(check_path)
    _CHECK_PATH = check_path.replace("\\", "/")
    return _CHECK_PATH


# ---------------------------------------------------------------------------
# 对外提供的样式表构建函数
# ---------------------------------------------------------------------------

def arrow_style_css():
    """返回微调器与下拉框自绘箭头的样式片段"""
    down, up = _arrow_icon_paths()
    return _ARROW_CSS.replace("__DOWN__", down).replace("__UP__", up)


def dialog_style_css():
    """返回偏好设置对话框完整样式 含自绘箭头与勾选图标"""
    check_path = _check_icon_path()
    css = _DIALOG_STYLE_TEMPLATE.substitute(_PALETTE).replace("__CHECK__", check_path)
    return css + arrow_style_css()


def file_dialog_style_css():
    """返回打开文件对话框完整样式 含自绘箭头"""
    return _FILE_DIALOG_STYLE_TEMPLATE.substitute(_PALETTE) + arrow_style_css()


def toc_list_style_css():
    """返回目录弹窗章节列表的样式"""
    return _TOC_LIST_STYLE_TEMPLATE.substitute(_PALETTE)


def menu_style_css():
    """返回主窗口右键菜单的样式"""
    return _MENU_STYLE_TEMPLATE.substitute(_PALETTE)


def toast_style_css():
    """返回主界面浮窗提示的样式"""
    return _TOAST_STYLE_TEMPLATE.substitute(_PALETTE)


def apply_dialog_style(dialog, layout=None):
    """给对话框应用统一样式 并设置标准边距与间距"""
    dialog.setStyleSheet(dialog_style_css())
    if layout:
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(9)
