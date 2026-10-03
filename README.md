# 自定义图片拼图游戏

这是一个使用 Python、Tkinter 和 Pillow 实现的 Windows 桌面拼图游戏。界面不依赖 CDN，图片只在本地处理，不会上传到网络。

## 已实现功能

- 点击“选择本地图片”上传 JPG、PNG、WEBP、BMP、GIF、TIFF 等本地图片。
- 支持 3×3、4×4、5×5、6×6 四种拼图尺寸。
- 每次开始或重置时使用 Sattolo 洗牌算法随机打乱，碎片不会直接落在正确位置。
- 鼠标拖动碎片，靠近正确位置时自动吸附并显示目标框。
- “提示原图”按钮短暂显示完整原图 1.5 秒。
- 显示完成进度、已用时间和拖动步数。
- 全部碎片归位后弹出通关窗口，可立即再玩一次。
- 支持窗口缩放，缩放时保持当前拼图进度。
- 开局碎片依次飞入，拖动时带有抬升阴影、速度拖尾和流光边框。
- 靠近正确位置时目标框会流动闪烁，吸附后有短促颜色脉冲反馈。
- 已启用 Windows 高 DPI 感知，缩放显示器上文字和拼图边缘更清晰。

## 项目文件

```text
拼图/
├─ jigsaw_game.py      # 完整游戏源码
├─ requirements.txt    # Pillow 与 PyInstaller
├─ build.ps1           # 一键安装、自检、打包脚本
├─ README.md
└─ .gitignore
```

## 初始化并运行

在项目目录打开 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python .\jigsaw_game.py
```

如果 PowerShell 禁止执行激活脚本，可以直接使用虚拟环境中的解释器：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\jigsaw_game.py
```

## 运行自检

```powershell
python .\jigsaw_game.py --self-test
```

自检会验证默认图片生成、四档拼图洗牌和 Tkinter 界面初始化。

## 打包 Windows EXE

最简单的方式是直接运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

也可以手动执行：

```powershell
python -m pip install -r requirements.txt
python .\jigsaw_game.py --self-test
python -m PyInstaller --noconfirm --clean --windowed --onefile --name CustomImageJigsaw .\jigsaw_game.py
```

打包完成后，可执行文件位于：

```text
dist\CustomImageJigsaw.exe
```

`--windowed` 会隐藏命令行窗口，`--onefile` 会生成单个 EXE 文件。

## 上传到 GitHub

当前机器没有检测到 GitHub CLI。可以先在 GitHub 网站创建一个空仓库，然后在项目目录执行：

```powershell
git init
git add .
git commit -m "feat: create Python image jigsaw desktop game"
git branch -M main
git remote add origin https://github.com/你的用户名/仓库名.git
git push -u origin main
```

如果之后安装了 GitHub CLI，也可以使用：

```powershell
gh repo create custom-image-jigsaw --public --source . --remote origin --push
```
