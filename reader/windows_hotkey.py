# -*- coding: utf-8 -*-
"""
windows_hotkey 模块
基于 Windows Native API 的全局热键引擎
在独立线程中运行消息循环 即使主界面被遮挡也能响应热键
"""

import ctypes
from ctypes import wintypes
import threading
import time

from PySide6.QtCore import QObject, Signal


# 全局热键的修饰键掩码
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

# Windows 消息相关常量
WM_HOTKEY = 0x0312
PM_REMOVE = 1

# 热键注册 id 每个管理器只注册一个热键 固定使用 1
HOTKEY_ID = 1

# 消息循环轮询间隔 秒 用于在空闲时释放 CPU
POLL_INTERVAL = 0.01


# 虚拟键码兜底映射
VIRTUAL_KEY_MAP = {
    'space': 0x20,
    'esc': 0x1B,
    'escape': 0x1B,
    'enter': 0x0D,
    'up': 0x26,
    'down': 0x28,
    'left': 0x25,
    'right': 0x27,
}

# 无法识别按键时的默认虚拟键码 Q 键
DEFAULT_VK = 0x51


user32 = ctypes.windll.user32


class WinHotkeyManager(QObject):
    """基于 Windows Native API 的全局热键引擎 永不掉线"""

    # 热键被触发时发出的信号
    triggered = Signal()

    def __init__(self):
        """初始化管理器状态与线程同步事件"""
        super().__init__()
        self._running = False
        self._thread = None
        self._current_hotkey_params = None
        self._registration_event = threading.Event()
        self._registered = False

    def register(self, hotkey_str):
        """注册一个全局热键 返回是否注册成功"""
        # 先注销旧热键 再解析新快捷键
        self.unregister()
        if not hotkey_str:
            return False

        # 解析快捷键字符串得到修饰键掩码与虚拟键码
        parts = hotkey_str.lower().split('+')
        mods = MOD_NOREPEAT
        key = 'q'
        for part in parts:
            part = part.strip()
            if part in ['alt', 'option']:
                mods |= MOD_ALT
            elif part in ['ctrl', 'control']:
                mods |= MOD_CONTROL
            elif part == 'shift':
                mods |= MOD_SHIFT
            elif part in ['win', 'windows', 'meta', 'cmd', 'command']:
                mods |= MOD_WIN
            else:
                key = part

        # 记录参数 清空事件并启动消息循环线程
        vk = self._get_vk(key)
        self._current_hotkey_params = (mods, vk)
        self._registration_event.clear()
        self._registered = False
        self._running = True
        self._thread = threading.Thread(target=self._msg_loop, daemon=True)
        self._thread.start()

        # 等待线程完成注册 最多一秒
        self._registration_event.wait(timeout=1.0)
        return self._registered

    def _get_vk(self, key):
        """把按键名转换成 Windows 虚拟键码"""
        if key in VIRTUAL_KEY_MAP:
            return VIRTUAL_KEY_MAP[key]
        # 单个字母或数字键取其大写 ASCII 作为键码
        if len(key) == 1 and key.isalnum():
            return ord(key.upper())
        # F1 到 F24 功能键
        if key.startswith('f') and key[1:].isdigit():
            return 0x6F + int(key[1:])
        return DEFAULT_VK

    def _msg_loop(self):
        """在独立线程中注册热键并循环处理窗口消息"""
        mods, vk = self._current_hotkey_params

        # 注册失败时通知主线程并退出
        if not user32.RegisterHotKey(None, HOTKEY_ID, mods, vk):
            self._running = False
            self._registration_event.set()
            print("Windows 原生全局热键注册失败。快捷键可能被系统或其他程序占用。")
            return

        # 注册成功 通知主线程继续
        self._registered = True
        self._registration_event.set()

        # 循环拉取消息 收到热键消息时发射信号
        msg = wintypes.MSG()
        while self._running:
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                if msg.message == WM_HOTKEY:
                    self.triggered.emit()
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                # 短暂休眠 避免空转占用 CPU
                time.sleep(POLL_INTERVAL)

        # 循环结束 注销热键并复位状态
        user32.UnregisterHotKey(None, HOTKEY_ID)
        self._registered = False

    def unregister(self):
        """停止消息循环并注销热键"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
            self._thread = None
        self._registered = False
