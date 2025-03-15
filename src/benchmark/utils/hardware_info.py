"""
硬件信息收集模块，负责收集系统和GPU信息
"""
import os
import json
import time
import platform
import psutil
import hashlib
from typing import Dict, List, Any, Optional
from src.utils.logger import setup_logger
from src.monitor.gpu_monitor import gpu_monitor

# 设置日志记录器
logger = setup_logger("hardware_info")

def collect_system_info() -> Dict[str, Any]:
    """
    收集系统信息
    
    Returns:
        Dict[str, Any]: 系统信息
    """
    system_info = {
        "device_type": "desktop",  # 默认为桌面设备
        "app_version": "1.0.0",    # 应用版本
        "os_info": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "architecture": platform.architecture()[0]
        },
        "cpu_info": {
            "brand": platform.processor(),
            "cores": psutil.cpu_count(logical=False),
            "threads": psutil.cpu_count(logical=True),
            "frequency": psutil.cpu_freq().current if psutil.cpu_freq() else 0
        },
        "memory_info": {
            "total": psutil.virtual_memory().total,
            "available": psutil.virtual_memory().available,
            "percent": psutil.virtual_memory().percent
        },
        "gpu_info": {
            "gpus": []
        },
        "network_info": {
            "hostname": platform.node()
        },
        "python_info": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "compiler": platform.python_compiler()
        },
        "timestamp": int(time.time() * 1000)
    }
    
    # 获取GPU信息
    try:
        gpu_stats = gpu_monitor.get_stats()
        if gpu_stats and hasattr(gpu_stats, 'gpus'):
            system_info["gpu_info"]["gpus"] = gpu_stats.gpus
    except Exception as e:
        logger.error(f"获取GPU信息失败: {str(e)}")
    
    return system_info

def get_hardware_info() -> Dict[str, Any]:
    """
    获取硬件信息，从GPU监控的SSH目标收集服务器信息
    
    Returns:
        Dict[str, Any]: 硬件信息
    """
    # 这里明确只获取GPU服务器的硬件信息，而不是本地设备
    hardware_info = {}
    
    try:
        logger.info("开始从GPU监控的SSH目标获取GPU服务器硬件信息...")
        # 获取GPU监控的统计信息
        gpu_stats = gpu_monitor.get_stats()
        
        if gpu_stats:
            logger.info("成功获取GPU服务器统计信息")
            logger.debug(f"GPU统计信息类型: {type(gpu_stats).__name__}")
            
            # 收集CPU信息
            cpu_info = "未知"
            try:
                if hasattr(gpu_stats, 'cpu_info'):
                    cpu_info = gpu_stats.cpu_info
                    logger.debug(f"从GPU服务器获取到CPU信息: {cpu_info}")
                else:
                    # 尝试通过SSH获取CPU信息
                    if hasattr(gpu_monitor, '_execute_command'):
                        logger.debug("尝试通过SSH命令获取GPU服务器CPU信息...")
                        cpu_cmd_result = gpu_monitor._execute_command("cat /proc/cpuinfo | grep 'model name' | head -n1 | cut -d':' -f2")
                        if cpu_cmd_result and cpu_cmd_result.strip():
                            cpu_info = cpu_cmd_result.strip()
                            logger.debug(f"通过SSH命令获取到GPU服务器CPU信息: {cpu_info}")
            except Exception as e:
                logger.warning(f"获取GPU服务器CPU信息时出错: {e}")
            
            hardware_info["cpu"] = cpu_info
            logger.debug(f"已获取GPU服务器CPU信息: {cpu_info}")
            
            # 收集内存信息
            memory_info = f"{gpu_stats.total_memory}GB" if hasattr(gpu_stats, 'total_memory') and gpu_stats.total_memory > 0 else "未知"
            hardware_info["memory"] = memory_info
            logger.debug(f"已获取GPU服务器内存信息: {memory_info}")
            
            # 收集系统信息 - 尝试执行多种命令获取系统信息，以兼容不同系统包括unraid
            system_info = ""
            try:
                if hasattr(gpu_monitor, '_execute_command'):
                    logger.debug("使用SSH执行命令获取GPU服务器系统信息...")
                    
                    # 尝试多种系统信息获取命令
                    commands = [
                        "lsb_release -d | cut -f2",                  # 标准Linux发行版
                        "cat /etc/os-release | grep PRETTY_NAME | cut -d'\"' -f2",  # 大多数现代Linux
                        "cat /etc/unraid-version 2>/dev/null",       # unRAID专用
                        "uname -a",                                  # 通用Unix/Linux
                        "hostnamectl | grep 'Operating System' | cut -d: -f2"  # systemd系统
                    ]
                    
                    for cmd in commands:
                        logger.debug(f"尝试执行: {cmd}")
                        cmd_result = gpu_monitor._execute_command(cmd)
                        if cmd_result and cmd_result.strip():
                            system_info = cmd_result.strip()
                            logger.debug(f"成功获取GPU服务器系统信息: {system_info}")
                            break
                            
                    if not system_info:
                        logger.warning("所有系统检测命令均未返回有效结果")
                        system_info = "未知Linux/Unix系统"
            except Exception as e:
                logger.warning(f"获取GPU服务器系统信息时出错: {e}")
                system_info = "未知"
            
            hardware_info["system"] = system_info
            logger.debug(f"已获取GPU服务器系统信息: {system_info}")
            
            # 收集GPU信息
            gpus = []
            if hasattr(gpu_stats, 'gpus') and gpu_stats.gpus:
                logger.debug(f"检测到GPU服务器上有 {len(gpu_stats.gpus)} 个GPU")
                for i, gpu in enumerate(gpu_stats.gpus):
                    gpu_name = gpu.get('info', 'Unknown GPU')
                    # 修复显卡内存单位问题：将MB转换为GB
                    memory_mb = int(gpu.get('memory_total', 0))
                    memory_gb = memory_mb / 1024  # 将MB转换为GB
                    gpu_str = f"{gpu_name} {memory_gb:.1f}GB"
                    gpus.append(gpu_str)
                    logger.debug(f"GPU服务器GPU {i+1}: {gpu_str} (原始内存值: {memory_mb}MB)")
            
            if gpus:
                # 统计相同GPU的数量
                gpu_counts = {}
                for gpu in gpus:
                    gpu_counts[gpu] = gpu_counts.get(gpu, 0) + 1
                
                # 构建GPU信息字符串
                gpu_info_parts = []
                for gpu, count in gpu_counts.items():
                    if count > 1:
                        gpu_info_parts.append(f"{gpu} *{count}")
                    else:
                        gpu_info_parts.append(gpu)
                
                gpu_info = " , ".join(gpu_info_parts)
                hardware_info["gpu"] = gpu_info
                logger.debug(f"已获取GPU服务器GPU信息: {gpu_info}")
            else:
                hardware_info["gpu"] = "未知"
                logger.debug("未检测到GPU服务器GPU信息，设置为'未知'")
            
            # 生成唯一硬件ID
            hardware_id = generate_hardware_fingerprint(hardware_info)
            hardware_info["id"] = hardware_id
            hardware_info["source"] = "gpu_server"  # 明确标记数据来源
            logger.debug(f"已生成GPU服务器硬件ID: {hardware_id}")
            
            # 输出完整的硬件信息
            logger.info("成功获取GPU服务器硬件信息，详细内容如下:")
            logger.info(f"CPU: {hardware_info['cpu']}")
            logger.info(f"内存: {hardware_info['memory']}")
            logger.info(f"系统: {hardware_info['system']}")
            logger.info(f"GPU: {hardware_info['gpu']}")
            logger.info(f"硬件ID: {hardware_info['id']}")
        else:
            logger.warning("无法获取GPU服务器统计信息，将使用本地系统信息作为备用")
            # 如果无法获取GPU统计信息，使用本地系统信息作为备用
            system_info = collect_system_info()
            hardware_info["cpu"] = system_info["cpu_info"]["brand"]
            hardware_info["memory"] = f"{int(system_info['memory_info']['total'] / (1024*1024*1024))}GB"
            hardware_info["system"] = f"{system_info['os_info']['system']} {system_info['os_info']['release']}"
            hardware_info["gpu"] = "未知"
            hardware_info["id"] = generate_hardware_fingerprint(hardware_info)
            hardware_info["source"] = "local"  # 明确标记数据来源
            
            logger.warning("使用本地系统信息作为备用，而非GPU服务器信息。这是不正确的，请检查GPU监控配置。")
            logger.info("备用硬件信息详细内容如下:")
            logger.info(f"CPU: {hardware_info['cpu']}")
            logger.info(f"内存: {hardware_info['memory']}")
            logger.info(f"系统: {hardware_info['system']}")
            logger.info(f"GPU: {hardware_info['gpu']}")
            logger.info(f"硬件ID: {hardware_info['id']}")
    except Exception as e:
        logger.error(f"获取GPU服务器硬件信息失败: {str(e)}")
        logger.error("将使用默认未知值")
        hardware_info = {
            "cpu": "未知",
            "memory": "未知",
            "system": "未知",
            "gpu": "未知",
            "id": "unknown-" + str(int(time.time())),
            "source": "error"  # 明确标记数据来源
        }
    
    return hardware_info

def generate_hardware_fingerprint(hardware_info: Dict[str, Any]) -> str:
    """
    生成硬件指纹
    
    Args:
        hardware_info: 硬件信息
        
    Returns:
        str: 硬件指纹
    """
    try:
        # 将硬件信息转换为JSON字符串
        hardware_str = json.dumps(hardware_info, sort_keys=True)
        
        # 使用SHA-256生成指纹
        fingerprint = hashlib.sha256(hardware_str.encode()).hexdigest()
        
        return fingerprint
    except Exception as e:
        logger.error(f"生成硬件指纹异常: {str(e)}")
        return "unknown-" + str(int(time.time())) 