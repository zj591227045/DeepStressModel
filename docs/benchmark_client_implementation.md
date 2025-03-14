# DeepStressModel 跑分功能实现文档

## 功能概述

DeepStressModel跑分功能是一个独立于主测试功能的模块，用于进行标准化的性能测试和排名。该功能支持在线和离线两种模式，确保在各种网络环境下都能完成跑分测试。

## 系统架构

### 模块依赖关系
```
GUI跑分模块 --> 跑分引擎模块 --> 数据集管理模块
    |              |               |
    v              v               v
结果管理模块 <-- 通信模块 <--> 排行榜服务器
```

## 详细模块设计

### 1. GUI跑分模块

#### 1.1 跑分设置界面
- 跑分功能启用开关
- 在线/离线模式选择
- 服务器连接配置
- 跑分数据集更新按钮
- 用户信息设置
  ```python
  class UserInfo:
      def __init__(self):
          self.device_id = self._generate_device_id()  # 设备唯一ID
          self.nickname = ""                           # 用户昵称
          
      def _generate_device_id(self):
          # 基于硬件信息生成唯一ID
          hardware_info = self._collect_hardware_info()
          return self._hash_hardware_info(hardware_info)
  ```

#### 1.2 用户界面交互流程
```
1. 首次启动
   ├── 生成设备唯一ID
   ├── 提示用户设置昵称
   └── 选择在线/离线模式

2. 联网模式
   ├── 连接服务器
   ├── 检查/更新数据集
   ├── 执行测试
   └── 实时上传结果

3. 离线模式
   ├── 导入数据集包
   ├── 执行测试
   └── 导出结果文件
```

### 2. 跑分引擎模块

#### 2.1 标准化测试流程
```python
class BenchmarkProcess:
    def run_benchmark(self):
        # 1. 环境检查阶段
        if not self._check_environment():
            raise EnvironmentError("环境检查失败")
            
        # 2. 数据集准备阶段
        dataset = self._prepare_dataset()
        if not self._verify_dataset_version(dataset):
            raise DatasetError("数据集版本验证失败")
            
        # 3. 执行测试阶段
        config = BenchmarkConfig(
            concurrent_requests=60,  # 固定并发数
            batch_size=1,           # 标准批次大小
            timeout=30              # 请求超时时间
        )
        result = self._run_test(dataset, config)
        
        # 4. 结果验证阶段
        if not self._verify_results(result):
            raise ValidationError("结果验证失败")
            
        return result
```

#### 2.2 性能指标计算
```python
class PerformanceMetrics:
    def calculate_metrics(self, test_results):
        return {
            'avg_latency': self._calculate_average_latency(test_results),
            'throughput': self._calculate_throughput(test_results),
            'avg_token_speed': self._calculate_token_generation_speed(test_results),
            'avg_char_speed': self._calculate_char_generation_speed(test_results),
            'error_rate': self._calculate_error_rate(test_results),
            'p95_latency': self._calculate_p95_latency(test_results),
            'p99_latency': self._calculate_p99_latency(test_results)
        }
    
    def _calculate_token_generation_speed(self, results):
        # 计算平均token生成速度（tokens/s）
        total_tokens = sum(r.output_tokens for r in results)
        total_time = sum(r.duration for r in results)
        return total_tokens / total_time if total_time > 0 else 0
```

### 3. 测试结果管理

#### 3.1 结果数据结构
```python
@dataclass
class BenchmarkResult:
    # 自动生成信息
    device_id: str                # 设备唯一ID
    gpu_info: List[GpuInfo]      # GPU信息列表
    cpu_info: CpuInfo            # CPU信息
    memory_size: int             # 内存大小(GB)
    dataset_version: str         # 数据集版本
    concurrent_requests: int     # 并发数
    total_duration: float        # 总用时(s)
    avg_char_speed: float       # 平均字符生成速度
    avg_tokens_per_second: float # 平均TPS
    
    # 手动填写信息
    nickname: str               # 用户昵称
    model_size: float          # 模型参数量(B)
    model_precision: str       # 模型精度
    framework_config: dict     # 框架配置参数
    notes: str                 # 备注信息
    
    # 测试详细数据
    test_details: List[TestDetail]  # 详细测试数据
```

#### 3.2 本地存储格式
```python
class ResultStorage:
    def save_result(self, result: BenchmarkResult):
        # 1. 保存JSON格式的结果文件
        result_json = self._convert_to_json(result)
        self._save_json_result(result_json)
        
        # 2. 保存详细测试数据
        self._save_test_details(result.test_details)
        
        # 3. 保存到SQLite数据库
        self._save_to_database(result)
    
    def _convert_to_json(self, result):
        return {
            "metadata": {
                "device_id": result.device_id,
                "timestamp": datetime.now().isoformat(),
                "version": "1.0"
            },
            "hardware_info": {
                "gpu": [gpu.to_dict() for gpu in result.gpu_info],
                "cpu": result.cpu_info.to_dict(),
                "memory": result.memory_size
            },
            "test_info": {
                "dataset_version": result.dataset_version,
                "concurrent_requests": result.concurrent_requests,
                "model_config": {
                    "size": result.model_size,
                    "precision": result.model_precision
                },
                "framework_config": result.framework_config
            },
            "results": {
                "total_duration": result.total_duration,
                "avg_char_speed": result.avg_char_speed,
                "avg_tps": result.avg_tokens_per_second
            },
            "user_info": {
                "nickname": result.nickname,
                "notes": result.notes
            }
        }
```

#### 3.3 离线模式工作流程
```
1. 数据集准备
   ├── 下载离线数据集包
   ├── 验证数据集完整性
   └── 导入本地存储

2. 测试执行
   ├── 环境检查
   ├── 执行标准测试流程
   └── 本地保存结果

3. 结果导出
   ├── 生成加密结果文件
   ├── 包含完整测试信息
   └── 导出为便携格式

4. 手动上传
   ├── 访问排行榜网站
   ├── 上传结果文件
   └── 填写用户昵称
```

### 4. 数据集管理模块

#### 4.1 加密数据集管理器
- 从服务器获取加密数据集
- 本地加密数据集存储
- 数据集完整性验证
- 数据集版本管理

#### 4.2 离线数据包管理器
- 导入离线数据包
- 验证数据包签名
- 管理本地数据包版本

### 5. 通信模块

#### 5.1 联网模式
- 与排行榜服务器的安全通信
- 数据集更新
- 结果上传
- 实时排名查询

#### 5.2 离线模式
- 生成加密结果文件
- 验证结果文件完整性
- 准备用于手动上传的数据包

### 6. 结果管理模块

#### 6.1 结果存储
- 本地跑分历史记录
- 加密结果文件管理
- 临时结果缓存

#### 6.2 结果分析
- 性能指标计算
- 与历史记录比较
- 生成详细报告

## 数据库设计

### 跑分配置表(benchmark_configs)
```sql
CREATE TABLE benchmark_configs (
    id INTEGER PRIMARY KEY,
    device_id TEXT NOT NULL,      -- 设备唯一ID
    nickname TEXT,                -- 用户昵称
    mode TEXT NOT NULL,           -- 'online' 或 'offline'
    server_url TEXT,              -- 排行榜服务器地址
    hardware_info TEXT,           -- 硬件信息JSON
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    UNIQUE(device_id)
);
```

### 跑分数据集表(benchmark_datasets)
```sql
CREATE TABLE benchmark_datasets (
    id INTEGER PRIMARY KEY,
    version TEXT NOT NULL,        -- 数据集版本
    hash TEXT NOT NULL,           -- 数据集哈希
    encrypted_path TEXT NOT NULL, -- 加密数据集路径
    downloaded_at TIMESTAMP,
    validated_at TIMESTAMP
);
```

### 跑分结果表(benchmark_results)
```sql
CREATE TABLE benchmark_results (
    id INTEGER PRIMARY KEY,
    dataset_version TEXT NOT NULL,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    score REAL,                   -- 综合跑分
    performance_metrics TEXT,     -- 详细性能指标JSON
    uploaded BOOLEAN,             -- 是否已上传
    result_file_path TEXT,        -- 加密结果文件路径
    created_at TIMESTAMP
);
```

## 安全设计

### 1. 数据安全

#### 1.1 多层加密机制
- 第一层：服务器端加密（数据集加密）
- 第二层：分发加密（解密器保护）
- 第三层：运行时加密（硬件绑定）

#### 1.2 密钥管理
```python
class KeyManager:
    def __init__(self):
        self._distribution_key = None
        self._runtime_key = None
        self._hardware_id = None
    
    def initialize(self, decoder_template):
        self._hardware_id = self._get_hardware_fingerprint()
        self._distribution_key = decoder_template.get_protected_key()
        self._runtime_key = self._derive_runtime_key()
    
    def _derive_runtime_key(self):
        if not self._distribution_key or not self._hardware_id:
            raise SecurityException("Key manager not properly initialized")
        return self._generate_runtime_key(self._distribution_key, self._hardware_id)
```

#### 1.3 解密器实现
```python
class DatasetDecoder:
    def __init__(self, decoder_template):
        self._key_manager = KeyManager()
        self._decoder_template = decoder_template
        self._initialized = False
    
    def initialize(self):
        # 初始化解密器并绑定硬件
        self._key_manager.initialize(self._decoder_template)
        self._initialized = True
    
    def decrypt_dataset(self, encrypted_dataset):
        if not self._initialized:
            raise SecurityException("Decoder not initialized")
        
        # 验证数据集完整性
        if not self._verify_dataset_integrity(encrypted_dataset):
            raise SecurityException("Dataset integrity check failed")
        
        # 使用运行时密钥解密数据集
        return self._decrypt_data(encrypted_dataset)
```

#### 1.4 安全存储
```python
class SecureStorage:
    def store_encrypted_dataset(self, encrypted_dataset, version_info):
        # 存储加密数据集
        storage_path = self._get_secure_storage_path()
        metadata = {
            'version': version_info['version'],
            'checksum': self._calculate_checksum(encrypted_dataset),
            'created_at': datetime.now().isoformat()
        }
        
        # 加密存储元数据
        self._store_encrypted_metadata(metadata)
        self._store_encrypted_data(encrypted_dataset, storage_path)
```

### 2. 通信安全

#### 2.1 安全通信实现
```python
class SecureCommunication:
    def __init__(self, server_public_key):
        self._server_public_key = server_public_key
        self._session_key = None
    
    def establish_secure_channel(self):
        # 建立安全通信通道
        self._session_key = self._generate_session_key()
        encrypted_session_key = self._encrypt_with_server_key(self._session_key)
        return self._perform_handshake(encrypted_session_key)
    
    def send_encrypted_result(self, benchmark_result):
        if not self._session_key:
            raise SecurityException("Secure channel not established")
        
        encrypted_result = self._encrypt_with_session_key(benchmark_result)
        signature = self._sign_data(encrypted_result)
        return self._send_data(encrypted_result, signature)
```

### 3. 防作弊机制

#### 3.1 硬件指纹实现
```python
class HardwareFingerprint:
    def generate_fingerprint(self):
        components = [
            self._get_cpu_info(),
            self._get_gpu_info(),
            self._get_motherboard_info(),
            self._get_mac_addresses()
        ]
        return self._generate_secure_hash(components)
    
    def verify_fingerprint(self, stored_fingerprint):
        current_fingerprint = self.generate_fingerprint()
        return self._secure_compare(current_fingerprint, stored_fingerprint)
```

#### 3.2 运行时保护
```python
class RuntimeProtection:
    def __init__(self):
        self._integrity_checker = IntegrityChecker()
        self._memory_protector = MemoryProtector()
    
    def secure_runtime(self):
        # 启动运行时保护
        self._integrity_checker.start_monitoring()
        self._memory_protector.protect_sensitive_memory()
    
    def verify_runtime_integrity(self):
        return (self._integrity_checker.verify_integrity() and
                self._memory_protector.verify_memory_protection())
```

## 开发路线图

### 第一阶段：基础功能
1. 跑分GUI界面实现
2. 加密数据集管理
3. 基础跑分流程

### 第二阶段：通信实现
1. 服务器通信模块
2. 离线模式支持
3. 结果加密与验证

### 第三阶段：完善功能
1. 性能优化
2. 安全机制完善
3. 用户体验改进

## 文件结构

```
src/
├── benchmark/                    # 跑分模块
│   ├── gui/                     
│   │   ├── benchmark_window.py  # 跑分主窗口
│   │   ├── settings_panel.py    # 设置面板
│   │   └── result_panel.py      # 结果显示面板
│   ├── engine/
│   │   ├── benchmark_manager.py # 跑分管理器
│   │   ├── result_validator.py  # 结果验证器
│   │   └── metrics.py          # 性能指标计算
│   ├── data/
│   │   ├── dataset_manager.py   # 数据集管理
│   │   ├── crypto.py           # 加密工具
│   │   └── result_storage.py   # 结果存储
│   └── network/
│       ├── online_client.py     # 在线通信客户端
│       └── offline_manager.py   # 离线数据管理
```

## 注意事项

### 1. 开发规范
- 严格遵循加密标准
- 确保跑分流程的一致性
- 做好异常处理和日志记录

### 2. 测试要求
- 全面的单元测试覆盖
- 模拟各种网络环境的测试
- 安全机制的渗透测试

### 3. 性能考虑
- 最小化加密开销
- 优化数据集加载
- 确保UI响应性 

## 开发规范

### 1. 加密相关规范
- 所有密钥操作必须在内存安全区域进行
- 禁止将密钥明文写入日志或配置文件
- 必须使用安全随机数生成器
- 定期验证密钥完整性

### 2. 安全编码规范
- 使用类型注解确保类型安全
- 所有外部输入必须进行验证
- 异常处理必须包含安全相关信息
- 敏感操作必须记录安全日志

### 3. 测试规范
- 必须包含密钥管理单元测试
- 必须包含解密器完整性测试
- 必须包含硬件指纹验证测试
- 必须包含内存保护测试 

## UI设计与交互

### 1. 主界面布局
```python
class BenchmarkMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DeepStressModel 跑分")
        
        # 主布局
        self.main_layout = QVBoxLayout()
        
        # 顶部工具栏
        self.toolbar = self._create_toolbar()
        
        # 标签页容器
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self._create_benchmark_tab(), "跑分测试")
        self.tab_widget.addTab(self._create_history_tab(), "历史记录")
```

### 2. 跑分测试界面
```python
class BenchmarkTab(QWidget):
    def __init__(self):
        super().__init__()
        
        # 左侧：测试控制面板
        self.control_panel = QWidget()
        self.control_layout = QVBoxLayout()
        
        # 用户信息和模式选择区域
        self.user_config = UserConfigWidget()
        
        # 数据集管理区域
        self.dataset_manager = DatasetManagerWidget()
        
        # 模型配置区域（复用现有测试界面的ModelSelector）
        self.model_selector = ModelSelector()  # 从主测试界面复用
        
        # 右侧：实时监控面板（复用现有测试界面的GPUMonitor）
        self.monitor_panel = QWidget()
        self.monitor_layout = QVBoxLayout()
        self.gpu_monitor = GPUMonitor()  # 从主测试界面复用
        
        # 性能指标图表
        self.performance_charts = PerformanceChartsWidget()
        
        # 底部：状态和控制
        self.status_bar = StatusBarWidget()
```

### 3. 用户配置组件
```python
class UserConfigWidget(QGroupBox):
    def __init__(self):
        super().__init__("用户配置")
        
        self.layout = QFormLayout()
        
        # 用户昵称输入
        self.nickname_input = QLineEdit()
        
        # 运行模式选择
        self.mode_select = QComboBox()
        self.mode_select.addItems(["联网模式", "离线模式"])
        
        self.layout.addRow("昵称:", self.nickname_input)
        self.layout.addRow("运行模式:", self.mode_select)
```

### 4. 数据集管理组件
```python
class DatasetManagerWidget(QGroupBox):
    def __init__(self):
        super().__init__("数据集管理")
        
        self.layout = QVBoxLayout()
        
        # 当前数据集信息显示
        self.dataset_info = QLabel()
        
        # 联网模式：更新按钮
        self.update_button = QPushButton("更新数据集")
        self.update_button.clicked.connect(self._update_dataset)
        
        # 离线模式：上传按钮
        self.upload_button = QPushButton("上传数据集")
        self.upload_button.clicked.connect(self._upload_dataset)
        
        # 根据模式显示/隐藏相应按钮
        self._update_mode_ui()
```

### 5. 监控界面组件
```python
class PerformanceChartsWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        self.layout = QVBoxLayout()
        
        # TPS曲线图
        self.tps_chart = LineChartWidget("Token生成速度")
        
        # 延迟分布图
        self.latency_chart = HistogramWidget("请求延迟分布")
        
        # 内存使用图
        self.memory_chart = AreaChartWidget("内存使用")
```

### 6. 历史记录界面
```python
class HistoryTab(QWidget):
    def __init__(self):
        super().__init__()
        
        # 历史记录表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(8)
        self.history_table.setHorizontalHeaderLabels([
            "测试时间", "数据集版本", "模型配置",
            "平均TPS", "平均延迟", "成功率",
            "上传状态", "操作"
        ])
        
        # 详情查看面板
        self.detail_panel = TestDetailPanel()
```

## 配置文件设计
```yaml
# config/benchmark_config.yaml
server:
  url: "https://benchmark.deepstressmodel.com"
  api_version: "v1"
  timeout: 30
  retry_count: 3
  
security:
  encryption_key_path: "/path/to/encryption/key"
  cert_path: "/path/to/cert"
  
storage:
  dataset_dir: "./datasets"
  result_dir: "./results"
  log_dir: "./logs"
```

## 数据结构设计

### 1. 配置数据结构
```python
@dataclass
class BenchmarkConfig:
    # 基本配置
    mode: str                     # 运行模式
    nickname: str                 # 用户昵称
    server_url: Optional[str]     # 服务器地址
    
    # 模型配置
    model_size: float            # 模型参数量
    model_precision: str         # 模型精度
    framework_config: dict       # 框架配置
    
    # 测试参数
    concurrent_requests: int = 60  # 固定并发数
    batch_size: int = 1          # 批次大小
    timeout: int = 30            # 超时时间
```

### 2. 测试数据结构
```python
@dataclass
class TestMetrics:
    timestamp: datetime          # 时间戳
    request_id: str             # 请求ID
    input_tokens: int           # 输入token数
    output_tokens: int          # 输出token数
    duration: float             # 处理时间
    gpu_util: List[float]       # GPU利用率
    memory_util: List[float]    # 内存利用率
    error: Optional[str]        # 错误信息

@dataclass
class TestSession:
    session_id: str             # 会话ID
    start_time: datetime        # 开始时间
    config: BenchmarkConfig     # 测试配置
    metrics: List[TestMetrics]  # 测试指标
    status: str                 # 会话状态
```

## 文件结构更新

```
src/
├── benchmark/
│   ├── gui/
│   │   ├── windows/
│   │   │   ├── main_window.py     # 主窗口
│   │   │   ├── benchmark_tab.py   # 跑分标签页
│   │   │   ├── history_tab.py     # 历史记录标签页
│   │   │   └── settings_tab.py    # 设置标签页
│   │   ├── widgets/
│   │   │   ├── model_config.py    # 模型配置组件
│   │   │   ├── test_params.py     # 测试参数组件
│   │   │   ├── performance.py     # 性能监控组件
│   │   │   └── charts/           # 图表组件
│   │   └── styles/
│   │       ├── dark_theme.qss     # 深色主题
│   │       └── light_theme.qss    # 浅色主题
│   ├── core/
│   │   ├── config.py             # 配置管理
│   │   ├── session.py            # 会话管理
│   │   └── metrics.py            # 指标计算
│   └── utils/
│       ├── chart_utils.py        # 图表工具
│       ├── data_export.py        # 数据导出
│       └── validators.py         # 数据验证
```

## 开发规范补充

### 1. UI开发规范

#### 1.1 布局规范
- 使用栅格布局确保界面整洁
- 保持8px的基础间距
- 组件对齐遵循Material Design规范
- 使用QSS样式表统一界面风格

#### 1.2 交互规范
```python
class InteractionGuidelines:
    # 响应时间要求
    MAX_UI_BLOCK_TIME = 100      # 最大UI阻塞时间(ms)
    PROGRESS_UPDATE_INTERVAL = 50 # 进度更新间隔(ms)
    
    # 反馈机制
    @staticmethod
    def show_operation_feedback(operation_type: str):
        # 操作反馈（加载动画、提示信息等）
        pass
    
    @staticmethod
    def handle_long_operation(operation: Callable):
        # 长时间操作处理（进度条、后台任务等）
        pass
```

#### 1.3 主题规范
```python
class ThemeConstants:
    # 颜色定义
    PRIMARY_COLOR = "#2196F3"
    SECONDARY_COLOR = "#FFC107"
    ERROR_COLOR = "#F44336"
    SUCCESS_COLOR = "#4CAF50"
    
    # 字体定义
    FONT_FAMILY = "Segoe UI"
    FONT_SIZES = {
        "small": 12,
        "normal": 14,
        "large": 16,
        "header": 20
    }
```

### 2. 数据处理规范

#### 2.1 数据验证
```python
class DataValidator:
    @staticmethod
    def validate_model_config(config: dict) -> bool:
        required_fields = ["size", "precision", "framework"]
        return all(field in config for field in required_fields)
    
    @staticmethod
    def validate_test_results(results: List[TestMetrics]) -> bool:
        # 验证测试结果的完整性和合理性
        return all(
            result.duration > 0 and
            result.output_tokens > 0
            for result in results
        )
```

#### 2.2 数据格式化
```python
class DataFormatter:
    @staticmethod
    def format_metrics(metrics: TestMetrics) -> dict:
        return {
            "timestamp": metrics.timestamp.isoformat(),
            "tps": metrics.output_tokens / metrics.duration,
            "latency": f"{metrics.duration * 1000:.2f}ms",
            "gpu_util": f"{max(metrics.gpu_util):.1f}%"
        }
```

### 3. 性能优化规范

#### 3.1 UI性能
```python
class UIPerformanceGuidelines:
    # 图表更新策略
    CHART_UPDATE_INTERVAL = 1000  # ms
    MAX_DATA_POINTS = 100        # 最大数据点数
    
    # 数据缓冲策略
    METRICS_BUFFER_SIZE = 1000   # 指标缓冲区大小
    
    @staticmethod
    def optimize_chart_update(chart: QChart):
        # 优化图表更新性能
        pass
```

#### 3.2 内存管理
```python
class MemoryManagement:
    @staticmethod
    def cleanup_test_session(session: TestSession):
        # 清理不需要的会话数据
        pass
    
    @staticmethod
    def optimize_metrics_storage(metrics: List[TestMetrics]):
        # 优化指标存储
        pass
``` 