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
            # 修改为使用data/benchmark/results作为默认目录
            # 相对于当前工作目录
            self.result_dir = os.path.join("data", "benchmark", "results")
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
            
            # 保存前先更新model字段，确保它使用model_info中的model_name
            if 'model_info' in result and isinstance(result['model_info'], dict) and 'model_name' in result['model_info']:
                model_name = result['model_info']['model_name']
                logger.info(f"[save_result] 从model_info.model_name更新顶级model字段: {model_name}")
                result['model'] = model_name
            
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
            
            # 如果更新中包含model_info且model_info中有model_name，更新顶级model字段
            if 'model_info' in updates and isinstance(updates['model_info'], dict) and 'model_name' in updates['model_info']:
                model_name = updates['model_info']['model_name']
                logger.info(f"[update_result] 从model_info.model_name更新顶级model字段: {model_name}")
                result['model'] = model_name
            
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
            # 确保model字段使用model_info中的model_name（如果存在）
            if 'model_info' in result and isinstance(result['model_info'], dict) and 'model_name' in result['model_info']:
                model_name = result['model_info']['model_name']
                logger.info(f"[save_encrypted_result] 从model_info.model_name更新顶级model字段: {model_name}")
                result['model'] = model_name
            
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
                # 文件已存在，可能需要更新framework_info和model字段
                updates = {}
                if 'framework_info' in result and result['framework_info']:
                    updates["framework_info"] = result['framework_info']
                    logger.info(f"[save_encrypted_result] 需要更新原始文件中的framework_info")
                
                if 'model_info' in result and result['model_info'] and 'model_name' in result['model_info']:
                    updates["model_info"] = result['model_info']
                    updates["model"] = result['model_info']['model_name']
                    logger.info(f"[save_encrypted_result] 需要更新原始文件中的model和model_info")
                
                # 使用update_result方法更新文件，而不是重新创建
                if updates:
                    self.update_result(original_path, updates)
                    logger.info(f"[save_encrypted_result] 已更新原始文件")
                
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
            
            # 获取结果文件所在的目录
            result_dir = os.path.dirname(original_path) if original_path and os.path.exists(original_path) else self.result_dir
            # 确保目录存在
            os.makedirs(result_dir, exist_ok=True)
            
            # 生成加密结果文件名
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            encrypted_file = f"benchmark_encrypted_{timestamp}.dat"
            encrypted_path = os.path.join(result_dir, encrypted_file)
            
            # 确保加密路径的目录存在
            encrypted_dir = os.path.dirname(encrypted_path)
            if encrypted_dir and not os.path.exists(encrypted_dir):
                logger.info(f"[save_encrypted_result] 创建加密文件目录: {encrypted_dir}")
                os.makedirs(encrypted_dir, exist_ok=True)
            
            # 创建加密器
            encryptor = BenchmarkEncryption()
            
            # 检查API密钥是否有效
            if not api_key:
                logger.error("[save_encrypted_result] API密钥为空，无法加密")
                return original_path, ""
            
            if len(api_key) < 32:
                logger.error(f"[save_encrypted_result] API密钥长度不足32字符 ({len(api_key)})")
                return original_path, ""
            
            try:
                # 加密并保存结果
                logger.info(f"[save_encrypted_result] 开始加密测试结果到: {encrypted_path}")
                encrypted_path_result = encryptor.encrypt_and_save(result_to_encrypt, encrypted_path, api_key)
                
                if not encrypted_path_result:
                    logger.error(f"[save_encrypted_result] 加密测试结果失败，返回路径为空")
                    return original_path, ""
                
                # 确认加密文件是否已创建
                if not os.path.exists(encrypted_path):
                    logger.error(f"[save_encrypted_result] 加密文件没有被创建: {encrypted_path}")
                    return original_path, ""
                
                logger.info(f"[save_encrypted_result] 测试结果已加密并保存到: {encrypted_path}")
                return original_path, encrypted_path
            
            except Exception as e:
                logger.error(f"[save_encrypted_result] 加密测试结果时发生错误: {str(e)}")
                return original_path, ""
        
        except Exception as e:
            logger.error(f"[save_encrypted_result] 加密并保存测试结果失败: {str(e)}")
            return "", ""
    
    def upload_encrypted_result(self, result: Dict[str, Any], api_key: str, 
                              server_url: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        上传加密的测试结果，如果已有加密文件则使用已有文件
        
        Args:
            result: 测试结果
            api_key: API密钥
            server_url: 服务器URL
            metadata: 元数据
            
        Returns:
            Dict[str, Any]: 上传结果，包含状态和消息
        """
        try:
            # 确保model字段使用model_info中的model_name（如果存在）
            if 'model_info' in result and isinstance(result['model_info'], dict) and 'model_name' in result['model_info']:
                model_name = result['model_info']['model_name']
                logger.info(f"[upload_encrypted_result] 从model_info.model_name更新顶级model字段: {model_name}")
                result['model'] = model_name
                # 同时更新metadata中的model_name
                if metadata and isinstance(metadata, dict) and 'model_name' in metadata:
                    metadata['model_name'] = model_name
                    logger.info(f"[upload_encrypted_result] 从model_info.model_name更新metadata.model_name: {model_name}")
            
            # 检查是否已有加密文件
            encrypted_path = ""
            if "encrypted_path" in result and os.path.exists(result["encrypted_path"]):
                logger.info(f"[upload_encrypted_result] 使用已存在的加密文件: {result['encrypted_path']}")
                encrypted_path = result["encrypted_path"]
                original_path = result.get("result_path", "")
            else:
                # 否则重新加密并保存结果
                logger.info(f"[upload_encrypted_result] 未找到已有加密文件，开始加密保存")
                original_path, encrypted_path = self.save_encrypted_result(result, api_key)
            
            if not encrypted_path or not os.path.exists(encrypted_path):
                logger.error(f"找不到加密的测试结果文件，无法上传: {encrypted_path}")
                return {
                    "status": "error",
                    "message": "找不到加密的测试结果文件，无法上传"
                }
            
            # 检查服务器URL
            if not server_url:
                logger.error("服务器URL为空，无法上传")
                return {
                    "status": "error",
                    "message": "服务器URL为空，无法上传"
                }
            
            # 开始上传
            import requests
            import json
            
            # 准备上传数据
            upload_data = {}
            
            # 添加API密钥（在请求头使用，这里只做备份）
            if api_key:
                upload_data["api_key"] = api_key
            
            # 添加元数据 - 确保是JSON格式的字符串
            if metadata and isinstance(metadata, dict):
                # 将元数据转换为JSON字符串
                metadata_json = json.dumps(metadata, ensure_ascii=False)
                upload_data["metadata"] = metadata_json
                logger.info(f"[upload_encrypted_result] 元数据已转换为JSON字符串，长度: {len(metadata_json)}")
            else:
                # 创建基本元数据
                basic_metadata = {
                    "submitter": result.get("nickname", "未命名用户"),
                    "model_name": result.get("model", "未知模型"),
                    "timestamp": datetime.now().isoformat()
                }
                metadata_json = json.dumps(basic_metadata, ensure_ascii=False)
                upload_data["metadata"] = metadata_json
                logger.info(f"[upload_encrypted_result] 已创建基本元数据: {basic_metadata}")
            
            # 准备文件
            try:
                files = {
                    "file": open(encrypted_path, "rb")
                }
                
                # 请求头设置
                headers = {
                    "X-API-Key": api_key if api_key else ""
                }
                
                logger.info(f"[upload_encrypted_result] 开始上传到: {server_url}")
                logger.info(f"[upload_encrypted_result] 上传数据包含字段: {list(upload_data.keys())}")
                
                # 上传
                response = requests.post(server_url, data=upload_data, files=files, headers=headers)
                
                # 关闭文件
                files["file"].close()
                
                # 解析响应
                if response.status_code == 200:
                    # 尝试解析JSON响应
                    try:
                        response_data = response.json()
                        
                        # 检查响应状态
                        if response_data.get("status") == "success":
                            upload_id = response_data.get("id", "unknown")
                            logger.info(f"测试结果上传成功，ID: {upload_id}")
                            return {
                                "status": "success",
                                "message": "测试结果上传成功",
                                "upload_id": upload_id,
                                "upload_result": response_data
                            }
                        else:
                            error_msg = response_data.get("message", "上传失败，服务器返回错误")
                            logger.error(f"测试结果上传失败: {error_msg}")
                            return {
                                "status": "error",
                                "message": error_msg
                            }
                    except json.JSONDecodeError:
                        # 响应不是JSON格式
                        logger.error("服务器返回的不是JSON格式")
                        return {
                            "status": "error",
                            "message": f"服务器返回的不是JSON格式: {response.text[:100]}"
                        }
                else:
                    # 响应状态码不是200
                    logger.error(f"服务器返回错误状态码: {response.status_code}, 响应: {response.text}")
                    return {
                        "status": "error",
                        "message": f"服务器返回错误状态码: {response.status_code}, 响应: {response.text}"
                    }
            except Exception as file_error:
                logger.error(f"处理文件上传时出错: {str(file_error)}")
                return {
                    "status": "error",
                    "message": f"处理文件上传时出错: {str(file_error)}"
                }
        except Exception as e:
            logger.error(f"上传测试结果失败: {str(e)}")
            return {
                "status": "error",
                "message": f"上传测试结果失败: {str(e)}"
            }


# 创建一个全局的结果处理器实例
result_handler = ResultHandler() 