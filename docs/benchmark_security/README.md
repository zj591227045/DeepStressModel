# DeepStressModel 基准测试安全方案

## 概述

本目录包含 DeepStressModel 基准测试工具的安全实现方案，主要解决以下问题：

1. 在客户端开源的情况下，如何确保测试日志的真实性和完整性
2. 如何支持离线测试模式下的安全加密
3. 如何防止测试结果被篡改或伪造
4. 服务端如何安全验证和处理加密的测试日志

安全方案采用非对称加密（RSA）+ 对称加密（AES-GCM）+ 数字签名的混合架构，确保了数据的机密性、完整性和不可否认性。

## 文件目录

本目录包含以下文件：

- `README.md` - 本文档，提供总体概述和导航
- `benchmark_security_scheme.md` - 详细的安全方案设计文档
- `benchmark_log_encrypt.py` - 客户端加密实现示例
- `benchmark_log_decrypt.py` - 服务端解密实现示例
- `ai_development_guide.md` - 针对AI开发者的安全模块开发指南
- `server_api_prompt.md` - 服务端API实现指南
- `client_encrypt_prompt.md` - 客户端加密模块开发指南

## 安全架构概述

安全架构基于以下核心原则：

1. **公钥混淆保护**：
   - 服务器持有私钥，客户端内置混淆的公钥
   - 公钥被分割并混淆存储，防止直接提取
   - 运行时动态重组公钥

2. **混合加密机制**：
   - 使用随机生成的会话密钥（AES-256）加密测试日志
   - 使用RSA公钥加密会话密钥
   - 采用AES-GCM模式提供认证加密功能

3. **数字签名与验证**：
   - 对原始测试日志计算哈希值
   - 使用从会话密钥派生的密钥生成HMAC签名
   - 添加时间戳，防止重放攻击

4. **多层次验证**：
   - 格式和版本验证
   - 时间戳验证（防止重放）
   - 签名验证（确保完整性）

5. **APIKEY一致性验证**：
   - 测试日志的加密与验证需使用相同的APIKEY
   - 防止未授权用户提交或验证测试记录
   - APIKEY哈希值嵌入在签名数据中

## 主要功能

### 客户端加密模块

客户端加密模块提供以下功能：

- 公钥混淆与保护
- 测试日志加密
- 数字签名生成
- APIKEY绑定
- 离线加密支持
- 服务器上传功能

### 服务端解密模块

服务端解密模块提供以下功能：

- 加密日志格式验证
- 会话密钥解密
- 测试日志解密
- 签名验证
- APIKEY验证
- 验证报告生成

### API服务

API服务提供以下功能：

- 测试日志上传、解密、验证和存储（单一接口）
- 返回上传状态和验证结果
- 对有效测试日志进行数据库存储
- APIKEY认证和授权

## 安全保障措施

安全方案实现了多重保障措施：

1. **数据加密**：使用AES-GCM提供认证加密，确保数据机密性和完整性
2. **公钥保护**：通过混淆和分割保护客户端中的公钥
3. **数字签名**：使用HMAC-SHA256进行签名，防止数据篡改
4. **时间戳验证**：防止重放攻击
5. **异常处理**：全面的错误处理和安全日志
6. **APIKEY绑定**：确保只有拥有正确APIKEY的用户才能提交和验证测试记录

## 使用指南

### 客户端加密

```python
# 示例：使用客户端加密模块加密测试日志
from benchmark_security.encrypt import BenchmarkEncryption

# 初始化加密器
encryptor = BenchmarkEncryption()

# 加密测试日志
encrypted_log = encryptor.encrypt_benchmark_log(test_log_data, api_key="your_api_key")

# 加密并保存到文件
encryptor.encrypt_and_save(test_log_data, "encrypted_log.json", api_key="your_api_key")

# 加密并上传到服务器
metadata = {
    "submitter": "测试工程师",
    "model_name": "TestModel-1",
    "model_version": "1.0.0",
    "hardware_info": "CPU: i9-12900K, RAM: 64GB",
    "notes": "性能基准测试"
}

result = encryptor.encrypt_and_upload(
    test_log_data,
    api_key="your_api_key",
    server_url="https://benchmark.example.com/api/v1/benchmark/upload",
    metadata=metadata
)
```

### 服务端解密

```python
# 示例：使用服务端解密模块解密和验证测试日志
from benchmark_security.decrypt import decrypt_and_verify

# 解密并验证
result = decrypt_and_verify(encrypted_package, api_key="your_api_key")

if result["validation"]["is_valid"]:
    # 验证成功，处理解密后的数据
    log_data = result["log_data"]
    print(f"验证成功，测试ID: {log_data.get('id')}")
else:
    # 验证失败，处理错误
    errors = result["validation"].get("errors", [])
    print(f"验证失败: {', '.join(errors)}")
```

## 安全考量

使用本安全方案时，请注意：

1. **私钥保护**：服务端私钥必须安全存储，避免泄露
2. **APIKEY管理**：正确管理和保护APIKEY
3. **加密更新**：定期更新加密算法和密钥，提高安全性
4. **错误处理**：正确处理和响应错误和异常情况
5. **日志记录**：记录所有重要操作，但避免记录敏感信息

## 更新日志

### 2024-03-16
- 添加APIKEY验证机制
- 简化API设计，实现单一上传接口
- 改进文档和示例代码
- 增强错误处理和验证逻辑

### 2024-03-10
- 初始版本发布
- 实现基本加密和解密功能
- 创建基础文档 