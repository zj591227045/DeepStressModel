# DeepStressModel-Leaderboard 开发规划

## 项目概述

DeepStressModel-Leaderboard 是 DeepStressModel 项目的配套服务端项目，提供全球性能测试排行榜服务。本项目采用现代化的Web技术栈，提供RESTful API接口，支持数据集分发、成绩排名、用户互动等功能。

## 开发环境

- Python 3.10+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose
- Nginx

## 系统架构

### 1. 微服务架构

```
                                    [负载均衡 Nginx]
                                           |
                    +--------------------+-------------------+
                    |                    |                  |
            [API Gateway 服务]    [数据集分发服务]     [WebSocket 服务]
                    |                    |                  |
            [身份验证服务]               |             [实时通知服务]
                    |                    |                  |
                    +--------------------+-------------------+
                                        |
                                [PostgreSQL + Redis]
```

### 2. 核心服务

1. **API Gateway 服务**
   - 路由管理
   - 请求限流
   - 响应缓存
   - 日志记录

2. **数据集分发服务**
   - 数据集版本管理
   - 加密传输
   - 分块下载
   - CDN分发

3. **排行榜管理服务**
   - 成绩验证
   - 排名计算
   - 数据统计
   - 反作弊系统

4. **用户互动服务**
   - 评论管理
   - 点赞系统
   - 通知推送

## 数据库设计

### 1. PostgreSQL 表结构

#### 1.1 数据集表(datasets)
```sql
CREATE TABLE datasets (
    id SERIAL PRIMARY KEY,
    version VARCHAR(50) NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    file_path TEXT NOT NULL,
    metadata JSONB,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

#### 1.2 排行榜记录表(benchmark_records)
```sql
CREATE TABLE benchmark_records (
    id SERIAL PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    framework VARCHAR(50) NOT NULL,
    model_params BIGINT NOT NULL,
    framework_config JSONB,
    gpu_config JSONB NOT NULL,
    score DECIMAL(10,2) NOT NULL,
    concurrent_count INTEGER NOT NULL,
    tps DECIMAL(10,2) NOT NULL,
    dataset_version VARCHAR(50) NOT NULL,
    machine_id VARCHAR(100) NOT NULL,
    likes_count INTEGER DEFAULT 0,
    dislikes_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_machine_framework UNIQUE (machine_id, framework)
);
```

#### 1.3 评论表(comments)
```sql
CREATE TABLE comments (
    id SERIAL PRIMARY KEY,
    record_id INTEGER REFERENCES benchmark_records(id),
    content TEXT NOT NULL,
    author_ip VARCHAR(45) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false
);
```

#### 1.4 互动记录表(interactions)
```sql
CREATE TABLE interactions (
    id SERIAL PRIMARY KEY,
    record_id INTEGER REFERENCES benchmark_records(id),
    machine_id VARCHAR(100) NOT NULL,
    interaction_type VARCHAR(10) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_interaction UNIQUE (record_id, machine_id)
);
```

### 2. Redis 缓存设计

```
# 排行榜缓存
leaderboard:global -> Sorted Set (score -> record_id)
leaderboard:framework:{framework_name} -> Sorted Set

# 记录详情缓存
record:{record_id} -> Hash

# 评论列表缓存
comments:{record_id} -> List

# 互动计数缓存
interactions:{record_id} -> Hash
```

## API 接口设计

### 1. RESTful API

#### 1.1 数据集接口
```
GET /api/v1/datasets/latest
GET /api/v1/datasets/{version}
GET /api/v1/datasets/{version}/download
```

#### 1.2 排行榜接口
```
POST /api/v1/benchmarks
GET /api/v1/benchmarks
GET /api/v1/benchmarks/{id}
GET /api/v1/benchmarks/frameworks/{framework}
```

#### 1.3 互动接口
```
POST /api/v1/benchmarks/{id}/like
POST /api/v1/benchmarks/{id}/dislike
POST /api/v1/benchmarks/{id}/comments
GET /api/v1/benchmarks/{id}/comments
```

### 2. WebSocket 接口
```
ws://api/v1/ws/leaderboard -> 实时排行榜更新
ws://api/v1/ws/notifications -> 实时通知
```

## 开发任务清单

### 第一阶段：基础设施搭建

1. 项目初始化
   - [ ] 创建FastAPI项目结构
   - [ ] 配置Docker开发环境
   - [ ] 设置CI/CD流程

2. 数据库设计
   - [ ] 实现数据库迁移
   - [ ] 创建数据模型
   - [ ] 设置Redis缓存

### 第二阶段：核心功能开发

1. 数据集管理
   - [ ] 实现数据集上传
   - [ ] 实现版本控制
   - [ ] 实现分发机制

2. 排行榜功能
   - [ ] 实现成绩提交
   - [ ] 实现排名计算
   - [ ] 实现数据验证

3. 互动功能
   - [ ] 实现评论系统
   - [ ] 实现点赞功能
   - [ ] 实现实时通知

### 第三阶段：性能优化

1. 缓存优化
   - [ ] 实现多级缓存
   - [ ] 优化缓存策略
   - [ ] 实现缓存预热

2. 性能监控
   - [ ] 集成性能监控
   - [ ] 实现日志分析
   - [ ] 设置告警机制

## AI开发提示

### 1. 项目结构生成

```
请帮我创建一个基于FastAPI的项目结构，包含以下要求：
1. 使用poetry进行依赖管理
2. 采用模块化设计
3. 包含完整的测试框架
4. 支持Docker部署
5. 包含CI/CD配置
```

### 2. 数据模型生成

```
请基于以下数据库表结构，生成SQLAlchemy模型：
1. 包含所有必要的关系
2. 添加适当的索引
3. 实现基础的CRUD方法
4. 添加数据验证
```

### 3. API接口实现

```
请帮我实现以下API接口：
1. 遵循RESTful设计规范
2. 包含完整的参数验证
3. 添加适当的缓存机制
4. 实现错误处理
5. 添加API文档
```

### 4. 缓存策略实现

```
请帮我实现以下缓存策略：
1. 使用Redis作为缓存层
2. 实现缓存预热机制
3. 处理缓存击穿问题
4. 实现缓存自动更新
```

### 5. 测试用例生成

```
请为以下功能生成测试用例：
1. 包含单元测试和集成测试
2. 使用pytest框架
3. 添加测试数据生成器
4. 实现测试覆盖率报告
```

### 6. 简化的测试验证机制

#### 6.1 设备认证（简化版）
```sql
CREATE TABLE device_registrations (
    id SERIAL PRIMARY KEY,
    machine_id VARCHAR(100) UNIQUE NOT NULL,
    hardware_info JSONB NOT NULL,     -- 包含CPU、内存、主板信息
    gpu_info JSONB NOT NULL,          -- 包含GPU配置信息
    api_key VARCHAR(64) UNIQUE,       -- API密钥
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

#### 6.2 测试会话（简化版）
```sql
CREATE TABLE benchmark_sessions (
    id SERIAL PRIMARY KEY,
    machine_id VARCHAR(100) NOT NULL,
    session_id VARCHAR(64) UNIQUE NOT NULL,
    test_status VARCHAR(20) NOT NULL,  -- 'running', 'completed', 'failed'
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    test_metrics JSONB,                -- 测试结果指标
    system_metrics JSONB,              -- 系统资源使用指标
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (machine_id) REFERENCES device_registrations(machine_id)
);
```

#### 6.3 简化的验证流程
```
[测试工具]                                    [排行榜服务]
    |                                             |
    |--- 1. 注册设备 ---------------------------->|
    |        - 硬件信息                           |
    |        - GPU信息                            |
    |                                             |
    |<-- 2. 返回API密钥 --------------------------|
    |                                             |
    |--- 3. 开始测试 ---------------------------->|
    |        - API密钥认证                        |
    |        - 测试参数                           |
    |                                             |
    |--- 4. 测试过程中定期上报 ----------------->|
    |        - 系统资源使用情况                   |
    |        - 当前测试指标                       |
    |                                             |
    |--- 5. 提交最终结果 ----------------------->|
    |        - 完整测试数据                       |
    |        - 系统资源使用记录                   |
```

#### 6.4 简化的客户端实现
```python
class BenchmarkClient:
    """测试客户端"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session_id = None
        self.metrics_collector = MetricsCollector()
    
    async def start_test(self, test_params: Dict) -> str:
        """开始测试"""
        response = await self.api_request(
            'POST',
            '/api/v1/benchmarks/start',
            data=test_params
        )
        self.session_id = response['session_id']
        return self.session_id
    
    async def report_metrics(self):
        """上报指标"""
        metrics = {
            'system': self.metrics_collector.get_system_metrics(),
            'test': self.metrics_collector.get_test_metrics()
        }
        await self.api_request(
            'POST',
            f'/api/v1/benchmarks/{self.session_id}/metrics',
            data=metrics
        )
    
    async def submit_results(self, results: Dict):
        """提交结果"""
        final_data = {
            'results': results,
            'metrics': self.metrics_collector.get_all_metrics()
        }
        return await self.api_request(
            'POST',
            f'/api/v1/benchmarks/{self.session_id}/submit',
            data=final_data
        )

class MetricsCollector:
    """指标收集器"""
    
    def get_system_metrics(self) -> Dict:
        """获取系统指标"""
        return {
            'cpu_usage': get_cpu_usage(),
            'memory_usage': get_memory_usage(),
            'gpu_usage': get_gpu_usage()
        }
    
    def get_test_metrics(self) -> Dict:
        """获取测试指标"""
        return {
            'tps': calculate_current_tps(),
            'latency': get_current_latency(),
            'concurrent_count': get_concurrent_count()
        }
```

#### 6.5 服务端验证逻辑
```python
class BenchmarkValidator:
    """测试验证器"""
    
    def validate_metrics(self, metrics: Dict) -> bool:
        """验证指标合理性"""
        return (
            self._validate_resource_usage(metrics['system']) and
            self._validate_performance(metrics['test'])
        )
    
    def _validate_resource_usage(self, system_metrics: Dict) -> bool:
        """验证资源使用是否合理"""
        # 简单的阈值检查
        return (
            0 <= system_metrics['cpu_usage'] <= 100 and
            0 <= system_metrics['memory_usage'] <= 100 and
            0 <= system_metrics['gpu_usage'] <= 100
        )
    
    def _validate_performance(self, test_metrics: Dict) -> bool:
        """验证性能指标是否合理"""
        # 简单的性能指标检查
        return (
            test_metrics['tps'] > 0 and
            test_metrics['latency'] > 0 and
            test_metrics['concurrent_count'] > 0
        )
```

#### 6.6 API接口（简化版）
```
# 设备管理
POST /api/v1/devices/register      # 注册设备
GET /api/v1/devices/status        # 获取设备状态

# 测试管理
POST /api/v1/benchmarks/start     # 开始测试
POST /api/v1/benchmarks/{id}/metrics  # 上报指标
POST /api/v1/benchmarks/{id}/submit   # 提交结果
GET /api/v1/benchmarks/{id}/status    # 获取测试状态
```

#### 6.7 安全考虑（简化版）

1. **基础安全**
   - API密钥认证
   - 请求频率限制
   - 基本的数据验证

2. **作弊防护**
   - 系统资源使用监控
   - 性能指标合理性检查
   - 测试时长验证

3. **数据安全**
   - HTTPS传输
   - 敏感信息加密
   - 数据完整性校验

## 部署架构

### 1. 开发环境
```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - .:/app
    depends_on:
      - postgres
      - redis
  
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: leaderboard
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"
```

### 2. 生产环境

```yaml
version: '3.8'
services:
  nginx:
    image: nginx:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - api

  api:
    build: .
    expose:
      - "8000"
    environment:
      - ENVIRONMENT=production
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_PASSWORD_FILE=/run/secrets/db_password

  redis:
    image: redis:7
    volumes:
      - redis_data:/data
    command: redis-server --requirepass ${REDIS_PASSWORD}

volumes:
  postgres_data:
  redis_data:
```

## 监控与维护

1. 性能监控
   - 使用Prometheus收集指标
   - 使用Grafana展示监控面板
   - 设置关键指标告警

2. 日志管理
   - 使用ELK栈收集日志
   - 实现日志分析
   - 设置异常告警

3. 备份策略
   - 数据库定时备份
   - 数据集文件备份
   - 配置文件备份

## 安全措施

1. API安全
   - 实现请求签名验证
   - 添加IP限流
   - 实现防重放攻击

2. 数据安全
   - 实现数据加密存储
   - 实现敏感信息脱敏
   - 实现数据访问审计

3. 运行安全
   - 容器安全配置
   - 网络访问控制
   - 定期安全扫描

## 安全认证设计

### 1. 认证机制

#### 1.1 设备注册流程
```
[测试工具]                                    [排行榜服务]
    |                                             |
    |--- 1. 生成设备唯一标识(machine_id) -------->|
    |        - 硬件信息哈希                       |
    |        - 显卡信息哈希                       |
    |                                             |
    |<-- 2. 返回注册码(registration_code) --------|
    |         - 12位字母数字组合                  |
    |         - 有效期24小时                      |
    |                                             |
    |--- 3. 用户在网页验证注册码 ---------------->|
    |         - 人机验证                          |
    |         - 邮箱验证                          |
    |                                             |
    |<-- 4. 生成设备密钥对 -----------------------|
    |         - 公钥分发给客户端                  |
    |         - 私钥服务端保存                    |
```

#### 1.2 请求认证流程
```
1. 每次API请求包含以下认证信息：
   - X-Device-ID: 设备唯一标识
   - X-Request-Time: 请求时间戳
   - X-Nonce: 随机字符串
   - X-Signature: 请求签名

2. 签名生成规则：
   signature = HMAC-SHA256(
     secret_key,
     device_id + request_time + nonce + request_body
   )

3. 防重放攻击：
   - 请求时间戳不能超过服务器时间5分钟
   - Nonce在5分钟内不能重复使用
```

### 2. 设备认证数据库设计

#### 2.1 设备注册表(device_registrations)
```sql
CREATE TABLE device_registrations (
    id SERIAL PRIMARY KEY,
    machine_id VARCHAR(100) UNIQUE NOT NULL,
    registration_code VARCHAR(12),
    registration_code_expires_at TIMESTAMP WITH TIME ZONE,
    hardware_hash TEXT NOT NULL,
    gpu_hash TEXT NOT NULL,
    is_verified BOOLEAN DEFAULT false,
    verification_email VARCHAR(255),
    public_key TEXT,
    private_key TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 添加索引
CREATE INDEX idx_machine_id ON device_registrations(machine_id);
CREATE INDEX idx_registration_code ON device_registrations(registration_code);
```

#### 2.2 请求Nonce表(request_nonces)
```sql
CREATE TABLE request_nonces (
    id SERIAL PRIMARY KEY,
    nonce VARCHAR(32) NOT NULL,
    machine_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_nonce UNIQUE (nonce, machine_id)
);

-- 添加过期清理
CREATE INDEX idx_nonce_created_at ON request_nonces(created_at);
-- 自动清理5分钟前的记录
CREATE OR REPLACE FUNCTION clean_expired_nonces()
RETURNS void AS $$
BEGIN
    DELETE FROM request_nonces 
    WHERE created_at < NOW() - INTERVAL '5 minutes';
END;
$$ LANGUAGE plpgsql;
```

### 3. 安全API接口

#### 3.1 设备注册接口
```
POST /api/v1/devices/register
Request:
{
    "hardware_hash": "string",
    "gpu_hash": "string"
}

Response:
{
    "machine_id": "string",
    "registration_code": "string",
    "expires_at": "datetime"
}
```

#### 3.2 设备验证接口
```
POST /api/v1/devices/verify
Request:
{
    "registration_code": "string",
    "email": "string"
}

Response:
{
    "public_key": "string",
    "expires_at": "datetime"
}
```

### 4. 客户端实现建议

#### 4.1 设备标识生成
```python
def generate_hardware_hash():
    """生成硬件信息哈希"""
    hardware_info = {
        'cpu': get_cpu_info(),
        'memory': get_memory_info(),
        'mainboard': get_mainboard_info(),
        'mac_addresses': get_mac_addresses()
    }
    return hashlib.sha256(json.dumps(hardware_info).encode()).hexdigest()

def generate_gpu_hash():
    """生成显卡信息哈希"""
    gpu_info = {
        'devices': get_gpu_devices(),
        'compute_capability': get_compute_capability(),
        'driver_version': get_driver_version()
    }
    return hashlib.sha256(json.dumps(gpu_info).encode()).hexdigest()
```

#### 4.2 请求签名生成
```python
def generate_request_signature(
    secret_key: str,
    device_id: str,
    request_time: str,
    nonce: str,
    body: str
) -> str:
    """生成请求签名"""
    message = f"{device_id}{request_time}{nonce}{body}"
    return hmac.new(
        secret_key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
```

### 5. 安全性考虑

1. **设备绑定**
   - 硬件信息和显卡信息的哈希确保设备唯一性
   - 防止同一份代码在多台机器上使用
   - 硬件变更需要重新注册

2. **人机验证**
   - 注册过程需要人工验证
   - 防止自动化注册攻击
   - 邮箱验证确保可追溯性

3. **请求防护**
   - 签名机制确保请求完整性
   - 时间戳防止重放攻击
   - Nonce防止请求重复使用

4. **密钥保护**
   - 客户端只存储公钥
   - 私钥服务端安全存储
   - 定期轮换密钥机制 