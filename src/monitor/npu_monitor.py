import time
from typing import Dict, Optional, List
import paramiko
from src.utils.logger import setup_logger
from src.utils.config import config
from src.data.db_manager import db_manager

logger = setup_logger("npu_monitor")

class NPUStats:
    """NPU统计数据类"""
    def __init__(
        self,
        npus: List[Dict] = None,  # 多NPU数据列表
        cpu_util: float = 0.0,    # CPU使用率
        memory_util: float = 0.0,  # 系统内存使用率
        disk_util: float = 0.0,    # 磁盘使用率
        disk_io_latency: float = 0.0,  # 磁盘IO延时（毫秒）
        network_io: Dict[str, float] = None,  # 网络IO统计
        timestamp: float = None,
        cpu_info: str = "",       # CPU型号信息
        npu_count: int = 0,       # NPU数量
        total_memory: int = 0     # 系统总内存(GB)
    ):
        self.npus = npus or []    # 多NPU数据
        self.cpu_util = cpu_util 
        self._memory_util = memory_util     # %
        self.disk_util = disk_util         # %
        self.disk_io_latency = disk_io_latency  # ms
        self.network_io = network_io or {}  # 包含上传下载速度
        self.timestamp = timestamp or time.time()
        self.cpu_info = cpu_info           # CPU型号
        self.npu_count = npu_count         # NPU数量
        self.total_memory = total_memory   # 系统总内存
    
    # 为了兼容现有代码，提供属性访问方法
    @property
    def npu_util(self) -> float:
        """第一个NPU的利用率"""
        return self.npus[0]['util'] if self.npus else 0.0
    
    @property
    def npu_memory_util(self) -> float:
        """第一个NPU的显存使用率"""
        if not self.npus:
            return 0.0
        npu = self.npus[0]
        return (npu['memory_used'] / npu['memory_total']) * 100 if npu['memory_total'] > 0 else 0
    
    @property
    def memory_used(self) -> float:
        """系统已用内存"""
        return self._memory_util
    
    @property
    def memory_total(self) -> float:
        """系统总内存"""
        return self.total_memory
    
    @property
    def temperature(self) -> float:
        """第一个NPU的温度"""
        return self.npus[0]['temperature'] if self.npus else 0.0
    
    @property
    def power_usage(self) -> float:
        """第一个NPU的功率使用"""
        return self.npus[0]['power_usage'] if self.npus else 0.0
    
    @property
    def npu_info(self) -> str:
        """第一个NPU的型号信息"""
        return self.npus[0]['info'] if self.npus else ""
    
    @property
    def memory_util(self) -> float:
        """系统内存使用率"""
        return self._memory_util
    
    @memory_util.setter
    def memory_util(self, value: float):
        """设置系统内存使用率"""
        self._memory_util = value
    
    def get_npu(self, index: int) -> Dict:
        """获取指定索引的NPU数据"""
        if 0 <= index < len(self.npus):
            return self.npus[index]
        return None
    
    def get_npu_memory_util(self, index: int) -> float:
        """获取指定NPU的显存使用率"""
        npu = self.get_npu(index)
        if not npu:
            return 0.0
        return (npu['memory_used'] / npu['memory_total']) * 100 if npu['memory_total'] > 0 else 0

class NPUMonitor:
    """远程NPU监控类"""
    def __init__(self, host: str, username: str, password: str, port: int = 22):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.client = None
        self.max_retries = config.get('ssh_max_retries', 3)  # 最大重试次数
        self.retry_interval = config.get('ssh_retry_interval', 2)  # 重试间隔（秒）
        # 添加网络IO历史数据
        self._last_net_stats = None
        self._last_net_time = None
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
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=5
                )
                logger.info(f"成功连接到远程服务器: {self.host}:{self.port}")
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
                output = stdout.read().decode().strip()
                error = stderr.read().decode().strip()
                if error:
                    raise Exception(error)
                return output
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

    def _get_network_speed(self) -> Dict[str, float]:
        """获取网络速度"""
        try:
            # 获取当前网络数据
            net_command = "cat /proc/net/dev | grep -E 'eth0|ens|enp' | head -n1 | awk '{print $2,$10}'"
            net_output = self._execute_command(net_command)
            if not net_output:
                return {'receive': 0, 'transmit': 0, 'receive_rate': 0.1, 'send_rate': 0.1}
            
            current_time = time.time()
            net_parts = net_output.split()
            if len(net_parts) < 2:
                return {'receive': 0, 'transmit': 0, 'receive_rate': 0.1, 'send_rate': 0.1}
                
            # 获取字节数
            net_recv = float(net_parts[0])
            net_send = float(net_parts[1])
            
            # 如果是第一次获取数据
            if self._last_net_stats is None:
                self._last_net_stats = (net_recv, net_send)
                self._last_net_time = current_time
                return {'receive': net_recv, 'transmit': net_send, 'receive_rate': 0.1, 'send_rate': 0.1}
            
            # 计算时间差
            time_diff = current_time - self._last_net_time
            if time_diff <= 0:
                return {'receive': net_recv, 'transmit': net_send, 'receive_rate': 0.1, 'send_rate': 0.1}
            
            # 计算速率（bytes/s）
            recv_speed = (net_recv - self._last_net_stats[0]) / time_diff
            send_speed = (net_send - self._last_net_stats[1]) / time_diff
            
            # 更新历史数据
            self._last_net_stats = (net_recv, net_send)
            self._last_net_time = current_time
            
            # 确保速率不小于0.1KB/s以保证显示
            recv_rate = max(0.1, recv_speed / 1024)  # KB/s
            send_rate = max(0.1, send_speed / 1024)
            
            return {
                'receive': net_recv, 
                'transmit': net_send,
                'receive_rate': recv_rate,
                'send_rate': send_rate
            }
            
        except Exception as e:
            logger.error(f"获取网络速度失败: {e}")
            return {'receive': 0, 'transmit': 0, 'receive_rate': 0.1, 'send_rate': 0.1}

    def get_stats(self) -> Optional[NPUStats]:
        """获取NPU和系统状态

        Returns:
            NPUStats: NPU统计信息
        """
        try:
            if not self.client:
                logger.warning("无法获取NPU信息：SSH连接未建立")
                return None

            # 获取NPU使用信息
            all_npUs = []
            npu_info = self._execute_command(
                "npu-smi info"
            )
            if not npu_info:
                return None

            # 解析NPU信息
            lines = npu_info.split('\n')
            headers = ["ID", "Health", "Power(W)", "Temp(C)", "Hugepages-Usage(page)", "AICore(%)", "Memory-Usage(MB)", "HBM-Usage(MB)"]
            start_index = 4  # 数据开始行

            for i in range(start_index, len(lines), 2):  # 每两个行为一组
                line1 = lines[i].split('|')[1:-1]
                line2 = lines[i+1].split('|')[1:-1]

                if len(line1) != 8 or len(line2) != 8:
                    continue

                npu_data = dict(zip(headers, [part.strip() for part in line1]))
                chip_data = dict(zip(headers, [part.strip() for part in line2]))

                npu_id = int(npu_data['ID'])
                npu_name = int(npu_data['Name'])
                health = npu_data['Health']
                power_usage = float(chip_data['Power(W)'])
                temperature = float(chip_data['Temp(C)'])
                ai_util = float(chip_data['AICore(%)'])
                memory_used, memory_total = map(float, chip_data['Memory-Usage(MB)'].split('/'))

                all_npUs.append({
                    'id': npu_id,
                    'health': health,
                    'power_usage': power_usage,
                    'temperature': temperature,
                    'util': ai_util,
                    'memory_used': memory_used,
                    'memory_total': memory_total,
                    'info': npu_name  
                })

            if not all_npUs:
                return None
            
            # 获取CPU使用率
            cpu_util_str = self._execute_command(
                "top -bn1 | grep 'Cpu(s)' | sed 's/.*, *\\([0-9.]*\\)%* id.*/\\1/' | awk '{print 100 - $1}'"
            )
            cpu_util = float(cpu_util_str) if cpu_util_str else 0.0
            
            # 获取内存使用情况
            mem_info_str = self._execute_command(
                "free -m | grep Mem | awk '{print $3,$2}'"
            )
            mem_output = mem_info_str.split()
            if len(mem_output) >= 2:
                mem_used = float(mem_output[0])
                mem_total = float(mem_output[1])
                memory_util = (mem_used / mem_total) * 100
                total_memory = int(mem_total / 1024)  # 转换为GB
            else:
                memory_util = 0
                total_memory = 0
            
            # 获取磁盘使用情况
            disk_util_str = self._execute_command(
                "df -h / | grep / | awk '{print $5}' | sed 's/%//'"
            )
            disk_util = float(disk_util_str) if disk_util_str else 0
            
            # 获取磁盘IO延迟 - 使用iowait百分比作为指标
            iowait_command = "top -bn1 | grep '%Cpu' | awk '{print $10}'"
            iowait_output = self._execute_command(iowait_command)
            
            try:
                # 将iowait百分比转换为毫秒单位的延迟值 (0-100% -> 0-100ms)
                iowait_percent = float(iowait_output) if iowait_output else 1.0
                disk_io_latency = iowait_percent  # 直接使用iowait百分比值作为毫秒数
            except (ValueError, TypeError):
                disk_io_latency = 1.0  # 默认值
            
            # 获取网络IO信息
            network_io = self._get_network_speed()
            
            # 获取CPU信息
            cpu_info_str = self._execute_command(
                "lscpu | grep 'Model name' | sed 's/Model name: *//'"
            )
            cpu_info = cpu_info_str.strip() if cpu_info_str else ""
            
            # 创建NPU统计对象
            stats = NPUStats(
                npus=all_npUs,
                cpu_util=cpu_util,
                memory_util=memory_util,
                disk_util=disk_util,
                disk_io_latency=disk_io_latency,
                network_io=network_io,
                cpu_info=cpu_info,
                npu_count=len(all_npUs),
                total_memory=total_memory
            )
            
            self._last_net_stats = network_io
            self._last_net_time = time.time()
            
            # 保存到数据库
            if db_manager:
                db_manager.add_npu_stats(
                    self.host,
                    stats.npu_util,
                    stats.npu_memory_util,
                    stats.temperature,
                    stats.power_usage,
                    stats.cpu_util,
                    stats.memory_util
                )
            
            return stats
            
        except Exception as e:
            logger.error(f"获取NPU状态错误: {e}")
            self.handle_connection_error()
            return None

    def handle_connection_error(self):
        """处理连接错误"""
        logger.info(f"处理连接错误: {self.host}")
        if self.client:
            try:
                self.client.close()
            except:
                pass
            self.client = None
        # 尝试重新连接
        self._connect()
    
    def __del__(self):
        """析构函数，关闭SSH连接"""
        if self.client:
            try:
                self.client.close()
            except:
                pass

class NPUMonitorManager:
    """NPU监控管理器"""
    def __init__(self):
        self.monitor = None
        self.active_server = None
    
    def init_monitor(self):
        """初始化NPU监控器"""
        try:
            # 获取活动的NPU服务器配置
            server = db_manager.get_active_npu_server()
            if server:
                self.setup_monitor(
                    server["host"],
                    server["username"],
                    server["password"],
                    server.get("port", 22)  # 使用默认端口22
                )
                logger.info(f"NPU监控器初始化成功: {server['host']}:{server.get('port', 22)}")
            else:
                logger.warning("未找到活动的NPU服务器配置")
                self.monitor = None
        except Exception as e:
            logger.error(f"初始化NPU监控器失败: {e}")
            self.monitor = None
    
    def setup_monitor(self, host: str, username: str, password: str, port: int = 22):
        """设置NPU监控器
        
        Args:
            host: 主机地址
            username: 用户名
            password: 密码
            port: SSH端口
        """
        try:
            self.monitor = NPUMonitor(host, username, password, port)
            logger.info(f"NPU监控器设置成功: {host}:{port}")
        except Exception as e:
            logger.error(f"设置NPU监控器失败: {e}")
            self.monitor = None
    
    def get_stats(self) -> Optional[NPUStats]:
        """获取NPU统计数据"""
        try:
            if not self.monitor:
                return None
            return self.monitor.get_stats()
        except Exception as e:
            logger.error(f"获取NPU统计数据失败: {e}")
            return None

# 创建全局NPU监控管理器实例，但不自动初始化
npu_monitor = NPUMonitorManager()



