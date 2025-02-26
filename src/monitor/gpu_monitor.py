"""
GPU监控模块，提供远程GPU监控功能
"""
import time
from typing import Dict, Optional
import paramiko
from src.utils.logger import setup_logger
from src.utils.config import config
from src.data.db_manager import db_manager

logger = setup_logger("gpu_monitor")

class GPUStats:
    """GPU统计数据类"""
    def __init__(
        self,
        memory_used: float,
        memory_total: float,
        gpu_util: float,
        temperature: float,
        power_usage: float = 0.0,  # 功率使用（瓦特）
        power_limit: float = 0.0,  # 功率限制（瓦特）
        cpu_util: float = 0.0,    # CPU使用率
        memory_util: float = 0.0,  # 系统内存使用率
        disk_util: float = 0.0,    # 磁盘使用率
        network_io: Dict[str, float] = None,  # 网络IO统计
        timestamp: float = None,
        cpu_info: str = "",       # CPU型号信息
        gpu_info: str = "",       # GPU型号信息
        gpu_count: int = 1,       # GPU数量
        total_memory: int = 0     # 系统总内存(GB)
    ):
        self.memory_used = memory_used      # MB
        self.memory_total = memory_total    # MB
        self.gpu_util = gpu_util            # %
        self.temperature = temperature      # °C
        self.power_usage = power_usage     # W
        self.power_limit = power_limit     # W
        self.cpu_util = cpu_util 
        self._memory_util = memory_util     # %
        self.disk_util = disk_util         # %
        self.network_io = network_io or {}  # 包含上传下载速度
        self.timestamp = timestamp or time.time()
        self.cpu_info = cpu_info           # CPU型号
        self.gpu_info = gpu_info           # GPU型号
        self.gpu_count = gpu_count         # GPU数量
        self.total_memory = total_memory   # 系统总内存
    
    @property
    def gpu_memory_util(self) -> float:
        """GPU内存使用率"""
        return (self.memory_used / self.memory_total) * 100 if self.memory_total > 0 else 0
    
    @property
    def memory_util(self) -> float:
        """系统内存使用率"""
        return self._memory_util
    
    @memory_util.setter
    def memory_util(self, value: float):
        """设置系统内存使用率"""
        self._memory_util = value

class GPUMonitor:
    """远程GPU监控类"""
    def __init__(self, host: str, username: str, password: str):
        self.host = host
        self.username = username
        self.password = password
        self.client = None
        self.max_retries = 3  # 最大重试次数
        self.retry_interval = 2  # 重试间隔（秒）
        self._connect()
    
    def _connect(self) -> bool:
        """连接到远程服务器"""
        for attempt in range(self.max_retries):
            try:
                if self.client:
                    try:
                        self.client.close()
                    except:
                        pass
                
                self.client = paramiko.SSHClient()
                self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self.client.connect(
                    self.host,
                    username=self.username,
                    password=self.password,
                    timeout=5
                )
                logger.info(f"成功连接到远程服务器: {self.host}")
                return True
            except Exception as e:
                logger.error(f"连接远程服务器失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_interval)
                    continue
                return False
        return False

    def _execute_command(self, command: str) -> Optional[str]:
        """执行远程命令"""
        for attempt in range(self.max_retries):
            try:
                if not self.client:
                    if not self._connect():
                        return None
                
                stdin, stdout, stderr = self.client.exec_command(command, timeout=5)
                return stdout.read().decode().strip()
            except Exception as e:
                logger.error(f"执行远程命令失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    # 重置连接
                    try:
                        self.client.close()
                    except:
                        pass
                    self.client = None
                    time.sleep(self.retry_interval)
                    continue
                return None
        return None

    def get_stats(self) -> Optional[GPUStats]:
        """获取GPU统计信息"""
        for attempt in range(self.max_retries):
            try:
                # 获取GPU信息
                nvidia_smi = self._execute_command("nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,power.limit,name --format=csv,noheader,nounits")
                if not nvidia_smi:
                    raise Exception("无法获取GPU信息")
                
                gpu_data = nvidia_smi.split(',')
                if len(gpu_data) < 7:
                    raise Exception("GPU数据格式错误")
                
                gpu_util = float(gpu_data[0])
                memory_used = float(gpu_data[1])
                memory_total = float(gpu_data[2])
                temperature = float(gpu_data[3])
                power_usage = float(gpu_data[4]) if gpu_data[4].strip() != 'N/A' else 0.0
                power_limit = float(gpu_data[5]) if gpu_data[5].strip() != 'N/A' else 0.0
                gpu_info = gpu_data[6].strip()
                
                # 获取CPU使用率
                cpu_command = "top -bn1 | grep 'Cpu(s)' | awk '{print $2}'"
                cpu_output = self._execute_command(cpu_command)
                if not cpu_output:
                    raise Exception("无法获取CPU信息")
                cpu_util = float(cpu_output)
                
                # 获取内存使用率
                memory_command = "free | grep Mem | awk '{print $3/$2 * 100.0}'"
                memory_output = self._execute_command(memory_command)
                if not memory_output:
                    raise Exception("无法获取内存信息")
                memory_util = float(memory_output)
                
                # 获取磁盘使用率
                disk_command = "df / | tail -1 | awk '{print $5}' | sed 's/%//'"
                disk_output = self._execute_command(disk_command)
                if not disk_output:
                    raise Exception("无法获取磁盘信息")
                disk_util = float(disk_output)
                
                # 获取网络IO
                net_command = "cat /proc/net/dev | grep -E 'eth0|ens|enp' | head -n1 | awk '{print $2,$10}'"
                net_output = self._execute_command(net_command)
                if not net_output:
                    raise Exception("无法获取网络信息")
                net_recv, net_send = map(float, net_output.split())
                
                # 获取CPU信息
                cpu_info_command = "cat /proc/cpuinfo | grep 'model name' | head -n1 | cut -d':' -f2"
                cpu_info = self._execute_command(cpu_info_command)
                if not cpu_info:
                    cpu_info = "未知CPU"
                
                # 获取系统总内存
                total_memory_command = "free -g | grep Mem | awk '{print $2}'"
                total_memory_output = self._execute_command(total_memory_command)
                if not total_memory_output:
                    raise Exception("无法获取系统总内存信息")
                total_memory = int(total_memory_output)
                
                # 获取GPU数量
                gpu_count_command = "nvidia-smi --query-gpu=gpu_name --format=csv,noheader | wc -l"
                gpu_count_output = self._execute_command(gpu_count_command)
                if not gpu_count_output:
                    raise Exception("无法获取GPU数量信息")
                gpu_count = int(gpu_count_output)
                
                return GPUStats(
                    memory_used=memory_used,
                    memory_total=memory_total,
                    gpu_util=gpu_util,
                    temperature=temperature,
                    power_usage=power_usage,
                    power_limit=power_limit,
                    cpu_util=cpu_util,
                    memory_util=memory_util,
                    disk_util=disk_util,
                    network_io={'receive': net_recv, 'transmit': net_send},
                    cpu_info=cpu_info.strip(),
                    gpu_info=gpu_info,
                    gpu_count=gpu_count,
                    total_memory=total_memory
                )
            except Exception as e:
                logger.error(f"获取GPU统计信息失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    # 重置连接
                    try:
                        self.client.close()
                    except:
                        pass
                    self.client = None
                    time.sleep(self.retry_interval)
                    continue
                return None
        return None
    
    def __del__(self):
        """析构函数，关闭SSH连接"""
        if self.client:
            try:
                self.client.close()
            except:
                pass

class GPUMonitorManager:
    """GPU监控管理器"""
    def __init__(self):
        self.monitor = None
        self.active_server = None
    
    def init_monitor(self):
        """初始化监控器"""
        try:
            # 获取活动的GPU服务器配置
            self.active_server = db_manager.get_active_gpu_server()
            
            if self.active_server:
                # 初始化远程监控
                logger.info(f"尝试初始化远程GPU监控: {self.active_server['host']}")
                self.setup_monitor(
                    self.active_server["host"],
                    self.active_server["username"],
                    self.active_server["password"]
                )
            else:
                logger.warning("未找到活动的GPU服务器配置")
                self.monitor = None
                
        except Exception as e:
            logger.error(f"初始化GPU监控失败: {e}")
            self.monitor = None
    
    def setup_monitor(self, host: str, username: str, password: str):
        """设置远程监控"""
        try:
            monitor = GPUMonitor(host, username, password)
            
            # 测试连接和数据获取
            stats = monitor.get_stats()
            if stats:
                self.monitor = monitor
                logger.info(f"已设置远程GPU监控: {host}")
            else:
                logger.error(f"无法从远程服务器获取GPU统计数据: {host}")
                self.monitor = None
                
        except Exception as e:
            logger.error(f"设置远程GPU监控失败: {e}")
            self.monitor = None
    
    def get_stats(self) -> Optional[GPUStats]:
        """获取GPU统计数据"""
        try:
            if not self.monitor:
                return None
            return self.monitor.get_stats()
        except Exception as e:
            logger.error(f"获取GPU统计数据失败: {e}")
            return None

# 创建全局GPU监控管理器实例，但不自动初始化
gpu_monitor = GPUMonitorManager()
