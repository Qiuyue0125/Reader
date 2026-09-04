# Reader

[中文](README.md) | [English](README_EN.md)

Reader is a lightweight, frameless Windows application for distraction-free reading of local e-books. Common actions can be performed entirely with keyboard shortcuts. The default configuration supports left-hand-only keyboard use, right-hand-only keyboard use, and mouse-only operation.

> This project is a modified version of [Y3-YYDS/YReader](https://github.com/Y3-YYDS/YReader/). Thanks to the original author for making their work available.

## Download

[Download the latest Reader for Windows x64](https://github.com/Qiuyue0125/Reader/releases/latest/download/reader.exe)

The downloaded `reader.exe` can be run directly. Reader does not write into system directories; it only creates a configuration file beside the executable.

## Preview

![Reader animated demo](./assets/demo.gif)

### Library and appearance settings

<p align="center">
  <img src="./assets/library.png" alt="Library" width="49%">
  <img src="./assets/settings.png" alt="Settings" width="49%">
</p>

### Chapter directory

![Chapter directory](./assets/chapters.png)

Press `C` to quickly open or close the chapter directory. Once it is open, type the beginning of a chapter title to locate it, use `↑` / `↓` to select a chapter, and press `Enter` to jump to it.

[View or download the full demonstration video (MP4)](https://github.com/Qiuyue0125/Reader/releases/download/v1.0.0/demo.mp4)

## Features

- Open local TXT, EPUB, and MOBI files
- Automatically detect chapters and display a chapter directory
- Automatically reflow and paginate text based on the current window size
- Automatic page turning, always-on-top mode, opacity controls, and hover-to-show text
- Boss key, global exit shortcut, and customizable shortcuts
- A recent-first library that stores books and reading progress
- Portable configuration: `reader_config.json` is stored beside the executable
- Single-instance operation and system tray controls

## Usage

### Open a book

Right-click the reading window and select **My Library**. On first use, click **Add Book**, choose a local e-book, and confirm. You can also enter a file path directly in the input field.

### Reading and chapter navigation

Reader automatically detects chapters and displays the text after opening a file. Text is reflowed whenever the window is resized. Reaching the end of a chapter automatically opens the next chapter.

To jump elsewhere, open **Chapter Directory** from the context menu or press `C`. Type the beginning of a chapter title to locate it, use the arrow keys to select it, and press `Enter` to jump.

### Window and appearance

The reading window is frameless. Drag the window to move it or drag an edge to resize it. Right-click and select **Application Settings** to configure the font, size, colors, opacity, line spacing, always-on-top behavior, hover display, and mouse-wheel paging.

### Automatic page turning

Set the interval in **Application Settings**, then enable automatic page turning. Toggle it again to stop. The page-turning speed can also be adjusted with shortcuts.

## Default shortcuts

These shortcuts can be changed in the **Shortcuts** section of Application Settings:

| Action | Default shortcut |
| --- | --- |
| Next page | `Z` |
| Previous page | `X` |
| Boss key | `Alt+Z` |
| Exit completely | `Alt+X` |
| Increase background opacity | `Ctrl+Up` |
| Decrease background opacity | `Ctrl+Down` |
| Increase text opacity | `Ctrl+Right` |
| Decrease text opacity | `Ctrl+Left` |
| Open chapter directory | `C` |
| Toggle automatic page turning | `Ctrl+E` |
| Increase page-turning speed | `Ctrl+S` |
| Decrease page-turning speed | `Ctrl+W` |

When the window is focused, the fixed arrow-key controls are also available: `←` previous page, `→` next page, `↓` hide/show, and `↑` exit completely. While the chapter directory is open, the up and down keys are used to select chapters instead.

## Run from source

Windows and Python 3.10 or later are required:

```powershell
cd reader
python -m pip install -r requirements.txt
python main.py
```

## Build

```powershell
cd reader
pyinstaller reader_win.spec --clean --noconfirm
```

The packaged application is written to the project's `dist` directory.

## FAQ

### A book cannot be opened after it was moved

The library stores absolute local paths. If a file is moved or renamed, its old entry will report that the file no longer exists. Add the book again from **My Library**.

### Why can the arrow keys not restore a hidden window?

Arrow-key shortcuts only work while the application window is focused. When Reader is hidden, use the global boss key (`Alt+Z` by default) to restore it.

## Credits and notice

This project is a modified version of [YReader](https://github.com/Y3-YYDS/YReader/) and is not an official release of the original project. The original project and its author retain their respective rights. Modifications in this repository are provided under the licensing information included with the repository.
