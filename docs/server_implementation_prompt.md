# DeepStressModel 服务端加密修改 AI 提示词

以下是向服务端开发团队提供的 AI 提示词，用于指导他们按照新规范修改离线包加密实现：

```
请根据 DeepStressModel 修订版加密规范 v2.0 修改服务端的离线包加密实现，重点解决数据集解密失败的问题。

主要问题：目前的实现在处理会话密钥长度为 54 字节时存在问题，导致客户端无法成功解密数据集。

请实现以下修改：

1. 更新数据集加密方法，使用 HKDF-SHA256 从会话密钥派生固定长度的 AES 密钥：
   - 从主会话密钥派生 32 字节的 AES-256 密钥
   - 使用随机盐值和固定的信息字符串 "dataset_encryption"
   - 确保即使会话密钥长度非标准也能派生有效的密钥

2. 修改加密数据的结构，添加必要的元数据：
   - 指定算法为 "AES-256-CBC-PKCS7"
   - 包含密钥派生方法和参数
   - 包含 IV 和加密数据

3. 更新离线包格式版本为 4.0，修改 JSON 结构为：
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

4. 请确保保留现有的私钥加密和会话密钥加密实现不变，仅修改数据集加密部分。

5. 添加详细的日志记录，包括：
   - 会话密钥的长度和格式
   - HKDF 派生密钥的参数和结果
   - 加密过程的各个步骤

6. 提供适当的错误处理，确保在密钥长度或格式不正确时提供明确的错误信息。

7. 添加单元测试验证新的加密实现。

参考文档：
- 完整规范：[docs/revised_crypto_specification.md]
- 实现指南：[docs/server_implementation_guide.md]
- 示例代码：[docs/revised_encrypt_example.py]

如需进一步解释或澄清，请随时提问。
```

此提示词应提供给服务端开发团队或AI辅助工具，引导他们正确实现新的加密规范。提示词明确指出了当前的问题和所需的更改，同时提供了详细的实现指南和参考资料。 