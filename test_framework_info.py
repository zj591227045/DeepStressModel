#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
框架信息获取测试脚本
"""
import sys
import paramiko
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def get_framework_info():
    """
    通过SSH连接到GPU服务器获取框架信息
    """
    try:
        logger.info("开始获取框架信息...")
        
        # 创建SSH客户端
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            # 连接到GPU服务器
            logger.info("正在连接GPU服务器...")
            ssh.connect('10.255.0.75', username='root', password='P@$$2023?!')
            logger.info("GPU服务器连接成功")
            
            # 步骤1: 获取所有GPU进程
            logger.info("执行nvidia-smi pmon命令...")
            stdin, stdout, stderr = ssh.exec_command('nvidia-smi pmon -c 1')
            pmon_output = stdout.read().decode()
            logger.info(f"nvidia-smi输出: {pmon_output}")
            
            # 解析输出找到所有GPU进程
            gpu_pids = []
            for line in pmon_output.split('\n'):
                if line and not line.startswith('#') and not line.startswith('GPU'):
                    parts = line.split()
                    if len(parts) >= 2:  # 确保有足够的列以获取PID
                        pid = parts[1]
                        command = parts[-1] if len(parts) > 2 else ""
                        gpu_pids.append((pid, command))
            
            if not gpu_pids:
                logger.warning("未找到GPU进程")
                return None
            
            logger.info(f"找到GPU进程: {gpu_pids}")
            
            # 步骤2: 检查进程名称，直接识别已知框架
            for pid, command in gpu_pids:
                if command.lower() == "ollama":
                    logger.info(f"检测到Ollama进程: {pid}")
                    return {
                        'framework': 'Ollama',
                        'pid': pid
                    }
                elif "llama.cpp" in command.lower() or "llama-cpp" in command.lower():
                    logger.info(f"检测到llama.cpp进程: {pid}")
                    return {
                        'framework': 'llama.cpp',
                        'pid': pid
                    }
            
            # 步骤3: 对于Python进程，获取详细信息和父进程
            for pid, command in gpu_pids:
                if "python" in command.lower():
                    logger.info(f"检测到Python进程: {pid}，获取详细信息")
                    
                    # 获取进程详细信息
                    stdin, stdout, stderr = ssh.exec_command(f'ps -ef | grep {pid}')
                    ps_output = stdout.read().decode()
                    logger.info(f"进程{pid}详细信息: {ps_output}")
                    
                    # 分析进程命令行
                    for line in ps_output.split('\n'):
                        if str(pid) in line and 'grep' not in line:
                            logger.info(f"分析命令行: {line}")
                            
                            # 检查命令行是否包含框架信息
                            cmd_lower = line.lower()
                            if 'vllm' in cmd_lower:
                                logger.info(f"从命令行检测到vLLM框架: {pid}")
                                return parse_vllm_info(line)
                            elif 'sglang' in cmd_lower:
                                logger.info(f"从命令行检测到SGLang框架: {pid}")
                                return {
                                    'framework': 'SGLang',
                                    'raw_command': line.strip(),
                                    'pid': pid
                                }
                            
                            # 如果直接检查命令行没找到，获取父进程
                            parent_pid = None
                            parts = line.split()
                            if len(parts) >= 3:
                                parent_pid = parts[2]
                                logger.info(f"获取进程{pid}的父进程: {parent_pid}")
                                
                                if parent_pid and parent_pid != "1":
                                    stdin, stdout, stderr = ssh.exec_command(f'ps -ef | grep {parent_pid}')
                                    parent_output = stdout.read().decode()
                                    logger.info(f"父进程{parent_pid}详细信息: {parent_output}")
                                    
                                    # 分析父进程命令行
                                    for parent_line in parent_output.split('\n'):
                                        if str(parent_pid) in parent_line and 'grep' not in parent_line:
                                            parent_cmd_lower = parent_line.lower()
                                            
                                            if 'vllm' in parent_cmd_lower:
                                                logger.info(f"从父进程命令行检测到vLLM框架: {parent_pid}")
                                                return parse_vllm_info(parent_line)
                                            elif 'sglang' in parent_cmd_lower:
                                                logger.info(f"从父进程命令行检测到SGLang框架: {parent_pid}")
                                                return {
                                                    'framework': 'SGLang',
                                                    'raw_command': parent_line.strip(),
                                                    'pid': parent_pid
                                                }
            
            # 如果未能识别框架，返回None
            logger.warning("未能识别框架类型")
            return None
            
        except Exception as e:
            logger.error(f"执行SSH命令失败: {str(e)}")
            return None
        
        finally:
            ssh.close()
            logger.info("SSH连接已关闭")
            
    except Exception as e:
        logger.error(f"获取框架信息时出错: {str(e)}")
        return None

def parse_vllm_info(cmd_line):
    """
    解析vLLM命令行，提取模型信息
    """
    try:
        import shlex
        
        framework_info = {
            'framework': 'vLLM',
            'raw_command': cmd_line.strip()
        }
        
        # 解析命令行参数
        args = shlex.split(cmd_line)
        for i, arg in enumerate(args):
            if i + 1 < len(args):
                if arg == '--model':
                    framework_info['model_path'] = args[i + 1]
                elif arg == '--served-model-name':
                    framework_info['model_name'] = args[i + 1]
                elif arg == '--dtype':
                    framework_info['dtype'] = args[i + 1]
                elif arg == '--gpu-memory-utilization':
                    try:
                        framework_info['gpu_mem_util'] = float(args[i + 1])
                    except:
                        framework_info['gpu_mem_util'] = args[i + 1]
                elif arg == '--max-model-len':
                    try:
                        framework_info['max_seq_len'] = int(args[i + 1])
                    except:
                        framework_info['max_seq_len'] = args[i + 1]
        
        return framework_info
        
    except Exception as e:
        logger.error(f"解析vLLM信息失败: {str(e)}")
        return {
            'framework': 'vLLM',
            'raw_command': cmd_line.strip(),
            'error': str(e)
        }

if __name__ == "__main__":
    info = get_framework_info()
    print(f"\n获取到的框架信息: {info}") 