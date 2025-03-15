# DeepStressModel 基准测试日志验证 API 开发提示词

你是一位经验丰富的后端工程师，专注于安全系统和API设计。请为DeepStressModel基准测试系统设计并实现一个验证测试日志的安全API。

## 背景

DeepStressModel是一个大型语言模型性能基准测试系统，客户端会生成加密的测试日志并上传到服务器。系统需要保证测试结果的真实性和不可篡改性。

## 需求

设计一个简单的FastAPI接口，用于：
1. 接收加密的测试日志
2. 验证测试日志的真实性和完整性
3. 解密并处理测试结果保存到数据库

## 安全要求

1. API端点必须使用APIKEY进行认证
2. 测试日志解密过程必须安全可靠
3. 防止伪造或篡改的测试结果被接受
4. 保护服务器私钥和敏感配置

## 技术规范

### 加密算法要求

- **会话密钥**：使用AES-256-GCM进行对称加密
- **密钥加密**：使用RSA-2048-OAEP进行会话密钥加密
- **数字签名**：使用HMAC-SHA256生成签名
- **APIKEY绑定**：使用HKDF派生密钥与会话密钥绑定

### 加密数据格式

加密的测试日志必须符合以下JSON格式：

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

## API规范

请实现以下API端点：

### 测试日志上传与处理

```
POST /api/v1/benchmark/upload
Content-Type: multipart/form-data
Authorization: APIKEY {api_key}

Form Data:
- file: 加密的测试日志文件（JSON格式）
- metadata: (可选) 提交者元数据信息，JSON格式
```

#### 元数据格式

```json
{
  "submitter": "用户名称或ID",
  "model_name": "测试的模型名称",
  "model_version": "模型版本",
  "hardware_info": "硬件配置信息",
  "notes": "附加说明"
}
```

功能：
- 接收加密的测试日志
- 执行格式验证
- 使用服务器私钥解密测试日志
- 验证数据签名和APIKEY绑定
- 将验证成功的测试记录保存到数据库
- 返回处理结果和状态

返回格式：
```json
{
  "status": "success" | "error",
  "message": "处理结果描述",
  "upload_id": "生成的上传ID",
  "validation": {
    "is_valid": true | false,
    "signature_valid": true | false,
    "format_valid": true | false,
    "api_key_valid": true | false,
    "errors": []
  },
  "benchmark_summary": {
    // 如果验证成功，包含基本的测试摘要信息
  }
}
```

## 解密与验证流程

解密和验证流程应按照以下步骤实现：

1. **解析加密数据**：
   ```python
   # 解析加密的JSON数据包
   encrypted_package = json.loads(file_content)
   ```

2. **会话密钥解密**：
   ```python
   # 使用私钥解密会话密钥
   encrypted_session_key = base64.b64decode(encrypted_package["encrypted_session_key"])
   session_key = decrypt_rsa_oaep(private_key, encrypted_session_key)
   ```

3. **测试记录解密**：
   ```python
   # 使用会话密钥解密数据
   encrypted_data = encrypted_package["encrypted_data"]
   nonce = base64.b64decode(encrypted_data["nonce"])
   ciphertext = base64.b64decode(encrypted_data["ciphertext"])
   
   decrypted_data = decrypt_aes_gcm(session_key, nonce, ciphertext)
   log_data = json.loads(decrypted_data)
   ```

4. **签名验证**：
   ```python
   # 验证签名
   signature = base64.b64decode(encrypted_package["signature"])
   signature_data = encrypted_package["signature_data"]
   
   # 构建签名验证密钥
   signing_key = derive_signing_key(session_key)
   
   # 验证签名
   expected_signature = hmac.new(
       signing_key, 
       json.dumps(signature_data, sort_keys=True).encode(), 
       hashlib.sha256
   ).digest()
   
   is_signature_valid = hmac.compare_digest(signature, expected_signature)
   ```

5. **APIKEY验证**：
   ```python
   # 验证API密钥绑定
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

## 数据模型设计

基于测试日志格式，设计主要数据模型：

```python
class BenchmarkResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    upload_id = db.Column(db.String, unique=True)
    api_key_id = db.Column(db.String)  # 关联的API密钥ID（不存储完整API密钥）
    api_key_verified = db.Column(db.Boolean, default=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    verified = db.Column(db.Boolean, default=False)
    
    # 提交者元数据
    submitter = db.Column(db.String)
    model_name = db.Column(db.String)
    model_version = db.Column(db.String)
    hardware_info = db.Column(db.String)
    notes = db.Column(db.Text)
    
    # 测试摘要数据（从解密的测试日志中提取）
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
    verification_details = db.Column(db.JSON)  # 验证详情
    
    # 测试详情
    test_details = db.relationship('TestDetail', backref='benchmark_result')
```

```python
class TestDetail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    benchmark_id = db.Column(db.Integer, db.ForeignKey('benchmark_result.id'))
    test_id = db.Column(db.Integer)  # 测试记录中的ID
    
    # 测试详细数据（选择性存储）
    latency = db.Column(db.Float)
    throughput = db.Column(db.Float)
    token_throughput = db.Column(db.Float)
    input_tokens = db.Column(db.Integer)
    output_tokens = db.Column(db.Integer)
    tokens = db.Column(db.Integer)
    status = db.Column(db.String)
    
    # 可选：存储完整的输入输出（注意：可能占用大量空间）
    # input_text = db.Column(db.Text)
    # output_text = db.Column(db.Text)
```

## 错误处理

实现统一的错误处理机制，确保返回一致的错误格式：

```python
class APIError(Exception):
    def __init__(self, code, message, details=None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

# 预定义错误类型
ERRORS = {
    "INVALID_FORMAT": {"code": "E1001", "message": "无效的文件格式"},
    "DECRYPTION_FAILED": {"code": "E1002", "message": "解密失败"},
    "SIGNATURE_INVALID": {"code": "E1003", "message": "签名验证失败"},
    "API_KEY_INVALID": {"code": "E1004", "message": "API密钥验证失败"},
    "UNAUTHORIZED": {"code": "E1005", "message": "未授权的访问"},
    "SERVER_ERROR": {"code": "E1006", "message": "服务器内部错误"}
}

@app.exception_handler(APIError)
async def api_error_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={
            "status": "error",
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details
            }
        }
    )
```

## 代码示例

下面是一个使用FastAPI和Python实现的基本框架：

```python
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from typing import Optional
import json
from datetime import datetime
import base64
import hmac
import hashlib
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

from models import BenchmarkResult, TestDetail
from database import get_db
from encryption import decrypt_rsa_oaep, decrypt_aes_gcm, derive_signing_key

app = FastAPI()
api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

async def get_api_key(api_key_header: str = Depends(api_key_header)):
    if not api_key_header:
        raise APIError(**ERRORS["UNAUTHORIZED"])
    
    # 格式应为 "APIKEY {api_key}"
    parts = api_key_header.split()
    if len(parts) != 2 or parts[0] != "APIKEY":
        raise APIError(**ERRORS["UNAUTHORIZED"])
    
    return parts[1]

@app.post("/api/v1/benchmark/upload")
async def upload_benchmark_log(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    # 1. 读取上传文件
    content = await file.read()
    try:
        encrypted_package = json.loads(content.decode('utf-8'))
    except json.JSONDecodeError:
        raise APIError(**ERRORS["INVALID_FORMAT"])
    
    # 解析可选元数据
    meta_data = {}
    if metadata:
        try:
            meta_data = json.loads(metadata)
        except json.JSONDecodeError:
            raise APIError(**ERRORS["INVALID_FORMAT"], details={"field": "metadata"})
    
    # 2. 解密和验证
    try:
        # 执行解密和验证
        decryption_result = decrypt_and_verify(encrypted_package, api_key)
        decrypted_log = decryption_result["log_data"]
        validation_result = decryption_result["validation"]
        
        if not validation_result["is_valid"]:
            return {
                "status": "error",
                "message": "验证失败",
                "validation": validation_result
            }
    except Exception as e:
        # 处理解密或验证失败
        validation_result = {
            "is_valid": False,
            "errors": [str(e)]
        }
        raise APIError(**ERRORS["DECRYPTION_FAILED"], details={"error": str(e)})
    
    # 3. 保存到数据库
    # 创建数据库记录
    benchmark_result = BenchmarkResult(
        upload_id=generate_upload_id(),
        api_key_id=generate_api_key_id(api_key),  # 生成API密钥标识符而非存储完整API密钥
        api_key_verified=validation_result["api_key_valid"],
        verified=True,
        
        # 元数据字段
        submitter=meta_data.get("submitter"),
        model_name=meta_data.get("model_name"),
        model_version=meta_data.get("model_version"),
        hardware_info=meta_data.get("hardware_info"),
        notes=meta_data.get("notes"),
        
        # 测试摘要数据
        dataset_version=decrypted_log.get("dataset_version"),
        start_time=datetime.fromtimestamp(decrypted_log.get("start_time", 0)),
        end_time=datetime.fromtimestamp(decrypted_log.get("end_time", 0)),
        total_time=decrypted_log.get("total_time"),
        total_tests=decrypted_log.get("total_tests"),
        successful_tests=decrypted_log.get("successful_tests"),
        success_rate=decrypted_log.get("success_rate"),
        avg_latency=decrypted_log.get("avg_latency"),
        avg_throughput=decrypted_log.get("avg_throughput"),
        tps=decrypted_log.get("tps"),
        total_input_chars=decrypted_log.get("total_input_chars"),
        total_output_chars=decrypted_log.get("total_output_chars"),
        total_chars=decrypted_log.get("total_chars"),
        total_tokens=decrypted_log.get("total_tokens"),
        verification_details=validation_result
    )
    
    db.add(benchmark_result)
    db.commit()
    
    # 可选：保存测试详情
    save_test_details(db, benchmark_result.id, decrypted_log.get("results", []))
    
    return {
        "status": "success",
        "message": "基准测试日志上传并验证成功",
        "upload_id": benchmark_result.upload_id,
        "validation": validation_result,
        "benchmark_summary": {
            "total_tests": decrypted_log.get("total_tests"),
            "success_rate": decrypted_log.get("success_rate"),
            "avg_latency": decrypted_log.get("avg_latency"),
            "tps": decrypted_log.get("tps")
        }
    }

# 帮助函数
def decrypt_and_verify(encrypted_package, api_key):
    """解密并验证加密的测试日志"""
    validation_result = {
        "is_valid": False,
        "signature_valid": False,
        "format_valid": False,
        "api_key_valid": False,
        "errors": []
    }
    
    # 格式验证
    required_fields = ["format_version", "encrypted_session_key", "encrypted_data", "signature_data", "signature"]
    if not all(field in encrypted_package for field in required_fields):
        validation_result["errors"].append("缺少必要字段")
        return {"validation": validation_result, "log_data": None}
    
    validation_result["format_valid"] = True
    
    try:
        # 1. 解密会话密钥
        encrypted_session_key = base64.b64decode(encrypted_package["encrypted_session_key"])
        session_key = decrypt_rsa_oaep(get_private_key(), encrypted_session_key)
        
        # 2. 验证签名
        signature = base64.b64decode(encrypted_package["signature"])
        signature_data = encrypted_package["signature_data"]
        
        signing_key = derive_signing_key(session_key)
        expected_signature = hmac.new(
            signing_key, 
            json.dumps(signature_data, sort_keys=True).encode(), 
            hashlib.sha256
        ).digest()
        
        is_signature_valid = hmac.compare_digest(signature, expected_signature)
        validation_result["signature_valid"] = is_signature_valid
        
        if not is_signature_valid:
            validation_result["errors"].append("签名验证失败")
            return {"validation": validation_result, "log_data": None}
        
        # 3. 验证API密钥绑定
        is_api_key_valid = verify_api_key_binding(session_key, signature_data, api_key)
        validation_result["api_key_valid"] = is_api_key_valid
        
        if not is_api_key_valid:
            validation_result["errors"].append("API密钥验证失败")
            return {"validation": validation_result, "log_data": None}
        
        # 4. 解密测试日志
        encrypted_data = encrypted_package["encrypted_data"]
        nonce = base64.b64decode(encrypted_data["nonce"])
        ciphertext = base64.b64decode(encrypted_data["ciphertext"])
        
        decrypted_data = decrypt_aes_gcm(session_key, nonce, ciphertext)
        log_data = json.loads(decrypted_data)
        
        # 5. 综合验证
        validation_result["is_valid"] = True
        
        return {
            "validation": validation_result,
            "log_data": log_data
        }
    except Exception as e:
        validation_result["errors"].append(f"解密或验证过程错误: {str(e)}")
        return {"validation": validation_result, "log_data": None}

def verify_api_key_binding(session_key, signature_data, api_key):
    """验证API密钥绑定"""
    stored_api_key_hash_b64 = signature_data.get("api_key_hash")
    if not stored_api_key_hash_b64:
        return False  # 不包含API密钥哈希，验证失败
    
    stored_api_key_hash = base64.b64decode(stored_api_key_hash_b64)
    
    # 使用当前用户的API密钥生成哈希
    current_hash = generate_api_key_hash(session_key, api_key)
    
    # 安全比较两个哈希值
    return hmac.compare_digest(stored_api_key_hash, current_hash)

def generate_api_key_hash(session_key, api_key):
    """生成API密钥哈希，与客户端保持一致"""
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
    
    # 计算APIKEY哈希
    return hashlib.sha256(binding_material).digest()

def save_test_details(db, benchmark_id, test_results):
    """保存测试详情到数据库"""
    for result in test_results:
        test_detail = TestDetail(
            benchmark_id=benchmark_id,
            test_id=result.get("id"),
            latency=result.get("latency"),
            throughput=result.get("throughput"),
            token_throughput=result.get("token_throughput"),
            input_tokens=result.get("input_tokens"),
            output_tokens=result.get("output_tokens"),
            tokens=result.get("tokens"),
            status=result.get("status")
        )
        db.add(test_detail)
    
    db.commit()

def generate_upload_id():
    """生成唯一的上传ID"""
    import uuid
    return f"upload_{uuid.uuid4().hex}"

def generate_api_key_id(api_key):
    """从API密钥生成唯一标识符，不存储完整API密钥"""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]

def get_private_key():
    """从安全存储加载私钥"""
    import os
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    
    # 从环境变量或密钥管理系统获取私钥
    # 注意：不要在代码中硬编码私钥
    private_key_path = os.environ.get("PRIVATE_KEY_PATH")
    
    with open(private_key_path, "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None,
            backend=default_backend()
        )
    
    return private_key
```

## 部署建议

- 使用HTTPS确保传输层安全
- 实现API密钥的安全存储和验证
- 为API添加速率限制
- 实现全面的日志记录和监控
- 确保私钥的安全存储和访问控制
- 定期更换和轮换密钥

请根据上述指南实现DeepStressModel基准测试日志上传和验证API。该API应简单易用，同时确保测试结果的真实性和完整性。 