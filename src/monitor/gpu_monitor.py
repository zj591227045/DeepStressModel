"""
GPU监控模块，提供本地和远程GPU监控功能
"""
import time
from typing import Dict, Optional, List
import paramiko
from py3nvml import py3nvml
from src.utils.logger import setup_logger
from src.utils.config import config

logger = setup_logger("gpu_monitor")

class GPUStats:
    """GPU统计数据类"""
    def __init__(
        self,
        memory_used: float,
        memory_total: float,
        gpu_util: float,
        temperature: float,
        fan_speed: float = 0.0,  # 风扇转速百分比
        power_usage: float = 0.0,  # 功率使用（瓦特）
        power_limit: float = 0.0,  # 功率限制（瓦特）
        cpu_util: float = 0.0,    # CPU使用率
        memory_util: float = 0.0,  # 系统内存使用率
        disk_util: float = 0.0,    # 磁盘使用率
        disk_io: Dict[str, float] = None,  # 磁盘IO统计
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
        self.fan_speed = fan_speed         # %
        self.power_usage = power_usage     # W
        self.power_limit = power_limit     # W
        self.cpu_util = cpu_util 
        self._memory_util = memory_util     # %
        self.disk_util = disk_util         # %
        self.disk_io = disk_io or {}       # 包含读写速度和延迟
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

class BaseGPUMonitor:
    """GPU监控基类"""
    def get_stats(self) -> Optional[GPUStats]:
        """获取GPU统计数据"""
        raise NotImplementedError

class LocalGPUMonitor(BaseGPUMonitor):
    """本地GPU监控"""
    def __init__(self):
        self._initialized = False
        try:
            py3nvml.nvmlInit()
            self.handle = py3nvml.nvmlDeviceGetHandleByIndex(0)
            self._initialized = True
            logger.info("本地GPU监控初始化成功")
        except Exception as e:
            logger.error(f"初始化本地GPU监控失败: {e}")
    
    def get_stats(self) -> Optional[GPUStats]:
        """获取GPU统计数据"""
        if not self._initialized:
            return None
        
        try:
            memory = py3nvml.nvmlDeviceGetMemoryInfo(self.handle)
            utilization = py3nvml.nvmlDeviceGetUtilizationRates(self.handle)
            temperature = py3nvml.nvmlDeviceGetTemperature(
                self.handle, py3nvml.NVML_TEMPERATURE_GPU
            )
            
            return GPUStats(
                memory_used=memory.used / 1024**2,    # 转换为MB
                memory_total=memory.total / 1024**2,   # 转换为MB
                gpu_util=utilization.gpu,
                temperature=temperature
            )
        except Exception as e:
            logger.error(f"获取GPU统计数据失败: {e}")
            return None
    
    def __del__(self):
        """清理资源"""
        if self._initialized:
            try:
                py3nvml.nvmlShutdown()
            except:
                pass

class RemoteGPUMonitor(BaseGPUMonitor):
    """远程GPU监控"""
    def __init__(self, host: str, username: str, password: str):
        self._initialized = False
        self.host = host
        self.username = username
        self.password = password
        self._client = None
        self._connect()
    
    def _connect(self):
        """建立SSH连接"""
        try:
            self._client = paramiko.SSHClient()
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._client.connect(
                self.host,
                username=self.username,
                password=self.password
            )
            self._initialized = True
            logger.info(f"远程GPU监控连接成功: {self.host}")
        except Exception as e:
            logger.error(f"远程GPU监控连接失败: {e}")
            self._client = None
    
    def _get_gpu_stats(self) -> Dict:
        """获取GPU统计数据"""
        cmd = (
            'nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu,'
            'temperature.gpu,fan.speed,power.draw,power.limit '
            '--format=csv,noheader,nounits'
        )
        stdin, stdout, stderr = self._client.exec_command(cmd)
        output = stdout.read().decode().strip()
        
        if not output:
            logger.error("远程GPU数据为空")
            return None
        
        memory_used, memory_total, gpu_util, temp, fan, power, power_limit = map(float, output.split(','))
        return {
            "memory_used": memory_used,
            "memory_total": memory_total,
            "gpu_util": gpu_util,
            "temperature": temp,
            "fan_speed": fan,
            "power_usage": power,
            "power_limit": power_limit
        }
    
    def _get_system_stats(self) -> Dict:
        """获取系统统计信息"""
        try:
            # 使用更可靠的命令获取系统信息
            command = (
                "echo -n 'CPU:' && top -bn1 | grep 'Cpu(s)' | awk '{print $2}' && "
                "echo -n 'MEM:' && free -m | grep 'Mem:' | awk '{print $3,$2}' && "
                "echo -n 'IO:' && iostat -d | grep '^nvme\|^sda' | head -n1 | awk '{print $3,$4}' && "
                "echo -n 'NET:' && cat /proc/net/dev | grep eth0 | awk '{print $2,$10}'"
            )
            
            stdin, stdout, stderr = self._client.exec_command(command)
            output = stdout.read().decode().strip()
            
            # 解析输出
            stats = {}
            parts = output.split('IO:')
            
            if len(parts) >= 2:
                # 解析CPU和内存使用率
                cpu_mem = parts[0].split('MEM:')
                if len(cpu_mem) >= 2:
                    try:
                        stats['cpu_util'] = float(cpu_mem[0].replace('CPU:', '').strip())
                        mem_parts = cpu_mem[1].strip().split()
                        if len(mem_parts) >= 2:
                            used_mem = float(mem_parts[0])
                            total_mem = float(mem_parts[1])
                            stats['memory_util'] = (used_mem / total_mem) * 100 if total_mem > 0 else 0
                    except (ValueError, IndexError):
                        stats['cpu_util'] = 0.0
                        stats['memory_util'] = 0.0
                
                # 解析磁盘IO
                io_net = parts[1].split('NET:')
                if len(io_net) >= 2:
                    try:
                        io_parts = io_net[0].strip().split()
                        stats['disk_io'] = {
                            'read': float(io_parts[0]) if io_parts else 0.0,
                            'write': float(io_parts[1]) if len(io_parts) > 1 else 0.0
                        }
                    except (ValueError, IndexError):
                        stats['disk_io'] = {'read': 0.0, 'write': 0.0}
                    
                    try:
                        net_parts = io_net[1].strip().split()
                        stats['network_io'] = {
                            'receive': float(net_parts[0]) / 1024 if net_parts else 0.0,  # 转换为KB/s
                            'transmit': float(net_parts[1]) / 1024 if len(net_parts) > 1 else 0.0
                        }
                    except (ValueError, IndexError):
                        stats['network_io'] = {'receive': 0.0, 'transmit': 0.0}
            
            return stats
        except Exception as e:
            logger.error(f"获取系统统计信息失败: {e}")
            return self._get_default_stats()
    
    def _get_hardware_info(self) -> Dict:
        """获取硬件信息"""
        try:
            # 获取CPU信息
            cpu_cmd = "lscpu | grep 'Model name' | cut -d ':' -f 2 | xargs"
            stdin, stdout, stderr = self._client.exec_command(cpu_cmd)
            cpu_info = stdout.read().decode().strip()
            
            # 获取GPU信息
            gpu_cmd = "nvidia-smi -L"
            stdin, stdout, stderr = self._client.exec_command(gpu_cmd)
            gpu_output = stdout.read().decode().strip().split('\n')
            gpu_count = len(gpu_output)
            gpu_info = gpu_output[0].split(':')[1].strip() if gpu_output else ""
            
            # 获取系统内存大小(GB)
            mem_cmd = "free -g | grep 'Mem:' | awk '{print $2}'"
            stdin, stdout, stderr = self._client.exec_command(mem_cmd)
            total_memory = int(stdout.read().decode().strip())
            
            return {
                "cpu_info": cpu_info,
                "gpu_info": gpu_info,
                "gpu_count": gpu_count,
                "total_memory": total_memory
            }
        except Exception as e:
            logger.error(f"获取硬件信息失败: {e}")
            return {
                "cpu_info": "",
                "gpu_info": "",
                "gpu_count": 1,
                "total_memory": 0
            }
    
    def get_stats(self) -> Optional[GPUStats]:
        """获取所有统计数据"""
        if not self._initialized or not self._client:
            return None
        
        try:
            # 获取GPU统计数据
            gpu_stats = self._get_gpu_stats()
            if not gpu_stats:
                return None
            
            # 获取系统统计数据
            system_stats = self._get_system_stats()
            
            # 获取硬件信息
            hardware_info = self._get_hardware_info()
            
            # 合并所有统计数据
            return GPUStats(
                **gpu_stats,
                **system_stats,
                **hardware_info
            )
            
        except Exception as e:
            logger.error(f"获取远程统计数据失败: {e}")
            return None
    
    def __del__(self):
        """清理资源"""
        if self._client:
            try:
                self._client.close()
            except:
                pass

class GPUMonitorManager:
    """GPU监控管理器"""
    def __init__(self):
        self.local_monitor = None
        self.remote_monitor = None
        self.history: List[GPUStats] = []
        self.history_size = config.get("gpu_monitor.history_size", 60)
        
        # 优先初始化远程监控
        remote_config = config.get("gpu_monitor.remote", {})
        logger.info(f"远程GPU监控配置: {remote_config}")
        
        if remote_config.get("enabled", False):
            logger.info("尝试初始化远程GPU监控...")
            self.setup_remote(
                host=remote_config["host"],
                username=remote_config["username"],
                password=remote_config["password"]
            )
        else:
            logger.info("远程GPU监控未启用")
        
        # 如果远程监控失败，初始化本地监控
        if not self.remote_monitor or not self.remote_monitor._initialized:
            logger.info("初始化本地GPU监控...")
            self.local_monitor = LocalGPUMonitor()
    
    def setup_remote(self, host: str, username: str, password: str):
        """设置远程监控"""
        logger.info(f"正在连接远程GPU监控: {host}")
        self.remote_monitor = RemoteGPUMonitor(host, username, password)
        if not self.remote_monitor._initialized:
            logger.warning("远程GPU监控初始化失败，将使用本地监控")
            self.remote_monitor = None
    
    def get_stats(self) -> Optional[GPUStats]:
        """获取GPU统计数据"""
        stats = None
        error_count = 0
        max_retries = 2  # 最大重试次数
        
        # 优先使用远程监控
        while error_count < max_retries:
            if self.remote_monitor and self.remote_monitor._initialized:
                try:
                    stats = self.remote_monitor.get_stats()
                    if stats:
                        self._update_history(stats)
                        return stats
                except Exception as e:
                    error_count += 1
                    logger.error(f"远程GPU监控获取数据失败 (尝试 {error_count}/{max_retries}): {e}")
                    if error_count == max_retries:
                        logger.warning("远程GPU监控失败次数过多，切换到本地监控")
                        break
            else:
                break
        
        # 如果远程监控失败或未配置，使用本地监控
        if self.local_monitor:
            try:
                stats = self.local_monitor.get_stats()
                if stats:
                    self._update_history(stats)
                return stats
            except Exception as e:
                logger.error(f"本地GPU监控获取数据失败: {e}")
        
        return None
    
    def _update_history(self, stats: GPUStats):
        """更新历史数据"""
        self.history.append(stats)
        if len(self.history) > self.history_size:
            self.history.pop(0)
    
    def get_history(self) -> List[GPUStats]:
        """获取历史数据"""
        return self.history.copy()

# 全局GPU监控管理器实例
gpu_manager = GPUMonitorManager()
