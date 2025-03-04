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
import time

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
        self._init_version_table()
        self._check_and_migrate()
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
            
    def _init_version_table(self):
        """初始化版本表"""
        try:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS db_version (
                    version INTEGER PRIMARY KEY,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 检查是否已有版本记录
            self.cursor.execute("SELECT version FROM db_version ORDER BY version DESC LIMIT 1")
            row = self.cursor.fetchone()
            if not row:
                # 插入初始版本
                self.cursor.execute("INSERT INTO db_version (version) VALUES (1)")
                self.conn.commit()
                logger.info("数据库版本初始化为 1")
        except Exception as e:
            logger.error(f"初始化版本表失败: {e}", exc_info=True)
            raise
    
    def _check_and_migrate(self):
        """检查并执行数据库迁移"""
        try:
            self.cursor.execute("SELECT version FROM db_version ORDER BY version DESC LIMIT 1")
            row = self.cursor.fetchone()
            current_version = row[0] if row else 0
            
            if current_version < 1:
                logger.info("执行数据库迁移: 版本 0 -> 1")
                # 删除旧的测试记录表
                self.cursor.execute("DROP TABLE IF EXISTS test_records")
                self.conn.commit()
                logger.info("已删除旧的测试记录表")
            
            if current_version < 2:
                logger.info("执行数据库迁移: 版本 1 -> 2")
                # 删除旧的测试记录表并创建新表
                self.cursor.execute("DROP TABLE IF EXISTS test_records")
                self.cursor.execute('''
                    CREATE TABLE test_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_name TEXT NOT NULL,
                        test_task_id TEXT NOT NULL UNIQUE,
                        model_name TEXT NOT NULL,
                        concurrency INTEGER NOT NULL,
                        total_tasks INTEGER NOT NULL,
                        successful_tasks INTEGER NOT NULL,
                        failed_tasks INTEGER NOT NULL,
                        avg_response_time REAL NOT NULL,
                        avg_generation_speed REAL NOT NULL,
                        total_chars INTEGER NOT NULL,
                        total_tokens INTEGER NOT NULL,
                        avg_tps REAL NOT NULL,
                        total_time REAL NOT NULL,
                        current_speed REAL NOT NULL,
                        test_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        log_file TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                self.conn.commit()
                logger.info("已更新测试记录表结构")
            
            # 更新数据库版本到 2
            if current_version != 2:
                self.cursor.execute("INSERT INTO db_version (version) VALUES (2)")
                self.conn.commit()
                logger.info("数据库版本已更新到 2")
                
        except Exception as e:
            logger.error(f"数据库迁移失败: {e}", exc_info=True)
            raise

    def _init_tables(self):
        """初始化数据库表"""
        try:
            logger.info("开始初始化数据库表")
            # 创建模型配置表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS model_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    api_url TEXT NOT NULL,
                    api_key TEXT NOT NULL,
                    model TEXT NOT NULL,
                    max_tokens INTEGER,
                    temperature REAL,
                    top_p REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建通用配置表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS configs (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建数据集表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS datasets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    prompts TEXT NOT NULL,
                    is_builtin BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建GPU服务器表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS gpu_servers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    host TEXT NOT NULL,
                    username TEXT NOT NULL,
                    password TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建测试记录表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS test_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_name TEXT NOT NULL,
                    test_task_id TEXT NOT NULL UNIQUE,
                    model_name TEXT NOT NULL,
                    concurrency INTEGER NOT NULL,
                    total_tasks INTEGER NOT NULL,
                    successful_tasks INTEGER NOT NULL,
                    failed_tasks INTEGER NOT NULL,
                    avg_response_time REAL NOT NULL,
                    avg_generation_speed REAL NOT NULL,
                    total_chars INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    avg_tps REAL NOT NULL,
                    total_time REAL NOT NULL,
                    current_speed REAL NOT NULL,
                    test_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    log_file TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            self.conn.commit()
            logger.info("数据库表初始化完成")
        except Exception as e:
            logger.error(f"初始化数据库表失败: {e}", exc_info=True)
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
            # 检查是否已存在同名配置
            self.cursor.execute("SELECT name FROM model_configs WHERE name = ?", (config_data["name"],))
            if self.cursor.fetchone():
                logger.error(f"模型配置已存在: {config_data['name']}")
                return False
                
            self.cursor.execute('''
                INSERT INTO model_configs 
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

    def update_model_config(self, config_data: Dict) -> bool:
        """更新模型配置"""
        try:
            self.cursor.execute('''
                UPDATE model_configs 
                SET api_url = ?, api_key = ?, model = ?, max_tokens = ?, temperature = ?, top_p = ?
                WHERE name = ?
            ''', (
                config_data["api_url"],
                config_data.get("api_key"),
                config_data["model"],
                config_data.get("max_tokens", 2000),
                config_data.get("temperature", 0.7),
                config_data.get("top_p", 0.9),
                config_data["name"]
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"更新模型配置失败: {e}")
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
                (name, prompts, is_builtin)
                VALUES (?, ?, ?)
            ''', (
                dataset_data["name"],
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
                (name, host, username, password, is_active)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                server_data["name"],
                server_data["host"],
                server_data["username"],
                server_data.get("password"),
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

    def get_test_records(self) -> List[Dict]:
        """获取所有测试记录
        
        Returns:
            List[Dict]: 测试记录列表
        """
        try:
            logger.info("开始获取测试记录")
            self.cursor.execute('''
                SELECT 
                    test_task_id, session_name, model_name, concurrency,
                    total_tasks, successful_tasks, failed_tasks,
                    avg_response_time, avg_generation_speed, total_chars,
                    total_tokens, avg_tps, total_time, current_speed,
                    test_time, log_file, created_at
                FROM test_records 
                ORDER BY created_at DESC
            ''')
            
            records = []
            for row in self.cursor.fetchall():
                record = dict(row)
                # 确保数值类型正确
                record["concurrency"] = int(record["concurrency"])
                record["total_tasks"] = int(record["total_tasks"])
                record["successful_tasks"] = int(record["successful_tasks"])
                record["failed_tasks"] = int(record["failed_tasks"])
                record["total_chars"] = int(record["total_chars"])
                record["total_tokens"] = int(record["total_tokens"])
                record["avg_response_time"] = float(record["avg_response_time"])
                record["avg_generation_speed"] = float(record["avg_generation_speed"])
                record["current_speed"] = float(record["current_speed"])
                record["avg_tps"] = float(record["avg_tps"])
                record["total_time"] = float(record["total_time"])
                records.append(record)
            
            logger.info(f"成功获取 {len(records)} 条测试记录")
            return records
            
        except Exception as e:
            logger.error(f"获取测试记录失败: {e}", exc_info=True)
            return []

    def clear_test_logs(self) -> bool:
        """清除测试日志文件"""
        try:
            records = self.get_test_records()
            for record in records:
                if record["log_file"] and os.path.exists(record["log_file"]):
                    os.remove(record["log_file"])
            return True
        except Exception as e:
            logger.error(f"清除测试日志失败: {e}")
            return False

    def save_test_record(self, record: Dict) -> bool:
        """保存测试记录
        
        Args:
            record: 测试记录数据
            
        Returns:
            bool: 是否保存成功
        """
        try:
            logger.info(f"开始保存测试记录: {record.get('test_task_id', 'unknown')}")
            logger.debug(f"原始记录数据: {record}")
            
            # 验证必要字段
            required_fields = [
                "test_task_id", "session_name", "model_name", "concurrency",
                "total_tasks", "successful_tasks", "failed_tasks",
                "avg_response_time", "avg_generation_speed", "total_chars",
                "total_tokens", "avg_tps", "total_time", "current_speed"
            ]
            
            for field in required_fields:
                if field not in record or record[field] is None:
                    logger.error(f"缺少必要字段: {field}")
                    return False
            
            # 数据类型转换和验证
            try:
                record["concurrency"] = int(record["concurrency"])
                record["total_tasks"] = int(record["total_tasks"])
                record["successful_tasks"] = int(record["successful_tasks"])
                record["failed_tasks"] = int(record["failed_tasks"])
                record["total_chars"] = int(record["total_chars"])
                record["total_tokens"] = int(record["total_tokens"])
                record["avg_response_time"] = float(record["avg_response_time"])
                record["avg_generation_speed"] = float(record["avg_generation_speed"])
                record["current_speed"] = float(record["current_speed"])
                record["avg_tps"] = float(record["avg_tps"])
                record["total_time"] = float(record["total_time"])
            except (ValueError, TypeError) as e:
                logger.error(f"数据类型转换失败: {e}")
                return False
            
            # 数据有效性验证
            if record["concurrency"] <= 0:
                logger.error("并发数必须大于0")
                return False
            
            if record["total_tasks"] <= 0:
                logger.error("总任务数必须大于0")
                return False
            
            if record["successful_tasks"] + record["failed_tasks"] != record["total_tasks"]:
                logger.error("成功任务数和失败任务数之和必须等于总任务数")
                return False
            
            # 使用REPLACE INTO替代INSERT INTO
            self.cursor.execute('''
                REPLACE INTO test_records (
                    test_task_id, session_name, model_name, concurrency,
                    total_tasks, successful_tasks, failed_tasks,
                    avg_response_time, avg_generation_speed, total_chars,
                    total_tokens, avg_tps, total_time, current_speed,
                    test_time, log_file
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                record["test_task_id"],
                record["session_name"],
                record["model_name"],
                record["concurrency"],
                record["total_tasks"],
                record["successful_tasks"],
                record["failed_tasks"],
                record["avg_response_time"],
                record["avg_generation_speed"],
                record["total_chars"],
                record["total_tokens"],
                record["avg_tps"],
                record["total_time"],
                record["current_speed"],
                record.get("test_time", time.strftime('%Y-%m-%d %H:%M:%S')),
                record.get("log_file")
            ))
            
            self.conn.commit()
            logger.info(f"测试记录保存成功: {record['test_task_id']}")
            return True
            
        except Exception as e:
            logger.error(f"保存测试记录失败: {e}", exc_info=True)
            return False

    def delete_test_record(self, session_name: str) -> bool:
        """删除测试记录
        
        Args:
            session_name: 会话名称
            
        Returns:
            bool: 是否删除成功
        """
        try:
            logger.debug(f"开始删除测试记录，会话名称: {session_name}")
            
            # 获取日志文件路径
            self.cursor.execute(
                "SELECT log_file FROM test_records WHERE session_name = ?",
                (session_name,)  # 只根据会话名称匹配
            )
            result = self.cursor.fetchone()
            
            if result is None:
                logger.warning(f"未找到会话记录: {session_name}")
                return False
                
            logger.debug(f"查询到的记录: {dict(result) if result else None}")
            
            if result and result["log_file"]:
                # 删除日志文件
                log_file = result["log_file"]
                logger.debug(f"尝试删除日志文件: {log_file}")
                
                if os.path.exists(log_file):
                    try:
                        os.remove(log_file)
                        logger.info(f"成功删除日志文件: {log_file}")
                    except Exception as e:
                        logger.warning(f"删除日志文件失败: {e}", exc_info=True)
                else:
                    logger.warning(f"日志文件不存在: {log_file}")
            
            # 删除数据库记录
            logger.debug(f"开始删除数据库记录: {session_name}")
            self.cursor.execute(
                "DELETE FROM test_records WHERE session_name = ?",
                (session_name,)  # 只根据会话名称匹配
            )
            
            if self.cursor.rowcount == 0:
                logger.warning(f"没有记录被删除，会话名称: {session_name}")
                return False
                
            self.conn.commit()
            logger.info(f"成功删除测试记录，会话名称: {session_name}")
            return True
            
        except Exception as e:
            logger.error(f"删除测试记录失败: {e}", exc_info=True)
            return False

    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        try:
            self.cursor.execute("SELECT value FROM configs WHERE key = ?", (key,))
            row = self.cursor.fetchone()
            if row:
                try:
                    return json.loads(row[0])
                except json.JSONDecodeError:
                    return row[0]
            return default
        except Exception as e:
            logger.error(f"获取配置失败: {e}")
            return default

    def set_config(self, key: str, value: Any) -> bool:
        """设置配置值
        
        Args:
            key: 配置键
            value: 配置值
            
        Returns:
            是否成功
        """
        try:
            # 将值转换为JSON字符串
            if not isinstance(value, str):
                value = json.dumps(value)
            
            self.cursor.execute('''
                INSERT OR REPLACE INTO configs (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (key, value))
            self.conn.commit()
            logger.info(f"保存配置成功: {key}={value}")
            return True
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False

    def add_gpu_stats(self, host, gpu_util, gpu_memory_util, temperature, power_usage, 
                     cpu_util=0, memory_util=0, disk_util=0, disk_io_latency=0,
                     network_recv=0, network_send=0, timestamp=None):
        """添加GPU监控数据到数据库
        
        Args:
            host: 服务器主机名
            gpu_util: GPU利用率
            gpu_memory_util: GPU内存利用率
            temperature: 温度
            power_usage: 功率使用
            cpu_util: CPU利用率
            memory_util: 内存利用率
            disk_util: 磁盘利用率
            disk_io_latency: 磁盘IO延迟
            network_recv: 网络接收速度
            network_send: 网络发送速度
            timestamp: 时间戳
            
        Returns:
            是否成功
        """
        try:
            if timestamp is None:
                timestamp = time.time()
                
            # 检查gpu_stats表是否存在，如果不存在则创建
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS gpu_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    host TEXT NOT NULL,
                    gpu_util REAL,
                    gpu_memory_util REAL,
                    temperature REAL,
                    power_usage REAL,
                    cpu_util REAL,
                    memory_util REAL,
                    disk_util REAL,
                    disk_io_latency REAL,
                    network_recv REAL,
                    network_send REAL,
                    timestamp REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            self.cursor.execute('''
                INSERT INTO gpu_stats (
                    host, gpu_util, gpu_memory_util, temperature, power_usage,
                    cpu_util, memory_util, disk_util, disk_io_latency,
                    network_recv, network_send, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                host, gpu_util, gpu_memory_util, temperature, power_usage,
                cpu_util, memory_util, disk_util, disk_io_latency,
                network_recv, network_send, timestamp
            ))
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"保存GPU统计数据失败: {e}")
            return False

# 创建全局数据库管理器实例
db_manager = DatabaseManager()
