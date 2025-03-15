# DeepStressModel 测试记录加密模块开发指南

你是一位专业的密码学工程师，擅长设计和实现安全的加密系统。请为DeepStressModel基准测试工具开发一个完整的测试记录加密模块。

## 背景介绍

DeepStressModel是一个用于评估大型语言模型性能的基准测试工具。测试工具需要生成加密的测试记录，确保测试结果的真实性和不可篡改性。由于测试工具是开源的，我们需要设计一个安全的加密方案，即使攻击者获取了源代码也难以伪造有效的测试记录。

## 安全设计原则

1. **混合加密架构**：使用RSA非对称加密与AES对称加密相结合
2. **数字签名**：确保数据完整性和来源真实性
3. **APIKEY绑定**：确保只有使用相同APIKEY的用户才能加密和验证测试记录
4. **公钥保护**：在客户端代码中保护公钥，防止直接提取

## 技术规范

### 加密算法要求

- **会话密钥**：使用AES-256-GCM进行对称加密
- **密钥加密**：使用RSA-2048-OAEP进行会话密钥加密
- **数字签名**：使用HMAC-SHA256生成签名
- **APIKEY绑定**：使用HKDF派生密钥与会话密钥绑定

### 服务器公钥

使用以下服务器公钥（已提供在项目中）：

```
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA7gSFgB9fNIvETchyd2SR
KlckmvnBhxtN1auoW65yVhJYZ+ElZ8drQ6Cx6mOjy5t5OSG/MATl8jfjaLDLEKij
dcsrv81sXvBJ0heNBeqz4Qasx4C42ot+zaaehPgAaz4MnsXg//zkJZldGtaoVtT1
7fTLN97qrh1PyqRjRcwCtfZA90+tCkelIH28a74updMkUXcu6Dd4NcPeUgXPd5Kf
iOF5N8JUMSfbqU+wAo3KHqR/r8gi/nLhggYNSts49zOdJiMBlL4R/kQe1jwQUUEn
aJZ7JTEcsKnr6oW4WJmQqZ6gSKHI8rljofJ8jwwYz3k1O24geCxIFZjE4jVicen+
zQIDAQAB
-----END PUBLIC KEY-----
```

## 功能需求

开发一个完整的测试记录加密模块，包含以下功能：

1. **核心加密功能**：
   - 使用AES-GCM加密测试记录JSON数据
   - 使用RSA加密随机会话密钥
   - 生成包含APIKEY哈希的数字签名
   - 支持测试记录打包和格式化

2. **公钥保护机制**：
   - 实现公钥混淆存储
   - 设计动态重组公钥的方法
   - 增加逆向工程难度

3. **APIKEY验证机制**：
   - 实现APIKEY哈希并嵌入签名数据
   - 确保加密和验证必须使用相同APIKEY

4. **离线加密支持**：
   - 支持将加密后的测试记录保存到本地文件
   - 提供元数据便于后续验证

5. **服务器上传功能**：
   - 提供将加密测试记录上传到服务器的功能
   - 处理服务器返回的验证结果

6. **错误处理与日志**：
   - 全面的错误处理机制
   - 安全日志（不泄露敏感信息）

## 测试记录格式

加密前的测试记录应包含以下字段：

```json
{
  "status": "success",
  "dataset_version": "版本标识",
  "start_time": 1742039446.924232,
  "end_time": 1742039527.5310478,
  "total_time": 80.6068,
  "total_tests": 100,
  "successful_tests": 100,
  "success_rate": 1.0,
  "avg_latency": 49.6409,
  "avg_throughput": 0.5455,
  "tps": 1.2405,
  "total_input_chars": 2292,
  "total_output_chars": 32631,
  "total_chars": 34923,
  "total_tokens": 9168,
  "results": [
    {
      "id": 1,
      "input": "测试输入内容",
      "output": "测试输出内容",
      "expected_output": "",
      "latency": 31.1440,
      "throughput": 0.7063,
      "token_throughput": 4.1741,
      "input_tokens": 21,
      "output_tokens": 109,
      "tokens": 130,
      "status": "success",
      "timestamp": 1742039478071,
      "start_time": 1742039446927,
      "end_time": 1742039478071
    }
    // 更多测试结果...
  ]
}
```

## 实现指南

### 1. 模块结构

创建一个名为`benchmark_encrypt.py`的Python模块，包含以下组件：

```python
# 主要类和函数
class BenchmarkEncryption:
    def __init__(self):
        # 初始化，加载公钥等
        pass
        
    def encrypt_benchmark_log(self, log_data, api_key):
        # 主加密函数
        pass
        
    def encrypt_and_save(self, log_data, output_path, api_key):
        # 加密并保存到文件
        pass
        
    def encrypt_and_upload(self, log_data, api_key, server_url, metadata=None):
        # 加密并上传到服务器
        pass
```

### 2. 加密流程设计

加密流程应按照以下步骤实现：

1. **会话密钥生成**：
   ```python
   # 生成随机会话密钥
   session_key = secrets.token_bytes(32)  # 256位随机密钥
   ```

2. **测试记录加密**：
   ```python
   # 使用AES-GCM模式加密
   encrypted_log = encrypt_aes_gcm(session_key, log_json)
   ```

3. **会话密钥加密**：
   ```python
   # 使用公钥加密会话密钥
   encrypted_session_key = encrypt_rsa_oaep(public_key, session_key)
   ```

4. **APIKEY处理**：
   ```python
   # 生成API密钥哈希（不直接存储API密钥）
   api_key_hash = generate_api_key_hash(session_key, api_key)
   ```

5. **数字签名生成**：
   ```python
   # 构建签名数据（包含API密钥哈希）
   signature_data = {
       "log_hash": base64.b64encode(log_hash).decode(),
       "timestamp": int(time.time()),
       "nonce": secrets.token_hex(16),
       "api_key_hash": base64.b64encode(api_key_hash).decode()
   }
   
   # 生成签名
   signature = hmac.new(
       signing_key, 
       json.dumps(signature_data, sort_keys=True).encode(), 
       hashlib.sha256
   ).digest()
   ```

6. **组装加密数据包**：
   ```python
   encrypted_package = {
       "format_version": "1.0",
       "encrypted_session_key": base64.b64encode(encrypted_session_key).decode(),
       "encrypted_data": encrypted_data,
       "signature_data": signature_data,
       "signature": base64.b64encode(signature).decode(),
       "timestamp": datetime.now().isoformat()
   }
   ```

### 3. 公钥保护设计

为防止直接从客户端提取公钥，实现以下保护措施：

1. **分割存储**：将公钥分割成多个片段
2. **混淆编码**：使用自定义编码方式
3. **动态重组**：运行时动态重组公钥

```python
def obfuscate_public_key(public_key_pem):
    # 分割和混淆公钥
    # 返回混淆后的片段
    pass

def reassemble_public_key():
    # 从混淆片段重组公钥
    pass
```

### 4. APIKEY绑定实现

确保加密和验证使用相同的APIKEY：

```python
def generate_api_key_hash(session_key, api_key):
    # 使用会话密钥和APIKEY生成密钥材料
    api_key_bytes = api_key.encode('utf-8')
    salt = b"deepstress_api_binding"
    
    # 使用HKDF派生APIKEY绑定密钥
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"api_key_binding",
        backend=default_backend()
    )
    
    binding_material = hkdf.derive(api_key_bytes + session_key)
    
    # 计算APIKEY哈希（不直接存储APIKEY）
    return hashlib.sha256(binding_material).digest()
```

### 5. 服务器上传实现

实现将加密测试记录上传到服务器的功能：

```python
def encrypt_and_upload(self, log_data, api_key, server_url, metadata=None):
    """加密测试记录并上传到服务器"""
    # 1. 加密测试记录
    encrypted_package = self.encrypt_benchmark_log(log_data, api_key)
    
    # 2. 准备上传
    # 创建临时文件或直接从内存上传
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
        temp_file_path = temp_file.name
        json.dump(encrypted_package, temp_file)
    
    try:
        # 3. 准备元数据（如果有）
        meta_payload = None
        if metadata:
            meta_payload = json.dumps(metadata)
        
        # 4. 上传文件
        files = {
            'file': ('benchmark_log.json', open(temp_file_path, 'rb'), 'application/json')
        }
        
        data = {}
        if meta_payload:
            data['metadata'] = meta_payload
        
        # 5. 发送请求
        headers = {
            'Authorization': f'APIKEY {api_key}'
        }
        
        response = requests.post(
            server_url,
            headers=headers,
            files=files,
            data=data
        )
        
        # 6. 处理响应
        if response.status_code == 200:
            result = response.json()
            return result
        else:
            # 处理错误
            error_msg = f"上传失败: {response.status_code}"
            try:
                error_data = response.json()
                if 'error' in error_data:
                    error_msg = f"上传失败: {error_data['error']['message']}"
            except:
                pass
            
            raise Exception(error_msg)
    
    finally:
        # 清理临时文件
        os.unlink(temp_file_path)
```

## 输出格式

加密后的测试记录应符合以下JSON格式：

```json
{
  "format_version": "1.0",
  "encrypted_session_key": "<base64_encrypted_key>",
  "encrypted_data": {
    "nonce": "<base64_nonce>",
    "ciphertext": "<base64_ciphertext>"
  },
  "signature_data": {
    "log_hash": "<base64_hash>",
    "timestamp": 1713274829,
    "nonce": "<random_hex>",
    "api_key_hash": "<base64_api_key_hash>"
  },
  "signature": "<base64_signature>",
  "timestamp": "2024-03-16T12:34:56.789Z"
}
```

## 元数据格式

当上传到服务器时，可以包含以下元数据：

```json
{
  "submitter": "用户名称或ID",
  "model_name": "测试的模型名称",
  "model_version": "模型版本",
  "hardware_info": "硬件配置信息",
  "notes": "附加说明"
}
```

## 使用示例

加密模块应提供简洁的API，便于集成到测试工具中：

```python
# 示例1：直接加密
encrypted_log = encryptor.encrypt_benchmark_log(test_log_data, api_key="your_api_key")

# 示例2：加密并保存到文件
metadata = encryptor.encrypt_and_save(test_log_data, "encrypted_log.json", api_key="your_api_key")

# 示例3：加密并上传到服务器
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

# 处理服务器响应
if result["status"] == "success":
    print(f"上传成功，ID: {result['upload_id']}")
    print(f"验证结果: {result['validation']['is_valid']}")
else:
    print(f"上传失败: {result['message']}")
```

## 错误处理

实现统一的错误处理机制，与服务端错误码对应：

```python
class EncryptionError(Exception):
    def __init__(self, code, message, details=None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

# 预定义错误类型
ERRORS = {
    "INVALID_DATA": {"code": "C1001", "message": "无效的测试数据格式"},
    "ENCRYPTION_FAILED": {"code": "C1002", "message": "加密失败"},
    "PUBLIC_KEY_ERROR": {"code": "C1003", "message": "公钥处理错误"},
    "API_KEY_ERROR": {"code": "C1004", "message": "API密钥错误"},
    "SERVER_ERROR": {"code": "C1005", "message": "服务器错误"},
    "UPLOAD_FAILED": {"code": "C1006", "message": "上传失败"}
}

# 使用方式
try:
    encrypted_data = encryptor.encrypt_benchmark_log(log_data, api_key)
except EncryptionError as e:
    print(f"错误 {e.code}: {e.message}")
    if e.details:
        print(f"详情: {e.details}")
```

## 命令行接口

提供命令行接口便于测试和使用：

```python
def main():
    import argparse
    parser = argparse.ArgumentParser(description="DeepStressModel 测试日志加密工具")
    parser.add_argument("input", help="测试日志文件路径", type=str)
    parser.add_argument("-o", "--output", help="输出文件路径", type=str, default=None)
    parser.add_argument("-k", "--api-key", help="API密钥", type=str, required=True)
    parser.add_argument("-u", "--upload", help="上传到服务器", action="store_true")
    parser.add_argument("-s", "--server", help="服务器URL", type=str, default="https://benchmark.example.com/api/v1/benchmark/upload")
    parser.add_argument("-m", "--metadata", help="元数据JSON文件路径", type=str, default=None)
    args = parser.parse_args()
    
    # 加载测试日志
    with open(args.input, 'r') as f:
        log_data = json.load(f)
    
    # 初始化加密器
    encryptor = BenchmarkEncryption()
    
    # 加载元数据
    metadata = None
    if args.metadata:
        with open(args.metadata, 'r') as f:
            metadata = json.load(f)
    
    try:
        if args.upload:
            # 加密并上传
            result = encryptor.encrypt_and_upload(
                log_data,
                api_key=args.api_key,
                server_url=args.server,
                metadata=metadata
            )
            print(json.dumps(result, indent=2))
        else:
            # 加密并保存到文件
            output_path = args.output or f"encrypted_{os.path.basename(args.input)}"
            encryptor.encrypt_and_save(log_data, output_path, api_key=args.api_key)
            print(f"已加密并保存到: {output_path}")
    
    except Exception as e:
        print(f"错误: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

## 安全考量

1. **密钥管理**：
   - 不要硬编码敏感信息
   - 安全处理内存中的密钥

2. **加密强度**：
   - 使用足够长的密钥
   - 使用安全的填充方式

3. **错误处理**：
   - 不泄露敏感信息的错误消息
   - 优雅处理异常情况

4. **防篡改**：
   - 验证所有输入数据
   - 保护公钥不被轻易提取

## 测试与验证

开发完成后，请确保模块能够通过以下测试：

1. 使用相同APIKEY加密和解密的测试
2. 使用不同APIKEY时验证失败的测试
3. 数据篡改检测测试
4. 离线加密和后续验证测试
5. 服务器上传和响应处理测试
6. 边界情况和错误处理测试

请开发一个安全、可靠且易于集成的测试记录加密模块，确保测试结果的真实性和不可篡改性。提交的代码应包含完整的注释、错误处理和单元测试。 