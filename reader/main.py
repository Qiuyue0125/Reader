# -*- coding: utf-8 -*-
"""
main 模块
阅读器主程序入口
定义主窗口 ReaderWindow 负责界面 文本排版 翻页 快捷键与配置保存
文本控件与排版函数已拆分到 reader_widget 界面样式已拆分到 styles
"""

import sys
import os
import re
import time
import signal
from urllib.parse import urlparse, parse_qs

try:
    from windows_hotkey import WinHotkeyManager
except ImportError as error:
    print(f"未能导入 Windows 原生热键模块: {error}")
    WinHotkeyManager = None

from PySide6.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget,
                               QMenu, QSystemTrayIcon, QMessageBox)
from PySide6.QtGui import (QColor, QKeySequence, QShortcut, QFontMetrics, QMouseEvent,
                           QWheelEvent, QIcon, QPixmap, QPainter, QFont)
from PySide6.QtCore import Qt, QTranslator, QLibraryInfo, QRect, QTimer, QEvent
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from utils import (load_config, save_config, make_local_file_url, local_path_from_url,
                   split_txt_chapters, parse_epub_chapters, parse_mobi_chapters, WEIGHT_MAP,
                   CONFIG_DEFAULTS)
from reader_widget import ReaderTextWidget, layout_text
from styles import menu_style_css, toast_style_css
from dialog_reading import FileDialog, TocDialog
from dialog_settings import SettingsDialog


# ---------------------------------------------------------------------------
# 模块级常量
# ---------------------------------------------------------------------------

# 可自定义快捷键到 QShortcut 对象名与处理函数名的映射
SHORTCUT_BINDINGS = {
    "key_prev_line": ("sc_custom_pl", "prev_line"),
    "key_next_line": ("sc_custom_nl", "next_line"),
    "key_bg_up": ("sc_bg_up", "increase_bg_opacity"),
    "key_bg_down": ("sc_bg_down", "decrease_bg_opacity"),
    "key_text_up": ("sc_text_up", "increase_text_opacity"),
    "key_text_down": ("sc_text_down", "decrease_text_opacity"),
    "key_toc": ("sc_toc", "open_toc_dialog"),
    "key_auto_toggle": ("sc_auto_toggle", "toggle_auto_page"),
    "key_auto_speed_up": ("sc_auto_speed_up", "auto_speed_up"),
    "key_auto_speed_down": ("sc_auto_speed_down", "auto_speed_down"),
}

# 这些配置项需要特殊转换后再保存 不能在通用循环里直接读取
_CONFIG_SPECIAL_KEYS = {"width", "height", "window_x", "window_y", "text_color", "bg_color"}

# 阅读区文本控件的水平与垂直边距总计 用于估算可用区域与默认窗口尺寸
_TEXT_H_MARGIN = ReaderTextWidget.HORIZONTAL_PADDING * 2
_TEXT_V_MARGIN: int = ReaderTextWidget.VERTICAL_PADDING * 2


class ReaderWindow(QMainWindow):
    """阅读器主窗口 无边框可拖动缩放 支持透明与置顶"""

    # ---------------------------------------------------------------------------
    # 初始化与配置
    # ---------------------------------------------------------------------------

    def __init__(self):
        """初始化主窗口 加载配置 构建界面并恢复上次阅读位置"""
        super().__init__()

        # 加载配置并同步到实例属性
        self.config = load_config()
        self._apply_config_attributes()

        # 当前书籍与阅读状态
        self.full_article_text = "右键打开书库，加载小说即可开始阅读..."
        self._raw_chapter_text = ""
        self.current_url = ""
        self.current_title = ""
        self.prev_chapter_url = ""
        self.next_chapter_url = ""
        self.current_toc_url = ""
        self.chapter_cache = {}
        self.toc_cache = {}

        # 阅读位置与翻页状态
        self.char_index = 0
        self.current_fit_count = 1
        self._force_reset_index = False
        self._jump_to_end_after_load = False
        # 防止一次输入事件在章节切换过程中重复触发下一章
        self._chapter_transitioning = False

        # 鼠标 悬停 拖动与缩放状态
        self._mouse_in_window = False
        self._hover_check_timer = None
        self.is_hidden = False
        self.dragPos = None
        self.resize_edge = ""
        self.resize_start_pos = None
        self.resize_start_geometry = None
        self.resize_margin = 3
        self._hidden_widgets = []

        # 全局热键管理器与几何保存定时器
        self._win_hotkey_manager = None
        self._win_quit_hotkey_manager = None
        self._last_toggle_time = 0
        self._geometry_save_timer = QTimer(self)
        self._geometry_save_timer.setSingleShot(True)
        self._geometry_save_timer.setInterval(500)
        self._geometry_save_timer.timeout.connect(self._save_geometry_config)

        # 依次构建界面 图标 托盘 快捷键 悬停检测与浮窗提示
        self.init_ui()
        self.update_icon()
        self.init_tray()
        self.init_shortcuts()
        self._init_hover_timer()
        self._init_toast()

        # 恢复上次打开的本地文件
        if self.file_history:
            if last_url := self.file_history[0].get("url"):
                self.start_async_load(last_url)

    def _apply_config_attributes(self):
        """把配置字典中的设置同步到实例属性"""
        # 特殊键需要转换 跳过它们 其余直接读取 缺失时用默认值
        for name, default in CONFIG_DEFAULTS.items():
            if name not in _CONFIG_SPECIAL_KEYS:
                setattr(self, name, self.config.get(name, default))
        # 颜色字符串转成 QColor 对象
        self.text_color = QColor(self.config.get("text_color", "#000000"))
        self.bg_color = QColor(self.config.get("bg_color", "#fcfbfb"))
        # 窗口坐标可能为 None 表示尚未保存过位置
        self.window_x = self.config.get("window_x", None)
        self.window_y = self.config.get("window_y", None)

    # ---------------------------------------------------------------------------
    # 界面构建
    # ---------------------------------------------------------------------------

    def init_ui(self):
        """构建主窗口界面 设置窗口标志与阅读文本控件"""
        self.apply_window_flags()
        self.setWindowTitle("reader")
        self.setMouseTracking(True)

        # 中央控件承载阅读文本 并监听鼠标事件
        self.central_widget = QWidget()
        self.central_widget.setMouseTracking(True)
        self.central_widget.installEventFilter(self)
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # 阅读文本控件 鼠标事件穿透 由中央控件统一处理
        self.label = ReaderTextWidget(self.full_article_text)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.label.setMouseTracking(True)
        self.layout.addWidget(self.label)

        self.apply_styles()
        self.setMinimumSize(100, 45)
        self._restore_window_geometry()

    def apply_window_flags(self):
        """根据置顶与任务栏设置重建窗口标志"""
        flags = Qt.WindowType.FramelessWindowHint
        if self.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        if not self.show_taskbar:
            flags |= Qt.WindowType.Tool
        self.setWindowFlags(flags)
        self._apply_window_attributes()

    def _apply_window_attributes(self):
        """重新应用窗口属性 setWindowFlags 后会丢失 需要重新设置"""
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # 禁用系统级窗口阴影
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

    def _default_window_size(self):
        """按汉字宽和行高估算默认窗口尺寸"""
        metrics = QFontMetrics(self.label.font())
        width = max(480, metrics.horizontalAdvance("阅" * 28) + _TEXT_H_MARGIN)
        height = max(70, self._line_height() * 3 + _TEXT_V_MARGIN)
        return width, height

    def _restore_window_geometry(self):
        """恢复上次保存的窗口位置与尺寸 越界时回退到屏幕中央"""
        default_width, default_height = self._default_window_size()
        try:
            configured_width = self.config.get("width")
            configured_height = self.config.get("height")
            width = max(self.minimumWidth(), int(
                default_width if configured_width is None else configured_width))
            height = max(self.minimumHeight(), int(
                default_height if configured_height is None else configured_height))
        except (TypeError, ValueError):
            width, height = default_width, default_height

        self.resize(width, height)

        try:
            x, y = int(self.window_x), int(self.window_y)
        except (TypeError, ValueError):
            x = y = None

        # 目标位置与任一屏幕有交集才使用 否则放到主屏中央
        target = QRect(x, y, width, height) if x is not None else QRect()
        on_screen = any(target.intersects(screen.availableGeometry()) for screen in QApplication.screens())
        if on_screen:
            self.move(x, y)
            return

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.x() + (screen.width() - width) // 2,
            screen.y() + (screen.height() - height) // 2,
        )

    # ---------------------------------------------------------------------------
    # 图标与托盘
    # ---------------------------------------------------------------------------

    def _bundled_icon_path(self):
        """返回打包时捆绑的图标路径 不存在时返回空串"""
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, 'logo.png')
        return path if os.path.exists(path) else ""

    def update_icon(self):
        """更新应用图标 优先自定义或打包图标 否则绘制默认图标"""
        icon_file = self.icon_path or self._bundled_icon_path()
        if icon_file and os.path.exists(icon_file):
            self.app_icon = QIcon(icon_file)
        else:
            # 绘制一个带 书 字的默认图标
            pixmap = QPixmap(64, 64)
            pixmap.fill(QColor("#2c3e50"))
            painter = QPainter(pixmap)
            painter.setPen(Qt.GlobalColor.white)
            painter.setFont(QFont("Microsoft YaHei", 32, QFont.Weight.Bold))
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "书")
            painter.end()
            self.app_icon = QIcon(pixmap)

        # 应用到窗口 应用与托盘
        self.setWindowIcon(self.app_icon)
        QApplication.setWindowIcon(self.app_icon)
        if hasattr(self, 'tray_icon'):
            self.tray_icon.setIcon(self.app_icon)

    def init_tray(self):
        """初始化系统托盘图标与右键菜单"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.app_icon)
        self.tray_icon.setToolTip("reader")

        # 托盘菜单 显示隐藏 一键居中 彻底退出
        self.tray_menu = QMenu()
        action_toggle = self.tray_menu.addAction("显示 / 隐藏")
        action_toggle.triggered.connect(self.toggle_visibility)
        action_center = self.tray_menu.addAction("一键居中")
        action_center.triggered.connect(self.center_window)
        self.tray_menu.addSeparator()
        action_quit = self.tray_menu.addAction("彻底退出")
        action_quit.triggered.connect(self.force_quit)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.tray_activated)
        self.tray_icon.show()

    def tray_activated(self, reason):
        """托盘图标被单击时切换窗口显示隐藏"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_visibility()

    def center_window(self):
        """把窗口移动到当前屏幕中央 多屏或分辨率变动后找回窗口"""
        # 若窗口被隐藏 先恢复显示
        if self.is_hidden:
            self.toggle_visibility()

        # 优先使用窗口当前所在屏幕 否则用主屏
        screen = None
        if self.windowHandle():
            screen = self.windowHandle().screen()
        if screen is None:
            screen = QApplication.primaryScreen()
        geo = screen.availableGeometry()

        # 移动到屏幕中央并置前 保存位置
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + (geo.height() - self.height()) // 2
        self.move(x, y)
        self.raise_()
        self.save_current_config()

    # ---------------------------------------------------------------------------
    # 样式与文本显示参数
    # ---------------------------------------------------------------------------

    def apply_styles(self):
        """根据当前设置应用字体 颜色与背景样式"""
        weight = WEIGHT_MAP.get(self.font_weight_name, QFont.Weight.Normal)
        font = QFont(self.font_family, self.font_size, weight)

        # 设置抗锯齿策略与字间距
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.NoSubpixelAntialias)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, self.letter_spacing)

        self.label.setFont(font)
        # 根据悬停状态计算实际文字不透明度
        tc_alpha = self._effective_text_alpha()
        self.label.set_display_options(self._line_height(), self.text_color, tc_alpha)

        # 全透明分层窗口在 Windows 上会变成鼠标穿透
        # 保留一个极小的透明度下限 保证整个矩形仍可交互
        bg_alpha = max(1 / 255, self.bg_opacity / 100.0)
        self.central_widget.setStyleSheet(
            f"background-color: rgba({self.bg_color.red()}, {self.bg_color.green()}, {self.bg_color.blue()}, {bg_alpha:.3f}); border: none;")

    def _line_height(self):
        """按行间距百分比计算当前实际行高"""
        metrics = QFontMetrics(self.label.font())
        return max(1, round(metrics.lineSpacing() * self.line_spacing / 100))

    def _effective_text_alpha(self):
        """根据悬停显示设置计算实际文字不透明度"""
        if self.hover_show_text and not self._mouse_in_window:
            return 0.0
        return self.text_opacity / 100.0

    # ---------------------------------------------------------------------------
    # 悬停显示
    # ---------------------------------------------------------------------------

    def _init_hover_timer(self):
        """初始化鼠标悬停检测定时器"""
        self._hover_check_timer = QTimer(self)
        self._hover_check_timer.setInterval(200)
        self._hover_check_timer.timeout.connect(self._check_mouse_hover)
        self._hover_check_timer.start()

    def _check_mouse_hover(self):
        """定时检查鼠标是否在窗口内 状态变化时刷新文字可见性"""
        if not self.hover_show_text or self.is_hidden:
            return
        local_mouse_pos = self.mapFromGlobal(self.cursor().pos())
        was_in = self._mouse_in_window
        self._mouse_in_window = self.rect().contains(local_mouse_pos)
        if was_in != self._mouse_in_window:
            self._update_text_visibility()

    def _update_text_visibility(self):
        """根据鼠标位置刷新文字可见性"""
        if not self.hover_show_text:
            return
        tc_alpha = self._effective_text_alpha()
        self.label.set_display_options(self._line_height(), self.text_color, tc_alpha)

    # ---------------------------------------------------------------------------
    # 浮窗提示
    # ---------------------------------------------------------------------------

    def _init_toast(self):
        """初始化半透明浮窗提示 不影响正文阅读"""
        self._toast = QLabel(self)
        self._toast.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._toast.setWordWrap(False)
        self._toast.setStyleSheet(toast_style_css())
        self._toast.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._toast.hide()

        # 定时器到时自动隐藏浮窗
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._toast.hide)

    def _flash_message(self, msg, duration_ms=1500):
        """在窗口中央显示单行浮窗提示 超长省略 到时自动隐藏"""
        # 计算可用宽度并对过长文本做省略
        max_w = max(60, self.width() - 8)
        fm = self._toast.fontMetrics()
        if fm.horizontalAdvance(msg) > max_w:
            msg = fm.elidedText(msg, Qt.TextElideMode.ElideRight, max_w)

        # 设置文本并居中显示
        self._toast.setText(msg)
        self._toast.adjustSize()
        self._toast.move(max(0, (self.width() - self._toast.width()) // 2),
                         max(0, (self.height() - self._toast.height()) // 2))
        self._toast.raise_()
        self._toast.show()
        self._toast_timer.start(duration_ms)

    # ---------------------------------------------------------------------------
    # 文本排版与翻页计算
    # ---------------------------------------------------------------------------

    def _available_text_area(self):
        """返回当前窗口内文本可用的宽度与高度"""
        width = max(10, self.width() - _TEXT_H_MARGIN)
        height = max(10, self.height() - _TEXT_V_MARGIN)
        return width, height

    def _fit_character_count(self, text, max_w, max_h):
        """计算指定文本在给定区域能容纳的字符数"""
        metrics = QFontMetrics(self.label.font())
        max_lines = max(1, max_h // self._line_height())
        return layout_text(text, metrics, max_w, max_lines)[0]

    def _fit_count_from_end(self, text, max_w, max_h):
        """用二分查找计算文本末尾能完整容纳的字符数"""
        low, high = 0, len(text)
        fit_count = 0
        while low <= high:
            mid = (low + high) // 2
            part = text[-mid:] if mid > 0 else ""
            if self._fit_character_count(part, max_w, max_h) >= len(part):
                fit_count = mid
                low = mid + 1
            else:
                high = mid - 1
        # 至少容纳一个字符 避免翻页卡住
        if fit_count == 0 and len(text) > 0:
            fit_count = 1
        return fit_count

    def update_text(self):
        """根据当前阅读位置截取并显示当前页文本"""
        if not self.full_article_text:
            return

        # 取当前阅读位置之后的剩余文本
        remaining_text = self.full_article_text[self.char_index:]

        # 剩余文本为空 无缝阅读则跳到下一章 否则清空显示
        if not remaining_text.strip():
            # 先清零当前页状态，再切换章节。切换是同步完成的，
            # 不能在 start_async_load 返回后覆盖新章节计算出的 fit_count。
            self.current_fit_count = 0
            if self.next_chapter_url:
                self._go_next_chapter()
            else:
                self.label.setText("")
            return

        # 计算能容纳的字符数并截取显示
        max_w, max_h = self._available_text_area()
        fit_count = self._fit_character_count(remaining_text, max_w, max_h)
        if fit_count == 0 and len(remaining_text) > 0:
            fit_count = 1
        self.current_fit_count = fit_count
        self.label.setText(remaining_text[:fit_count])

    def refresh_text_line_breaks(self):
        """根据保留换行设置重新处理已加载文本"""
        if not getattr(self, '_raw_chapter_text', ''):
            return
        if self.keep_paragraph_breaks:
            self.full_article_text = self._prepare_multiline_text(self._raw_chapter_text)
        else:
            self.full_article_text = re.sub(r'\n', ' ', self._raw_chapter_text)
        self.update_text()

    def _prepare_multiline_text(self, text):
        """保留原文空白并为无缩进的正文段落补两个全角空格"""
        lines = text.split('\n')
        for index, line in enumerate(lines):
            # 空行或首行的标题行不处理
            if not line or (index == 0 and line.startswith('【') and '】' in line):
                continue
            # 无任何缩进的行补两个全角空格
            if line[0] not in ' \t\u3000':
                lines[index] = '\u3000\u3000' + line
        return '\n'.join(lines)

    # ---------------------------------------------------------------------------
    # 书籍加载
    # ---------------------------------------------------------------------------

    def start_async_load(self, url):
        """加载入口 仅接受本地文件地址"""
        if urlparse(url).scheme not in ('file', 'localbook'):
            self.label.setText("【仅支持本地 txt、epub 和 mobi 文件】")
            return
        self.start_local_load(url)

    def start_local_load(self, url):
        """按地址加载本地书籍 必要时先解析章节缓存"""
        path = local_path_from_url(url)
        if not os.path.exists(path):
            self.label.setText("【本地文件不存在，可能已被移动或删除】")
            return

        try:
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            target_url = url

            # 缓存缺失时预加载整本书 未指定章节则定位到第一章
            if target_url not in self.chapter_cache:
                first_url, toc_url = self.prepare_local_book(path)
                if 'chapter' not in query:
                    target_url = first_url

            self.current_url = target_url
            self.on_load_finished(*self.chapter_cache[target_url])
        except Exception as e:
            self._chapter_transitioning = False
            self.label.setText(f"【打开文件失败: {e}】")

    def prepare_local_book(self, path):
        """预加载本地文件章节 返回第一章地址与目录地址"""
        path = os.path.abspath(path)
        ext = os.path.splitext(path)[1].lower()
        if ext == '.txt':
            chapters = split_txt_chapters(path)
        elif ext == '.epub':
            chapters = parse_epub_chapters(path)
        elif ext == '.mobi':
            chapters = parse_mobi_chapters(path)
        else:
            raise ValueError("仅支持 txt、epub 和 mobi 文件")

        # 生成目录地址与每个章节的地址
        toc_url = make_local_file_url(path, toc=True)
        toc_entries = []
        urls = [make_local_file_url(path, idx) for idx in range(len(chapters))]
        for idx, chapter in enumerate(chapters):
            u = urls[idx]
            prev_url = urls[idx - 1] if idx > 0 else ""
            next_url = urls[idx + 1] if idx + 1 < len(urls) else ""
            title = chapter.get("title") or f"第{idx + 1}章"
            text = chapter.get("text", "")
            # 缓存章节内容与其前后章与目录地址
            self.chapter_cache[u] = (text, prev_url, next_url, title, u, toc_url)
            toc_entries.append((title, u))
        self.toc_cache[toc_url] = toc_entries

        first_url = urls[0] if urls else ""
        if not first_url:
            raise ValueError("未能从文件中识别到正文")
        return first_url, toc_url

    def get_cached_toc(self, toc_url):
        """返回目录地址对应的章节条目列表"""
        return self.toc_cache.get(toc_url)

    def on_load_finished(self, text, prev_url, next_url, title_text, original_url, toc_url):
        """章节内容加载完成 更新文本与阅读位置"""
        # 已切换目标则忽略过期结果
        if original_url != self.current_url:
            return

        # 根据保留换行设置处理章节文本
        self._raw_chapter_text = f"【{title_text}】\n{text}"
        if self.keep_paragraph_breaks:
            self.full_article_text = self._prepare_multiline_text(self._raw_chapter_text)
        else:
            self.full_article_text = re.sub(r'\n', ' ', self._raw_chapter_text)
        self.prev_chapter_url = prev_url
        self.next_chapter_url = next_url
        if toc_url:
            self.current_toc_url = toc_url
        self.current_title = title_text

        # 按不同场景决定阅读起始位置
        if hasattr(self, '_refresh_char_index'):
            # 重新加载 尽量回到刷新前的位置
            self.char_index = min(self._refresh_char_index, len(self.full_article_text))
            del self._refresh_char_index
        elif self._force_reset_index:
            # 显式要求回到本章开头
            self.char_index = 0
            self._force_reset_index = False
        elif self._jump_to_end_after_load:
            # 无缝阅读向上翻页 跳到上一章末尾
            self._jump_to_end_after_load = False
            max_w, max_h = self._available_text_area()
            fit_count = self._fit_count_from_end(self.full_article_text, max_w, max_h)
            self.char_index = max(0, len(self.full_article_text) - fit_count)
        else:
            # 默认从历史记录恢复进度 否则从开头
            self.char_index = 0
            for item in self.file_history:
                if local_path_from_url(item.get("url", "")) == local_path_from_url(original_url):
                    self.char_index = item.get("char_index", 0)
                    break

        # 更新文件历史 去重后插到最前 不限制书籍数量
        book_path = local_path_from_url(original_url)
        book_title = os.path.splitext(os.path.basename(book_path))[0] or title_text
        new_entry = {"title": book_title, "url": original_url, "char_index": self.char_index}
        self.file_history = [
            item for item in self.file_history
            if local_path_from_url(item.get("url", "")) != book_path
        ]
        self.file_history.insert(0, new_entry)
        self.save_current_config()
        self.update_text()
        self._chapter_transitioning = False

    def refresh_current_page(self):
        """重新加载当前章节 并尽量保持阅读位置"""
        if not self.current_url:
            QMessageBox.information(self, "提示", "当前没有可刷新的内容")
            return

        # 清除当前书籍的缓存 避免章节增删或目录变化时仍用旧数据
        current_url = self.current_url
        current_index = self.char_index
        book_path = local_path_from_url(current_url)
        self.chapter_cache = {
            url: value for url, value in self.chapter_cache.items()
            if local_path_from_url(url) != book_path
        }
        self.toc_cache = {
            url: value for url, value in self.toc_cache.items()
            if local_path_from_url(url) != book_path
        }
        # 记录刷新前位置 重新加载后恢复
        self._refresh_char_index = current_index
        self._force_reset_index = False
        self.start_async_load(self.current_url)

    # ---------------------------------------------------------------------------
    # 翻页控制
    # ---------------------------------------------------------------------------

    def prev_line(self):
        """向上翻一句 回到上一屏 已到开头则切上一章"""
        if self.char_index > 0:
            # 二分查找当前位置之前能容纳的字符数
            text_before = self.full_article_text[:self.char_index]
            max_w, max_h = self._available_text_area()
            back_fit_count = self._fit_count_from_end(text_before, max_w, max_h)
            self.char_index = max(0, self.char_index - back_fit_count)
            self.update_text()
            self.save_reading_progress()
        else:
            # 已在开头 自动跳到上一章末尾
            if self.prev_chapter_url:
                self._jump_to_end_after_load = True
                self.start_async_load(self.prev_chapter_url)

    def next_line(self):
        """向下翻一句 显示下一屏"""
        if self.current_fit_count == 0:
            # 当前无内容 自动切到下一章
            if self.next_chapter_url:
                self._go_next_chapter()
            return

        if self.char_index < len(self.full_article_text):
            old_url = self.current_url
            self.char_index += self.current_fit_count
            self.update_text()
            if self.current_url != old_url:
                return
            self.save_reading_progress()

    def _go_next_chapter(self):
        """在当前章节读完后切换到下一章"""
        if self._chapter_transitioning:
            return
        if self.next_chapter_url:
            self._chapter_transitioning = True
            self._force_reset_index = True
            self.start_async_load(self.next_chapter_url)
        else:
            self.label.setText("【未找到下一章，可能已是最新章】")

    def toggle_auto_page(self):
        """切换自动翻页的开启与关闭"""
        if self._auto_page_active:
            self._auto_page_timer.stop()
            self._auto_page_active = False
            self._flash_message("【自动翻页已关闭】")
        else:
            self._auto_page_timer.setInterval(int(self.auto_page_interval * 1000))
            self._auto_page_timer.start()
            self._auto_page_active = True
            self._flash_message(f"【自动翻页已开启：{self.auto_page_interval:.1f}秒/次】")

    def _adjust_auto_interval(self, delta):
        """按步长调整自动翻页间隔 并保存配置"""
        self.auto_page_interval = min(60, max(1, round(self.auto_page_interval + delta, 1)))
        if self._auto_page_active:
            self._auto_page_timer.setInterval(int(self.auto_page_interval * 1000))
        self._flash_message(f"【自动翻页速度：{self.auto_page_interval:.1f}秒/次】")
        self.save_current_config()

    def auto_speed_up(self):
        """缩短翻页间隔 加快自动翻页"""
        self._adjust_auto_interval(-0.2)

    def auto_speed_down(self):
        """增加翻页间隔 减慢自动翻页"""
        self._adjust_auto_interval(0.2)

    # ---------------------------------------------------------------------------
    # 鼠标交互 拖动与缩放
    # ---------------------------------------------------------------------------

    def _resize_edge_at(self, pos):
        """根据鼠标位置判断当前在窗口哪条缩放边缘"""
        m, rect = self.resize_margin, self.rect()
        ol, or_, ot, ob = pos.x() <= m, pos.x() >= rect.width() - m, pos.y() <= m, pos.y() >= rect.height() - m
        if ol and ot:
            return "top_left"
        if or_ and ot:
            return "top_right"
        if ol and ob:
            return "bottom_left"
        if or_ and ob:
            return "bottom_right"
        if ol:
            return "left"
        if or_:
            return "right"
        if ot:
            return "top"
        if ob:
            return "bottom"
        return ""

    def _update_cursor(self, pos):
        """根据缩放边缘更新鼠标形状"""
        edge = self._resize_edge_at(pos)
        shape = Qt.CursorShape.ArrowCursor
        if edge in ("left", "right"):
            shape = Qt.CursorShape.SizeHorCursor
        elif edge in ("top", "bottom"):
            shape = Qt.CursorShape.SizeVerCursor
        elif edge in ("top_left", "bottom_right"):
            shape = Qt.CursorShape.SizeFDiagCursor
        elif edge in ("top_right", "bottom_left"):
            shape = Qt.CursorShape.SizeBDiagCursor
        self.setCursor(shape)
        self.central_widget.setCursor(shape)

    def _resize_from_mouse(self, global_pos):
        """根据鼠标位移调整窗口几何尺寸"""
        if not self.resize_edge or not self.resize_start_pos or not self.resize_start_geometry:
            return
        delta = global_pos - self.resize_start_pos
        geo = QRect(self.resize_start_geometry)
        mw, mh = self.minimumWidth(), self.minimumHeight()
        # 各边缘按位移调整 并受最小尺寸约束
        if "left" in self.resize_edge:
            new_left = geo.left() + delta.x()
            if geo.right() - new_left + 1 >= mw:
                geo.setLeft(new_left)
        if "right" in self.resize_edge:
            geo.setRight(max(geo.left() + mw - 1, geo.right() + delta.x()))
        if "top" in self.resize_edge:
            new_top = geo.top() + delta.y()
            if geo.bottom() - new_top + 1 >= mh:
                geo.setTop(new_top)
        if "bottom" in self.resize_edge:
            geo.setBottom(max(geo.top() + mh - 1, geo.bottom() + delta.y()))
        self.setGeometry(geo)

    def _handle_mouse_move(self, pos, global_pos, buttons):
        """处理鼠标移动 缩放或拖动窗口或更新光标"""
        # 正在缩放边缘且按住左键时调整尺寸
        if self.resize_edge and buttons == Qt.MouseButton.LeftButton:
            self._resize_from_mouse(global_pos)
            return True
        # 按住左键拖动窗口
        if buttons == Qt.MouseButton.LeftButton and self.dragPos:
            self.move(self.pos() + global_pos - self.dragPos)
            self.dragPos = global_pos
            return True
        self._update_cursor(pos)
        return False

    def _handle_mouse_press(self, pos, global_pos):
        """处理鼠标按下 记录缩放边缘或拖动起点"""
        self.resize_edge = self._resize_edge_at(pos)
        if self.resize_edge:
            self.resize_start_pos = global_pos
            self.resize_start_geometry = self.geometry()
        else:
            self.dragPos = global_pos

    def _handle_mouse_release(self, pos):
        """处理鼠标释放 清空拖动与缩放状态"""
        self.dragPos, self.resize_edge = None, ""
        self.resize_start_pos, self.resize_start_geometry = None, None
        self._update_cursor(pos)

    def eventFilter(self, watched, event):
        """拦截中央控件的鼠标事件 转给拖动缩放处理逻辑"""
        if watched is self.central_widget and isinstance(event, QMouseEvent):
            pos = self.mapFromGlobal(event.globalPosition().toPoint())
            if event.type() == QEvent.Type.MouseMove:
                self._handle_mouse_move(pos, event.globalPosition().toPoint(), event.buttons())
                return True
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._handle_mouse_press(pos, event.globalPosition().toPoint())
                return True
            if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                self._handle_mouse_release(pos)
                return True
        return super().eventFilter(watched, event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """转发窗口鼠标移动事件"""
        if self._handle_mouse_move(
                event.position().toPoint(), event.globalPosition().toPoint(), event.buttons()):
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        """转发窗口鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._handle_mouse_press(event.position().toPoint(), event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """转发窗口鼠标释放事件"""
        self._handle_mouse_release(event.position().toPoint())
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        """滚轮翻页 向上回一句 向下进一句"""
        if not self.mouse_wheel_page:
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y() or event.pixelDelta().y()
        if delta > 0:
            self.prev_line()
            event.accept()
        elif delta < 0:
            self.next_line()
            event.accept()
        else:
            super().wheelEvent(event)

    def leaveEvent(self, event):
        """鼠标离开窗口时恢复普通光标"""
        if not self.resize_edge:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)

    # ---------------------------------------------------------------------------
    # 窗口事件 退出与配置保存
    # ---------------------------------------------------------------------------

    def resizeEvent(self, event):
        """窗口尺寸变化时保存配置并刷新文本显示"""
        self.config["width"], self.config["height"] = self.width(), self.height()
        self._geometry_save_timer.start()
        self.update_text()
        super().resizeEvent(event)

    def moveEvent(self, event):
        """窗口移动时更新坐标并延迟保存配置"""
        self.window_x, self.window_y = self.x(), self.y()
        self.config["window_x"], self.config["window_y"] = self.window_x, self.window_y
        self._geometry_save_timer.start()
        super().moveEvent(event)

    def force_quit(self):
        """彻底退出程序 停止定时器与热键 保存配置"""
        # 停止悬停检测定时器 避免退出时报 QSocketNotifier 错误
        if self._hover_check_timer:
            self._hover_check_timer.stop()
        # 停止自动翻页定时器
        if hasattr(self, '_auto_page_timer') and self._auto_page_timer:
            self._auto_page_timer.stop()
        self._geometry_save_timer.stop()
        self.save_current_config()

        # 注销全局热键
        for manager in (self._win_hotkey_manager, self._win_quit_hotkey_manager):
            if manager:
                try:
                    manager.unregister()
                except Exception:
                    pass

        # 隐藏托盘图标并退出事件循环
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
        QApplication.instance().quit()

    def closeEvent(self, event):
        """关闭窗口时执行彻底退出"""
        self.force_quit()
        event.accept()

    def save_current_config(self):
        """收集所有设置并保存到配置文件"""
        # 通用设置直接读取实例属性 特殊键跳过
        for name in CONFIG_DEFAULTS:
            if name in _CONFIG_SPECIAL_KEYS:
                continue
            if hasattr(self, name) and not callable(getattr(self, name)):
                self.config[name] = getattr(self, name)

        # 窗口几何与颜色单独转换后保存
        self.config["width"] = self.width()
        self.config["height"] = self.height()
        self.config["window_x"] = self.x()
        self.config["window_y"] = self.y()
        self.config["text_color"] = self.text_color.name()
        self.config["bg_color"] = self.bg_color.name()
        save_config(self.config)

    def _save_geometry_config(self):
        """仅保存窗口几何信息 供延迟定时器调用"""
        self.config["width"], self.config["height"] = self.width(), self.height()
        self.config["window_x"], self.config["window_y"] = self.x(), self.y()
        save_config(self.config)

    def save_reading_progress(self):
        """把当前阅读位置写回文件历史并置顶"""
        book_path = local_path_from_url(self.current_url)
        if not book_path:
            return
        # 找到对应书籍的历史条目 更新并移动到最前
        for item in self.file_history:
            if local_path_from_url(item.get('url', '')) == book_path:
                item['url'] = self.current_url
                item['char_index'] = self.char_index
                item['title'] = os.path.splitext(os.path.basename(book_path))[0] or self.current_title
                self.file_history.remove(item)
                self.file_history.insert(0, item)
                self.save_current_config()
                return

    # ---------------------------------------------------------------------------
    # 快捷键与全局热键
    # ---------------------------------------------------------------------------

    def init_shortcuts(self):
        """初始化所有快捷键 全局热键与自动翻页定时器"""
        # 绑定可自定义快捷键
        for key_name, (shortcut_name, handler_name) in SHORTCUT_BINDINGS.items():
            shortcut = QShortcut(QKeySequence(getattr(self, key_name)), self)
            shortcut.activated.connect(getattr(self, handler_name))
            setattr(self, shortcut_name, shortcut)

        # 老板键与退出键使用应用级快捷键
        self.sc_boss = QShortcut(QKeySequence(self.key_boss), self)
        self.sc_boss.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.sc_boss.activated.connect(self.toggle_visibility)

        self.sc_quit = QShortcut(QKeySequence(self.key_quit), self)
        self.sc_quit.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.sc_quit.activated.connect(self.force_quit)

        # 创建原生全局热键管理器
        if WinHotkeyManager:
            self._win_hotkey_manager = WinHotkeyManager()
            self._win_hotkey_manager.triggered.connect(self.toggle_visibility)
            self._win_quit_hotkey_manager = WinHotkeyManager()
            self._win_quit_hotkey_manager.triggered.connect(self.force_quit)

        self.register_global_boss_key(self.key_boss)
        self.register_global_quit_key(self.key_quit)

        # 方向键默认快捷键
        # 上一页/下一页
        QShortcut(QKeySequence(Qt.Key.Key_Left), self).activated.connect(self.prev_line)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self).activated.connect(self.next_line)

        # 隐藏与关闭窗口
        QShortcut(QKeySequence(Qt.Key.Key_Up), self).activated.connect(self.force_quit)
        QShortcut(QKeySequence(Qt.Key.Key_Down), self).activated.connect(self.toggle_visibility)

        # 自动翻页定时器
        self._auto_page_timer = QTimer(self)
        self._auto_page_timer.timeout.connect(self.next_line)
        self._auto_page_active = False

    def _register_global_hotkey(self, manager, hotkey_str):
        """尝试用原生热键管理器注册 返回是否成功"""
        success = False
        if manager:
            try:
                success = manager.register(hotkey_str)
            except Exception as error:
                print(f"Windows 全局热键注册失败: {error}")
        return success

    def register_global_boss_key(self, hotkey_str):
        """注册老板键 原生热键成功时禁用应用级快捷键避免重复"""
        success = self._register_global_hotkey(self._win_hotkey_manager, hotkey_str)
        if hasattr(self, 'sc_boss'):
            self.sc_boss.setEnabled(not success)

    def register_global_quit_key(self, hotkey_str):
        """注册退出键 原生热键成功时禁用应用级快捷键避免重复"""
        success = self._register_global_hotkey(self._win_quit_hotkey_manager, hotkey_str)
        if hasattr(self, 'sc_quit'):
            self.sc_quit.setEnabled(not success)

    def update_custom_shortcuts(self):
        """设置变化后刷新所有自定义快捷键"""
        for key_name, (shortcut_name, _) in SHORTCUT_BINDINGS.items():
            getattr(self, shortcut_name).setKey(QKeySequence(getattr(self, key_name)))
        self.sc_boss.setKey(QKeySequence(self.key_boss))
        self.sc_quit.setKey(QKeySequence(self.key_quit))

    # ---------------------------------------------------------------------------
    # 背景与文字不透明度调整
    # ---------------------------------------------------------------------------

    def _adjust_bg_opacity(self, delta):
        """按步长调整背景不透明度并保存"""
        self.bg_opacity = min(100, max(0, self.bg_opacity + delta))
        self.apply_styles()
        self.save_current_config()

    def increase_bg_opacity(self):
        """增加背景不透明度"""
        self._adjust_bg_opacity(10)

    def decrease_bg_opacity(self):
        """降低背景不透明度"""
        self._adjust_bg_opacity(-10)

    def _adjust_text_opacity(self, delta):
        """按步长调整文字不透明度并保存"""
        self.text_opacity = min(100, max(0, self.text_opacity + delta))
        self.apply_styles()
        self.save_current_config()

    def increase_text_opacity(self):
        """增加文字不透明度"""
        self._adjust_text_opacity(5)

    def decrease_text_opacity(self):
        """降低文字不透明度"""
        self._adjust_text_opacity(-5)

    # ---------------------------------------------------------------------------
    # 窗口显示隐藏与菜单
    # ---------------------------------------------------------------------------

    def toggle_visibility(self):
        """切换窗口显示与隐藏 带防抖避免快速连击"""
        now = time.time()
        if hasattr(self, '_last_toggle_time') and now - self._last_toggle_time < 0.3:
            return
        self._last_toggle_time = now

        if self.is_hidden:
            # 恢复显示之前隐藏的所有顶层窗口
            self.is_hidden = False
            widgets, self._hidden_widgets = self._hidden_widgets, []
            for widget in widgets:
                try:
                    widget.show()
                except RuntimeError:
                    pass
            if self in widgets:
                self.raise_()
                self.activateWindow()
        else:
            # 记录当前可见的顶层窗口并全部隐藏
            self._hidden_widgets = [
                widget for widget in QApplication.topLevelWidgets()
                if widget.isVisible()
            ]
            for widget in self._hidden_widgets:
                widget.hide()
            self.is_hidden = True

    def contextMenuEvent(self, event):
        """弹出右键菜单"""
        menu = QMenu(self)
        menu.setStyleSheet(menu_style_css())

        # 打开文件
        menu.addAction("我的书库", self.open_file_dialog)

        # 章节目录 无目录时禁用
        action_toc = menu.addAction("章节目录")
        if self.current_toc_url:
            action_toc.triggered.connect(self.open_toc_dialog)
        else:
            action_toc.setEnabled(False)

        # 重新加载 无内容时禁用
        action_refresh = menu.addAction("重新加载")
        if self.current_url:
            action_refresh.triggered.connect(self.refresh_current_page)
        else:
            action_refresh.setEnabled(False)

        menu.addAction("应用设置", self.open_settings)
        menu.addSeparator()

        menu.addAction("退出程序", self.force_quit)
        menu.exec(event.globalPos())

    # ---------------------------------------------------------------------------
    # 对话框入口
    # ---------------------------------------------------------------------------

    def open_file_dialog(self):
        """打开我的书库"""
        FileDialog(self).exec()

    def open_settings(self):
        """打开偏好设置弹窗"""
        SettingsDialog(self).exec()

    def open_toc_dialog(self):
        """打开目录弹窗"""
        if self.current_toc_url:
            TocDialog(self, self.current_toc_url).exec()


# ---------------------------------------------------------------------------
# 程序入口
# ---------------------------------------------------------------------------

def main():
    """程序入口 完成单实例锁 界面初始化与事件循环"""
    # 单实例锁 若已有实例在运行则通知其显示窗口后退出
    socket_name = 'ReaderSingleInstance'
    local_socket = QLocalSocket()
    local_socket.connectToServer(socket_name)
    if local_socket.waitForConnected(500):
        local_socket.write(b'show')
        local_socket.waitForBytesWritten(500)
        local_socket.disconnectFromServer()
        sys.exit(0)
    del local_socket

    # 创建本地服务器 监听后续实例的连接请求
    local_server = QLocalServer()
    local_server.removeServer(socket_name)
    local_server.listen(socket_name)

    # 创建应用并设置基础信息
    app = QApplication(sys.argv)
    app.setApplicationName("reader")
    app.setApplicationDisplayName("reader")
    app.setQuitOnLastWindowClosed(False)

    # 尽早设置应用图标
    icon_base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    icon_file = os.path.join(icon_base, 'logo.png')
    if os.path.exists(icon_file):
        app.setWindowIcon(QIcon(icon_file))

    # 加载中文翻译
    translator = QTranslator()
    if translator.load("qtbase_zh_CN", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)

    # 创建并显示主窗口
    window = ReaderWindow()
    window.show()

    def _on_new_connection():
        """处理其他实例的连接请求 恢复显示所有窗口"""
        client = local_server.nextPendingConnection()
        if client:
            client.waitForReadyRead(500)
            client.disconnectFromServer()

        # 若窗口被隐藏则恢复显示 否则确保所有顶层窗口可见
        if window.is_hidden:
            window._last_toggle_time = 0
            window.toggle_visibility()
        else:
            for w in QApplication.topLevelWidgets():
                w.show()
        window.activateWindow()
        window.raise_()

    local_server.newConnection.connect(_on_new_connection)

    # 将控制台 Ctrl+C/IDE 停止转换为 Qt 正常退出，避免中断落在定时器回调中
    def _handle_sigint(signum, frame):
        app.quit()

    signal.signal(signal.SIGINT, _handle_sigint)

    # 进入事件循环。控制台中按 Ctrl+C 时，先停止定时器并静默退出，
    # 避免 KeyboardInterrupt 被显示为定时器回调异常。
    try:
        exit_code = app.exec()
    except KeyboardInterrupt:
        window.force_quit()
        return
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
