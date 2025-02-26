"""
数据库管理器模块，负责所有数据库操作
"""
import os
import sqlite3
import logging
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from src.utils.config import config
from src.data.test_datasets import DATASETS  # 导入默认数据集

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = "data/deepstress.db"):
        """初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._ensure_db_directory()
        self.conn = None
        self.cursor = None
        self._connect()
        self._init_tables()
        self._init_default_data()
        
    def _ensure_db_directory(self):
        """确保数据库目录存在"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
    def _connect(self):
        """连接到数据库"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # 设置行工厂以支持列名访问
            self.cursor = self.conn.cursor()
            logger.info(f"成功连接到数据库: {self.db_path}")
        except Exception as e:
            logger.error(f"连接数据库失败: {str(e)}")
            raise
            
    def _init_tables(self):
        """初始化数据库表"""
        try:
            # 模型配置表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS model_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    api_url TEXT NOT NULL,
                    api_key TEXT,
                    model TEXT NOT NULL,
                    max_tokens INTEGER DEFAULT 2000,
                    temperature REAL DEFAULT 0.7,
                    top_p REAL DEFAULT 0.9,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 数据集表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS datasets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    category TEXT,
                    prompts TEXT NOT NULL,  -- JSON格式存储的提示列表
                    is_builtin BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # GPU服务器配置表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS gpu_servers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    host TEXT NOT NULL,
                    port INTEGER DEFAULT 22,
                    username TEXT NOT NULL,
                    password TEXT,
                    ssh_key TEXT,
                    is_active BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            self.conn.commit()
            logger.info("数据库表初始化完成")
        except Exception as e:
            logger.error(f"初始化数据库表失败: {str(e)}")
            raise

    def _init_default_data(self):
        """初始化默认数据"""
        try:
            # 导入默认数据集
            for name, prompts in DATASETS.items():
                # 检查数据集是否已存在
                self.cursor.execute("SELECT name FROM datasets WHERE name = ?", (name,))
                if not self.cursor.fetchone():
                    dataset_data = {
                        "name": name,
                        "prompts": json.dumps(prompts, ensure_ascii=False),
                        "is_builtin": True
                    }
                    self.cursor.execute(
                        "INSERT INTO datasets (name, prompts, is_builtin) VALUES (?, ?, ?)",
                        (dataset_data["name"], dataset_data["prompts"], dataset_data["is_builtin"])
                    )
            
            self.conn.commit()
            logger.info("默认数据初始化完成")
        except Exception as e:
            logger.error(f"初始化默认数据失败: {e}")

    def get_model_configs(self) -> List[Dict]:
        """获取所有模型配置"""
        try:
            self.cursor.execute("SELECT * FROM model_configs ORDER BY created_at DESC")
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取模型配置失败: {e}")
            return []

    def add_model_config(self, config_data: Dict) -> bool:
        """添加模型配置"""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO model_configs 
                (name, api_url, api_key, model, max_tokens, temperature, top_p)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                config_data["name"],
                config_data["api_url"],
                config_data.get("api_key"),
                config_data["model"],
                config_data.get("max_tokens", 2000),
                config_data.get("temperature", 0.7),
                config_data.get("top_p", 0.9)
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"添加模型配置失败: {e}")
            return False

    def delete_model_config(self, name: str) -> bool:
        """删除模型配置"""
        try:
            self.cursor.execute("DELETE FROM model_configs WHERE name = ?", (name,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"删除模型配置失败: {e}")
            return False

    def get_datasets(self) -> List[Dict]:
        """获取所有数据集"""
        try:
            self.cursor.execute("SELECT * FROM datasets ORDER BY created_at DESC")
            datasets = []
            for row in self.cursor.fetchall():
                dataset = dict(row)
                # 解析JSON格式的prompts
                if isinstance(dataset["prompts"], str):
                    try:
                        dataset["prompts"] = json.loads(dataset["prompts"])
                    except json.JSONDecodeError as e:
                        logger.error(f"解析数据集 {dataset['name']} 的提示时出错: {e}")
                        # 如果JSON解析失败，尝试将字符串按行分割
                        dataset["prompts"] = dataset["prompts"].split("\n")
                datasets.append(dataset)
            return datasets
        except Exception as e:
            logger.error(f"获取数据集失败: {e}")
            return []

    def add_dataset(self, dataset_data: Dict) -> bool:
        """添加数据集"""
        try:
            # 确保 prompts 是列表
            prompts = dataset_data.get("prompts", [])
            if not isinstance(prompts, list):
                if isinstance(prompts, str):
                    # 如果是字符串，尝试解析JSON
                    try:
                        prompts = json.loads(prompts)
                    except json.JSONDecodeError:
                        # 如果JSON解析失败，按行分割
                        prompts = prompts.split("\n")
                else:
                    prompts = []
            
            # 转换为JSON字符串
            prompts_json = json.dumps(prompts, ensure_ascii=False)
            
            self.cursor.execute('''
                INSERT OR REPLACE INTO datasets 
                (name, description, category, prompts, is_builtin)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                dataset_data["name"],
                dataset_data.get("description"),
                dataset_data.get("category"),
                prompts_json,
                dataset_data.get("is_builtin", False)
            ))
            self.conn.commit()
            logger.info(f"成功添加数据集: {dataset_data['name']}")
            return True
        except Exception as e:
            logger.error(f"添加数据集失败: {e}")
            return False

    def delete_dataset(self, name: str) -> bool:
        """删除数据集"""
        try:
            self.cursor.execute("DELETE FROM datasets WHERE name = ? AND NOT is_builtin", (name,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"删除数据集失败: {e}")
            return False

    def get_gpu_servers(self) -> List[Dict]:
        """获取所有GPU服务器配置"""
        try:
            self.cursor.execute("SELECT * FROM gpu_servers ORDER BY created_at DESC")
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取GPU服务器配置失败: {e}")
            return []

    def add_gpu_server(self, server_data: Dict) -> bool:
        """添加GPU服务器配置"""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO gpu_servers 
                (name, host, port, username, password, ssh_key, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                server_data["name"],
                server_data["host"],
                server_data.get("port", 22),
                server_data["username"],
                server_data.get("password"),
                server_data.get("ssh_key"),
                server_data.get("is_active", False)
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"添加GPU服务器配置失败: {e}")
            return False

    def delete_gpu_server(self, name: str) -> bool:
        """删除GPU服务器配置"""
        try:
            self.cursor.execute("DELETE FROM gpu_servers WHERE name = ?", (name,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"删除GPU服务器配置失败: {e}")
            return False

    def get_active_gpu_server(self) -> Optional[Dict]:
        """获取当前激活的GPU服务器配置"""
        try:
            self.cursor.execute("SELECT * FROM gpu_servers WHERE is_active = 1 LIMIT 1")
            row = self.cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"获取激活的GPU服务器配置失败: {e}")
            return None

    def set_gpu_server_active(self, name: str) -> bool:
        """设置GPU服务器为激活状态"""
        try:
            self.cursor.execute("UPDATE gpu_servers SET is_active = 0")  # 先取消所有服务器的激活状态
            self.cursor.execute("UPDATE gpu_servers SET is_active = 1 WHERE name = ?", (name,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"设置GPU服务器激活状态失败: {e}")
            return False
            
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.info("数据库连接已关闭")
            
    def __del__(self):
        """析构函数，确保关闭数据库连接"""
        self.close()

# 创建全局数据库管理器实例
db_manager = DatabaseManager()
