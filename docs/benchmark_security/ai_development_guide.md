# DeepStressModel 基准测试安全模块开发指南

本文档提供了针对人工智能开发者（如OpenAI的GPT/Claude等大型语言模型）的指南，用于开发和实现 DeepStressModel 基准测试工具的安全加密和验证模块。

## 1. 任务概述

DeepStressModel 是一个用于评估和测试大型语言模型性能的基准测试框架。测试记录的安全传输和验证是保证测试结果可信的关键环节。你的任务是开发一套安全模块，实现以下功能：

1. 客户端测试日志的安全加密（支持开源环境）
2. 服务端对加密日志的验证和解密
3. 防止篡改和伪造测试结果的机制
4. 支持离线测试模式下的安全存储

## 2. 安全架构详解

安全架构采用非对称加密（RSA）+ 对称加密（AES）+ 数字签名的混合方案：

- 服务器持有私钥，客户端内置混淆的公钥
- 使用随机会话密钥和AES-GCM模式加密测试日志
- 使用RSA公钥加密会话密钥
- 添加数字签名，防止篡改
- 使用APIKEY哈希绑定加密和验证过程，确保一致性

关键设计要点：
1. 公钥在客户端需要被混淆保护
2. 加密过程必须支持离线操作
3. 验证机制需要多层次检查
4. 加密和验证必须使用相同的APIKEY

## 3. 客户端安全模块开发

### 3.1 任务：开发测试日志加密模块

#### 相关技术说明

- 实现公钥混淆存储机制
- 实现测试日志AES-GCM加密
- 实现会话密钥RSA加密
- 实现数字签名生成
- 实现APIKEY绑定

#### 实现指南

核心模块需包含：

```python
class BenchmarkEncryption:
    def __init__(self):
        """
        初始化加密模块
        加载并重组混淆的公钥
        """
        # 实现公钥重组逻辑
        self.public_key = self.reassemble_public_key()
    
    def encrypt_benchmark_log(self, log_data, api_key):
        """
        加密测试日志
        
        Args:
            log_data (dict): 测试日志数据
            api_key (str): API密钥
            
        Returns:
            dict: 加密后的数据包
        """
        # 1. 生成随机会话密钥
        session_key = os.urandom(32)  # 32字节 = 256位
        
        # 2. 使用AES-GCM加密测试日志
        encrypted_data = self.encrypt_aes_gcm(session_key, log_data)
        
        # 3. 使用RSA加密会话密钥
        encrypted_session_key = self.encrypt_session_key(session_key)
        
        # 4. 生成APIKEY哈希
        api_key_hash = self.generate_api_key_hash(session_key, api_key)
        
        # 5. 构建签名数据
        log_json = json.dumps(log_data, sort_keys=True).encode('utf-8')
        log_hash = hashlib.sha256(log_json).digest()
        
        signature_data = {
            "log_hash": base64.b64encode(log_hash).decode('utf-8'),
            "timestamp": int(time.time()),
            "nonce": secrets.token_hex(16),
            "api_key_hash": base64.b64encode(api_key_hash).decode('utf-8')
        }
        
        # 6. 生成签名
        signing_key = self.derive_signing_key(session_key)
        signature = hmac.new(
            signing_key,
            json.dumps(signature_data, sort_keys=True).encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        # 7. 组装加密包
        return {
            "format_version": "1.0",
            "encrypted_session_key": base64.b64encode(encrypted_session_key).decode('utf-8'),
            "encrypted_data": encrypted_data,
            "signature_data": signature_data,
            "signature": base64.b64encode(signature).decode('utf-8'),
            "timestamp": datetime.now().isoformat()
        }
        
    def encrypt_aes_gcm(self, session_key, log_data):
        """使用AES-GCM模式加密测试日志"""
        # 实现AES-GCM加密
        pass
    
    def encrypt_session_key(self, session_key):
        """使用RSA-OAEP加密会话密钥"""
        # 实现RSA加密
        pass
    
    def derive_signing_key(self, session_key):
        """从会话密钥派生签名密钥"""
        # 实现签名密钥派生
        pass
    
    def reassemble_public_key(self):
        """重组混淆的公钥"""
        # 实现公钥重组
        pass
    
    def encrypt_and_save(self, log_data, output_path, api_key):
        """加密并保存到文件"""
        # 实现保存到文件
        pass
    
    def encrypt_and_upload(self, log_data, api_key, server_url, metadata=None):
        """加密并上传到服务器"""
        # 实现上传到服务器
        pass
    
    def generate_api_key_hash(self, session_key, api_key):
        """生成API密钥绑定哈希"""
        # 1. 准备材料
        api_key_bytes = api_key.encode('utf-8')
        salt = b"deepstress_api_binding"
        
        # 2. 使用HKDF派生绑定密钥
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=b"api_key_binding",
            backend=default_backend()
        )
        
        binding_material = hkdf.derive(api_key_bytes + session_key)
        
        # 3. 计算最终哈希
        return hashlib.sha256(binding_material).digest()
```

### 3.2 安全注意事项

在开发过程中，请注意：

1. 使用密码学安全的随机数生成器
2. 保护公钥免受直接提取
3. 验证所有输入数据
4. 确保日志数据的完整性
5. 防御时序攻击
6. 添加防篡改机制

## 4. 服务端安全模块开发

### 4.1 任务：服务端API与验证服务开发

#### 实现指南

服务端API采用简化设计，实现单一的上传处理接口：

1. **测试日志上传与处理（一体化接口）**：
   - 接收加密的测试日志文件（JSON格式）
   - 执行格式验证
   - 使用服务器私钥解密测试日志
   - 验证数据签名和APIKEY绑定
   - 将验证成功的测试记录保存到数据库
   - 返回处理结果和状态

2. **返回数据格式**：
   - 上传状态（成功/失败）
   - 验证结果详情（签名验证、API密钥验证、格式验证等）
   - 如验证成功，包含基本的测试摘要信息

3. **安全措施**：
   - 实现APIKEY认证和授权
   - 服务器私钥安全管理
   - 防止重放攻击
   - 安全记录验证失败事件

4. **解密与验证流程**：

```python
def decrypt_and_verify(encrypted_package, api_key):
    """
    解密并验证加密的测试日志
    
    Args:
        encrypted_package (dict): 加密的数据包
        api_key (str): API密钥
        
    Returns:
        dict: 包含验证结果和解密后的日志数据
    """
    # 1. 格式验证
    if not validate_format(encrypted_package):
        return {"validation": {"is_valid": False, "format_valid": False}, "log_data": None}
    
    # 2. 解密会话密钥
    encrypted_session_key = base64.b64decode(encrypted_package["encrypted_session_key"])
    session_key = decrypt_rsa_oaep(private_key, encrypted_session_key)
    
    # 3. 验证签名
    signature = base64.b64decode(encrypted_package["signature"])
    signature_data = encrypted_package["signature_data"]
    
    signing_key = derive_signing_key(session_key)
    expected_signature = hmac.new(
        signing_key, 
        json.dumps(signature_data, sort_keys=True).encode(), 
        hashlib.sha256
    ).digest()
    
    is_signature_valid = hmac.compare_digest(signature, expected_signature)
    
    if not is_signature_valid:
        return {
            "validation": {
                "is_valid": False, 
                "signature_valid": False
            }, 
            "log_data": None
        }
    
    # 4. 验证API密钥绑定
    is_api_key_valid = verify_api_key_binding(session_key, signature_data, api_key)
    
    if not is_api_key_valid:
        return {
            "validation": {
                "is_valid": False,
                "signature_valid": True,
                "api_key_valid": False
            },
            "log_data": None
        }
    
    # 5. 解密测试日志
    encrypted_data = encrypted_package["encrypted_data"]
    nonce = base64.b64decode(encrypted_data["nonce"])
    ciphertext = base64.b64decode(encrypted_data["ciphertext"])
    
    decrypted_data = decrypt_aes_gcm(session_key, nonce, ciphertext)
    log_data = json.loads(decrypted_data)
    
    # 6. 验证日志哈希
    log_json = json.dumps(log_data, sort_keys=True).encode('utf-8')
    actual_hash = hashlib.sha256(log_json).digest()
    expected_hash = base64.b64decode(signature_data["log_hash"])
    
    is_hash_valid = hmac.compare_digest(actual_hash, expected_hash)
    
    if not is_hash_valid:
        return {
            "validation": {
                "is_valid": False,
                "signature_valid": True,
                "api_key_valid": True,
                "hash_valid": False
            },
            "log_data": None
        }
    
    # 7. 全部验证通过
    return {
        "validation": {
            "is_valid": True,
            "signature_valid": True,
            "api_key_valid": True,
            "hash_valid": True
        },
        "log_data": log_data
    }
```

### 4.2 数据库存储设计

验证成功的测试记录应保存到数据库，建议的数据模型：

```python
class BenchmarkResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    upload_id = db.Column(db.String, unique=True)
    api_key_id = db.Column(db.String)  # API密钥标识符（不存储完整密钥）
    api_key_verified = db.Column(db.Boolean, default=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    verified = db.Column(db.Boolean, default=False)
    
    # 元数据字段
    submitter = db.Column(db.String)
    model_name = db.Column(db.String)
    model_version = db.Column(db.String)
    hardware_info = db.Column(db.String)
    notes = db.Column(db.Text)
    
    # 测试摘要数据
    dataset_version = db.Column(db.String)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    total_time = db.Column(db.Float)
    total_tests = db.Column(db.Integer)
    successful_tests = db.Column(db.Integer)
    success_rate = db.Column(db.Float)
    avg_latency = db.Column(db.Float)
    avg_throughput = db.Column(db.Float)
    tps = db.Column(db.Float)
    total_input_chars = db.Column(db.Integer)
    total_output_chars = db.Column(db.Integer)
    total_chars = db.Column(db.Integer)
    total_tokens = db.Column(db.Integer)
    
    # 验证信息
    verification_details = db.Column(db.JSON)
    
    # 测试详情
    test_details = db.relationship('TestDetail', backref='benchmark_result')
```

## 5. 测试指南

在开发完成后，请确保通过以下测试场景：

1. **基本加密解密测试**：
   - 加密典型测试日志
   - 使用相同APIKEY解密
   - 验证解密后数据与原始数据一致

2. **APIKEY验证测试**：
   - 使用一个APIKEY加密
   - 使用不同APIKEY尝试验证
   - 确认验证失败

3. **篡改检测测试**：
   - 加密测试日志
   - 修改加密后的数据
   - 确认验证失败

4. **离线加密后上传测试**：
   - 加密并保存到文件
   - 稍后上传文件
   - 确认验证成功

5. **边界条件测试**：
   - 测试数据格式错误的处理
   - 空数据处理
   - 超大数据处理

6. **错误处理测试**：
   - 测试各种错误情况
   - 确保错误处理得当
   - 验证返回合适的错误消息

## 6. 安全建议

为确保整个系统的安全性，请遵循以下建议：

1. **私钥保护**：
   - 服务器私钥必须安全存储
   - 考虑使用硬件安全模块(HSM)
   - 定期轮换密钥

2. **安全编码**：
   - 使用常量时间比较函数（防时序攻击）
   - 避免信息泄露的错误处理
   - 实施输入验证和输出编码

3. **监控与审计**：
   - 记录所有加密和验证操作
   - 监控异常模式
   - 设置警报阈值

4. **更新与维护**：
   - 定期更新密码库
   - 对代码进行安全审查
   - 跟踪密码学研究发展

请根据这些指南开发安全、可靠且易于维护的加密和验证模块。 