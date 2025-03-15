# DeepStressModel 测试结果加密功能使用指南

本文档介绍如何使用 DeepStressModel 基准测试工具的测试结果加密功能，包括加密保存和上传到验证服务器的功能。

## 背景介绍

为确保测试结果的真实性和不可篡改性，DeepStressModel 基准测试工具提供了测试结果加密功能。加密后的测试结果可以保存到本地或上传到验证服务器，以便后续验证和比较。

## 加密技术说明

测试结果加密使用以下技术：

1. **混合加密架构**：使用RSA非对称加密与AES对称加密相结合
2. **数字签名**：确保数据完整性和来源真实性
3. **APIKEY绑定**：确保只有使用相同APIKEY的用户才能加密和验证测试记录
4. **公钥保护**：在客户端代码中保护公钥，防止直接提取

## 使用方法

### 1. 在跑分测试时自动加密上传

在运行基准测试时，可以设置`encrypt_and_upload`参数为`True`，以在测试结束后自动加密并上传结果：

```python
# 使用BenchmarkManager进行测试并加密上传结果
from src.benchmark.benchmark_manager import BenchmarkManager

benchmark_manager = BenchmarkManager()
benchmark_manager.set_api_key("your_api_key")  # 设置API密钥

# 运行测试并加密上传结果
result = await benchmark_manager.run_benchmark(
    model="test_model",
    api_url="http://localhost:8000/api/chat",
    encrypt_and_upload=True  # 启用加密上传功能
)

# 查看加密上传结果
if "encryption_result" in result:
    print(f"加密结果: {result['encryption_result']}")
```

### 2. 单独加密并上传测试结果

如果已经有测试结果，可以使用`encrypt_and_upload_result`方法单独加密并上传：

```python
# 对已有的测试结果进行加密上传
from src.benchmark.benchmark_manager import BenchmarkManager

benchmark_manager = BenchmarkManager()
benchmark_manager.set_api_key("your_api_key")  # 设置API密钥

# 假设已有测试结果
existing_result = {
    "status": "success",
    "dataset_version": "test_v1.0",
    "start_time": 1742039446.924232,
    "end_time": 1742039527.5310478,
    "total_time": 80.6068,
    # 其他测试结果数据...
}

# 加密并上传结果
upload_result = benchmark_manager.encrypt_and_upload_result(
    result=existing_result,
    api_key="your_api_key",  # 可选，如果已设置则可省略
    server_url="https://benchmark.example.com/api/v1/benchmark/upload",  # 可选
    save_encrypted=True,  # 是否同时保存加密结果到本地
    metadata={  # 可选元数据
        "submitter": "测试工程师",
        "model_name": "TestModel-1",
        "model_version": "1.0.0",
        "notes": "性能基准测试"
    }
)

print(f"上传结果: {upload_result}")
```

### 3. 使用命令行工具加密并上传已有结果

我们还提供了命令行工具，可以对已有的测试结果文件进行加密和上传：

```bash
# 加密并保存到本地文件
python -m src.benchmark.crypto.tools.encrypt_and_upload \
    /path/to/benchmark_result.json \
    -k your_api_key \
    -o /path/to/encrypted_result.json

# 加密并上传到服务器
python -m src.benchmark.crypto.tools.encrypt_and_upload \
    /path/to/benchmark_result.json \
    -k your_api_key \
    -u \
    -s https://benchmark.example.com/api/v1/benchmark/upload

# 加密并上传，同时指定元数据文件
python -m src.benchmark.crypto.tools.encrypt_and_upload \
    /path/to/benchmark_result.json \
    -k your_api_key \
    -u \
    -m /path/to/metadata.json
```

元数据文件格式示例（JSON格式）：

```json
{
  "submitter": "测试工程师",
  "model_name": "TestModel-1",
  "model_version": "1.0.0",
  "hardware_info": "CPU: i9-12900K, RAM: 64GB",
  "notes": "性能基准测试"
}
```

## 加密结果格式

加密后的测试结果符合以下JSON格式：

```json
{
  "format_version": "1.0",
  "encrypted_session_key": "<base64_encrypted_key>",
  "encrypted_data": {
    "nonce": "<base64_nonce>",
    "data": "<base64_ciphertext>"
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

## 错误处理

加密过程中可能出现以下错误：

- `C1001`: 无效的测试数据格式
- `C1002`: 加密失败
- `C1003`: 公钥处理错误
- `C1004`: API密钥错误
- `C1005`: 服务器错误
- `C1006`: 上传失败

在使用时应妥善处理这些错误，确保加密和上传过程的稳定性。

## 注意事项

1. API密钥是加密和验证的关键，请妥善保管
2. 加密后的测试结果可以安全地分享，因为只有使用相同API密钥的验证者才能验证其真实性
3. 上传加密结果时，请确保网络连接稳定
4. 建议在上传前先保存一份原始测试结果作为备份 