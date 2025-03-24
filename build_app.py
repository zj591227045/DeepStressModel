import os
import sys
import shutil
import subprocess
from pathlib import Path

def clean_build_folders():
    """清理build和dist文件夹"""
    print("清理旧的构建文件...")
    folders_to_clean = ['build', 'dist']
    for folder in folders_to_clean:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f"已删除 {folder}/ 文件夹")

def create_spec_file():
    """创建自定义spec文件"""
    print("创建打包配置...")
    
    spec_content = """# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

block_cipher = None

# 项目根目录
ROOT_DIR = Path('.').absolute()

# 添加数据文件
added_files = [
    ('data', 'data'),
    ('resources', 'resources'),
    ('src/benchmark/crypto/key_module/prebuilt', 'src/benchmark/crypto/key_module/prebuilt'),
]

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtNetwork',
        'matplotlib.backends.backend_qt5agg',
        'aiohttp',
        'sqlalchemy',
        'sqlite3',
        'py3nvml',
        'paramiko',
        'tiktoken',
        'psutil',
        'python-dotenv',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DeepStressModel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/icon.ico' if Path('resources/icon.ico').exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DeepStressModel',
)
"""
    
    with open('DeepStressModel.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print("已创建 DeepStressModel.spec 文件")

def build_app():
    """构建应用程序"""
    print("开始构建应用程序...")
    
    # 使用spec文件构建
    build_cmd = ['pyinstaller', 'DeepStressModel.spec', '--noconfirm']
    process = subprocess.run(build_cmd, shell=True, check=True)
    
    if process.returncode == 0:
        print("应用程序构建成功!")
        # 检查结果
        dist_path = Path('dist/DeepStressModel')
        if dist_path.exists():
            print(f"可执行文件已生成: {dist_path.absolute()}")
            print(f"请运行 {dist_path/'DeepStressModel.exe'} 启动应用程序")
        else:
            print("警告: 未找到生成的可执行文件!")
    else:
        print("应用程序构建失败!")
        sys.exit(1)

def create_standalone_exe():
    """创建单文件可执行文件"""
    print("正在创建单文件可执行版本...")
    
    standalone_cmd = [
        'pyinstaller', 
        'src/main.py', 
        '--name=DeepStressModel-Standalone',
        '--onefile',
        '--windowed',
        '--add-data=data;data',
        '--add-data=resources;resources',
        '--add-data=src/benchmark/crypto/key_module/prebuilt;src/benchmark/crypto/key_module/prebuilt',
        '--noconfirm'
    ]
    
    if Path('resources/icon.ico').exists():
        standalone_cmd.append('--icon=resources/icon.ico')
    
    process = subprocess.run(standalone_cmd, shell=True, check=True)
    
    if process.returncode == 0:
        print("单文件可执行文件构建成功!")
        standalone_path = Path('dist/DeepStressModel-Standalone.exe')
        if standalone_path.exists():
            print(f"可执行文件已生成: {standalone_path.absolute()}")
        else:
            print("警告: 未找到生成的单文件可执行文件!")
    else:
        print("单文件可执行文件构建失败!")

def create_debug_exe():
    """创建带调试控制台的可执行文件"""
    print("正在创建调试版本...")
    
    debug_cmd = [
        'pyinstaller', 
        'src/main.py', 
        '--name=DeepStressModel-Debug',
        '--onefile',
        '--console',  # 启用控制台窗口
        '--add-data=data;data',
        '--add-data=resources;resources',
        '--add-data=src/benchmark/crypto/key_module/prebuilt;src/benchmark/crypto/key_module/prebuilt',
        '--noconfirm'
    ]
    
    if Path('resources/icon.ico').exists():
        debug_cmd.append('--icon=resources/icon.ico')
    
    process = subprocess.run(debug_cmd, shell=True, check=True)
    
    if process.returncode == 0:
        print("调试版本构建成功!")
        debug_path = Path('dist/DeepStressModel-Debug.exe')
        if debug_path.exists():
            print(f"调试版本已生成: {debug_path.absolute()}")
            print("运行方式: DeepStressModel-Debug.exe --debug")
        else:
            print("警告: 未找到生成的调试版本!")
    else:
        print("调试版本构建失败!")

if __name__ == "__main__":
    # 清理旧的构建文件
    clean_build_folders()
    
    # 创建打包配置文件
    create_spec_file()
    
    # 构建应用程序(文件夹模式)
    build_app()
    
    # 构建单文件可执行版本
    create_standalone_exe()
    
    # 构建调试版本
    create_debug_exe()
    
    print("打包过程完成!") 