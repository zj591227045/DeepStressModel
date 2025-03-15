from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext
from Cython.Build import cythonize
import os
import sys
import platform
import shutil

# 系统平台检测
is_windows = sys.platform.startswith('win')
is_mac = sys.platform.startswith('darwin')
is_linux = sys.platform.startswith('linux')

# 当前文件所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 项目根目录
project_root = os.path.abspath(os.path.join(current_dir, "../../../.."))

# 编译器选项，根据平台不同调整
extra_compile_args = []
extra_link_args = []

if is_windows:
    # Windows平台编译选项
    extra_compile_args = ['/O2']
elif is_mac:
    # macOS平台编译选项
    extra_compile_args = ['-O3', '-Wall']
    extra_link_args = ['-stdlib=libc++']
else:
    # Linux和其他平台
    extra_compile_args = ['-O3', '-Wall']

# 设置模块的输出名称和路径
# 在key_module目录生成完整文件名的模块
module_name = "key_storage"
# 源文件相对路径
source_file = os.path.join(current_dir, "key_storage.pyx")

# 获取当前平台和Python版本信息
def get_platform_info():
    """获取当前平台和Python版本信息"""
    system = platform.system().lower()
    py_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    
    # 映射系统名称到预编译目录名
    system_map = {
        "windows": "windows",
        "darwin": "macos",
        "linux": "linux"
    }
    
    # 获取预编译目录路径
    if system in system_map:
        platform_dir = system_map[system]
        return platform_dir, py_version
    return None, py_version

# 定义扩展模块
ext_modules = [
    Extension(
        module_name,
        [source_file],
        extra_compile_args=extra_compile_args,
        extra_link_args=extra_link_args
    )
]

# 自定义build_ext命令，扩展标准build_ext
class CustomBuildExt(build_ext):
    def run(self):
        # 调用父类的run方法完成标准构建
        build_ext.run(self)
        
        # 复制编译后的文件
        self.copy_extensions_to_source()
    
    def copy_extensions_to_source(self):
        # 获取所有扩展模块的输出文件路径
        for ext in self.extensions:
            fullname = self.get_ext_fullname(ext.name)
            filename = self.get_ext_filename(fullname)
            build_path = os.path.join(self.build_lib, filename)
            
            if os.path.exists(build_path):
                # 目标路径1: key_module目录
                target_module = os.path.join(current_dir, os.path.basename(filename))
                
                # 复制到key_module目录
                self.copy_file(build_path, target_module)
                print(f"已复制编译后的模块到: {target_module}")
                
                # 获取平台信息
                platform_dir, py_version = get_platform_info()
                if platform_dir:
                    # 目标路径2: 预编译目录
                    prebuilt_dir = os.path.join(
                        current_dir, 
                        "prebuilt", 
                        platform_dir, 
                        py_version
                    )
                    
                    # 确保目录存在
                    os.makedirs(prebuilt_dir, exist_ok=True)
                    
                    # 复制到预编译目录
                    target_prebuilt = os.path.join(prebuilt_dir, os.path.basename(filename))
                    self.copy_file(build_path, target_prebuilt)
                    print(f"已复制编译后的模块到预编译目录: {target_prebuilt}")

# 设置
setup(
    name="benchmark_key_storage",
    version="0.1.0",
    description="加密公钥存储模块",
    ext_modules=cythonize(ext_modules, compiler_directives={
        'language_level': "3",
        'embedsignature': True
    }),
    zip_safe=False,
    cmdclass={
        'build_ext': CustomBuildExt,
    },
) 