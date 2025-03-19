# 基准测试API调用手册

本文档详细说明了基准测试API的调用方式，重点介绍两个主要接口：上传基准测试日志和获取基准测试日志状态。

## 目录

- [认证方式](#认证方式)
- [上传基准测试日志](#上传基准测试日志)
- [获取基准测试日志状态](#获取基准测试日志状态)
- [错误处理](#错误处理)
- [示例代码](#示例代码)

## 认证方式

所有API调用都需要通过API密钥进行认证。API密钥应通过以下两种方式之一提供：

1. 作为`X-API-Key`请求头：
   ```
   X-API-Key: your_api_key_here
   ```

2. 作为`Authorization`请求头（添加`Bearer`前缀）：
   ```
   Authorization: Bearer your_api_key_here
   ```

推荐使用`X-API-Key`方式，因为服务器优先处理此头部。

## 上传基准测试日志

上传加密的基准测试日志文件，服务器将验证并处理该日志。

### 请求信息

- **URL**: `/api/v1/benchmark-result/upload`
- **方法**: `POST`
- **Content-Type**: `multipart/form-data`

### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|-------|-----|------|-----|
| file | File | 是 | 加密的基准测试日志文件（JSON格式） |
| metadata | String | 否 | 额外的元数据信息（JSON字符串） |

### 文件格式要求

上传的基准测试日志文件必须是经过加密的JSON文件，符合以下结构：

```json
{
  "format_version": "1.0",
  "encrypted_session_key": "base64_encoded_encrypted_key",
  "encrypted_data": {
    "nonce": "base64_encoded_nonce",
    "ciphertext": "base64_encoded_ciphertext"
  },
  "signature_data": {
    "log_hash": "base64_encoded_hash",
    "timestamp": 1742051234,
    "nonce": "base64_encoded_nonce",
    "api_key_hash": "base64_encoded_api_key_hash"
  },
  "signature": "base64_encoded_signature",
  "timestamp": "2025-03-15T23:07:14.753Z"
}
```

### 元数据格式

元数据是可选的，如提供，必须是一个有效的JSON字符串，包含以下建议字段：

```json
{
  "submitter": "用户昵称",
  "device_id": "设备ID",
  "model_name": "模型名称",
  "hardware_info": {
    "cpu": "CPU信息",
    "memory": "内存信息",
    "gpu": "GPU信息"
  },
  "notes": "备注信息"
}
```

### 响应

成功响应（状态码：200）：

```json
{
  "status": "success",
  "message": "基准测试日志上传并验证成功",
  "upload_id": "upload_e1271d28341649cba21b94bff523566e",
  "benchmark_id": 41,
  "validation": {
    "is_valid": true,
    "format_valid": true,
    "timestamp_valid": true,
    "signature_valid": true,
    "api_key_valid": true,
    "errors": []
  },
  "benchmark_summary": {
    "total_tests": 100,
    "success_rate": 0.95,
    "avg_latency": 0.5,
    "tps": 2.0,
    "model": "test-model"
  }
}
```

### 重要字段说明

- `upload_id`: 上传会话的唯一标识符，可用于后续查询上传状态
- `benchmark_id`: 在数据库中创建的基准测试记录ID
- `validation`: 包含验证结果的详细信息
- `benchmark_summary`: 包含基准测试结果摘要

## 获取基准测试日志状态

获取已上传基准测试日志的处理状态和验证结果。

### 请求信息

- **URL**: `/api/v1/benchmark-result/status/{uploadId}`
- **方法**: `GET`

### 路径参数

| 参数名 | 类型 | 必填 | 说明 |
|-------|-----|------|-----|
| uploadId | String | 是 | 上传API返回的upload_id |

### 响应

成功响应（状态码：200）：

```json
{
  "status": "success",
  "upload_id": "upload_e1271d28341649cba21b94bff523566e",
  "benchmark_id": 41,
  "processing_status": "completed",
  "validation": {
    "is_valid": true,
    "format_valid": true,
    "timestamp_valid": true,
    "signature_valid": true,
    "api_key_valid": true,
    "errors": []
  },
  "created_at": "2025-03-15T23:07:14.753Z"
}
```

### 处理状态说明

`processing_status`字段可能的值：

- `pending`: 日志已上传，等待处理
- `processing`: 日志正在处理中
- `completed`: 处理已完成
- `failed`: 处理失败

## 错误处理

API可能返回以下错误状态码：

| 状态码 | 说明 |
|-------|-----|
| 400 | 请求格式错误（文件格式无效、验证失败等） |
| 401 | 未授权（API密钥无效或缺失） |
| 404 | 资源不存在（指定的uploadId不存在） |
| 500 | 服务器内部错误 |

错误响应格式示例：

```json
{
  "status": "error",
  "message": "验证失败",
  "code": "E1003",
  "details": {
    "errors": ["签名验证失败"]
  }
}
```

### 错误代码对照表

| 错误代码 | 描述 |
|---------|-----|
| E1001 | 无效的文件格式 |
| E1002 | 解密失败 |
| E1003 | 签名验证失败 |
| E1004 | API密钥验证失败 |
| E1005 | 未授权的访问 |
| E1006 | 服务器内部错误 |

## 示例代码

### JavaScript（使用axios）

```javascript
import axios from 'axios';

// 上传基准测试日志
async function uploadBenchmarkLog(file, metadata, apiKey) {
  const formData = new FormData();
  formData.append('file', file);
  
  if (metadata) {
    formData.append('metadata', JSON.stringify(metadata));
  }
  
  try {
    const response = await axios.post('/api/v1/benchmark-result/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
        'X-API-Key': apiKey
      }
    });
    
    return response.data;
  } catch (error) {
    console.error('上传失败:', error.response?.data || error.message);
    throw error;
  }
}

// 获取基准测试日志状态
async function getBenchmarkLogStatus(uploadId, apiKey) {
  try {
    const response = await axios.get(`/api/v1/benchmark-result/status/${uploadId}`, {
      headers: {
        'X-API-Key': apiKey
      }
    });
    
    return response.data;
  } catch (error) {
    console.error('获取状态失败:', error.response?.data || error.message);
    throw error;
  }
}
```

### Python（使用requests）

```python
import json
import requests

# 上传基准测试日志
def upload_benchmark_log(file_path, metadata=None, api_key=None):
    url = "http://localhost:8000/api/v1/benchmark-result/upload"
    
    files = {
        'file': (file_path.split('/')[-1], open(file_path, 'rb'), 'application/json')
    }
    
    data = {}
    if metadata:
        data['metadata'] = json.dumps(metadata)
    
    headers = {}
    if api_key:
        headers['X-API-Key'] = api_key
    
    response = requests.post(
        url,
        files=files,
        data=data,
        headers=headers
    )
    
    return response.json()

# 获取基准测试日志状态
def get_benchmark_log_status(upload_id, api_key=None):
    url = f"http://localhost:8000/api/v1/benchmark-result/status/{upload_id}"
    
    headers = {}
    if api_key:
        headers['X-API-Key'] = api_key
    
    response = requests.get(url, headers=headers)
    
    return response.json()
```

## 注意事项

1. **加密要求**: 上传的基准测试日志必须使用服务器公钥加密，并通过API密钥进行签名验证
2. **时间戳验证**: 日志中的时间戳不能与服务器时间相差超过5分钟
3. **API密钥绑定**: 日志必须与用于上传的API密钥绑定，两者必须匹配
4. **安全存储**: 请保管好您的API密钥，不要在客户端代码中硬编码

---

更多详细信息，请参考[基准测试安全方案文档](./benchmark_security_scheme.md)和[加密使用指南](./encrypt_usage.md)。 