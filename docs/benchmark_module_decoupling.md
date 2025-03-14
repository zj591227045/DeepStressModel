# DeepStressModel 跑分模块解耦策略

本文档详细说明了 DeepStressModel 跑分模块与测试工具默认测试模块的解耦策略，包括架构设计、代码实现和配置管理。

## 目录

- [解耦目标](#解耦目标)
- [解耦策略](#解耦策略)
  - [架构层面解耦](#架构层面解耦)
  - [代码层面解耦](#代码层面解耦)
  - [功能层面解耦](#功能层面解耦)
- [实现方案](#实现方案)
  - [目录结构设计](#目录结构设计)
  - [接口设计](#接口设计)
  - [配置管理](#配置管理)
  - [动态加载机制](#动态加载机制)
- [迁移计划](#迁移计划)
- [测试策略](#测试策略)

## 解耦目标

跑分模块与测试工具默认测试模块解耦的主要目标是：

1. **功能独立**：跑分模块可以独立开启或关闭，不影响核心测试功能
2. **代码隔离**：跑分模块的代码与核心测试模块的代码完全分离
3. **错误隔离**：跑分模块的错误不会影响核心测试功能
4. **资源隔离**：跑分模块使用独立的资源，不与核心测试模块共享关键资源
5. **可维护性**：便于独立维护和更新跑分模块，不影响核心测试模块

## 解耦策略

### 架构层面解耦

#### 1. 插件化架构

将跑分模块设计为可选插件，通过插件管理器动态加载和卸载。

```python
# 插件管理器示例
class PluginManager:
    def __init__(self):
        self.plugins = {}
        
    def register_plugin(self, name, plugin):
        self.plugins[name] = plugin
        
    def get_plugin(self, name):
        return self.plugins.get(name)
        
    def has_plugin(self, name):
        return name in self.plugins
```

#### 2. 依赖注入

使用依赖注入模式，减少模块间的直接依赖。

```python
# 依赖注入示例
class TestManager:
    def __init__(self, plugin_manager=None):
        self.plugin_manager = plugin_manager
        
    def run_test(self, config):
        # 核心测试逻辑
        result = self._execute_test(config)
        
        # 如果启用了跑分插件，则调用跑分功能
        if self.plugin_manager and self.plugin_manager.has_plugin('benchmark'):
            benchmark_plugin = self.plugin_manager.get_plugin('benchmark')
            benchmark_plugin.process_result(result)
            
        return result
```

#### 3. 事件驱动

使用事件驱动模式，通过事件总线进行模块间通信。

```python
# 事件总线示例
class EventBus:
    def __init__(self):
        self.listeners = {}
        
    def subscribe(self, event_type, listener):
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(listener)
        
    def publish(self, event_type, data):
        if event_type in self.listeners:
            for listener in self.listeners[event_type]:
                listener(data)
```

### 代码层面解耦

#### 1. 独立的模块结构

创建独立的 `benchmark` 目录，包含所有跑分相关的代码。

```
src/
├── api/
├── benchmark/  # 跑分模块
│   ├── api/
│   ├── crypto/
│   ├── data/
│   ├── gui/
│   └── utils/
├── engine/
├── gui/
└── utils/
```

#### 2. 接口隔离

定义清晰的接口，用于跑分模块与核心测试模块之间的通信。

```python
# 接口定义示例
class BenchmarkInterface:
    def process_test_result(self, result):
        """处理测试结果"""
        pass
        
    def get_benchmark_status(self):
        """获取跑分状态"""
        pass
        
    def is_benchmark_enabled(self):
        """检查跑分功能是否启用"""
        pass
```

#### 3. 工厂模式

使用工厂模式创建对象，隐藏具体实现细节。

```python
# 工厂模式示例
class BenchmarkFactory:
    @staticmethod
    def create_benchmark_manager(config):
        if config.get('benchmark_enabled', False):
            from src.benchmark.benchmark_manager import BenchmarkManager
            return BenchmarkManager(config)
        else:
            return None
```

### 功能层面解耦

#### 1. 功能开关

实现全局功能开关，允许完全禁用跑分功能。

```python
# 配置示例
config = {
    'benchmark_enabled': True,  # 是否启用跑分功能
    'benchmark_server_url': 'https://benchmark.example.com',
    'benchmark_api_key': 'your_api_key'
}
```

#### 2. 资源隔离

确保跑分模块使用独立的资源文件和配置。

```python
# 资源加载示例
def load_resources(module_name):
    resource_path = f"resources/{module_name}"
    if not os.path.exists(resource_path):
        os.makedirs(resource_path)
    return resource_path
```

#### 3. 错误隔离

实现错误隔离机制，确保跑分模块的错误不会传播到核心测试模块。

```python
# 错误隔离示例
def safe_call(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Error in function {func.__name__}: {str(e)}")
        return None
```

## 实现方案

### 目录结构设计

```
src/
├── api/                  # 核心API模块
├── benchmark/            # 跑分模块（新增）
│   ├── __init__.py
│   ├── api/              # 跑分API客户端
│   │   ├── __init__.py
│   │   └── benchmark_api_client.py
│   ├── crypto/           # 加密相关代码
│   │   ├── __init__.py
│   │   ├── crypto_utils.py
│   │   ├── data_encryptor.py
│   │   ├── signature_manager.py
│   │   └── timestamp_validator.py
│   ├── data/             # 数据处理代码
│   │   ├── __init__.py
│   │   ├── offline_package.py
│   │   └── result_file.py
│   ├── gui/              # UI相关代码
│   │   ├── __init__.py
│   │   ├── benchmark_tab.py
│   │   ├── benchmark_history_tab.py
│   │   └── widgets/
│   ├── utils/            # 工具函数
│   │   ├── __init__.py
│   │   └── error_handler.py
│   ├── benchmark_manager.py  # 跑分管理器
│   └── plugin.py         # 插件注册
├── engine/               # 核心引擎模块
├── gui/                  # 核心GUI模块
├── utils/                # 核心工具模块
└── main.py               # 主程序入口
```

### 接口设计

#### 1. 插件接口

```python
# src/utils/plugin_interface.py
from abc import ABC, abstractmethod

class PluginInterface(ABC):
    @abstractmethod
    def initialize(self, app_context):
        """初始化插件"""
        pass
        
    @abstractmethod
    def cleanup(self):
        """清理插件资源"""
        pass
        
    @abstractmethod
    def get_name(self):
        """获取插件名称"""
        pass
        
    @abstractmethod
    def get_version(self):
        """获取插件版本"""
        pass
        
    @abstractmethod
    def is_enabled(self):
        """检查插件是否启用"""
        pass
```

#### 2. 跑分插件实现

```python
# src/benchmark/plugin.py
from src.utils.plugin_interface import PluginInterface
from src.benchmark.benchmark_manager import BenchmarkManager

class BenchmarkPlugin(PluginInterface):
    def __init__(self):
        self.benchmark_manager = None
        self.app_context = None
        self.enabled = False
        
    def initialize(self, app_context):
        self.app_context = app_context
        self.enabled = app_context.config.get('benchmark_enabled', False)
        
        if self.enabled:
            self.benchmark_manager = BenchmarkManager(app_context.config)
            # 注册UI组件
            if hasattr(app_context, 'ui_manager'):
                from src.benchmark.gui.benchmark_tab import BenchmarkTab
                from src.benchmark.gui.benchmark_history_tab import BenchmarkHistoryTab
                app_context.ui_manager.register_tab('benchmark', BenchmarkTab())
                app_context.ui_manager.register_tab('benchmark_history', BenchmarkHistoryTab())
        
        return self.enabled
        
    def cleanup(self):
        if self.benchmark_manager:
            self.benchmark_manager.cleanup()
            self.benchmark_manager = None
            
        # 移除UI组件
        if self.enabled and hasattr(self.app_context, 'ui_manager'):
            self.app_context.ui_manager.unregister_tab('benchmark')
            self.app_context.ui_manager.unregister_tab('benchmark_history')
        
    def get_name(self):
        return "benchmark"
        
    def get_version(self):
        return "1.0.0"
        
    def is_enabled(self):
        return self.enabled
```

### 配置管理

#### 1. 配置文件

```json
// config.json
{
  "core": {
    "log_level": "info",
    "language": "zh_CN"
  },
  "plugins": {
    "benchmark": {
      "enabled": true,
      "server_url": "https://benchmark.deepstressmodel.com",
      "api_key": "",
      "auto_upload": false
    }
  }
}
```

#### 2. 配置加载

```python
# src/utils/config.py
import json
import os

class Config:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.config = self._load_config()
        
    def _load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"core": {}, "plugins": {}}
        
    def save_config(self):
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2)
            
    def get(self, key, default=None):
        """获取配置项"""
        parts = key.split('.')
        value = self.config
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value
        
    def set(self, key, value):
        """设置配置项"""
        parts = key.split('.')
        config = self.config
        for i, part in enumerate(parts[:-1]):
            if part not in config:
                config[part] = {}
            config = config[part]
        config[parts[-1]] = value
        self.save_config()
        
    def is_plugin_enabled(self, plugin_name):
        """检查插件是否启用"""
        return self.get(f"plugins.{plugin_name}.enabled", False)
```

### 动态加载机制

#### 1. 插件管理器

```python
# src/utils/plugin_manager.py
import importlib
import os
import logging

logger = logging.getLogger(__name__)

class PluginManager:
    def __init__(self, app_context):
        self.app_context = app_context
        self.plugins = {}
        
    def discover_plugins(self):
        """发现可用插件"""
        plugin_dirs = [
            os.path.join('src', 'benchmark'),
            # 其他插件目录
        ]
        
        for plugin_dir in plugin_dirs:
            if os.path.exists(os.path.join(plugin_dir, 'plugin.py')):
                module_path = plugin_dir.replace(os.path.sep, '.') + '.plugin'
                try:
                    module = importlib.import_module(module_path)
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            attr.__module__ == module.__name__ and 
                            'Plugin' in attr_name):
                            plugin_instance = attr()
                            self.plugins[plugin_instance.get_name()] = plugin_instance
                            logger.info(f"发现插件: {plugin_instance.get_name()} v{plugin_instance.get_version()}")
                except Exception as e:
                    logger.error(f"加载插件模块 {module_path} 失败: {str(e)}")
        
    def initialize_plugins(self):
        """初始化插件"""
        for name, plugin in list(self.plugins.items()):
            try:
                if self.app_context.config.is_plugin_enabled(name):
                    if plugin.initialize(self.app_context):
                        logger.info(f"插件 {name} 初始化成功")
                    else:
                        logger.warning(f"插件 {name} 初始化失败")
                        del self.plugins[name]
                else:
                    logger.info(f"插件 {name} 已禁用")
                    del self.plugins[name]
            except Exception as e:
                logger.error(f"初始化插件 {name} 失败: {str(e)}")
                del self.plugins[name]
        
    def cleanup_plugins(self):
        """清理插件资源"""
        for name, plugin in self.plugins.items():
            try:
                plugin.cleanup()
                logger.info(f"插件 {name} 清理完成")
            except Exception as e:
                logger.error(f"清理插件 {name} 失败: {str(e)}")
        
    def get_plugin(self, name):
        """获取插件实例"""
        return self.plugins.get(name)
        
    def has_plugin(self, name):
        """检查插件是否存在"""
        return name in self.plugins
```

#### 2. 主程序集成

```python
# src/main.py
import logging
from src.utils.config import Config
from src.utils.plugin_manager import PluginManager
from src.gui.main_window import MainWindow

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AppContext:
    def __init__(self):
        self.config = Config()
        self.plugin_manager = PluginManager(self)
        self.ui_manager = None
        
    def initialize(self):
        """初始化应用程序"""
        logger.info("初始化应用程序...")
        
        # 发现并初始化插件
        self.plugin_manager.discover_plugins()
        self.plugin_manager.initialize_plugins()
        
        # 创建主窗口
        self.main_window = MainWindow(self)
        self.ui_manager = self.main_window.ui_manager
        
        logger.info("应用程序初始化完成")
        
    def cleanup(self):
        """清理资源"""
        logger.info("清理应用程序资源...")
        
        # 清理插件资源
        self.plugin_manager.cleanup_plugins()
        
        logger.info("应用程序资源清理完成")
        
    def run(self):
        """运行应用程序"""
        self.initialize()
        self.main_window.show()
        # 进入事件循环
        
    def exit(self):
        """退出应用程序"""
        self.cleanup()
        # 退出事件循环

def main():
    app_context = AppContext()
    app_context.run()

if __name__ == "__main__":
    main()
```

## 迁移计划

从现有代码迁移到解耦架构的计划如下：

### 1. 准备阶段

1. **创建新的目录结构**
   - 创建 `src/benchmark` 目录及子目录
   - 创建插件接口和管理器

2. **实现配置管理**
   - 更新配置文件格式，添加插件配置
   - 实现插件配置加载和保存

### 2. 迁移阶段

1. **迁移跑分管理器**
   - 将 `src/engine/benchmark_manager.py` 迁移到 `src/benchmark/benchmark_manager.py`
   - 调整代码以适应新的接口和依赖注入

2. **迁移UI组件**
   - 将 `src/gui/benchmark_tab.py` 迁移到 `src/benchmark/gui/benchmark_tab.py`
   - 将 `src/gui/benchmark_history_tab.py` 迁移到 `src/benchmark/gui/benchmark_history_tab.py`
   - 调整代码以适应新的接口和动态加载机制

3. **实现新功能**
   - 实现安全通信机制
   - 实现排行榜API客户端
   - 实现离线测试场景

### 3. 集成阶段

1. **实现插件注册**
   - 创建 `src/benchmark/plugin.py`
   - 实现插件接口

2. **更新主程序**
   - 更新 `src/main.py` 以支持插件加载
   - 更新 `src/gui/main_window.py` 以支持动态UI加载

3. **测试和调试**
   - 测试插件加载和卸载
   - 测试功能开关
   - 测试错误隔离

## 测试策略

### 1. 单元测试

- 为插件接口和管理器编写单元测试
- 为跑分模块的核心功能编写单元测试
- 测试插件的加载、初始化和清理

### 2. 集成测试

- 测试跑分模块与核心测试模块的集成
- 测试插件的动态加载和卸载
- 测试配置变更对插件的影响

### 3. 功能测试

- 测试启用和禁用跑分功能
- 测试在线和离线测试场景
- 测试错误处理和恢复机制

### 4. 性能测试

- 测试插件加载对启动时间的影响
- 测试跑分功能对测试性能的影响
- 测试内存使用情况 