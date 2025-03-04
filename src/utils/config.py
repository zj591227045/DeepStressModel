"""
配置管理模块，负责加载和管理应用程序配置
"""
import os
from pathlib import Path
from typing import Dict, Any
import json
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent

# 数据目录
DATA_DIR = ROOT_DIR / "data"
RESOURCES_DIR = ROOT_DIR / "resources"

# 确保必要的目录存在
DATA_DIR.mkdir(exist_ok=True)
RESOURCES_DIR.mkdir(exist_ok=True)

# 数据库配置
DATABASE_URL = f"sqlite:///{DATA_DIR}/deepstress.db"

# 默认配置
DEFAULT_CONFIG = {
    "window": {
        "title": "DeepStressModel",
        "width": 1200,
        "height": 800,
        "language": "zh_CN"
    },
    "openai_api": {
        "stream_mode": True,  # 默认启用流式输出
    },
    "gpu": {
        "poll_interval": 0.5,  # GPU监控轮询间隔，单位秒
    },
    "gpu_monitor": {
        "update_interval": 2.0,  # GPU监控更新间隔（秒）
        "history_size": 60,      # 保存历史数据点数量
        "remote": {
            "enabled": False     # 默认使用本地监控
        }
    },
    "test": {
        "default_concurrency": 1,
        "max_concurrency": 9999,
        "timeout": 60,           # API请求超时时间（秒）
        "retry_count": 1,        # 失败重试次数
    },
    "models": {}  # 移除默认模型配置
}

class Config:
    """配置管理类"""
    
    def __init__(self):
        self._config = DEFAULT_CONFIG.copy()
        self._config_file = DATA_DIR / "config.json"
        self._load_config()
        self.save_config()  # 确保配置文件存在
    
    def _load_config(self):
        """从文件加载配置"""
        try:
            if self._config_file.exists():
                with open(self._config_file, "r", encoding="utf-8") as f:
                    loaded_config = json.load(f)
                    # 递归更新配置
                    self._update_dict(self._config, loaded_config)
                    print(f"配置加载成功: {self._config}")
            else:
                print("配置文件不存在，将使用默认配置")
        except Exception as e:
            print(f"加载配置文件失败: {e}")
    
    def _update_dict(self, d: dict, u: dict) -> dict:
        """递归更新字典"""
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                self._update_dict(d[k], v)
            else:
                d[k] = v
        return d
    
    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
            print("配置保存成功")
        except Exception as e:
            print(f"保存配置文件失败: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        keys = key.split(".")
        value = self._config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any):
        """设置配置项"""
        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self.save_config()

# 全局配置实例
config = Config()
