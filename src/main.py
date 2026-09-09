"""应用入口与单实例管理。"""
import os
import signal
import sys

from PySide6.QtCore import QLibraryInfo, QTranslator
from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from reader.utils import asset_path
from reader.window import ReaderWindow


def main():
    """程序入口 完成单实例锁 界面初始化与事件循环"""
    # 创建应用并设置基础信息
    app = QApplication(sys.argv)
    app.setApplicationName("reader")
    app.setApplicationDisplayName("reader")
    app.setQuitOnLastWindowClosed(False)

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

    # 尽早设置应用图标
    icon_file = asset_path('logo.png')
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
