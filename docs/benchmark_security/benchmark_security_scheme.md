# DeepStressModel 基准测试日志安全方案

## 1. 概述

本文档详细描述了 DeepStressModel 基准测试工具中，测试日志的安全生成、加密、传输和验证方案。该方案旨在解决以下挑战：

- 客户端代码是开源的，需要保护加密机制不被轻易破解
- 支持离线测试模式，无需实时连接服务器即可完成加密
- 确保测试日志的完整性和真实性，防止篡改
- 允许服务端验证测试日志的合法性

## 2. 安全架构设计

### 2.1 整体架构

我们采用非对称加密（RSA）+ 数字签名的混合加密架构：

```
┌───────────────┐     ┌────────────────┐     ┌───────────────┐
│  测试日志生成  │────▶│ 混合加密与签名  │────▶│  加密日志存储  │
└───────────────┘     └────────────────┘     └───────────────┘
                                                     │
                                                     ▼
┌───────────────┐     ┌────────────────┐     ┌───────────────┐
│  服务端验证    │◀────│  解密与验签     │◀────│  日志上传     │
└───────────────┘     └────────────────┘     └───────────────┘
```

### 2.2 核心安全机制

1. **公钥保护机制**：
   - 服务器持有私钥，客户端内置公钥
   - 公钥本身通过代码混淆和特殊编码保护，防止直接提取
   - 公钥分散存储在多个位置，运行时动态组装

2. **混合加密**：
   - 使用随机生成的对称密钥（AES）加密测试日志数据
   - 使用非对称加密（RSA）加密对称密钥
   - 结合多层加密确保数据安全

3. **数字签名**：
   - 对原始测试日志进行哈希处理（SHA-256）
   - 将哈希值包含在加密数据中，服务端验证完整性
   - 添加时间戳和随机盐值，防止重放攻击

4. **APIKEY验证**：
   - 使用APIKEY生成加密哈希，确保数据来源的一致性
   - 防止未授权用户提交伪造的测试记录
   - 只有使用相同APIKEY的用户才能验证测试记录

## 3. 加密方案详细设计

### 3.1 加密算法选择

- **对称加密**：AES-256-GCM
  - 高效率，适合大量数据
  - GCM模式提供认证和完整性保护
  - 256位密钥提供足够的安全强度

- **非对称加密**：RSA-2048-OAEP
  - 用于保护会话密钥
  - OAEP填充提供额外安全保护
  - 2048位密钥在安全性和性能间取得平衡

- **哈希算法**：SHA-256
  - 用于数据完整性校验
  - 安全强度足够，计算效率高

- **消息认证码**：HMAC-SHA256
  - 用于验证数据完整性和来源
  - 基于密钥的哈希提供更强保护

### 3.2 加密数据格式

加密后的测试记录以JSON格式存储，包含以下字段：

```json
{
  "format_version": "1.0",
  "encrypted_session_key": "使用RSA加密的会话密钥（Base64编码）",
  "encrypted_data": {
    "nonce": "AES-GCM加密用的Nonce（Base64编码）",
    "ciphertext": "AES-GCM加密的数据（Base64编码）"
  },
  "signature_data": {
    "log_hash": "原始日志的SHA-256哈希（Base64编码）",
    "timestamp": 1613475642,
    "nonce": "随机值，防止重放攻击",
    "api_key_hash": "APIKEY哈希值（Base64编码）"
  },
  "signature": "基于signature_data的HMAC签名（Base64编码）",
  "timestamp": "ISO格式的加密时间"
}
```

### 3.3 加密流程

1. **生成随机会话密钥**：
   ```python
   def generate_session_key():
       # 生成256位随机密钥
       return os.urandom(32)  # 32字节 = 256位
   ```

2. **使用AES-GCM加密测试日志**：
   ```python
   def encrypt_aes_gcm(session_key, log_data):
       # 生成随机Nonce
       nonce = os.urandom(12)  # AES-GCM推荐12字节
       
       # 创建加密器
       cipher = Cipher(
           algorithms.AES(session_key),
           modes.GCM(nonce),
           backend=default_backend()
       )
       encryptor = cipher.encryptor()
       
       # 加密数据
       log_json = json.dumps(log_data).encode('utf-8')
       ciphertext = encryptor.update(log_json) + encryptor.finalize()
       
       # 获取认证标签
       tag = encryptor.tag
       
       # 合并密文和认证标签
       encrypted_data = ciphertext + tag
       
       return {
           "nonce": base64.b64encode(nonce).decode('utf-8'),
           "ciphertext": base64.b64encode(encrypted_data).decode('utf-8')
       }
   ```

3. **使用RSA加密会话密钥**：
   ```python
   def encrypt_session_key(session_key):
       # 获取公钥（通过混淆保护）
       public_key = reassemble_public_key()
       
       # RSA-OAEP加密
       encrypted_key = public_key.encrypt(
           session_key,
           padding.OAEP(
               mgf=padding.MGF1(algorithm=hashes.SHA256()),
               algorithm=hashes.SHA256(),
               label=None
           )
       )
       
       return base64.b64encode(encrypted_key).decode('utf-8')
   ```

4. **生成数据哈希和签名**：
   ```python
   def generate_signature(session_key, log_data, api_key):
       # 计算原始数据哈希
       log_json = json.dumps(log_data).encode('utf-8')
       log_hash = hashlib.sha256(log_json).digest()
       
       # 生成API密钥哈希
       api_key_hash = generate_api_key_hash(session_key, api_key)
       
       # 构建签名数据
       signature_data = {
           "log_hash": base64.b64encode(log_hash).decode('utf-8'),
           "timestamp": int(time.time()),
           "nonce": secrets.token_hex(16),
           "api_key_hash": base64.b64encode(api_key_hash).decode('utf-8')
       }
       
       # 派生签名密钥
       signing_key = derive_signing_key(session_key, signature_data["timestamp"])
       
       # 计算HMAC签名
       signature = hmac.new(
           signing_key,
           json.dumps(signature_data, sort_keys=True).encode('utf-8'),
           hashlib.sha256
       ).digest()
       
       return signature_data, base64.b64encode(signature).decode('utf-8')
   ```

5. **组装加密数据包**：
   ```python
   def encrypt_benchmark_log(log_data, api_key):
       # 生成会话密钥
       session_key = generate_session_key()
       
       # 加密日志数据
       encrypted_data = encrypt_aes_gcm(session_key, log_data)
       
       # 加密会话密钥
       encrypted_session_key = encrypt_session_key(session_key)
       
       # 生成签名
       signature_data, signature = generate_signature(session_key, log_data, api_key)
       
       # 组装最终数据包
       return {
           "format_version": "1.0",
           "encrypted_session_key": encrypted_session_key,
           "encrypted_data": encrypted_data,
           "signature_data": signature_data,
           "signature": signature,
           "timestamp": datetime.now().isoformat()
       }
   ```

## 4. 验证方案详细设计

### 4.1 验证前检查

在解密和深度验证前，首先进行基本格式检查：

1. **格式检查**：
   ```python
   def validate_format(encrypted_package):
       # 验证加密包含必要字段
       required_fields = ["format_version", "encrypted_session_key", 
                         "encrypted_data", "signature_data", "signature"]
       return all(field in encrypted_package for field in required_fields)
   ```

2. **时间戳验证**：
   ```python
   def validate_timestamp(signature_data):
       current_time = int(time.time())
       timestamp = signature_data.get("timestamp", 0)
       # 允许5分钟的时间偏差（防止时间同步问题）
       return abs(current_time - timestamp) < 300
   ```

### 4.2 解密流程

1. **使用私钥解密会话密钥**：
   ```python
   def decrypt_session_key(encrypted_session_key):
       # 加载服务器私钥
       private_key = load_private_key()
       # 解密会话密钥
       return private_key.decrypt(
           base64.b64decode(encrypted_session_key),
           padding.OAEP(
               mgf=padding.MGF1(algorithm=hashes.SHA256()),
               algorithm=hashes.SHA256(),
               label=None
           )
       )
   ```

2. **使用会话密钥解密测试日志**：
   ```python
   def decrypt_log_data(session_key, encrypted_data):
       # 使用AES-GCM解密
       return decrypt_aes_gcm(session_key, base64.b64decode(encrypted_data))
   ```

3. **验证签名**：
   ```python
   def verify_signature(session_key, signature_data, signature, decrypted_log):
       # 计算解密后日志的哈希值
       actual_hash = hashlib.sha256(decrypted_log).digest()
       expected_hash = base64.b64decode(signature_data["log_hash"])
       
       # 验证哈希值匹配
       if not hmac.compare_digest(actual_hash, expected_hash):
           return False
           
       # 派生签名密钥
       signing_key = derive_signing_key(session_key, signature_data["timestamp"])
       
       # 验证HMAC签名
       calculated_signature = hmac.new(
           signing_key, 
           json.dumps(signature_data).encode(), 
           hashlib.sha256
       ).digest()
       
       return hmac.compare_digest(calculated_signature, base64.b64decode(signature))
   ```

4. **验证APIKEY绑定**：
   ```python
   def verify_api_key_binding(session_key, signature_data, api_key):
       # 从签名数据中提取API密钥哈希
       stored_api_key_hash_b64 = signature_data.get("api_key_hash")
       if not stored_api_key_hash_b64:
           return False  # 不包含API密钥哈希，验证失败
       
       stored_api_key_hash = base64.b64decode(stored_api_key_hash_b64)
       
       # 使用当前用户的API密钥生成哈希
       current_hash = generate_api_key_hash(session_key, api_key)
       
       # 安全比较两个哈希值
       return hmac.compare_digest(stored_api_key_hash, current_hash)
   ```

## 5. 安全增强措施

### 5.1 公钥混淆与保护

为防止直接从客户端提取公钥，我们使用以下技术混淆公钥：

```python
def obfuscate_public_key(public_key_pem):
    # 1. 将公钥转换为字节
    key_bytes = public_key_pem.encode()
    
    # 2. 使用自定义编码（非标准Base64）
    custom_encoding_table = generate_custom_encoding_table(seed=42)
    encoded_key = custom_encode(key_bytes, custom_encoding_table)
    
    # 3. 分割成多个片段
    fragments = split_into_fragments(encoded_key, fragment_count=5)
    
    # 4. 为每个片段添加混淆数据
    obfuscated_fragments = []
    for i, fragment in enumerate(fragments):
        # 添加混淆头和尾
        obfuscation_prefix = generate_obfuscation_data(f"prefix_{i}", len(fragment)//3)
        obfuscation_suffix = generate_obfuscation_data(f"suffix_{i}", len(fragment)//4)
        
        # 组合片段
        obfuscated_fragment = obfuscation_prefix + fragment + obfuscation_suffix
        
        # 添加位置信息（混淆）
        position_marker = encrypt_position(i, len(fragments))
        
        obfuscated_fragments.append({
            "data": obfuscated_fragment,
            "marker": position_marker
        })
    
    # 5. 打乱片段顺序
    random.shuffle(obfuscated_fragments)
    
    return obfuscated_fragments

def reassemble_public_key():
    # 1. 获取混淆的公钥片段
    obfuscated_fragments = get_obfuscated_key_fragments()
    
    # 2. 对片段排序
    sorted_fragments = sorted(obfuscated_fragments, 
                             key=lambda x: decrypt_position(x["marker"]))
    
    # 3. 提取每个片段中的实际数据
    actual_fragments = []
    for i, fragment in enumerate(sorted_fragments):
        # 去除混淆头和尾
        prefix_len = len(fragment["data"]) // 3
        suffix_len = len(fragment["data"]) // 4
        actual_fragment = fragment["data"][prefix_len:-suffix_len]
        actual_fragments.append(actual_fragment)
    
    # 4. 合并片段
    encoded_key = "".join(actual_fragments)
    
    # 5. 使用自定义解码
    custom_encoding_table = generate_custom_encoding_table(seed=42)
    key_bytes = custom_decode(encoded_key, custom_encoding_table)
    
    # 6. 转换回PEM格式
    public_key_pem = key_bytes.decode()
    
    return load_public_key(public_key_pem)
```

### 5.2 防篡改机制

添加以下机制防止测试日志篡改：

1. **数据完整性检查**：使用HMAC验证数据未被修改
2. **时间戳验证**：防止重放攻击
3. **测试数据关联性检查**：验证测试日志内部数据的一致性

### 5.3 APIKEY验证机制

为确保测试记录的真实性和一致性，我们实现了基于APIKEY的验证机制：

1. **APIKEY一致性验证**：
   - 客户端加密过程中包含APIKEY哈希
   - 服务端验证上传者的APIKEY与加密时使用的APIKEY是否一致
   - 只有使用相同APIKEY的用户才能提交和验证测试记录

2. **实现方式**：
   ```python
   def generate_api_key_hash(session_key: bytes, api_key: str) -> bytes:
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

3. **验证流程**：
   - 客户端：在加密过程中将APIKEY哈希嵌入签名数据
   - 服务端：使用当前用户的APIKEY重新计算哈希并与嵌入值比较
   - 验证失败则拒绝测试记录

4. **安全性考量**：
   - APIKEY本身不会在加密数据中明文存储
   - 使用密钥派生函数将APIKEY与会话密钥绑定
   - 即使获取了加密数据也无法提取原始APIKEY

## 6. 服务端API设计

### 6.1 API端点

API服务器采用简化设计，仅提供一个单一的端点：

1. **测试日志上传与处理（一体化接口）**
   - `POST /api/v1/benchmark/upload`
   - 功能：
     - 接收加密的测试日志
     - 执行格式验证
     - 使用服务器私钥解密测试日志
     - 验证数据签名和完整性
     - 将验证成功的测试记录保存到数据库
     - 返回处理结果和状态

这种简化设计将所有操作集成到单一接口中，减少了API复杂性，同时保持了完整的功能。

## 7. 离线加密支持

离线加密模式下，测试日志会被安全加密并存储在本地，等待后续上传：

```python
def encrypt_and_store_offline_log(log_data, output_path, api_key):
    # 1. 加密测试日志
    encrypted_package = encrypt_log(log_data, api_key)
    
    # 2. 存储加密后的数据
    with open(output_path, 'w') as f:
        json.dump(encrypted_package, f)
    
    # 3. 生成元数据（用于后续验证）
    metadata = {
        "timestamp": encrypted_package["signature_data"]["timestamp"],
        "log_hash": encrypted_package["signature_data"]["log_hash"],
        "nonce": encrypted_package["signature_data"]["nonce"]
    }
    
    # 4. 返回元数据（可用于校验或显示）
    return metadata
```

## 8. 安全注意事项

- **密钥管理**：服务端私钥必须安全存储，避免泄露
- **代码混淆**：客户端关键代码应进行混淆，增加逆向工程难度
- **定期更新**：定期更新加密算法和密钥，提高安全性
- **防护措施**：添加反调试和完整性检查，防止运行时篡改
- **最小权限**：客户端只包含必要的加密组件，避免包含敏感信息

## 9. 实现示例

完整的加密和解密实现示例见附带的示例代码：
- `benchmark_log_encrypt.py` - 客户端加密实现
- `benchmark_log_decrypt.py` - 服务端解密实现 