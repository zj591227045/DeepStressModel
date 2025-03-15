#!/usr/bin/env python3
"""
测试Cython编译的key_storage模块
"""
import os
import sys

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, project_root)

def test_key_storage():
    """测试key_storage模块"""
    print("测试key_storage模块...")
    
    try:
        # 尝试导入模块
        from key_storage import get_public_key
        
        # 获取公钥
        public_key = get_public_key()
        
        # 验证公钥格式
        if not public_key.startswith(b"-----BEGIN PUBLIC KEY-----"):
            print("错误：公钥格式不正确（开头）")
            return False
            
        if not public_key.endswith(b"-----END PUBLIC KEY-----"):
            print("错误：公钥格式不正确（结尾）")
            return False
        
        # 打印公钥长度和部分内容
        print(f"公钥获取成功！长度：{len(public_key)} 字节")
        print(f"公钥前缀：{public_key[:40]}")
        print(f"公钥后缀：{public_key[-40:]}")
        
        return True
    except ImportError as e:
        print(f"错误：无法导入key_storage模块 - {e}")
        print("请先运行 'python setup.py build_ext --inplace' 编译模块")
        return False
    except Exception as e:
        print(f"错误：测试失败 - {e}")
        return False

def main():
    """主函数"""
    print("===== Cython模块测试 =====")
    
    # 检查是否已编译模块
    module_dir = os.path.dirname(os.path.abspath(__file__))
    compiled_module = False
    
    # 检查当前目录和项目根目录
    dirs_to_check = [module_dir, project_root]
    
    for check_dir in dirs_to_check:
        for file in os.listdir(check_dir):
            if file.startswith('key_storage') and (file.endswith('.so') or file.endswith('.pyd')):
                compiled_module = True
                print(f"找到编译后的模块：{os.path.join(check_dir, file)}")
                break
        if compiled_module:
            break
    
    if not compiled_module:
        print("警告：未找到编译后的模块文件")
        print("请先运行 'python setup.py build_ext --inplace' 编译模块")
    
    # 测试模块
    success = test_key_storage()
    
    if success:
        print("\n✓ 测试通过！key_storage模块工作正常。")
        return 0
    else:
        print("\n✗ 测试失败！请检查模块编译是否正确。")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 