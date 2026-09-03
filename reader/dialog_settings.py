# -*- coding: utf-8 -*-
"""
dialog_settings 模块
定义偏好设置对话框 SettingsDialog
集中管理阅读与窗口 文字外观 快捷键 其他四组设置项
"""

from PySide6.QtWidgets import (QVBoxLayout, QFormLayout, QCheckBox, QHBoxLayout, QGridLayout,
                               QComboBox, QLabel, QPushButton,
                               QKeySequenceEdit, QColorDialog, QFileDialog, QWidget, QScrollArea,
                               QAbstractSpinBox, QSizePolicy)
from PySide6.QtGui import QColor, QFont, QKeySequence
from PySide6.QtCore import Qt

from utils import (WEIGHT_MAP, RoundedDialog,
                   WheelGuardSpinBox, WheelGuardDoubleSpinBox,
                   WheelGuardComboBox, WheelGuardFontComboBox)
from styles import apply_dialog_style


# 普通设置项到控件与读取方法的映射
# 键为配置字段名 值为控件属性名与读取方法名
SETTING_CONTROLS = {
    "keep_paragraph_breaks": ("cb_keep_breaks", "isChecked"),
    "show_taskbar": ("cb_taskbar", "isChecked"),
    "always_on_top": ("cb_always_on_top", "isChecked"),
    "hover_show_text": ("cb_hover_show", "isChecked"),
    "mouse_wheel_page": ("cb_mouse_wheel_page", "isChecked"),
    "font_family": ("font_combo", "currentFont"),
    "font_size": ("size_spin", "value"),
    "font_weight_name": ("weight_combo", "currentText"),
    "text_opacity": ("text_opacity_spin", "value"),
    "bg_opacity": ("bg_opacity_spin", "value"),
    "letter_spacing": ("spin_letter", "value"),
    "line_spacing": ("spin_line", "value"),
}

# 快捷键配置字段到编辑控件属性名的映射
SHORTCUT_CONTROLS = {
    "key_prev_line": "ks_prev_line",
    "key_next_line": "ks_next_line",
    "key_boss": "ks_boss",
    "key_quit": "ks_quit",
    "key_bg_up": "ks_bg_up",
    "key_bg_down": "ks_bg_down",
    "key_text_up": "ks_text_up",
    "key_text_down": "ks_text_down",
    "key_toc": "ks_toc",
    "key_auto_toggle": "ks_auto_toggle",
    "key_auto_speed_up": "ks_auto_speed_up",
    "key_auto_speed_down": "ks_auto_speed_down",
}


class SettingsDialog(RoundedDialog):
    """偏好设置对话框 保存时把设置写回主窗口并立即生效"""

    def __init__(self, parent):
        """初始化对话框 保存主窗口引用与颜色临时值"""
        super().__init__(parent)
        self.setWindowTitle("偏好设置 - reader")
        self.resize(680, 660)
        self.setMinimumSize(600, 500)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        # 颜色修改先存临时值 点击保存后才写回主窗口
        self.parent = parent
        self.temp_text_color = parent.text_color
        self.temp_bg_color = parent.bg_color
        self.init_ui()

    def init_ui(self):
        """构建设置对话框的完整界面"""
        main_layout = QVBoxLayout(self)
        apply_dialog_style(self, main_layout)

        # 标题栏 左侧标题 右侧关闭按钮
        header = QHBoxLayout()
        title = QLabel("偏好设置")
        title.setObjectName("dialogTitle")
        header.addWidget(title)
        header.addStretch()
        close_button = QPushButton("×")
        close_button.setObjectName("closeButton")
        close_button.setToolTip("关闭")
        close_button.clicked.connect(self.reject)
        header.addWidget(close_button)
        main_layout.addLayout(header)

        # 表单容器 限制宽度让内容居中 不让表单撑满整个滚动区域
        form_container = QWidget()
        form_container.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        form_container.setMaximumWidth(560)
        form_layout = QFormLayout(form_container)
        form_layout.setHorizontalSpacing(10)
        form_layout.setVerticalSpacing(8)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        # 阅读与窗口组
        form_layout.addRow(self._section_title("阅读与窗口"))
        self.cb_taskbar = QCheckBox("在任务栏显示程序图标")
        self.cb_taskbar.setChecked(self.parent.show_taskbar)
        form_layout.addRow("任务栏:", self.cb_taskbar)

        self.cb_hover_show = QCheckBox("鼠标移到阅读框时才显示文字，移开后隐藏")
        self.cb_hover_show.setChecked(self.parent.hover_show_text)
        form_layout.addRow("悬停显示:", self.cb_hover_show)

        self.cb_mouse_wheel_page = QCheckBox("支持鼠标滚轮翻页")
        self.cb_mouse_wheel_page.setChecked(self.parent.mouse_wheel_page)
        form_layout.addRow("鼠标翻页:", self.cb_mouse_wheel_page)

        self.cb_keep_breaks = QCheckBox("保留原文换行、空行和缩进，无缩进段落自动缩进两格")
        self.cb_keep_breaks.setChecked(self.parent.keep_paragraph_breaks)
        form_layout.addRow("保留换行:", self.cb_keep_breaks)

        self.cb_always_on_top = QCheckBox("阅读窗口始终显示在最前")
        self.cb_always_on_top.setChecked(self.parent.always_on_top)
        form_layout.addRow("窗口置顶:", self.cb_always_on_top)

        # 文字与外观组
        form_layout.addRow(self._section_title("文字与外观"))

        self.font_combo = WheelGuardFontComboBox()
        self.font_combo.setCurrentFont(QFont(self.parent.font_family))

        self.size_spin = WheelGuardSpinBox()
        self.size_spin.setRange(8, 150)
        self.size_spin.setValue(self.parent.font_size)

        self.weight_combo = WheelGuardComboBox()
        self.weight_combo.addItems(list(WEIGHT_MAP.keys()))
        self.weight_combo.setCurrentText(self.parent.font_weight_name)

        self.spin_letter = WheelGuardSpinBox()
        self.spin_letter.setRange(0, 50)
        self.spin_letter.setValue(self.parent.letter_spacing)
        self.spin_letter.setToolTip("字间距像素")

        self.spin_line = WheelGuardSpinBox()
        self.spin_line.setRange(50, 300)
        self.spin_line.setSuffix(" %")
        self.spin_line.setValue(self.parent.line_spacing)
        self.spin_line.setToolTip("行间距")

        self.btn_text_color = QPushButton("修改文字颜色")
        self.btn_text_color.setObjectName("secondaryButton")
        self.btn_text_color.clicked.connect(self.choose_text_color)

        self.text_opacity_spin = WheelGuardSpinBox()
        self.text_opacity_spin.setRange(0, 100)
        self.text_opacity_spin.setSuffix(" %")
        self.text_opacity_spin.setValue(self.parent.text_opacity)

        self.btn_bg_color = QPushButton("修改背景颜色")
        self.btn_bg_color.setObjectName("secondaryButton")
        self.btn_bg_color.clicked.connect(self.choose_bg_color)

        self.bg_opacity_spin = WheelGuardSpinBox()
        self.bg_opacity_spin.setRange(0, 100)
        self.bg_opacity_spin.setSuffix(" %")
        self.bg_opacity_spin.setValue(self.parent.bg_opacity)

        def _label(text):
            """创建右对齐的说明标签"""
            label = QLabel(text)
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return label

        # 外观设置按网格排布 两列标签两列控件
        appearance_grid = QGridLayout()
        appearance_grid.setHorizontalSpacing(10)
        appearance_grid.setVerticalSpacing(8)
        appearance_grid.addWidget(_label("字体:"), 0, 0)
        appearance_grid.addWidget(self.font_combo, 0, 1, 1, 3)
        appearance_grid.addWidget(_label("字大小:"), 1, 0)
        appearance_grid.addWidget(self.size_spin, 1, 1)
        appearance_grid.addWidget(_label("字粗细:"), 1, 2)
        appearance_grid.addWidget(self.weight_combo, 1, 3)
        appearance_grid.addWidget(_label("字间距:"), 2, 0)
        appearance_grid.addWidget(self.spin_letter, 2, 1)
        appearance_grid.addWidget(_label("行间距:"), 2, 2)
        appearance_grid.addWidget(self.spin_line, 2, 3)
        appearance_grid.addWidget(_label("文字颜色:"), 3, 0)
        appearance_grid.addWidget(self.btn_text_color, 3, 1)
        appearance_grid.addWidget(_label("不透明度:"), 3, 2)
        appearance_grid.addWidget(self.text_opacity_spin, 3, 3)
        appearance_grid.addWidget(_label("背景颜色:"), 4, 0)
        appearance_grid.addWidget(self.btn_bg_color, 4, 1)
        appearance_grid.addWidget(_label("不透明度:"), 4, 2)
        appearance_grid.addWidget(self.bg_opacity_spin, 4, 3)
        appearance_grid.setColumnStretch(1, 1)
        appearance_grid.setColumnStretch(3, 1)
        form_layout.addRow(appearance_grid)

        # 快捷键组
        form_layout.addRow(self._section_title("快捷键"))

        # 快捷键定义 控件名 标签文本 配置字段名
        shortcut_defs = [
            ("ks_next_line", "下一句:", "key_next_line"),
            ("ks_prev_line", "上一句:", "key_prev_line"),
            ("ks_boss", "老板键:", "key_boss"),
            ("ks_quit", "彻底关闭:", "key_quit"),
            ("ks_toc", "目录:", "key_toc"),
            ("ks_auto_toggle", "自动翻页:", "key_auto_toggle"),
            ("ks_auto_speed_up", "翻页加速:", "key_auto_speed_up"),
            ("ks_auto_speed_down", "翻页减速:", "key_auto_speed_down"),
            ("ks_bg_up", "背景加深:", "key_bg_up"),
            ("ks_bg_down", "背景减淡:", "key_bg_down"),
            ("ks_text_up", "文字加深:", "key_text_up"),
            ("ks_text_down", "文字减淡:", "key_text_down"),
        ]

        # 快捷键按两列网格排布 每行两个编辑器
        shortcut_grid = QGridLayout()
        shortcut_grid.setHorizontalSpacing(10)
        shortcut_grid.setVerticalSpacing(8)
        for index, (control_name, label_text, key_attr) in enumerate(shortcut_defs):
            editor = QKeySequenceEdit(QKeySequence(getattr(self.parent, key_attr)))
            setattr(self, control_name, editor)
            label = QLabel(label_text)
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            shortcut_grid.addWidget(label, index // 2, (index % 2) * 2)
            shortcut_grid.addWidget(editor, index // 2, (index % 2) * 2 + 1)
        shortcut_grid.setColumnStretch(1, 1)
        shortcut_grid.setColumnStretch(3, 1)
        form_layout.addRow(shortcut_grid)

        # 其他组
        form_layout.addRow(self._section_title("其他"))

        self.auto_interval_spin = WheelGuardDoubleSpinBox()
        self.auto_interval_spin.setRange(1.0, 60.0)
        self.auto_interval_spin.setSingleStep(0.2)
        self.auto_interval_spin.setDecimals(1)
        self.auto_interval_spin.setSuffix(" 秒")
        self.auto_interval_spin.setValue(self.parent.auto_page_interval)
        self.auto_interval_spin.setToolTip("保存后主界面会短暂提示当前间隔")

        self.btn_icon = QPushButton("选择程序图标（PNG / ICO）")
        self.btn_icon.setObjectName("secondaryButton")
        self.btn_icon.clicked.connect(self.choose_icon)

        other_grid = QGridLayout()
        other_grid.setHorizontalSpacing(10)
        other_grid.setVerticalSpacing(8)
        other_grid.addWidget(_label("自动翻页间隔:"), 0, 0)
        other_grid.addWidget(self.auto_interval_spin, 0, 1)
        other_grid.addWidget(_label("个性化图标:"), 0, 2)
        other_grid.addWidget(self.btn_icon, 0, 3)
        other_grid.setColumnStretch(1, 1)
        other_grid.setColumnStretch(3, 1)
        form_layout.addRow(other_grid)

        # 滚动区域 内容水平居中
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        centered = QWidget()
        centered_layout = QHBoxLayout(centered)
        centered_layout.setContentsMargins(0, 0, 0, 0)
        centered_layout.setSpacing(0)
        centered_layout.addWidget(form_container)
        centered_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(centered)
        scroll.viewport().setAutoFillBackground(False)
        main_layout.addWidget(scroll, 1)

        # 底部保存按钮
        self.btn_apply = QPushButton("保存所有设置并应用")
        self.btn_apply.setObjectName("primaryButton")
        self.btn_apply.clicked.connect(self.apply_settings)
        main_layout.addWidget(self.btn_apply)

        # 输入框默认会在悬停时抢焦点并改变数值 统一改为点击后才响应滚轮
        for widget in (self.findChildren(QAbstractSpinBox)
                       + self.findChildren(QComboBox)
                       + self.findChildren(QKeySequenceEdit)):
            widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _section_title(self, text):
        """创建分节标题标签"""
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    def _get_translated_color_dialog(self, initial_color, title):
        """创建颜色选择对话框 关闭透明度并用非原生对话框保证中文"""
        dialog = QColorDialog(initial_color, self)
        dialog.setWindowTitle(title)
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, False)
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        return dialog

    def choose_text_color(self):
        """弹出颜色选择框修改文字颜色临时值"""
        init_color = QColor(self.temp_text_color)
        init_color.setAlpha(255)
        if dialog := self._get_translated_color_dialog(init_color, "请选择文字颜色"):
            if dialog.exec():
                self.temp_text_color = dialog.currentColor()
                self.btn_text_color.setText("文字颜色已选定")

    def choose_bg_color(self):
        """弹出颜色选择框修改背景颜色临时值"""
        init_color = QColor(self.temp_bg_color)
        init_color.setAlpha(255)
        if dialog := self._get_translated_color_dialog(init_color, "请选择背景颜色"):
            if dialog.exec():
                self.temp_bg_color = dialog.currentColor()
                self.btn_bg_color.setText("背景颜色已选定")

    def choose_icon(self):
        """选择自定义程序图标并立即生效保存"""
        if path := QFileDialog.getOpenFileName(self, "选择自定义图标", "", "Images (*.png *.ico *.jpg *.jpeg *.webp)")[0]:
            self.parent.icon_path = path
            self.parent.update_icon()
            self.parent.save_current_config()
            self.btn_icon.setText("✅ 图标已更换并保存")

    def apply_settings(self):
        """把界面上的所有设置写回主窗口并应用"""
        # 记录会触发额外操作的设置是否发生变化
        taskbar_changed = self.parent.show_taskbar != self.cb_taskbar.isChecked()
        bosskey_changed = self.parent.key_boss != self.ks_boss.keySequence().toString()
        quitkey_changed = self.parent.key_quit != self.ks_quit.keySequence().toString()
        always_on_top_changed = self.parent.always_on_top != self.cb_always_on_top.isChecked()

        # 保留换行变化时需要重新处理已加载文本
        layout_changed = self.parent.keep_paragraph_breaks != self.cb_keep_breaks.isChecked()

        # 写回所有普通设置 字体族需要额外取 family 名称
        for setting, (control_name, getter_name) in SETTING_CONTROLS.items():
            value = getattr(getattr(self, control_name), getter_name)()
            if setting == "font_family":
                value = value.family()
            setattr(self.parent, setting, value)

        # 写回颜色
        self.parent.text_color = self.temp_text_color
        self.parent.bg_color = self.temp_bg_color

        # 写回所有快捷键
        for setting, control_name in SHORTCUT_CONTROLS.items():
            sequence = getattr(self, control_name).keySequence().toString()
            setattr(self.parent, setting, sequence)

        # 自动翻页间隔仅在变化时保存并提示 避免无关操作也弹浮窗
        new_interval = self.auto_interval_spin.value()
        if new_interval != self.parent.auto_page_interval:
            self.parent.auto_page_interval = new_interval
            if self.parent._auto_page_active:
                self.parent._auto_page_timer.setInterval(int(new_interval * 1000))
            self.parent._flash_message(f"【自动翻页间隔已设为：{new_interval:.1f}秒/次】")

        # 刷新快捷键绑定
        self.parent.update_custom_shortcuts()

        # 排版设置变化时重新处理换行符
        if layout_changed:
            self.parent.refresh_text_line_breaks()

        # 老板键或退出键变化时重新注册全局热键
        if bosskey_changed and self.parent._win_hotkey_manager:
            self.parent.register_global_boss_key(self.parent.key_boss)
        if quitkey_changed and self.parent._win_quit_hotkey_manager:
            self.parent.register_global_quit_key(self.parent.key_quit)

        # 任务栏或置顶变化时需要重建窗口标志并重新显示
        if taskbar_changed or always_on_top_changed:
            self.parent.apply_window_flags()
            if not self.parent.is_hidden:
                self.parent.show()

        # 应用样式 刷新文本 保存配置 最后关闭弹窗
        self.parent.apply_styles()
        self.parent.update_text()
        self.parent.save_current_config()
        self.accept()
