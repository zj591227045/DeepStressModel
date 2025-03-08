# DeepStressModel 排行榜服务器实现文档

## 功能概述

DeepStressModel排行榜服务器是一个独立的Web应用，用于管理跑分数据集、接收并验证测试结果、展示排行榜数据。服务器支持在线和离线两种模式的数据提交，并提供完整的管理后台。

## 系统架构

### 整体架构
```
前端应用 <--> API网关 <--> 应用服务器 <--> 数据库
                            |
                            v
                        文件存储系统
```

### 技术选择
- 后端框架：FastAPI
- 数据库：PostgreSQL
- 缓存：Redis
- 文件存储：MinIO
- 前端框架：Vue.js + Element Plus

## 详细模块设计

### 1. API模块

#### 1.1 公开API
- 排行榜数据查询
- 数据集下载
- 结果提交
- 用户注册与认证

#### 1.2 管理API
- 数据集管理
- 用户管理
- 结果审核
- 系统配置

### 2. 数据集管理模块

#### 2.1 数据集版本控制
- 版本号管理
- 更新日志
- 发布控制
- 兼容性检查

#### 2.2 数据集加密
- 加密算法实现
- 密钥管理
- 签名生成
- 完整性验证

#### 2.3 数据集加密实现
```python
class DatasetEncryptionService:
    def __init__(self, master_key_service):
        self._master_key_service = master_key_service
        self._key_derivation = KeyDerivationService()
    
    def encrypt_dataset(self, dataset_content, version):
        # 1. 生成数据集密钥
        dataset_key = self._generate_dataset_key(version)
        
        # 2. 加密数据集
        encrypted_dataset = self._encrypt_dataset_content(
            content=dataset_content,
            key=dataset_key
        )
        
        # 3. 生成解密器模板
        decoder_template = self._generate_decoder_template(
            dataset_key=dataset_key,
            version=version
        )
        
        # 4. 保存加密信息
        self._store_encryption_info(version, dataset_key)
        
        return {
            'encrypted_dataset': encrypted_dataset,
            'decoder_template': decoder_template,
            'version_info': self._generate_version_info(version)
        }
    
    def _generate_dataset_key(self, version):
        master_key = self._master_key_service.get_current_master_key()
        return self._key_derivation.derive_dataset_key(
            master_key=master_key,
            version=version,
            salt=os.urandom(32)
        )
```

#### 2.4 密钥管理服务
```python
class MasterKeyService:
    def __init__(self):
        self._key_store = SecureKeyStore()
        self._rotation_manager = KeyRotationManager()
    
    def get_current_master_key(self):
        return self._key_store.get_active_master_key()
    
    def rotate_master_key(self):
        new_key = self._generate_new_master_key()
        self._rotation_manager.perform_rotation(new_key)
        self._key_store.store_master_key(new_key)
```

#### 2.5 解密器模板生成
```python
class DecoderTemplateGenerator:
    def generate_template(self, dataset_key, version):
        # 1. 生成分发密钥
        distribution_key = self._generate_distribution_key(dataset_key)
        
        # 2. 创建解密器代码
        decoder_code = self._generate_decoder_code(distribution_key)
        
        # 3. 混淆代码
        obfuscated_code = self._obfuscate_decoder(decoder_code)
        
        # 4. 打包模板
        return self._package_template(
            obfuscated_code=obfuscated_code,
            version=version
        )
```

### 3. 结果验证模块

#### 3.1 在线结果验证
- 实时结果验证
- 性能指标计算
- 作弊检测
- 结果存档

#### 3.2 离线结果处理
- 结果文件解密
- 批量导入
- 数据一致性检查
- 异常处理

### 4. 排行榜模块

#### 4.1 排名计算
- 多维度评分
- 实时排名更新
- 历史记录追踪
- 统计分析

#### 4.2 展示功能
- 总榜单
- 分类榜单
- 趋势分析
- 详细报告

### 5. 用户管理模块

#### 5.1 简化用户系统
```python
class UserSystem:
    def __init__(self):
        self._admin_auth = AdminAuth()
        self._device_registry = DeviceRegistry()
    
    async def register_device(self, device_info: DeviceInfo) -> str:
        # 验证设备信息并注册
        return await self._device_registry.register(device_info)
    
    async def update_nickname(self, device_id: str, nickname: str) -> bool:
        # 更新用户昵称
        return await self._device_registry.update_nickname(device_id, nickname)
```

#### 5.2 设备注册
```python
class DeviceRegistry:
    async def register(self, device_info: DeviceInfo) -> str:
        # 验证设备信息
        if not self._validate_device_info(device_info):
            raise ValidationError("Invalid device info")
        
        # 检查是否已存在
        existing_device = await self._find_device(device_info.hardware_id)
        if existing_device:
            return existing_device.device_id
        
        # 注册新设备
        device_id = self._generate_device_id(device_info)
        await self._save_device(device_id, device_info)
        return device_id
```

### 6. 评分系统

#### 6.1 多维度评分实现
```python
class ScoringSystem:
    def calculate_scores(self, result: BenchmarkResult) -> Dict[str, float]:
        scores = {}
        
        # 1. 性能评分（基于TPS和延迟）
        scores['performance'] = self._calculate_performance_score(
            tps=result.avg_tokens_per_second,
            latency=result.avg_latency
        )
        
        # 2. 效率评分（考虑硬件利用率）
        scores['efficiency'] = self._calculate_efficiency_score(
            result.gpu_utilization,
            result.memory_utilization
        )
        
        # 3. 稳定性评分（考虑请求成功率和延迟波动）
        scores['stability'] = self._calculate_stability_score(
            result.error_rate,
            result.latency_std_dev
        )
        
        # 4. 综合评分
        scores['overall'] = self._calculate_overall_score(scores)
        
        return scores
```

#### 6.2 榜单分类实现
```python
class LeaderboardCategories:
    def __init__(self):
        self.categories = {
            'overall': OverallLeaderboard(),
            'by_model_size': ModelSizeLeaderboard(),
            'by_precision': PrecisionLeaderboard(),
            'by_gpu_count': GpuCountLeaderboard()
        }
    
    async def update_rankings(self, result: BenchmarkResult):
        scores = self._scoring_system.calculate_scores(result)
        
        # 更新各个榜单
        for category in self.categories.values():
            await category.update_ranking(result, scores)
```

#### 6.3 评分规则定义
```python
class ScoringRules:
    # 性能评分规则
    PERFORMANCE_WEIGHTS = {
        'tps': 0.6,
        'latency': 0.4
    }
    
    # 效率评分规则
    EFFICIENCY_WEIGHTS = {
        'gpu_utilization': 0.5,
        'memory_utilization': 0.3,
        'power_efficiency': 0.2
    }
    
    # 稳定性评分规则
    STABILITY_WEIGHTS = {
        'error_rate': 0.4,
        'latency_variance': 0.3,
        'throughput_stability': 0.3
    }
    
    # 综合评分权重
    OVERALL_WEIGHTS = {
        'performance': 0.5,
        'efficiency': 0.3,
        'stability': 0.2
    }
```

## 数据库设计

### 用户表(users)
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    organization_id INTEGER,
    role VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### 组织表(organizations)
```sql
CREATE TABLE organizations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    contact_email VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### 数据集表(datasets)
```sql
CREATE TABLE datasets (
    id SERIAL PRIMARY KEY,
    version VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    file_path VARCHAR(255) NOT NULL,
    hash VARCHAR(64) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP WITH TIME ZONE
);
```

### 设备表(devices)
```sql
CREATE TABLE devices (
    device_id VARCHAR(64) PRIMARY KEY,
    hardware_fingerprint VARCHAR(128) UNIQUE NOT NULL,
    nickname VARCHAR(50),
    hardware_info JSONB NOT NULL,
    first_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### 测试结果表(benchmark_results)
```sql
CREATE TABLE benchmark_results (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    dataset_version VARCHAR(20) NOT NULL,
    model_config JSONB NOT NULL,      -- 包含参数量、精度等
    hardware_config JSONB NOT NULL,   -- 包含GPU、CPU、内存信息
    framework_config JSONB,           -- 框架配置参数
    performance_metrics JSONB NOT NULL,-- 性能指标
    scores JSONB NOT NULL,            -- 各维度评分
    notes TEXT,                       -- 备注信息
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES devices(device_id)
);
```

### 排行榜表(rankings)
```sql
CREATE TABLE rankings (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,     -- 榜单类别
    result_id INTEGER NOT NULL,
    device_id VARCHAR(64) NOT NULL,
    score DECIMAL(10,2) NOT NULL,
    rank_position INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (result_id) REFERENCES benchmark_results(id),
    FOREIGN KEY (device_id) REFERENCES devices(device_id)
);
```

## API设计

### 1. 公开API

#### 排行榜相关
```
GET /api/v1/rankings
GET /api/v1/rankings/{type}
GET /api/v1/rankings/user/{user_id}
```

#### 数据集相关
```
GET /api/v1/datasets
GET /api/v1/datasets/{version}
GET /api/v1/datasets/{version}/download
```

#### 结果提交
```
POST /api/v1/results
POST /api/v1/results/offline
GET /api/v1/results/{id}
```

### 2. 管理API

#### 数据集管理
```
POST /api/v1/admin/datasets
PUT /api/v1/admin/datasets/{id}
DELETE /api/v1/admin/datasets/{id}
```

#### 用户管理
```
GET /api/v1/admin/users
POST /api/v1/admin/users
PUT /api/v1/admin/users/{id}
DELETE /api/v1/admin/users/{id}
```

### 3. 设备管理API
```
POST /api/v1/devices/register
- 请求：设备硬件信息
- 响应：设备ID

PUT /api/v1/devices/{device_id}/nickname
- 请求：新昵称
- 响应：更新状态
```

### 4. 结果提交API
```
POST /api/v1/results
- 请求：完整的测试结果数据
- 响应：评分和排名信息

POST /api/v1/results/offline
- 请求：离线结果文件
- 响应：评分和排名信息
```

### 5. 排行榜API
```
GET /api/v1/rankings/{category}
- 参数：榜单类别、分页信息
- 响应：排行榜数据

GET /api/v1/rankings/device/{device_id}
- 响应：设备的所有排名信息
```

## 安全设计

### 1. 认证与授权
- JWT token认证
- 基于角色的访问控制
- API访问限流
- 请求签名验证

### 2. 数据安全
- 数据传输加密
- 敏感信息脱敏
- 数据备份策略
- 审计日志记录

### 3. 防作弊机制
- 硬件信息验证
- 结果一致性检查
- 异常检测算法
- IP地址监控

### 4. 密钥管理架构

#### 4.1 主密钥管理
```python
class MasterKeyManagement:
    def __init__(self):
        self._hsm_client = HSMClient()  # 硬件安全模块客户端
        self._key_backup = SecureKeyBackup()
    
    def generate_master_key(self):
        # 在HSM中生成主密钥
        key_material = self._hsm_client.generate_key()
        # 备份密钥
        self._key_backup.backup_master_key(key_material)
        return key_material
    
    def rotate_master_key(self):
        # 主密钥轮换流程
        new_key = self.generate_master_key()
        self._update_derived_keys(new_key)
        self._archive_old_key()
```

#### 4.2 密钥派生系统
```python
class KeyDerivationSystem:
    def derive_dataset_key(self, master_key, version, params):
        # 使用HKDF派生数据集密钥
        context = self._build_derivation_context(version, params)
        return self._hkdf_derive(
            master_key=master_key,
            context=context,
            salt=os.urandom(32)
        )
    
    def derive_distribution_key(self, dataset_key, params):
        # 派生用于分发的密钥
        return self._hkdf_derive(
            master_key=dataset_key,
            context=self._build_distribution_context(params),
            salt=os.urandom(32)
        )
```

### 5. 数据安全实现

#### 5.1 数据加密服务
```python
class DataEncryptionService:
    def __init__(self, key_management):
        self._key_management = key_management
        self._cipher_suite = CipherSuite()
    
    def encrypt_dataset(self, data, version):
        # 1. 获取加密密钥
        encryption_key = self._key_management.get_encryption_key(version)
        
        # 2. 加密数据
        encrypted_data = self._cipher_suite.encrypt(
            data=data,
            key=encryption_key,
            aad=self._generate_aad(version)  # 附加认证数据
        )
        
        # 3. 生成验证标签
        verification_tag = self._generate_verification_tag(
            encrypted_data=encrypted_data,
            version=version
        )
        
        return {
            'encrypted_data': encrypted_data,
            'verification_tag': verification_tag,
            'metadata': self._generate_metadata(version)
        }
```

#### 5.2 安全存储服务
```python
class SecureStorageService:
    def store_encrypted_dataset(self, encrypted_data, metadata):
        # 1. 验证数据完整性
        self._verify_data_integrity(encrypted_data, metadata)
        
        # 2. 加密元数据
        encrypted_metadata = self._encrypt_metadata(metadata)
        
        # 3. 安全存储
        storage_result = self._store_data(
            encrypted_data=encrypted_data,
            encrypted_metadata=encrypted_metadata
        )
        
        # 4. 验证存储结果
        return self._verify_storage(storage_result)
```

### 6. 防作弊系统

#### 6.1 结果验证服务
```python
class ResultValidationService:
    def validate_benchmark_result(self, result, hardware_info):
        # 1. 验证硬件指纹
        if not self._verify_hardware_fingerprint(hardware_info):
            raise ValidationError("Invalid hardware fingerprint")
        
        # 2. 检查结果一致性
        if not self._check_result_consistency(result):
            raise ValidationError("Inconsistent result data")
        
        # 3. 性能指标分析
        if not self._analyze_performance_metrics(result):
            raise ValidationError("Suspicious performance metrics")
        
        # 4. 记录验证结果
        self._log_validation_result(result, hardware_info)
```

## 部署架构

### 1. 生产环境
```
                    [负载均衡器]
                         |
        +---------------+---------------+
        |               |               |
    [应用服务器1]  [应用服务器2]  [应用服务器3]
        |               |               |
        +---------------+---------------+
                         |
                    [数据库集群]
                         |
                    [文件存储]
```

### 2. 服务配置
- Nginx负载均衡
- Docker容器化部署
- Kubernetes编排
- HTTPS证书配置

## 监控与维护

### 1. 系统监控
- 服务器性能监控
- API调用统计
- 错误日志分析
- 资源使用监控

### 2. 数据维护
- 定期数据备份
- 历史数据归档
- 数据一致性检查
- 性能优化

## 开发路线图

### 第一阶段：基础功能
1. 基础API实现
2. 数据库设计与实现
3. 用户认证系统

### 第二阶段：核心功能
1. 排行榜系统
2. 数据集管理
3. 结果验证系统

### 第三阶段：高级功能
1. 管理后台
2. 数据分析
3. 性能优化

## 文件结构

```
server/
├── src/
│   ├── api/                      # API路由
│   │   ├── v1/
│   │   │   ├── rankings.py
│   │   │   ├── datasets.py
│   │   │   ├── results.py
│   │   │   └── admin/
│   │   ├── core/                     # 核心功能
│   │   │   ├── security.py
│   │   │   ├── config.py
│   │   │   └── dependencies.py
│   │   ├── db/                       # 数据库
│   │   │   ├── models.py
│   │   │   ├── crud.py
│   │   │   └── migrations/
│   │   ├── services/                 # 业务逻辑
│   │   │   ├── ranking.py
│   │   │   ├── validation.py
│   │   │   └── dataset.py
│   │   └── utils/                    # 工具函数
│   │       ├── crypto.py
│   │       ├── storage.py
│   │       └── validators.py
│   ├── tests/                        # 测试
│   ├── alembic/                      # 数据库迁移
│   ├── docker/                       # Docker配置
│   └── frontend/                     # 前端应用
│       ├── src/
│       │   ├── components/
│       │   ├── views/
│       │   └── store/
│       └── public/
```

## 注意事项

### 1. 开发规范
- 遵循RESTful API设计
- 使用类型注解
- 编写完整的测试
- 保持代码文档更新

### 2. 性能优化
- 使用适当的缓存策略
- 优化数据库查询
- 实现合理的分页
- 控制响应大小

### 3. 安全考虑
- 定期安全审计
- 漏洞扫描
- 更新依赖包
- 监控异常访问

### 4. 密钥管理规范
- 主密钥必须存储在硬件安全模块中
- 派生密钥必须使用HKDF
- 密钥材料禁止写入日志
- 必须实现密钥轮换机制

### 5. 加密算法规范
- 对称加密使用AES-256-GCM
- 非对称加密使用RSA-4096
- 哈希函数使用SHA-384或更高
- 必须使用安全随机数生成器

### 6. 安全开发规范
- 所有加密操作必须有单元测试
- 定期进行安全代码审计
- 使用静态代码分析工具
- 保持依赖包的最新安全补丁

### 7. 部署安全规范
- 使用专用加密服务器
- 实施网络隔离
- 启用安全审计日志
- 定期进行安全漏洞扫描

### 8. 安全审计
- 定期进行安全审计
- 监控异常访问
- 更新依赖包
- 实现安全审计日志 