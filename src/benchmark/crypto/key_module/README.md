# 密钥存储模块

该模块提供基准测试日志加密所需的公钥存储和处理功能，采用Cython编译以增强安全性。

## 文件说明

- `key_storage.pyx`: Cython源代码，包含公钥存储和处理逻辑
- `setup.py`: 编译配置文件
- `prebuilt/`: 预编译的二进制模块目录，按操作系统和Python版本组织
- 测试脚本:
  - `test_key_module.py`: 测试密钥存储模块
  - `test_benchmark_encrypt.py`: 测试基准测试日志加密功能
  - `test_full_functionality.py`: 测试完整功能链

## 预编译模块使用

模块设计支持自动检测和使用预编译二进制文件，无需手动编译。预编译文件的目录结构如下：

```
prebuilt/
├── windows/              # Windows系统
│   ├── python3.9/        # Python 3.9版本
│   ├── python3.10/       # Python 3.10版本
│   └── ...
├── macos/                # macOS系统
│   ├── python3.9/        # Python 3.9版本
│   └── ...
└── linux/                # Linux系统
    ├── python3.9/        # Python 3.9版本
    └── ...
```

系统会根据当前运行环境（操作系统和Python版本）自动选择合适的预编译文件。

### 预编译文件的限制

预编译文件有以下限制：

1. **特定平台依赖**：预编译文件只能在特定操作系统和Python版本上使用
2. **可能缺少某些平台**：如果您使用的操作系统或Python版本没有对应的预编译文件，需要自行编译
3. **CPU架构限制**：预编译文件可能只支持特定的CPU架构（如x86_64、arm64等）

## 手动编译模块

如果没有适合您环境的预编译文件，或者您需要修改源代码，可以手动编译模块：

```bash
python src/benchmark/crypto/key_module/setup.py build_ext --inplace
```

编译成功后，会自动将编译后的文件复制到以下位置：
- `src/benchmark/crypto/key_module/`目录
- 对应的预编译目录（如`prebuilt/macos/python3.13/`）

## 测试模块

编译完成后，可以运行测试脚本验证模块功能：

```bash
# 测试密钥存储模块
python src/benchmark/crypto/key_module/test_key_module.py

# 测试基准测试日志加密功能
python src/benchmark/crypto/key_module/test_benchmark_encrypt.py

# 测试完整功能链
python src/benchmark/crypto/key_module/test_full_functionality.py
```

## 安全注意事项

- `key_storage.pyx`文件包含敏感信息，**不应该**包含在公开发布的代码中
- 编译后的二进制模块（`.so`或`.pyd`文件）可以安全分发
- 为提高安全性，建议定期更新公钥并重新编译模块

## 使用示例

```python
# 导入模块 - 系统会自动查找合适的预编译文件或已编译模块
from src.benchmark.crypto.benchmark_log_encrypt import BenchmarkEncryption

# 初始化加密器
encryptor = BenchmarkEncryption()

# 加密数据
encrypted_data = encryptor.encrypt_benchmark_log(data, api_key)

# 保存加密数据
encryptor.encrypt_and_save(data, "output.json", api_key)
```

## 为其他平台编译

如果您需要为其他平台编译模块，可以按照以下步骤操作：

1. 在目标平台上安装必要的依赖：
   ```bash
   pip install cython setuptools wheel
   ```

2. 编译模块：
   ```bash
   python src/benchmark/crypto/key_module/setup.py build_ext --inplace
   ```

3. 验证编译结果：
   ```bash
   python src/benchmark/crypto/key_module/test_key_module.py
   ```

编译成功后，系统会自动将编译后的文件复制到对应的预编译目录。您可以将这些文件提交到版本控制系统，以便其他用户使用。

## 文件分发策略

在发布项目时，应遵循以下原则：

1. **应该分发的文件**：
   - 预编译的二进制模块（`prebuilt/`目录下的`.so`或`.pyd`文件）
   - `benchmark_log_encrypt.py`及其依赖文件
   - 编译和使用说明（`README.md`）

2. **不应分发的文件**：
   - `key_storage.pyx`（包含敏感密钥信息）
   - 包含API密钥等敏感信息的测试脚本

## 问题排查

如果遇到"缺少编译的key_storage模块"错误，请按以下步骤处理：

1. 检查是否有适合您环境的预编译文件：
   ```bash
   ls -la src/benchmark/crypto/key_module/prebuilt/{对应的操作系统}/{对应的Python版本}/
   ```

2. 如果没有找到预编译文件，尝试自行编译：
   ```bash
   python src/benchmark/crypto/key_module/setup.py build_ext --inplace
   ```

3. 如果编译失败，检查是否安装了必要的依赖，如Cython和相应的编译器（Windows上的Visual C++、Linux上的GCC等） 