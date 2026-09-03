# -*- coding: utf-8 -*-
"""
utils 模块
存放配置读写 文本文件解析 基础对话框与微调控件等通用工具
界面样式相关的代码已迁移到 styles 模块统一管理
"""

import sys
import os
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from urllib.parse import urlparse, quote, unquote, parse_qs

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QFont, QColor, QPainter, QPen
from PySide6.QtWidgets import QDialog, QSpinBox, QDoubleSpinBox, QComboBox, QFontComboBox


# ---------------------------------------------------------------------------
# 配置默认值与路径
# ---------------------------------------------------------------------------

CONFIG_DEFAULTS = {
    "file_history": [], "width": None, "height": None,
    "bg_opacity": 0, "text_opacity": 80,
    "show_taskbar": False, "hover_show_text": False, "mouse_wheel_page": True,
    "keep_paragraph_breaks": True, "letter_spacing": 0, "line_spacing": 100,
    "font_size": 10, "font_family": "Microsoft YaHei UI",
    "font_weight_name": "中等 (Medium)", "text_color": "#000000", "bg_color": "#fcfbfb",
    "key_prev_line": "X", "key_next_line": "Z", "key_boss": "Alt+Z", "key_quit": "Alt+X",
    "key_bg_up": "Ctrl+Up", "key_bg_down": "Ctrl+Down",
    "key_text_up": "Ctrl+Right", "key_text_down": "Ctrl+Left",
    "key_toc": "C", "key_auto_toggle": "Ctrl+E",
    "key_auto_speed_up": "Ctrl+S", "key_auto_speed_down": "Ctrl+W",
    "auto_page_interval": 6.0, "icon_path": "", "window_x": None, "window_y": None,
    "always_on_top": True,
}


def get_data_dir():
    """返回配置数据目录 打包后取可执行文件目录 源码运行时取脚本目录"""
    if getattr(sys, 'frozen', False):
        data_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        data_dir = os.path.dirname(os.path.abspath(__file__))
    return data_dir


# 配置数据目录与配置文件路径
DATA_DIR = get_data_dir()
CONFIG_FILE = os.path.join(DATA_DIR, "reader_config.json")


# 字体粗细名称到 Qt 枚举的映射
WEIGHT_MAP = {
    "极细 (Thin)": QFont.Weight.Thin,
    "细体 (Light)": QFont.Weight.Light,
    "常规 (Normal)": QFont.Weight.Normal,
    "中等 (Medium)": QFont.Weight.Medium,
    "半粗 (DemiBold)": QFont.Weight.DemiBold,
    "加粗 (Bold)": QFont.Weight.Bold,
    "极粗 (Black)": QFont.Weight.Black
}


# ---------------------------------------------------------------------------
# 章节标题识别
# ---------------------------------------------------------------------------

# 匹配形如 第X章 楔子 番外 结局 等章节标题的正则
TITLE_CHAPTER_PATTERN = re.compile(
    r'(第\s*[0-9０-９零〇一二两三四五六七八九十百千万]+\s*[章节回折卷篇]\s*[^_\-|—–]*)'
    r'|(楔子|番外|大?结局|引子|序[章言]|终章|完本感言?|尾声)\s*[^_\-|—–]*',
    re.IGNORECASE
)


def clean_title_text(raw_title):
    """清理标题文本 优先提取章节标题部分 否则按分隔符回退处理"""
    # 先压缩空白并去首尾空格
    text = re.sub(r'\s+', ' ', raw_title).strip()
    # 能直接匹配到章节标题则返回匹配片段
    if match := TITLE_CHAPTER_PATTERN.search(text):
        return match.group(0).strip()

    # 无法直接匹配时按常见分隔符拆分 找含章节标题的一段
    fallback = raw_title
    for sep in ['|', '_', '—', '–', '-']:
        parts = [part.strip() for part in fallback.split(sep) if part.strip()]
        if chapter_part := next((part for part in parts if TITLE_CHAPTER_PATTERN.search(part)), ""):
            return TITLE_CHAPTER_PATTERN.search(chapter_part).group(0).strip()
        if parts:
            fallback = parts[0]
    return fallback.strip() or raw_title


# ---------------------------------------------------------------------------
# 本地文件地址与读取
# ---------------------------------------------------------------------------

def make_local_file_url(path, chapter_index=None, toc=False):
    """把本地文件路径转成程序自定义的 localbook 地址"""
    url = "localbook://reader?path=" + quote(os.path.abspath(path), safe='')
    if toc:
        return url + "&toc=1"
    if chapter_index is not None:
        return url + f"&chapter={chapter_index}"
    return url


def local_path_from_url(url):
    """从文件地址反解出本地路径 支持 localbook 与 file 两种协议"""
    parsed = urlparse(url)
    if parsed.scheme == 'localbook':
        return parse_qs(parsed.query).get('path', [''])[0]
    path = unquote(parsed.path)
    # Windows 下 file 协议的路径可能带前导斜杠 需要去掉
    if sys.platform.startswith('win') and re.match(r'^/[A-Za-z]:/', path):
        path = path[1:]
    return path


def read_text_file(path):
    """按常见中文编码依次尝试读取文本文件 最终用替换模式兜底"""
    with open(path, 'rb') as f:
        data = f.read()
    # 依次尝试带 BOM 的 utf8 普通 utf8 国标 大五码
    for encoding in ['utf-8-sig', 'utf-8', 'gb18030', 'big5']:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode('utf-8', errors='replace')


def normalize_plain_text(text):
    """统一换行符并去掉首尾换行 保留原文空格缩进与空行"""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    return text.strip('\n')


# ---------------------------------------------------------------------------
# 各格式章节解析
# ---------------------------------------------------------------------------

def split_txt_chapters(path):
    """把纯文本文件按章节标题行拆分成章节列表"""
    text = read_text_file(path).replace('\r\n', '\n').replace('\r', '\n')

    # 匹配单独占一行的章节标题
    chapter_line_pattern = re.compile(
        r'^[^\S\r\n]*((第\s*[0-9０-９零〇一二两三四五六七八九十百千万]+\s*[章节回折卷篇].*)|(楔子|番外|大?结局|引子|序[章言]|终章|完本感言?|尾声).*)[^\S\r\n]*$',
        re.IGNORECASE | re.MULTILINE
    )
    matches = list(chapter_line_pattern.finditer(text))

    # 没有识别到章节时整本作为一章
    if not matches:
        return [{"title": os.path.splitext(os.path.basename(path))[0], "text": normalize_plain_text(text)}]

    chapters = []

    # 第一个标题之前的内容作为引言章节
    intro = text[:matches[0].start()].strip('\r\n')
    if intro.strip():
        intro_title = os.path.splitext(os.path.basename(path))[0]
        if title_match := re.search(r'《([^》]+)》', intro):
            intro_title = title_match.group(1)
        chapters.append({"title": intro_title, "text": normalize_plain_text(intro)})

    # 每个标题到下一个标题之间的内容作为一章
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        title = re.sub(r'\s+', ' ', match.group(1)).strip()
        body = text[start:end].strip('\r\n')
        if body.strip():
            chapters.append({"title": title, "text": normalize_plain_text(body)})
    return chapters


def _xml_local_name(tag):
    """去掉 XML 标签的命名空间前缀 只返回本地名"""
    return tag.rsplit('}', 1)[-1]


def _epub_join(base_dir, href):
    """把 EPUB 内部的相对链接拼成 zip 内的规范化路径"""
    href = unquote(href.split('#', 1)[0])
    return os.path.normpath(os.path.join(base_dir, href)).replace('\\', '/')


def parse_epub_chapters(path):
    """解析 EPUB 文件 提取各章节标题与正文"""
    chapters = []
    with zipfile.ZipFile(path) as zf:
        # 读取 container.xml 找到主目录文件 opf
        container = ET.fromstring(zf.read('META-INF/container.xml'))
        rootfile = next((elem.get('full-path') for elem in container.iter()
                         if _xml_local_name(elem.tag) == 'rootfile' and elem.get('full-path')), None)
        if not rootfile:
            raise ValueError("未找到 EPUB 主目录文件")

        # 解析 manifest 保存每个资源的 href 类型与属性
        opf_dir = os.path.dirname(rootfile)
        opf = ET.fromstring(zf.read(rootfile))
        manifest = {}
        for elem in opf.iter():
            if _xml_local_name(elem.tag) == 'item' and elem.get('id') and elem.get('href'):
                manifest[elem.get('id')] = {
                    'href': elem.get('href'),
                    'media-type': elem.get('media-type', ''),
                    'properties': elem.get('properties', ''),
                }
        spine_ids = [elem.get('idref') for elem in opf.iter()
                     if _xml_local_name(elem.tag) == 'itemref' and elem.get('idref')]

        # 按阅读顺序遍历 spine 逐个解析正文页面
        for idref in spine_ids:
            item_info = manifest.get(idref)
            if not item_info:
                continue

            # 跳过图片 css js 等非页面资源
            media_type = item_info['media-type']
            if media_type and 'xhtml' not in media_type and 'html' not in media_type:
                continue

            # 跳过导航页与目录页
            props = item_info['properties']
            if 'nav' in props or 'toc' in props:
                continue

            item_path = _epub_join(opf_dir, item_info['href'])
            if item_path not in zf.namelist():
                continue

            # 解析 HTML 并清理脚本样式与导航节点
            soup = BeautifulSoup(zf.read(item_path), 'html.parser')
            for unwanted in soup.find_all(['script', 'style', 'nav']):
                unwanted.decompose()

            # 提取标题 优先标题标签 否则用文件名
            title_tag = soup.find(['h1', 'h2', 'h3']) or soup.find('title')
            raw_title = title_tag.get_text(" ", strip=True) if title_tag else os.path.splitext(os.path.basename(item_path))[0]
            title = clean_title_text(raw_title) if TITLE_CHAPTER_PATTERN.search(raw_title) else re.sub(r'\s+', ' ', raw_title).strip()

            # 跳过目录页与封面页
            title_lower = title.lower()
            if any(kw in title_lower for kw in ['目录', 'content', 'table of contents', 'toc', '封面', 'cover']):
                continue

            # 提取正文 先移除标题标签避免标题在正文中重复
            body_soup = soup.body or soup
            for t_tag in body_soup.find_all(['h1', 'h2', 'h3']):
                t_tag.decompose()

            if text := body_soup.get_text(separator='\n', strip=True):
                # 保留段落换行 压缩行内多余空白
                text = re.sub(r'[^\S\n]+', ' ', text)
                text = re.sub(r'\n{2,}', '\n', text).strip()
                # 跳过内容过少的页面 可能是空白页或版权页
                if len(text) < 20:
                    continue
                chapters.append({"title": title or f"第{len(chapters) + 1}章", "text": text})

    if not chapters:
        raise ValueError("未能从 EPUB 读取到正文")
    return chapters


def parse_mobi_chapters(path):
    """解析 MOBI 文件章节 借助 mobi 库转成 EPUB 或 HTML 后再解析"""
    import shutil
    try:
        import mobi
    except ImportError:
        raise ValueError("需要安装 mobi 库：pip install mobi")

    tempdir = None
    try:
        # 提取 MOBI 内容 得到转出的文件路径
        tempdir, extracted_path = mobi.extract(path)
        ext = os.path.splitext(extracted_path)[1].lower()

        if ext == '.epub':
            # MOBI8 格式 直接复用 EPUB 解析
            return parse_epub_chapters(extracted_path)
        elif ext in ('.html', '.htm'):
            # MOBI7 格式 解析单个 HTML 文件
            return _parse_mobi_html(extracted_path)
        else:
            raise ValueError(f"不支持的 MOBI 提取格式: {ext}")
    finally:
        # 无论成功失败都清理临时目录
        if tempdir and os.path.exists(tempdir):
            shutil.rmtree(tempdir, ignore_errors=True)


def _parse_mobi_html(html_path):
    """解析 MOBI7 提取出的单个 HTML 文件"""
    with open(html_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    soup = BeautifulSoup(content, 'html.parser')
    for unwanted in soup.find_all(['script', 'style', 'nav']):
        unwanted.decompose()

    # 匹配章节标题的正则
    chapter_pattern = re.compile(
        r'(第\s*[0-9０-９零〇一二两三四五六七八九十百千万]+\s*[章节回折卷篇].*)',
        re.IGNORECASE
    )

    # 收集所有可能是章节标题的元素
    chapter_headers = []
    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'b']):
        text = tag.get_text(strip=True)
        if chapter_pattern.match(text):
            chapter_headers.append(tag)

    # 能识别到多个标题时按标题拆分
    if chapter_headers:
        chapters = []
        for idx, header in enumerate(chapter_headers):
            title = re.sub(r'\s+', ' ', header.get_text(strip=True))
            # 收集当前标题到下一个标题之间的所有文本
            text_parts = []
            for sibling in header.next_siblings:
                if hasattr(sibling, 'name') and sibling in chapter_headers[idx + 1:idx + 2]:
                    break
                if hasattr(sibling, 'name') and sibling.name in ['h1', 'h2', 'h3', 'h4'] and sibling != header:
                    if chapter_pattern.match(sibling.get_text(strip=True)):
                        break
                if hasattr(sibling, 'get_text'):
                    text_parts.append(sibling.get_text(strip=True))
                elif isinstance(sibling, str):
                    text_parts.append(sibling.strip())

            text = re.sub(r'\s+', ' ', ' '.join(text_parts)).strip()
            if text and len(text) > 10:
                chapters.append({"title": title, "text": text})

        if chapters:
            return chapters

    # 无法按章节拆分时整本作为一章返回
    text = re.sub(r'\s+', ' ', soup.get_text(" ", strip=True)).strip()
    if not text:
        raise ValueError("未能从 MOBI 读取到正文")
    title = os.path.splitext(os.path.basename(html_path))[0]
    return [{"title": title, "text": text}]


# ---------------------------------------------------------------------------
# 配置读写
# ---------------------------------------------------------------------------

def load_config():
    """读取当前版本配置文件，缺失或损坏时使用默认值"""
    default_config = CONFIG_DEFAULTS.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            default_config.update(data)
        except Exception:
            # 配置文件损坏时静默回退到默认配置
            pass
    return default_config


def save_config(config):
    """原子方式保存配置 先写临时文件再替换 避免写入中断损坏配置"""
    temp_file = CONFIG_FILE + ".tmp"
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, CONFIG_FILE)
    except OSError as error:
        print(f"保存配置失败: {error}")
        # 保存失败时清理残留的临时文件
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# 基础对话框与微调控件
# ---------------------------------------------------------------------------

class RoundedDialog(QDialog):
    """无边框半透明对话框 自绘圆角面板

    使用 WA_TranslucentBackground 后 顶层窗口不会渲染样式表里的
    背景与圆角 因此在这里手动绘制圆角面板
    """

    def __init__(self, parent=None):
        """初始化透明窗口与默认圆角面板颜色"""
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._radius = 7
        self._bg_color = QColor(255, 255, 255, 248)
        self._border_color = QColor(228, 231, 235)
        self._drag_pos = None

    def set_rounded_style(self, radius=None, bg_color=None, border_color=None):
        """更新圆角面板的半径与配色 传入 None 表示保持不变"""
        if radius is not None:
            self._radius = radius
        if bg_color is not None:
            self._bg_color = QColor(bg_color)
        if border_color is not None:
            self._border_color = QColor(border_color)
        self.update()

    def paintEvent(self, event):
        """绘制带边框的圆角面板"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(self._border_color, 1))
        painter.setBrush(self._bg_color)
        painter.drawRoundedRect(rect, self._radius, self._radius)

    # 无边框窗口没有标题栏 这里实现按住背景拖动窗口
    def mousePressEvent(self, event):
        """记录拖动起点 准备移动窗口"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """按住左键时随鼠标移动窗口"""
        if self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """松开鼠标 结束拖动"""
        if self._drag_pos is not None:
            self._drag_pos = None
            event.accept()
            return
        super().mouseReleaseEvent(event)


class WheelGuardSpinBox(QSpinBox):
    """仅在获得焦点时才响应鼠标滚轮的整数输入框"""

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class WheelGuardDoubleSpinBox(QDoubleSpinBox):
    """仅在获得焦点时才响应鼠标滚轮的浮点输入框"""

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class WheelGuardComboBox(QComboBox):
    """仅在获得焦点时才响应鼠标滚轮的下拉框"""

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class WheelGuardFontComboBox(QFontComboBox):
    """仅在获得焦点时才响应鼠标滚轮的字体下拉框"""

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()
