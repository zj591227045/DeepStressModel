"""
结果处理模块，负责保存和处理测试结果
"""
import os
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from src.utils.logger import setup_logger
from src.benchmark.crypto.benchmark_log_encrypt import BenchmarkEncryption

# 设置日志记录器
logger = setup_logger("result_handler")

class ResultHandler:
    """结果处理类，用于保存和处理测试结果"""
    
    def __init__(self, result_dir=None):
        """
        初始化结果处理器
        
        Args:
            result_dir: 结果保存目录
        """
        # 如果没有指定结果目录，使用默认目录
        if not result_dir:
            self.result_dir = os.path.join(os.path.expanduser("~"), ".deepstressmodel", "benchmark_results")
        else:
            self.result_dir = result_dir
        
        # 确保目录存在
        os.makedirs(self.result_dir, exist_ok=True)
    
    def _truncate_text(self, text: str, max_length: int = 50) -> str:
        """
        截断文本，超过指定长度的部分用...代替
        
        Args:
            text: 要截断的文本
            max_length: 最大长度，默认50
            
        Returns:
            str: 截断后的文本
        """
        if isinstance(text, str) and len(text) > max_length:
            return text[:max_length] + "..."
        return text
    
    def save_result(self, result: Dict[str, Any]) -> str:
        """
        保存测试结果
        
        Args:
            result: 测试结果
            
        Returns:
            str: 结果文件路径
        """
        try:
            # 添加调试日志，检查输入的framework_info
            logger.info(f"[save_result] 开始保存测试结果，framework_info存在: {'framework_info' in result}")
            if 'framework_info' in result:
                logger.info(f"[save_result] 输入的framework_info: {result['framework_info']}")
            
            # 生成结果文件名
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            result_file = f"benchmark_result_{timestamp}.json"
            result_path = os.path.join(self.result_dir, result_file)
            
            # 在保存前记录硬件信息
            if "hardware_info" in result:
                logger.info("保存结果文件中包含以下硬件信息:")
                hardware_info = result["hardware_info"]
                logger.info(f"CPU: {hardware_info.get('cpu', '未知')}")
                logger.info(f"内存: {hardware_info.get('memory', '未知')}")
                logger.info(f"系统: {hardware_info.get('system', '未知')}")
                logger.info(f"GPU: {hardware_info.get('gpu', '未知')}")
                logger.info(f"硬件ID: {hardware_info.get('id', '未知')}")
            else:
                logger.warning("结果中未包含硬件信息！")
            
            # 截断每个测试结果的输入和输出文本，减小日志文件大小
            if "results" in result and isinstance(result["results"], list):
                truncated_count = 0
                total_items = len(result["results"])
                
                for item in result["results"]:
                    # 截断input字段
                    if "input" in item:
                        original = item["input"]
                        item["input"] = self._truncate_text(original)
                        if original != item["input"]:
                            truncated_count += 1
                    
                    # 截断output字段
                    if "output" in item:
                        original = item["output"]
                        item["output"] = self._truncate_text(original)
                        if original != item["output"]:
                            truncated_count += 1
                    
                    # 截断error字段
                    if "error" in item:
                        original = item["error"]
                        item["error"] = self._truncate_text(original)
                        if original != item["error"]:
                            truncated_count += 1
                
                if truncated_count > 0:
                    logger.info(f"已截断 {truncated_count} 个字段，测试项总数: {total_items}")
            
            # 保存结果
            with open(result_path, 'w', encoding='utf-8') as f:
                # 保存前再次检查framework_info
                logger.info(f"[save_result] 保存前检查，framework_info存在: {'framework_info' in result}")
                if 'framework_info' in result:
                    logger.info(f"[save_result] 保存前的framework_info: {result['framework_info']}")
                
                json.dump(result, f, ensure_ascii=False, indent=2)
                logger.info(f"[save_result] 已写入JSON文件")
            
            logger.info(f"测试结果已保存到: {result_path}")
            return result_path
        except Exception as e:
            logger.error(f"保存测试结果失败: {str(e)}")
            return ""
    
    def load_result(self, result_path: str) -> Optional[Dict[str, Any]]:
        """
        加载测试结果
        
        Args:
            result_path: 结果文件路径
            
        Returns:
            Optional[Dict[str, Any]]: 测试结果或None（失败时）
        """
        try:
            if not os.path.exists(result_path):
                logger.error(f"结果文件不存在: {result_path}")
                return None
            
            # 读取结果文件
            with open(result_path, 'r', encoding='utf-8') as f:
                result = json.load(f)
            
            logger.info(f"成功加载测试结果: {result_path}")
            return result
        except Exception as e:
            logger.error(f"加载测试结果失败: {str(e)}")
            return None
    
    def update_result(self, result_path: str, updates: Dict[str, Any]) -> bool:
        """
        更新测试结果
        
        Args:
            result_path: 结果文件路径
            updates: 要更新的字段
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 加载结果
            result = self.load_result(result_path)
            if not result:
                return False
            
            # 更新字段
            result.update(updates)
            
            # 保存结果
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            logger.info(f"成功更新测试结果: {result_path}")
            return True
        except Exception as e:
            logger.error(f"更新测试结果失败: {str(e)}")
            return False
    
    def save_encrypted_result(self, result: Dict[str, Any], api_key: str) -> Tuple[str, str]:
        """
        加密并保存测试结果
        
        Args:
            result: 测试结果
            api_key: API密钥
            
        Returns:
            Tuple[str, str]: 原始结果文件路径和加密结果文件路径
        """
        try:
            # 检查framework_info
            logger.info(f"[save_encrypted_result] 开始加密保存，framework_info存在: {'framework_info' in result}")
            if 'framework_info' in result:
                logger.info(f"[save_encrypted_result] 加密前framework_info: {result['framework_info']}")
            else:
                logger.warning("[save_encrypted_result] 加密前结果中不存在framework_info")
            
            # 获取原始结果文件路径，如果存在
            original_path = result.get("result_path", "")
            
            # 如果原始结果已经存在，则使用它；否则创建一个新的
            if original_path and os.path.exists(original_path):
                logger.info(f"[save_encrypted_result] 使用已存在的原始结果文件: {original_path}")
                # 文件已存在，可能需要更新framework_info
                if 'framework_info' in result and result['framework_info']:
                    # 使用update_result方法更新文件，而不是重新创建
                    self.update_result(original_path, {"framework_info": result['framework_info']})
                    logger.info(f"[save_encrypted_result] 更新了原始文件中的framework_info")
                
                # 读取更新后的文件内容
                try:
                    with open(original_path, 'r', encoding='utf-8') as f:
                        result_to_encrypt = json.load(f)
                        logger.info(f"[save_encrypted_result] 读取现有文件成功，framework_info存在: {'framework_info' in result_to_encrypt}")
                except Exception as e:
                    logger.error(f"[save_encrypted_result] 读取原始文件时出错: {str(e)}")
                    # 回退到使用内存中的结果
                    result_to_encrypt = result
            else:
                # 如果没有原始文件，或原始文件不存在，则创建一个新的
                logger.info("[save_encrypted_result] 原始结果文件不存在，将创建新文件")
                original_path = self.save_result(result)
                # 使用刚创建的结果进行加密
                result_to_encrypt = result
            
            # 生成加密结果文件名
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            encrypted_file = f"encrypted_benchmark_result_{timestamp}.json"
            encrypted_path = os.path.join(self.result_dir, encrypted_file)
            
            try:
                # 初始化加密器
                logger.debug("开始初始化加密器...")
                encryptor = BenchmarkEncryption()
                
                # 确保加密器初始化成功
                if not encryptor.public_key:
                    error_msg = getattr(encryptor, 'init_error', {}).get('message', "公钥未初始化")
                    logger.error(f"加密失败: {error_msg}")
                    return original_path, ""
                
                # 加密并保存结果
                logger.debug("开始加密测试结果...")
                encrypted_path_result = encryptor.encrypt_and_save(result_to_encrypt, encrypted_path, api_key)
                
                if not encrypted_path_result:
                    logger.error("加密保存失败，返回值为空")
                    return original_path, ""
                    
                logger.info(f"加密结果已保存到: {encrypted_path}")
                return original_path, encrypted_path
            except Exception as e:
                logger.error(f"加密过程中出错: {str(e)}")
                return original_path, ""
        except Exception as e:
            logger.error(f"保存加密结果失败: {str(e)}")
            return "", ""
    
    def upload_encrypted_result(self, result: Dict[str, Any], api_key: str, 
                              server_url: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        加密并上传测试结果到服务器
        
        Args:
            result: 测试结果
            api_key: API密钥
            server_url: 服务器URL
            metadata: 元数据，如提交者信息、模型信息等
            
        Returns:
            Dict[str, Any]: 服务器响应结果
        """
        try:
            # 初始化加密器
            encryptor = BenchmarkEncryption()
            
            # 准备元数据
            if not metadata:
                metadata = {}
            
            # 添加硬件信息到元数据
            if "hardware_info" in result:
                metadata["hardware_info"] = result["hardware_info"]
            
            if "model" in result:
                metadata["model_name"] = result["model"]
            
            # 加密并上传结果
            response = encryptor.encrypt_and_upload(
                result, 
                api_key=api_key,
                server_url=server_url,
                metadata=metadata
            )
            
            logger.info(f"加密结果已上传，ID: {response.get('upload_id', 'unknown')}")
            return response
        except Exception as e:
            logger.error(f"上传加密结果失败: {str(e)}")
            return {"status": "error", "message": str(e)}


# 创建一个全局的结果处理器实例
result_handler = ResultHandler() 