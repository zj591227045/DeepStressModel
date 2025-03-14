# DeepStressModel 离线包加密规范 v2.0

本文档详细描述了 DeepStressModel 离线包的加密流程和规范，包括私钥加密、会话密钥加密和数据集加密。
该规范兼容现有的私钥和会话密钥加密方法，但对数据集加密部分进行了优化和标准化。

## 加密流程概述

离线包加密采用三层加密结构：

1. **用户验证层**：使用用户的 API 密钥（通过 PBKDF2 派生）加密 RSA 私钥
2. **密钥交换层**：使用 RSA 公私钥对会话密钥进行加密
3. **数据加密层**：使用从会话密钥派生的 AES 密钥加密实际数据集

```
┌─────────────────┐
│    数据集       │
└────────┬────────┘
         │ AES-CBC 加密
         ▼
┌─────────────────┐      ┌─────────────────┐
│   会话密钥      │◄─────┤  密钥派生函数   │
└────────┬────────┘      └─────────────────┘
         │ RSA 加密
         ▼
┌─────────────────┐      ┌─────────────────┐
│   RSA 私钥      │◄─────┤ 用户 API 密钥   │
└─────────────────┘      └─────────────────┘
```

## 1. 私钥加密（API 密钥 → RSA 私钥）

使用 PBKDF2 派生密钥加密 RSA 私钥，此部分保持不变。

### 加密步骤：

1. 生成随机盐值（32 字节）
2. 从用户 API 密钥派生密钥：
   ```
   kdf = PBKDF2HMAC(
     algorithm=SHA256,
     length=32,
     salt=salt,
     iterations=100000
   )
   key = kdf.derive(api_key.encode('utf-8'))
   ```
3. 生成随机 IV（16 字节）
4. 使用 AES-CBC 模式和 PKCS7 填充加密 RSA 私钥的 PEM 格式：
   ```
   cipher = AES(key, CBC, iv)
   encrypted_data = cipher.encrypt(pad(private_key_pem, PKCS7))
   ```
5. 包装加密结果：
   ```json
   {
     "salt": "<base64_encoded_salt>",
     "iv": "<base64_encoded_iv>",
     "data": "<base64_encoded_encrypted_data>"
   }
   ```

### 解密步骤：

1. 解码 salt、iv 和加密数据
2. 从用户 API 密钥派生密钥（与加密步骤相同）
3. 使用 AES-CBC 解密
4. 去除 PKCS7 填充
5. 解析 PEM 格式的 RSA 私钥

## 2. 会话密钥加密（RSA 私钥 → 会话密钥）

使用 RSA 公钥加密会话密钥，此部分保持不变。

### 加密步骤：

1. 生成随机会话密钥（32 字节）
2. 使用 RSA 公钥和 PKCS1v15 填充加密会话密钥：
   ```
   encrypted_session_key = rsa_public_key.encrypt(
     session_key,
     padding=PKCS1v15()
   )
   ```
3. Base64 编码加密结果

### 解密步骤：

1. Base64 解码加密的会话密钥
2. 使用 RSA 私钥和 PKCS1v15 填充解密会话密钥：
   ```
   session_key = rsa_private_key.decrypt(
     encrypted_session_key,
     padding=PKCS1v15()
   )
   ```
3. 如果 PKCS1v15 解密失败，尝试使用 OAEP 填充方式解密

## 3. 数据集加密（会话密钥 → 数据集）

**本部分进行了优化和标准化**，确保了在任何情况下会话密钥都能正确地用于 AES 加密。

### 加密步骤：

1. 从会话密钥派生标准长度的 AES 密钥：
   ```
   derived_key = HKDF-SHA256(
     master_key=session_key,
     salt=random_salt(16),
     info=b"dataset_encryption",
     length=32  # 固定使用 256 位密钥
   )
   ```

2. 生成随机 IV（16 字节）

3. 使用 AES-CBC 模式和 PKCS7 填充加密 JSON 格式的数据集：
   ```
   cipher = AES(derived_key, CBC, iv)
   encrypted_data = cipher.encrypt(pad(json.dumps(dataset).encode('utf-8'), PKCS7))
   ```

4. 包装加密结果，明确提供派生密钥所需的所有参数：
   ```json
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
   ```

### 解密步骤：

1. 解码 key_derivation.salt、iv 和加密数据
2. 使用相同的 HKDF 参数派生 AES 密钥：
   ```
   derived_key = HKDF-SHA256(
     master_key=session_key,
     salt=decoded_salt,
     info=b"dataset_encryption",
     length=32
   )
   ```
3. 使用 AES-CBC 模式和派生密钥解密数据：
   ```
   cipher = AES(derived_key, CBC, iv)
   decrypted_padded = cipher.decrypt(encrypted_data)
   ```
4. 去除 PKCS7 填充
5. 解析 JSON 格式的数据集

## 完整离线包结构

以下是完整的离线包 JSON 结构：

```json
{
  "metadata": {
    "package_format": "4.0",
    "dataset_id": 1,
    "created_at": "2024-05-10T12:34:56Z",
    "expires_at": "2024-06-10T12:34:56Z"
  },
  "encrypted_private_key": {
    "salt": "<base64_encoded_salt>",
    "iv": "<base64_encoded_iv>",
    "data": "<base64_encoded_encrypted_data>"
  },
  "dataset": {
    "encrypted_session_key": "<base64_encoded_encrypted_session_key>",
    "encrypted_data": {
      "algorithm": "AES-256-CBC-PKCS7",
      "key_derivation": {
        "method": "HKDF-SHA256",
        "salt": "<base64_encoded_salt>",
        "info": "dataset_encryption"
      },
      "iv": "<base64_encoded_iv>",
      "data": "<base64_encoded_encrypted_data>"
    },
    "timestamp": "<timestamp>",
    "user_signature": "<signature>"
  }
}
```

## 密钥派生函数 (HKDF) 说明

HKDF (HMAC-based Key Derivation Function) 是一种强大的密钥派生函数，用于从不规则或弱密钥材料安全地派生密钥。它遵循 RFC 5869 标准。

HKDF 分为两步：
1. 提取步骤 - 从输入密钥材料中提取随机性
2. 扩展步骤 - 将提取的随机性扩展为所需长度的密钥

使用 HKDF 的优势：
1. 可以处理任意长度的输入密钥材料
2. 可以生成标准长度的加密密钥
3. 可以通过信息字符串"info"绑定密钥到特定上下文
4. 安全性得到广泛验证和接受

在数据集加密中使用 HKDF 可以解决会话密钥长度非标准的问题，确保生成的 AES 密钥始终满足要求。

## 加密算法选择理由

1. **AES-256-CBC**：
   - 广泛支持，兼容性强
   - 足够安全的对称加密算法
   - 密码块链接（CBC）模式提供良好的数据保护

2. **PKCS7 填充**：
   - 标准填充方法，广泛支持
   - 适用于块加密算法

3. **HKDF-SHA256**：
   - 专为密钥派生设计，安全性高
   - 可处理任意长度的输入密钥材料
   - 可通过 info 参数绑定到特定上下文

## 实现注意事项

1. 所有随机数（盐值、IV、会话密钥）必须使用密码学安全的随机数生成器生成
2. 转换为 JSON 时应使用 UTF-8 编码
3. 所有二进制数据（密钥、IV、加密数据等）必须使用 Base64 编码后存储在 JSON 中
4. 加密前应验证所有参数的有效性，特别是密钥长度
5. 实现应处理所有可能的异常情况，提供有意义的错误信息

## 安全建议

1. 定期轮换 API 密钥
2. 为每个离线包生成新的 RSA 密钥对和会话密钥
3. 设置合理的离线包过期时间
4. 实现访问控制，确保只有授权用户能获取离线包
5. 记录所有加密操作，以便审计和故障排除 