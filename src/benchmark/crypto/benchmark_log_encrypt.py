"""
基准测试日志加密模块

提供对DeepStressModel基准测试结果的加密功能，确保测试结果的真实性和不可篡改性。
使用混合加密架构（RSA非对称加密与AES对称加密相结合）。
"""
import os
import json
import time
import base64
import hashlib
import secrets
import tempfile
import requests
import platform
import importlib.util
from datetime import datetime
from typing import Dict, Any, Optional, Union, Tuple

from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend

from src.utils.logger import setup_logger
from src.benchmark.crypto.crypto_utils import CryptoUtils

# 设置日志记录器
logger = setup_logger("benchmark_log_encrypt")

def find_prebuilt_module():
    """
    根据当前平台查找预编译的key_storage模块
    
    Returns:
        tuple: (模块导入成功标志, 导入位置描述, get_public_key函数或None)
    """
    import sys
    
    # 尝试获取当前Python版本对应的预编译模块
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
        # 构建预编译文件的父目录路径
        prebuilt_dir = os.path.join(
            os.path.dirname(__file__), 
            "key_module", 
            "prebuilt", 
            platform_dir, 
            py_version
        )
        
        logger.debug(f"尝试从预编译目录加载: {prebuilt_dir}")
        
        # 检查目录是否存在
        if os.path.exists(prebuilt_dir):
            # 找出所有可能的预编译文件
            for filename in os.listdir(prebuilt_dir):
                if filename.startswith('key_storage') and (filename.endswith('.so') or filename.endswith('.pyd')):
                    # 找到预编译文件，尝试加载
                    module_path = os.path.join(prebuilt_dir, filename)
                    logger.debug(f"尝试加载预编译模块: {module_path}")
                    
                    try:
                        # 使用importlib动态加载模块
                        spec = importlib.util.spec_from_file_location("key_storage", module_path)
                        if spec and spec.loader:
                            key_storage = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(key_storage)
                            if hasattr(key_storage, 'get_public_key'):
                                return True, f"预编译模块({platform_dir}/{py_version})", key_storage.get_public_key
                    except Exception as e:
                        logger.warning(f"加载预编译模块失败: {str(e)}")
    
    return False, "未找到预编译模块", None

# 从编译的Cython模块导入公钥功能
# 按照以下顺序尝试导入：
# 1. 预编译目录中与当前平台匹配的模块
# 2. key_module目录中编译的模块
# 3. 项目根目录中的模块
# 4. 动态搜索路径

# 首先尝试从预编译目录导入
prebuilt_success, import_location, prebuilt_get_public_key = find_prebuilt_module()

if prebuilt_success:
    # 使用预编译模块的get_public_key函数
    get_public_key = prebuilt_get_public_key
else:
    # 如果没有找到预编译模块，尝试常规导入
    try:
        # 1. 优先尝试从key_module目录导入
        from src.benchmark.crypto.key_module.key_storage import get_public_key
        import_location = "key_module目录"
    except ImportError:
        try:
            # 2. 然后尝试从项目根目录导入(兼容性导入)
            from key_storage import get_public_key
            import_location = "项目根目录"
        except ImportError:
            try:
                # 3. 如果编译的模块在上述位置找不到，尝试通过添加路径
                import sys
                # 添加key_module目录到sys.path
                module_dir = os.path.join(os.path.dirname(__file__), "key_module")
                if module_dir not in sys.path:
                    sys.path.insert(0, module_dir)
                # 添加项目根目录到sys.path
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
                if project_root not in sys.path:
                    sys.path.insert(0, project_root)
                from key_storage import get_public_key
                import_location = "通过sys.path"
            except ImportError:
                # 4. 如果没有找到编译好的模块，提供一个错误提示
                def get_public_key():
                    raise RuntimeError("""
                    缺少编译的key_storage模块。您可以:
                    1. 请确认您的平台是否有预编译模块可用
                    2. 或者运行 'python src/benchmark/crypto/key_module/setup.py build_ext --inplace' 自行编译模块
                    """)
                import_location = "未找到模块"

logger.debug(f"从{import_location}导入key_storage模块")

# 预定义错误类型
class EncryptionError(Exception):
    """加密过程中的错误"""
    def __init__(self, code: str, message: str, details: Dict[str, Any] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

# 错误代码定义
ERRORS = {
    "INVALID_DATA": {"code": "C1001", "message": "无效的测试数据格式"},
    "ENCRYPTION_FAILED": {"code": "C1002", "message": "加密失败"},
    "PUBLIC_KEY_ERROR": {"code": "C1003", "message": "公钥处理错误"},
    "API_KEY_ERROR": {"code": "C1004", "message": "API密钥错误"},
    "SERVER_ERROR": {"code": "C1005", "message": "服务器错误"},
    "UPLOAD_FAILED": {"code": "C1006", "message": "上传失败"}
}

class BenchmarkEncryption:
    """基准测试日志加密类"""
    
    def __init__(self):
        """初始化基准测试日志加密类"""
        # 在初始化时获取公钥
        self.public_key = None
        try:
            # 使用Cython编译的模块获取公钥
            self.public_key = get_public_key()
            logger.debug("公钥加载成功")
        except Exception as e:
            logger.error(f"公钥加载失败: {str(e)}")
            raise EncryptionError(
                ERRORS["PUBLIC_KEY_ERROR"]["code"],
                ERRORS["PUBLIC_KEY_ERROR"]["message"],
                {"details": str(e)}
            )
    
    def _generate_api_key_hash(self, session_key: bytes, api_key: str) -> bytes:
        """
        生成API密钥哈希
        
        Args:
            session_key: 会话密钥
            api_key: API密钥
            
        Returns:
            bytes: API密钥哈希
        """
        try:
            api_key_bytes = api_key.encode('utf-8')
            salt = b"deepstress_api_binding"
            
            # 使用HKDF派生API密钥绑定密钥
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                info=b"api_key_binding",
                backend=default_backend()
            )
            
            binding_material = hkdf.derive(api_key_bytes + session_key)
            
            # 计算API密钥哈希（不直接存储API密钥）
            return hashlib.sha256(binding_material).digest()
        except Exception as e:
            logger.error(f"API密钥哈希生成失败: {str(e)}")
            raise EncryptionError(
                ERRORS["API_KEY_ERROR"]["code"],
                ERRORS["API_KEY_ERROR"]["message"],
                {"details": str(e)}
            )
    
    def encrypt_benchmark_log(self, log_data: Dict[str, Any], api_key: str) -> Dict[str, Any]:
        """
        加密基准测试日志
        
        Args:
            log_data: 基准测试日志数据
            api_key: API密钥
            
        Returns:
            Dict[str, Any]: 加密后的数据包
        """
        try:
            # 验证输入数据
            if not isinstance(log_data, dict):
                raise ValueError("测试数据必须是字典类型")
            
            if not api_key or not isinstance(api_key, str):
                raise ValueError("API密钥不能为空且必须是字符串类型")
            
            # 将数据转换为JSON字符串
            log_json = json.dumps(log_data, ensure_ascii=False)
            
            # 生成随机会话密钥
            session_key = CryptoUtils.generate_aes_key()  # 生成256位随机密钥
            
            # 使用AES-GCM模式加密测试记录
            encrypted_data = CryptoUtils.aes_encrypt(log_json, session_key)
            
            # 使用公钥加密会话密钥
            encrypted_session_key = CryptoUtils.rsa_encrypt(session_key, self.public_key)
            
            # 计算原始数据的哈希值
            log_hash = hashlib.sha256(log_json.encode('utf-8')).digest()
            
            # 生成API密钥哈希
            api_key_hash = self._generate_api_key_hash(session_key, api_key)
            
            # 构建签名数据
            signature_data = {
                "log_hash": base64.b64encode(log_hash).decode(),
                "timestamp": int(time.time()),
                "nonce": secrets.token_hex(16),
                "api_key_hash": base64.b64encode(api_key_hash).decode()
            }
            
            # 生成签名
            signature_key = hashlib.sha256(session_key + api_key.encode('utf-8')).digest()
            
            # 修复HMAC调用方式
            h = hmac.HMAC(
                signature_key,
                algorithm=hashes.SHA256(),
                backend=default_backend()
            )
            h.update(json.dumps(signature_data, sort_keys=True).encode())
            signature = h.finalize()
            
            # 组装加密数据包
            encrypted_package = {
                "format_version": "1.0",
                "encrypted_session_key": encrypted_session_key,
                "encrypted_data": encrypted_data,
                "signature_data": signature_data,
                "signature": base64.b64encode(signature).decode(),
                "timestamp": datetime.now().isoformat()
            }
            
            return encrypted_package
        except ValueError as e:
            logger.error(f"输入数据验证失败: {str(e)}")
            raise EncryptionError(
                ERRORS["INVALID_DATA"]["code"],
                ERRORS["INVALID_DATA"]["message"],
                {"details": str(e)}
            )
        except Exception as e:
            logger.error(f"加密失败: {str(e)}")
            raise EncryptionError(
                ERRORS["ENCRYPTION_FAILED"]["code"],
                ERRORS["ENCRYPTION_FAILED"]["message"],
                {"details": str(e)}
            )
    
    def encrypt_and_save(self, log_data: Dict[str, Any], output_path: str, api_key: str) -> str:
        """
        加密基准测试日志并保存到文件
        
        Args:
            log_data: 基准测试日志数据
            output_path: 输出文件路径
            api_key: API密钥
            
        Returns:
            str: 保存的文件路径
        """
        try:
            # 加密测试记录
            encrypted_package = self.encrypt_benchmark_log(log_data, api_key)
            
            # 将加密数据包保存到文件
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(encrypted_package, f, ensure_ascii=False, indent=2)
            
            logger.info(f"加密数据已保存到: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"保存加密数据失败: {str(e)}")
            raise EncryptionError(
                ERRORS["ENCRYPTION_FAILED"]["code"],
                ERRORS["ENCRYPTION_FAILED"]["message"],
                {"details": str(e)}
            )
    
    def encrypt_and_upload(self, log_data: Dict[str, Any], api_key: str, 
                          server_url: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        加密基准测试日志并上传到服务器
        
        Args:
            log_data: 基准测试日志数据
            api_key: API密钥
            server_url: 服务器URL
            metadata: 元数据，如提交者信息、模型信息等
            
        Returns:
            Dict[str, Any]: 服务器响应结果
        """
        try:
            # 加密测试记录
            encrypted_package = self.encrypt_benchmark_log(log_data, api_key)
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
                temp_file_path = temp_file.name
                json.dump(encrypted_package, temp_file, ensure_ascii=False, indent=2)
            
            try:
                # 准备元数据（如果有）
                meta_payload = None
                if metadata:
                    meta_payload = json.dumps(metadata, ensure_ascii=False)
                
                # 准备上传文件
                files = {
                    'file': ('benchmark_log.json', open(temp_file_path, 'rb'), 'application/json')
                }
                
                data = {}
                if meta_payload:
                    data['metadata'] = meta_payload
                
                # 设置请求头
                headers = {
                    'Authorization': f'APIKEY {api_key}'
                }
                
                # 发送请求
                response = requests.post(
                    server_url,
                    headers=headers,
                    files=files,
                    data=data
                )
                
                # 处理响应
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"上传成功，ID: {result.get('upload_id', 'unknown')}")
                    return result
                else:
                    # 处理错误
                    error_msg = f"上传失败: 状态码 {response.status_code}"
                    try:
                        error_data = response.json()
                        if 'error' in error_data:
                            error_msg = f"上传失败: {error_data['error'].get('message', '未知错误')}"
                    except:
                        pass
                    
                    logger.error(error_msg)
                    raise EncryptionError(
                        ERRORS["UPLOAD_FAILED"]["code"],
                        error_msg,
                        {"status_code": response.status_code}
                    )
            
            finally:
                # 清理临时文件
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
        
        except EncryptionError:
            # 重新抛出已经格式化的加密错误
            raise
        except Exception as e:
            logger.error(f"上传过程发生错误: {str(e)}")
            raise EncryptionError(
                ERRORS["SERVER_ERROR"]["code"],
                ERRORS["SERVER_ERROR"]["message"],
                {"details": str(e)}
            )

def main():
    """命令行入口点"""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="DeepStressModel 测试日志加密工具")
    parser.add_argument("input", help="测试日志文件路径", type=str)
    parser.add_argument("-o", "--output", help="输出文件路径", type=str, default=None)
    parser.add_argument("-k", "--api-key", help="API密钥", type=str, required=True)
    parser.add_argument("-u", "--upload", help="上传到服务器", action="store_true")
    parser.add_argument("-s", "--server", help="服务器URL", type=str, 
                        default="https://benchmark.example.com/api/v1/benchmark/upload")
    parser.add_argument("-m", "--metadata", help="元数据JSON文件路径", type=str, default=None)
    args = parser.parse_args()
    
    try:
        # 加载测试日志
        with open(args.input, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
        
        # 初始化加密器
        encryptor = BenchmarkEncryption()
        
        # 加载元数据
        metadata = None
        if args.metadata:
            with open(args.metadata, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        
        if args.upload:
            # 加密并上传
            result = encryptor.encrypt_and_upload(
                log_data,
                api_key=args.api_key,
                server_url=args.server,
                metadata=metadata
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            # 加密并保存到文件
            output_path = args.output or f"encrypted_{os.path.basename(args.input)}"
            encryptor.encrypt_and_save(log_data, output_path, api_key=args.api_key)
            print(f"已加密并保存到: {output_path}")
    
    except EncryptionError as e:
        print(f"错误 {e.code}: {e.message}")
        if e.details:
            print(f"详情: {e.details}")
        sys.exit(1)
    except Exception as e:
        print(f"未预期的错误: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 