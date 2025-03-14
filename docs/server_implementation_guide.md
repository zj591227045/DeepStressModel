# DeepStressModel 服务端加密实现指南

本文档提供了在 DeepStressModel 服务端实现修订版加密规范（v2.0）的详细指南。该规范主要解决了数据集加密中的问题，同时保持与现有私钥和会话密钥加密兼容。

## 变更概述

1. **数据结构变更**：
   - 离线包格式版本升级到 4.0
   - 扩展了加密数据的元数据，明确记录加密算法和密钥派生参数

2. **算法变更**：
   - 数据集加密现在使用 HKDF 派生密钥，以解决会话密钥长度不标准的问题
   - 标准化了 AES 模式和填充方式

3. **兼容性**：
   - 私钥加密和会话密钥加密保持不变
   - 数据集加密的修改是向后不兼容的，需要客户端同步更新

## 服务端修改指南

### 1. 添加 HKDF 密钥派生

需要实现符合 RFC 5869 的 HKDF 密钥派生函数。如果您使用的密码库已包含 HKDF 实现，可以直接使用；否则，需要按照以下步骤实现：

```python
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

def derive_key_with_hkdf(master_key, salt, info, length=32):
    """
    使用 HKDF 从主密钥派生密钥
    
    Args:
        master_key (bytes): 主密钥（会话密钥）
        salt (bytes): 盐值
        info (bytes): 绑定到特定上下文的信息
        length (int): 派生密钥长度，默认32字节
        
    Returns:
        bytes: 派生的密钥
    """
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        info=info,
        backend=default_backend()
    )
    return hkdf.derive(master_key)
```

### 2. 修改数据集加密方法

将现有的 `encrypt_dataset` 或类似函数修改为使用 HKDF 派生密钥：

```python
def encrypt_dataset(dataset, session_key):
    """
    使用会话密钥加密数据集
    
    Args:
        dataset (dict): 要加密的数据集
        session_key (bytes): 会话密钥
        
    Returns:
        dict: 加密后的数据结构
    """
    # 将数据集转换为JSON字符串
    dataset_json = json.dumps(dataset, ensure_ascii=False).encode('utf-8')
    
    # 生成随机盐值
    salt = os.urandom(16)
    
    # 定义信息字符串
    info = b"dataset_encryption"
    
    # 使用HKDF从会话密钥派生AES密钥
    derived_key = derive_key_with_hkdf(
        master_key=session_key,
        salt=salt,
        info=info,
        length=32  # 256位密钥
    )
    
    # 生成随机IV
    iv = os.urandom(16)
    
    # 对数据集JSON进行PKCS7填充
    padder = sym_padding.PKCS7(algorithms.AES.block_size).padder()
    padded_data = padder.update(dataset_json) + padder.finalize()
    
    # 使用AES-CBC加密
    cipher = Cipher(algorithms.AES(derived_key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
    
    # 构建加密结果
    result = {
        "algorithm": "AES-256-CBC-PKCS7",
        "key_derivation": {
            "method": "HKDF-SHA256",
            "salt": base64.b64encode(salt).decode(),
            "info": "dataset_encryption"
        },
        "iv": base64.b64encode(iv).decode(),
        "data": base64.b64encode(encrypted_data).decode()
    }
    
    return result
```

### 3. 更新离线包格式

修改生成离线包的代码以使用新的数据结构：

```python
def create_offline_package(dataset, api_key, private_key, public_key, dataset_id=1):
    """
    创建完整的离线包
    
    Args:
        dataset (dict): 数据集
        api_key (str): API密钥
        private_key (object): RSA私钥对象
        public_key (object): RSA公钥对象
        dataset_id (int): 数据集ID
        
    Returns:
        dict: 完整的离线包
    """
    # 使用API密钥加密私钥
    encrypted_private_key = encrypt_private_key(private_key, api_key)
    
    # 生成随机会话密钥
    session_key = os.urandom(32)
    
    # 使用RSA公钥加密会话密钥
    encrypted_session_key = encrypt_session_key(session_key, public_key)
    
    # 使用会话密钥加密数据集
    encrypted_data = encrypt_dataset(dataset, session_key)
    
    # 生成时间戳和签名
    timestamp = str(int(time.time() * 1000))
    signature = generate_signature(dataset, timestamp, api_key)
    
    # 构建离线包
    now = datetime.now()
    package = {
        "metadata": {
            "package_format": "4.0",
            "dataset_id": dataset_id,
            "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "expires_at": (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        },
        "encrypted_private_key": encrypted_private_key,
        "dataset": {
            "encrypted_session_key": encrypted_session_key,
            "encrypted_data": encrypted_data,
            "timestamp": timestamp,
            "user_signature": signature
        }
    }
    
    return package
```

### 4. 添加版本检测

为了支持旧版客户端，可以添加版本检测和向后兼容性代码：

```python
def encrypt_dataset_with_version(dataset, session_key, version="4.0"):
    """
    基于版本使用会话密钥加密数据集
    
    Args:
        dataset (dict): 要加密的数据集
        session_key (bytes): 会话密钥
        version (str): 请求的格式版本
        
    Returns:
        dict: 加密后的数据结构
    """
    if version == "4.0":
        # 使用新规范加密
        return encrypt_dataset(dataset, session_key)
    else:
        # 使用旧规范加密（旧的实现）
        return encrypt_dataset_legacy(dataset, session_key)
```

## 实现细节说明

### 配置项

您可能需要添加以下配置项以控制加密行为：

```python
# config.py 或类似文件
CRYPTO_CONFIG = {
    "default_package_format": "4.0",
    "hkdf_iterations": 1000,
    "pbkdf2_iterations": 100000,
    "key_length": 32,
    "legacy_support": True
}
```

### 日志记录

为了方便调试，建议添加详细的加密过程日志：

```python
import logging

logger = logging.getLogger("crypto")

def encrypt_dataset(dataset, session_key):
    try:
        logger.debug(f"开始加密数据集，会话密钥长度: {len(session_key)}")
        
        # ... 加密逻辑 ...
        
        logger.debug("数据集加密成功")
        return encrypted_result
    except Exception as e:
        logger.error(f"数据集加密失败: {str(e)}")
        raise
```

### 错误处理

为了提高稳健性，增强错误处理并提供明确的错误信息：

```python
class CryptoError(Exception):
    """加密相关错误的基类"""
    pass

class KeyDerivationError(CryptoError):
    """密钥派生错误"""
    pass

class EncryptionError(CryptoError):
    """加密过程错误"""
    pass

def derive_key_with_hkdf(master_key, salt, info, length=32):
    if not isinstance(master_key, bytes):
        raise KeyDerivationError("主密钥必须是字节类型")
    
    if len(master_key) < 16:
        raise KeyDerivationError(f"主密钥长度不足，至少需要16字节，实际长度: {len(master_key)}")
    
    try:
        # ... 密钥派生逻辑 ...
    except Exception as e:
        raise KeyDerivationError(f"HKDF密钥派生失败: {str(e)}")
```

## 测试指南

实施新加密规范后，应进行以下测试：

1. **单元测试**：
   - 测试 HKDF 密钥派生功能
   - 测试修改后的数据集加密函数
   - 测试完整的离线包生成

2. **集成测试**：
   - 使用新客户端解密由新服务端生成的离线包
   - 使用新客户端解密由旧服务端生成的离线包（如果保持向后兼容）

3. **安全审计**：
   - 确保没有引入新的安全漏洞
   - 验证所有加密参数（盐值、IV等）均使用密码学安全的随机源
   - 确认没有密钥材料泄露到日志

## AI辅助实现提示

您可以使用以下AI提示来指导相关模块的实现：

```
请帮我实现 DeepStressModel 离线包加密系统的数据集加密模块，遵循以下加密规范：

1. 使用 HKDF-SHA256 从任意长度的会话密钥派生一个固定长度(32字节)的 AES 密钥
2. 使用 AES-256-CBC 模式和 PKCS7 填充加密数据集的 JSON 字符串
3. 清晰记录加密参数，包括算法、盐值、IV 和派生方法
4. 数据结构应符合规范 v2.0，使用 "encrypted_data" 格式：
   {
     "algorithm": "AES-256-CBC-PKCS7",
     "key_derivation": {
       "method": "HKDF-SHA256",
       "salt": "<base64_encoded_salt>",
       "info": "dataset_encryption"
     },
     "iv": "<base64_encoded_iv>",
     "data": "<base64_encoded_encrypted_data>"
   }

请使用 Python 和 cryptography 库实现并确保代码健壮、安全，包含适当的异常处理和日志记录。
```

## 部署考虑事项

1. **版本迁移**：
   - 考虑为老客户端维护旧版加密接口
   - 在升级期间可能需要同时支持新旧版本

2. **性能影响**：
   - HKDF派生步骤会略微增加服务端负载
   - 可以考虑将密集型加密操作放在后台线程执行

3. **监控**：
   - 添加指标以跟踪加密操作的成功/失败率
   - 记录不同版本客户端的使用情况，帮助确定何时可以停止支持旧版本

## 结语

通过实施这些更改，服务端将能够生成符合新规范的加密离线包，解决之前数据集解密中遇到的问题。新的加密方案通过使用标准化的密钥派生函数，确保了无论会话密钥长度如何，都能生成适合AES加密的标准长度密钥。 