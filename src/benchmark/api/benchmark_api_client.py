"""
排行榜API客户端模块，用于与排行榜服务器通信
"""
import json
import aiohttp
import asyncio
import time
from typing import Dict, Any, Optional, Union, List
from src.utils.logger import setup_logger
from src.benchmark.crypto.timestamp_validator import TimestampValidator
from src.benchmark.crypto.signature_manager import SignatureManager
from src.benchmark.crypto.data_encryptor import DataEncryptor

# 设置日志记录器
logger = setup_logger("benchmark_api_client")

class BenchmarkAPIClient:
    """排行榜API客户端类，用于与排行榜服务器通信"""
    
    def __init__(
        self,
        server_url: str,
        api_key: str = None,
        server_public_key: bytes = None,
        connect_timeout: int = 10,
        max_retries: int = 3
    ):
        """
        初始化排行榜API客户端
        
        Args:
            server_url: 服务器URL
            api_key: API密钥，用于签名
            server_public_key: 服务器公钥，用于加密会话密钥
            connect_timeout: 连接超时时间，单位为秒
            max_retries: 最大重试次数
        """
        # 确保服务器URL格式正确
        self.server_url = server_url.rstrip("/")
        if not self.server_url.endswith("/api/v1"):
            self.server_url += "/api/v1"
        
        self.api_key = api_key
        self.server_public_key = server_public_key
        self.connect_timeout = connect_timeout
        self.max_retries = max_retries
        
        # 设备信息
        self.device_id = None
        self.session_token = None
        
        # 创建加密工具
        self.timestamp_validator = TimestampValidator()
        self.signature_manager = SignatureManager(api_key) if api_key else None
        self.data_encryptor = DataEncryptor(api_key, server_public_key)
        
        # 创建异步HTTP会话
        self.session = None
        
        # nonce 相关
        self.current_nonce = None
        self.use_nonce = True  # 默认使用 nonce 机制
        
        logger.info(f"初始化排行榜API客户端: URL={server_url}")
    
    async def _ensure_session(self):
        """确保HTTP会话已创建"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(
                    connect=self.connect_timeout,
                    sock_connect=self.connect_timeout,
                    sock_read=None,  # 不限制读取超时
                    total=None  # 不限制总体超时
                )
            )
    
    async def close(self):
        """关闭客户端会话"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("排行榜API客户端会话已关闭")
    
    async def sync_time(self) -> bool:
        """
        同步时间，获取服务器时间并更新时间偏移
        
        Returns:
            bool: 同步是否成功
        """
        try:
            await self._ensure_session()
            
            # 构建URL
            url = f"{self.server_url}/time"
            
            try:
                # 发送请求
                async with self.session.get(url) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        if "server_time" in response_data:
                            server_time = int(response_data["server_time"])
                            self.timestamp_validator.update_time_offset(server_time)
                            logger.info(f"时间同步成功，服务器时间: {server_time}")
                            return True
                        else:
                            logger.error("响应中缺少服务器时间")
                    else:
                        error_text = await response.text()
                        logger.error(f"时间同步失败: {response.status} - {error_text}")
            except Exception as e:
                logger.error(f"时间同步请求异常: {str(e)}")
            
            # 如果服务器不支持时间同步，使用备用方案
            # 添加一个固定的时间偏移（10秒），确保时间戳在服务器的有效期内
            logger.info("服务器不支持时间同步，使用备用方案")
            current_time = int(time.time() * 1000)
            server_time = current_time + 10000  # 假设服务器时间比客户端快10秒
            self.timestamp_validator.update_time_offset(server_time)
            logger.info(f"使用备用时间偏移: +10秒")
            return True
            
        except Exception as e:
            logger.error(f"时间同步异常: {str(e)}")
            return False
    
    async def get_nonce(self) -> str:
        """
        从服务器获取一次性随机数(nonce)
        
        Returns:
            str: 获取到的nonce
        """
        try:
            await self._ensure_session()
            
            # 构建URL
            endpoint = "client/nonce"  # 修正路径
            url = f"{self.server_url}/{endpoint.lstrip('/')}"
            logger.debug(f"获取nonce的URL: {url}")
            
            # 发送请求
            async with self.session.get(url) as response:
                if response.status == 200:
                    response_data = await response.json()
                    logger.debug(f"获取nonce响应数据: {response_data}")
                    
                    # 直接检查nonce字段
                    if "nonce" in response_data:
                        self.current_nonce = response_data["nonce"]
                        logger.info(f"获取nonce成功: {self.current_nonce}")
                        return self.current_nonce
                    else:
                        logger.error(f"响应中缺少nonce: {response_data}")
                        # 如果无法获取nonce，生成一个随机nonce
                        import uuid
                        self.current_nonce = str(uuid.uuid4()).replace("-", "")
                        logger.warning(f"使用本地生成的nonce: {self.current_nonce}")
                        return self.current_nonce
                else:
                    error_text = await response.text()
                    logger.error(f"获取nonce失败: {response.status} - {error_text}")
                    # 如果无法获取nonce，生成一个随机nonce
                    import uuid
                    self.current_nonce = str(uuid.uuid4()).replace("-", "")
                    logger.warning(f"使用本地生成的nonce: {self.current_nonce}")
                    return self.current_nonce
        except Exception as e:
            logger.error(f"获取nonce异常: {str(e)}")
            # 如果无法获取nonce，生成一个随机nonce
            import uuid
            self.current_nonce = str(uuid.uuid4()).replace("-", "")
            logger.warning(f"使用本地生成的nonce: {self.current_nonce}")
            return self.current_nonce
    
    async def _make_request(
        self,
        endpoint: str,
        data: Dict[str, Any],
        method: str = "POST",
        retry_count: int = None,
        headers: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        发送请求到服务器
        
        Args:
            endpoint: API端点
            data: 请求数据
            method: 请求方法，默认为POST
            retry_count: 重试次数，如果为None则使用默认值
            headers: 自定义请求头
            
        Returns:
            Dict[str, Any]: 响应数据
        """
        if retry_count is None:
            retry_count = self.max_retries
        
        await self._ensure_session()
        
        # 如果使用nonce机制，先获取nonce
        if self.use_nonce and endpoint != "nonce":
            if not self.current_nonce:
                await self.get_nonce()
        
        # 生成时间戳
        timestamp = self.timestamp_validator.generate_timestamp()
        
        # 构建签名
        signature = None
        if self.signature_manager:
            # 如果使用nonce，将nonce也包含在签名中
            if self.use_nonce and self.current_nonce:
                signature = self.signature_manager.generate_signature(data, f"{timestamp}:{self.current_nonce}")
            else:
                signature = self.signature_manager.generate_signature(data, timestamp)
        
        # 构建请求数据
        request_data = {
            "data": data,
            "timestamp": timestamp,
            "signature": signature
        }
        
        # 如果有nonce，添加到请求数据
        if self.use_nonce and self.current_nonce:
            request_data["nonce"] = self.current_nonce
        
        # 构建请求头
        request_headers = {
            "Content-Type": "application/json",
            "X-Timestamp": timestamp
        }
        
        # 如果有nonce，添加到请求头
        if self.use_nonce and self.current_nonce:
            request_headers["X-Nonce"] = self.current_nonce
        
        # 如果有签名，添加到请求头
        if signature:
            request_headers["X-Signature"] = signature
        
        # 如果有自定义请求头，添加到请求头
        if headers:
            request_headers.update(headers)
        
        # 构建URL
        url = f"{self.server_url}/{endpoint.lstrip('/')}"
        logger.debug(f"准备发送请求: method={method}, url={url}")
        logger.debug(f"服务器基础URL: {self.server_url}")
        logger.debug(f"请求端点: {endpoint}")
        logger.debug(f"完整URL: {url}")
        logger.debug(f"请求头: {request_headers}")
        logger.debug(f"请求数据: {request_data}")
        
        for attempt in range(retry_count + 1):
            try:
                logger.debug(f"尝试第 {attempt + 1} 次发送请求...")
                async with self.session.request(
                    method,
                    url,
                    json=request_data,
                    headers=request_headers
                ) as response:
                    # 检查响应状态
                    if response.status == 200:
                        # 记录原始响应内容
                        raw_response = await response.text()
                        logger.debug(f"原始响应内容: {raw_response[:200]}...")  # 只记录前200个字符
                        
                        try:
                            # 解析响应数据
                            response_data = json.loads(raw_response)
                            logger.debug(f"响应数据类型: {type(response_data)}")
                            logger.debug(f"响应数据结构: {list(response_data.keys()) if isinstance(response_data, dict) else '非字典类型'}")
                        
                            # 如果响应中包含服务器时间，更新时间偏移
                            if "server_time" in response_data:
                                server_time = int(response_data["server_time"])
                                self.timestamp_validator.update_time_offset(server_time)
                                logger.debug(f"更新服务器时间偏移: {server_time}")
                            
                            # 验证响应数据格式
                            if not isinstance(response_data, dict):
                                raise ValueError(f"响应数据格式错误，期望字典类型，实际类型: {type(response_data)}")
                            
                            if "status" not in response_data:
                                raise ValueError("响应数据缺少status字段")
                        
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON解析错误: {e}")
                            raise ValueError(f"响应数据JSON解析失败: {e}") from e
                        
                        # 使用后清除当前nonce
                        if self.use_nonce:
                            self.current_nonce = None
                        
                        return response_data
                    else:
                        # 处理错误响应
                        error_text = await response.text()
                        logger.error(f"请求失败: {response.status} - {error_text}")
                        logger.debug(f"失败请求详情: method={method}, url={url}")
                        logger.debug(f"失败请求头: {request_headers}")
                        logger.debug(f"失败请求数据: {request_data}")
                        logger.debug(f"失败响应头: {dict(response.headers)}")
                        
                        try:
                            error_json = json.loads(error_text)
                            logger.debug(f"错误响应JSON: {error_json}")
                        except:
                            logger.debug(f"错误响应不是JSON格式: {error_text}")
                        
                        # 检查是否是时间戳问题
                        if response.status == 400 and "无效的时间戳" in error_text:
                            # 尝试从响应中获取服务器时间
                            try:
                                error_data = json.loads(error_text)
                                if "server_time" in error_data:
                                    server_time = int(error_data["server_time"])
                                    self.timestamp_validator.update_time_offset(server_time)
                                    logger.info("已从错误响应中更新时间偏移")
                                    
                                    # 更新时间戳并重新生成签名
                                    timestamp = self.timestamp_validator.generate_timestamp()
                                    request_headers["X-Timestamp"] = timestamp
                                    request_data["timestamp"] = timestamp
                                    
                                    if self.signature_manager:
                                        if self.use_nonce and self.current_nonce:
                                            signature = self.signature_manager.generate_signature(data, f"{timestamp}:{self.current_nonce}")
                                        else:
                                            signature = self.signature_manager.generate_signature(data, timestamp)
                                        request_headers["X-Signature"] = signature
                                        request_data["signature"] = signature
                                    
                                    # 立即重试，不计入重试次数
                                    continue
                            except Exception as e:
                                logger.error(f"解析错误响应失败: {str(e)}")
                        
                        # 如果是nonce问题，尝试获取新的nonce
                        if self.use_nonce and "无效的nonce" in error_text:
                            await self.get_nonce()
                            if self.current_nonce:
                                request_headers["X-Nonce"] = self.current_nonce
                                request_data["nonce"] = self.current_nonce
                                
                                if self.signature_manager:
                                    if self.use_nonce and self.current_nonce:
                                        signature = self.signature_manager.generate_signature(data, f"{timestamp}:{self.current_nonce}")
                                    else:
                                        signature = self.signature_manager.generate_signature(data, timestamp)
                                    request_headers["X-Signature"] = signature
                                    request_data["signature"] = signature
                                
                                # 立即重试，不计入重试次数
                                continue
                        
                        # 如果还有重试次数，则重试
                        if attempt < retry_count:
                            retry_delay = 2 ** attempt  # 指数退避
                            logger.info(f"将在 {retry_delay} 秒后重试 ({attempt + 1}/{retry_count})")
                            await asyncio.sleep(retry_delay)
                        else:
                            raise Exception(f"请求失败: {response.status} - {error_text}")
            except aiohttp.ClientError as e:
                logger.error(f"请求异常: {str(e)}")
                if attempt < retry_count:
                    retry_delay = 2 ** attempt  # 指数退避
                    logger.info(f"将在 {retry_delay} 秒后重试 ({attempt + 1}/{retry_count})")
                    await asyncio.sleep(retry_delay)
                else:
                    raise Exception(f"请求异常: {str(e)}")
        
        raise Exception("超过最大重试次数")
    
    async def register_device(
        self,
        hardware_info: Dict[str, Any] = None,
        nickname: str = None
    ) -> Dict[str, Any]:
        """
        注册设备
        
        Args:
            hardware_info: 硬件信息（可选，不再使用）
            nickname: 设备名称
            
        Returns:
            Dict[str, Any]: 注册结果
        """
        try:
            # 先尝试同步时间
            await self.sync_time()
            
            # 如果使用nonce，获取nonce
            if self.use_nonce and not self.current_nonce:
                await self.get_nonce()
            
            # 构建请求数据 - 简化注册信息，不包含硬件信息
            data = {
                "client_id": self._generate_client_id(),
                "nickname": nickname or "未命名设备",
                "registration_time": self.timestamp_validator.generate_timestamp(),
                "client_version": "1.0.0"
            }
            
            # 打印请求数据，用于调试
            logger.debug(f"设备注册请求数据: {data}")
            
            # 发送请求
            response = await self._make_request("register", data)
            
            # 处理响应
            if response.get("status") == "success":
                # 更新设备ID和API密钥
                self.device_id = response["data"]["device_id"]
                self.api_key = response["data"]["api_key"]
                
                # 更新签名管理器和数据加密器
                self.signature_manager = SignatureManager(self.api_key)
                self.data_encryptor.api_key = self.api_key
                
                logger.info(f"设备注册成功，设备ID: {self.device_id}")
                return response["data"]
            else:
                error_msg = response.get("message", "未知错误")
                logger.error(f"设备注册失败: {error_msg}")
                raise Exception(f"设备注册失败: {error_msg}")
        except Exception as e:
            logger.error(f"设备注册异常: {str(e)}")
            raise
    
    async def authenticate(self) -> Dict[str, Any]:
        """
        设备认证
        
        Returns:
            Dict[str, Any]: 认证结果
        """
        try:
            # 检查API密钥
            if not self.api_key:
                raise ValueError("API密钥未设置，请先设置API密钥")
            
            # 构建请求数据
            data = {
                "device_id": self.device_id or "",  # 如果设备ID为空，传递空字符串
                "api_key": self.api_key
            }
            
            # 发送请求
            response = await self._make_request("client/authenticate", data)
            
            # 检查响应状态
            if response.get("status") == "success":
                # 如果服务器返回了设备ID，更新本地设备ID
                if "device_id" in response.get("data", {}) and not self.device_id:
                    self.device_id = response["data"]["device_id"]
                
                # 保存会话令牌
                if "session_token" in response.get("data", {}):
                    self.session_token = response["data"]["session_token"]
                
                return response
            else:
                raise ValueError(response.get("message", "认证失败"))
        except Exception as e:
            logger.error(f"认证失败: {str(e)}")
            raise
    
    def _generate_signature(self, data: Dict[str, Any], timestamp: str, nonce: str) -> str:
        """
        生成签名
        
        Args:
            data: 请求数据
            timestamp: 时间戳
            nonce: 随机数
            
        Returns:
            str: 签名
        """
        try:
            # 将数据转换为JSON字符串
            data_str = json.dumps(data, sort_keys=True)
            
            # 拼接数据、时间戳、随机数和API密钥
            message = f"{data_str}{timestamp}{nonce}{self.api_key}"
            
            # 使用SHA-256生成签名
            import hashlib
            signature = hashlib.sha256(message.encode()).hexdigest()
            
            return signature
        except Exception as e:
            logger.error(f"生成签名异常: {str(e)}")
            raise
    
    async def get_datasets(self) -> List[Dict[str, Any]]:
        """
        获取数据集列表
        
        Returns:
            List[Dict[str, Any]]: 数据集列表
        """
        try:
            # 检查设备ID和会话令牌
            if not self.device_id or not self.session_token:
                raise ValueError("设备ID或会话令牌未设置，请先认证")
            
            # 构建请求数据
            data = {
                "device_id": self.device_id,
                "session_token": self.session_token
            }
            
            # 发送请求
            response = await self._make_request("client/datasets", data, method="GET")
            
            # 检查响应状态
            if response.get("status") == "success":
                logger.info(f"获取数据集列表成功，共 {len(response.get('data', []))} 个数据集")
                return response.get("data", [])
            else:
                logger.error(f"获取数据集列表失败: {response.get('message')}")
                raise Exception(f"获取数据集列表失败: {response.get('message')}")
        except Exception as e:
            logger.error(f"获取数据集列表异常: {str(e)}")
            raise
    
    async def download_dataset(self, dataset_version: str) -> Dict[str, Any]:
        """
        下载数据集
        
        Args:
            dataset_version: 数据集版本
            
        Returns:
            Dict[str, Any]: 下载结果
        """
        try:
            # 检查设备ID和会话令牌
            if not self.device_id or not self.session_token:
                raise ValueError("设备ID或会话令牌未设置，请先认证")
            
            # 构建请求数据
            data = {
                "device_id": self.device_id,
                "session_token": self.session_token,
                "dataset_version": dataset_version
            }
            
            # 发送请求
            response = await self._make_request("client/datasets/download", data)
            
            # 检查响应状态
            if response.get("status") == "success":
                logger.info(f"获取数据集下载链接成功: {dataset_version}")
                return response.get("data", {})
            else:
                logger.error(f"获取数据集下载链接失败: {response.get('message')}")
                raise Exception(f"获取数据集下载链接失败: {response.get('message')}")
        except Exception as e:
            logger.error(f"获取数据集下载链接异常: {str(e)}")
            raise
    
    async def download_dataset_file(self, download_url: str) -> bytes:
        """
        下载数据集文件
        
        Args:
            download_url: 下载URL
            
        Returns:
            bytes: 数据集文件内容
        """
        try:
            await self._ensure_session()
            
            async with self.session.get(download_url) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    error_text = await response.text()
                    logger.error(f"下载数据集文件失败: {response.status} - {error_text}")
                    raise Exception(f"下载数据集文件失败: {response.status} - {error_text}")
        except Exception as e:
            logger.error(f"下载数据集文件异常: {str(e)}")
            raise
    
    async def submit_result(self, result: Dict[str, Any], hardware_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        提交测试结果
        
        Args:
            result: 测试结果
            hardware_info: 测试设备的硬件信息
            
        Returns:
            Dict[str, Any]: 提交结果
        """
        try:
            # 检查设备ID和会话令牌
            if not self.device_id or not self.session_token:
                raise ValueError("设备ID或会话令牌未设置，请先认证")
            
            # 构建请求数据
            data = {
                "device_id": self.device_id,
                "session_token": self.session_token,
                "result": result
            }
            
            # 如果提供了硬件信息，添加到请求中
            if hardware_info:
                data["hardware_info"] = hardware_info
                data["hardware_fingerprint"] = self._generate_hardware_fingerprint(hardware_info)
                logger.debug(f"提交结果包含硬件信息: {len(str(hardware_info))} 字节")
            
            # 发送请求
            response = await self._make_request("client/results", data)
            
            # 检查响应状态
            if response.get("status") == "success":
                logger.info(f"提交测试结果成功，结果ID: {response.get('data', {}).get('result_id')}")
                return response.get("data", {})
            else:
                logger.error(f"提交测试结果失败: {response.get('message')}")
                raise Exception(f"提交测试结果失败: {response.get('message')}")
        except Exception as e:
            logger.error(f"提交测试结果异常: {str(e)}")
            raise
    
    def _generate_hardware_fingerprint(self, hardware_info: Dict[str, Any]) -> str:
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
            import hashlib
            fingerprint = hashlib.sha256(hardware_str.encode()).hexdigest()
            
            return fingerprint
        except Exception as e:
            logger.error(f"生成硬件指纹异常: {str(e)}")
            raise

    def _generate_client_id(self) -> str:
        """
        生成客户端ID
        
        Returns:
            str: 客户端ID
        """
        try:
            # 生成一个随机字符串作为客户端ID
            import random
            import string
            client_id = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(16))
            return client_id
        except Exception as e:
            logger.error(f"生成客户端ID异常: {str(e)}")
            raise
    
    async def get_offline_package(self, dataset_id: Union[int, str] = 1) -> Dict[str, Any]:
        """
        获取离线测试数据包
        
        Args:
            dataset_id: 数据集ID（整数），默认为1
            
        Returns:
            Dict[str, Any]: 离线包数据
        """
        try:
            # 检查API密钥
            if not self.api_key:
                raise ValueError("API密钥未设置，请先设置API密钥")
            
            # 确保dataset_id是整数
            dataset_id = int(dataset_id)
            logger.debug(f"准备获取离线包: dataset_id={dataset_id}, api_key={self.api_key[:4]}...")
            
            # 强制重置会话，确保使用全新的HTTP连接
            if self.session and not self.session.closed:
                try:
                    await self.session.close()
                    logger.debug("关闭旧的HTTP会话")
                except Exception as e:
                    logger.warning(f"关闭旧会话失败: {e}")
            
            self.session = None
            
            # 确保会话已创建
            await self._ensure_session()
            
            # 构建请求头
            headers = {
                "X-API-Key": self.api_key
            }
            logger.debug(f"请求头: {headers}")
            
            # 构建请求数据
            data = {}  # 空数据，因为所有信息都在URL和请求头中
            
            # 记录完整请求URL - 移除client前缀，因为基础URL已经包含了
            endpoint = f"datasets/offline-package/{dataset_id}"
            full_url = f"{self.server_url}/{endpoint.lstrip('/')}"
            logger.debug(f"请求URL: {full_url}")
            
            # 发送请求
            logger.debug("开始发送请求...")
            try:
                async with self.session.request(
                    "POST",
                    full_url,
                    json=data,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        # 读取原始响应内容
                        raw_response = await response.text()
                        logger.debug(f"原始响应内容: {raw_response[:200]}...")  # 只记录前200个字符
                        
                        try:
                            # 解析响应数据
                            package_data = json.loads(raw_response)
                            logger.debug(f"响应数据类型: {type(package_data)}")
                            logger.debug(f"响应数据结构: {list(package_data.keys()) if isinstance(package_data, dict) else '非字典类型'}")
                            
                            # 验证离线包数据
                            if not isinstance(package_data, dict):
                                raise ValueError(f"响应数据格式错误，期望字典类型，实际类型: {type(package_data)}")
                            
                            # 验证包格式
                            package_format = package_data.get("metadata", {}).get("package_format")
                            if package_format not in ["3.0", "4.0"]:
                                logger.error(f"不支持的离线包格式: {package_format}")
                                raise ValueError(f"不支持的离线包格式，需要3.0或4.0版本")
                            logger.debug(f"检测到离线包格式版本: {package_format}")
                            
                            # 检查必要的字段
                            required_fields = ["metadata", "encrypted_private_key", "dataset"]
                            missing_fields = [field for field in required_fields if field not in package_data]
                            if missing_fields:
                                raise ValueError(f"离线包数据缺少必要字段: {', '.join(missing_fields)}")
                            
                            logger.info(f"获取离线包成功: 数据集ID={dataset_id}, 包格式版本={package_format}")
                            return package_data
                        except json.JSONDecodeError as e:
                            logger.error(f"解析响应JSON失败: {str(e)}")
                            logger.debug(f"无法解析的响应内容: {raw_response[:200]}...")
                            raise ValueError(f"解析响应JSON失败: {str(e)}")
                    else:
                        # 处理错误响应
                        error_text = await response.text()
                        logger.error(f"请求失败: {response.status} - {error_text}")
                        raise Exception(f"获取离线包失败: {error_text}")
            finally:
                # 确保每次请求完成后关闭会话
                if self.session and not self.session.closed:
                    try:
                        await self.session.close()
                        logger.debug("请求完成，关闭HTTP会话")
                        self.session = None
                    except Exception as e:
                        logger.warning(f"关闭会话失败: {e}")
        except Exception as e:
            logger.error(f"获取离线包异常: {str(e)}")
            raise
    
    async def save_offline_package(self, offline_package: Dict[str, Any], save_path: str) -> str:
        """
        保存离线包到文件
        
        Args:
            offline_package: 离线包数据
            save_path: 保存路径
            
        Returns:
            str: 文件保存路径
        """
        try:
            import os
            import json
            from pathlib import Path
            import time
            
            # 确保目录存在
            save_dir = Path(save_path)
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # 获取数据集ID
            dataset_id = offline_package.get("metadata", {}).get("dataset_id", "unknown")
            
            # 生成文件名
            file_path = save_dir / f"dsm_offline_package_{dataset_id}_{int(time.time() * 1000)}.json"
            
            # 保存为文件
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(offline_package, f, indent=2)
            
            logger.info(f"离线包已保存到: {file_path}")
            return str(file_path)
        except Exception as e:
            logger.error(f"保存离线包异常: {str(e)}")
            raise
    
    async def decrypt_offline_package(self, package_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        解密离线包
        
        Args:
            package_data: 离线包数据（字典或JSON字符串）
            
        Returns:
            Dict[str, Any]: 解密后的数据集
        """
        try:
            import base64
            import hashlib
            import json
            
            # 如果API密钥未设置，抛出异常
            if not self.api_key:
                logger.error("API密钥未设置，无法解密离线包")
                raise ValueError("API密钥未设置，无法解密离线包")
            
            logger.debug(f"开始解密离线包，使用API密钥: {self.api_key[:4]}...")
            logger.debug(f"离线包数据结构: {list(package_data.keys()) if isinstance(package_data, dict) else '非字典类型'}")
            
            # 验证包格式
            package_format = package_data.get("metadata", {}).get("package_format")
            if package_format not in ["3.0", "4.0"]:
                logger.error(f"不支持的离线包格式: {package_format}")
                raise ValueError(f"不支持的离线包格式，需要3.0或4.0版本")
            logger.debug(f"检测到离线包格式版本: {package_format}")
            
            # 提取加密私钥和数据集
            encrypted_private_key = package_data["encrypted_private_key"]
            encrypted_dataset = package_data["dataset"]
            
            logger.debug("开始解密私钥...")
            # 1. 使用API密钥解密私钥
            if not isinstance(encrypted_private_key, dict) or not all(k in encrypted_private_key for k in ["salt", "iv", "data"]):
                logger.error("加密私钥格式错误")
                raise ValueError("加密私钥格式错误，需要包含salt、iv和data字段")
            
            logger.debug(f"加密私钥结构: {list(encrypted_private_key.keys())}")
            logger.debug(f"salt长度: {len(encrypted_private_key['salt'])}")
            logger.debug(f"iv长度: {len(encrypted_private_key['iv'])}")
            logger.debug(f"加密数据长度: {len(encrypted_private_key['data'])}")
            
            private_key_pem = self._decrypt_with_derived_key(
                password=self.api_key,
                salt=encrypted_private_key["salt"],
                iv=encrypted_private_key["iv"],
                encrypted_data=encrypted_private_key["data"]
            )
            if not private_key_pem:
                logger.error("私钥解密失败，API密钥可能不正确")
                raise ValueError("私钥解密失败，API密钥可能不正确")
            logger.debug("私钥解密成功")
            
            logger.debug("开始解密会话密钥...")
            # 2. 使用私钥解密会话密钥
            encrypted_session_key = base64.b64decode(encrypted_dataset["encrypted_session_key"])
            session_key = self._decrypt_with_private_key(encrypted_session_key, private_key_pem)
            if not session_key:
                logger.error("会话密钥解密失败")
                raise ValueError("会话密钥解密失败")
            logger.debug("会话密钥解密成功")
            
            logger.debug("开始解密数据集...")
            # 3. 使用会话密钥解密数据集
            encrypted_data = encrypted_dataset["encrypted_data"]
            dataset = self._decrypt_with_aes(encrypted_data, session_key)
            if not dataset:
                logger.error("数据集解密失败")
                raise ValueError("数据集解密失败")
            logger.debug(f"数据集解密成功，数据结构: {list(dataset.keys()) if isinstance(dataset, dict) else '非字典类型'}")
            
            # 4. 验证用户签名
            timestamp = encrypted_dataset["timestamp"]
            user_signature = encrypted_dataset["user_signature"]
            
            calculated_signature = self._generate_offline_signature(dataset, timestamp, self.api_key)
            if calculated_signature != user_signature:
                logger.warning("用户签名验证失败，数据集可能被篡改")
            else:
                logger.debug("用户签名验证成功")
            
            logger.info("离线包解密成功")
            return dataset
        except Exception as e:
            logger.error(f"解密离线包异常: {str(e)}")
            raise
    
    def _decrypt_with_derived_key(self, password: str, salt: str, iv: str, encrypted_data: str) -> str:
        """
        使用PBKDF2派生密钥进行解密
        
        Args:
            password: 用于派生密钥的密码
            salt: Base64编码的盐值
            iv: Base64编码的初始化向量
            encrypted_data: Base64编码的加密数据
            
        Returns:
            str: 解密后的数据
        """
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            import base64
            
            # 记录输入参数信息
            logger.debug("=== 输入参数检查 ===")
            logger.debug(f"密码长度: {len(password)}")
            logger.debug(f"密码前8个字符: {password[:8]}")
            
            # Base64解码并记录参数
            salt_bytes = base64.b64decode(salt)
            iv_bytes = base64.b64decode(iv)
            encrypted_bytes = base64.b64decode(encrypted_data)
            
            logger.debug("=== 解码后参数信息 ===")
            logger.debug(f"盐值(hex): {salt_bytes.hex()}, 长度: {len(salt_bytes)}字节")
            logger.debug(f"IV(hex): {iv_bytes.hex()}, 长度: {len(iv_bytes)}字节")
            logger.debug(f"加密数据长度: {len(encrypted_bytes)}字节")
            logger.debug(f"加密数据前32字节(hex): {encrypted_bytes[:32].hex()}")
            
            # 派生密钥
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt_bytes,
                iterations=100000,
                backend=default_backend()
            )
            key = kdf.derive(password.encode())
            logger.debug(f"派生密钥(hex): {key.hex()}, 长度: {len(key)}字节")
            
            # 解密
            cipher = Cipher(
                algorithms.AES(key),
                modes.CBC(iv_bytes),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(encrypted_bytes) + decryptor.finalize()
            
            logger.debug(f"填充数据长度: {len(padded_data)}字节")
            logger.debug(f"最后一个块: {padded_data[-16:].hex()}")
            
            # 移除PKCS7填充
            padding_length = padded_data[-1]
            unpadded_data = padded_data[:-padding_length]
            
            logger.debug(f"去除填充后数据长度: {len(unpadded_data)}字节")
            
            # 转换为字符串
            try:
                decrypted_str = unpadded_data.decode('utf-8')
                logger.debug("=== 解密数据检查 ===")
                logger.debug(f"解密数据前100个字符: {decrypted_str[:100]}")
                logger.debug(f"解密数据后100个字符: {decrypted_str[-100:]}")
                
                # 检查并修正PEM格式
                if "-----BEGIN" in decrypted_str and "-----END" in decrypted_str:
                    # 提取PEM内容
                    start_marker = "-----BEGIN"
                    end_marker = "-----END"
                    start_idx = decrypted_str.index(start_marker)
                    end_idx = decrypted_str.rindex(end_marker) + len(end_marker)
                    
                    # 提取完整的PEM块
                    pem_block = decrypted_str[start_idx:end_idx]
                    
                    # 识别完整的头部和尾部标记
                    pem_lines = pem_block.strip().split('\n')
                    if len(pem_lines) >= 2:  # 至少需要头部和尾部
                        # 获取密钥类型
                        header = pem_lines[0]
                        key_type = ""
                        if "PRIVATE KEY" in header:
                            key_type = "PRIVATE KEY"
                        elif "PUBLIC KEY" in header:
                            key_type = "PUBLIC KEY"
                        elif "CERTIFICATE" in header:
                            key_type = "CERTIFICATE"
                        elif "RSA PRIVATE KEY" in header:
                            key_type = "RSA PRIVATE KEY"
                        else:
                            # 尝试提取BEGIN后面的类型
                            try:
                                key_type = header.split("BEGIN ")[1].split("-----")[0].strip()
                                logger.debug(f"提取到的密钥类型: {key_type}")
                            except:
                                key_type = "PRIVATE KEY"  # 默认私钥类型
                                logger.debug(f"无法提取密钥类型，使用默认类型: {key_type}")
                        
                        # 检查并修正头部
                        correct_header = f"-----BEGIN {key_type}-----"
                        if pem_lines[0] != correct_header:
                            logger.debug(f"修正头部: {pem_lines[0]} -> {correct_header}")
                            pem_lines[0] = correct_header
                        
                        # 检查并修正尾部
                        correct_footer = f"-----END {key_type}-----"
                        if pem_lines[-1] != correct_footer:
                            logger.debug(f"修正尾部: {pem_lines[-1]} -> {correct_footer}")
                            pem_lines[-1] = correct_footer
                        
                        # 重新组装PEM，确保每行都有正确的换行
                        corrected_pem = '\n'.join(line.strip() for line in pem_lines)
                        logger.debug("=== PEM格式修正 ===")
                        logger.debug(f"PEM行数: {len(pem_lines)}")
                        logger.debug(f"修正后PEM头部: {pem_lines[0]}")
                        logger.debug(f"修正后PEM尾部: {pem_lines[-1]}")
                        
                        # 验证PEM格式
                        if not (corrected_pem.startswith("-----BEGIN") and corrected_pem.endswith("-----")):
                            logger.error("PEM格式无效：缺少必要的标记")
                            logger.debug(f"完整PEM内容: {corrected_pem}")
                            return None
                        
                        return corrected_pem
                    else:
                        logger.error("PEM格式无效：缺少必要的行")
                        logger.debug(f"完整解密数据: {decrypted_str}")
                        return None
                else:
                    logger.error("解密数据不符合PEM格式：缺少BEGIN/END标记")
                    logger.debug(f"完整解密数据: {decrypted_str}")
                    return None
                
            except UnicodeDecodeError as ude:
                logger.error(f"UTF-8解码失败: {str(ude)}")
                logger.debug(f"解密数据(hex): {unpadded_data.hex()}")
                raise
                
        except Exception as e:
            logger.error(f"派生密钥解密失败: {str(e)}")
            return None
    
    def _decrypt_with_private_key(self, encrypted_data: bytes, private_key_pem: str) -> bytes:
        """
        使用RSA私钥解密数据
        
        Args:
            encrypted_data: 加密数据
            private_key_pem: PEM格式的RSA私钥
            
        Returns:
            bytes: 解密后的数据
        """
        try:
            from cryptography.hazmat.primitives.asymmetric import padding, rsa
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.serialization import load_pem_private_key
            from cryptography.hazmat.backends import default_backend
            import re
            
            # 详细记录私钥格式
            logger.debug("=== 私钥格式详细检查 ===")
            logger.debug(f"私钥总长度: {len(private_key_pem)} 字符")
            
            # 检查PEM格式
            pem_lines = private_key_pem.strip().split('\n')
            logger.debug(f"PEM行数: {len(pem_lines)}")
            logger.debug(f"PEM头部: {pem_lines[0]}")
            logger.debug(f"PEM尾部: {pem_lines[-1]}")
            
            # 自动修复PEM格式
            corrected_pem = private_key_pem
            needs_correction = False
            
            # 检查头部和尾部
            if "BEGIN" in pem_lines[0]:
                # 提取密钥类型
                key_type = ""
                match = re.search(r"-----BEGIN ([^-]+)-----", pem_lines[0])
                if match:
                    key_type = match.group(1)
                    logger.debug(f"从头部提取的密钥类型: {key_type}")
                else:
                    key_type = "PRIVATE KEY"  # 默认类型
                    logger.debug(f"无法从头部提取密钥类型，使用默认类型: {key_type}")
                    # 修正头部
                    pem_lines[0] = f"-----BEGIN {key_type}-----"
                    needs_correction = True
                
                # 检查尾部
                if pem_lines[-1] != f"-----END {key_type}-----":
                    logger.debug(f"尾部标记不匹配，原标记: {pem_lines[-1]}")
                    pem_lines[-1] = f"-----END {key_type}-----"
                    logger.debug(f"修正后的尾部标记: {pem_lines[-1]}")
                    needs_correction = True
            
            # 如果需要修正，重新组装PEM
            if needs_correction:
                corrected_pem = '\n'.join(line.strip() for line in pem_lines)
                logger.debug("已修正PEM格式")
            
            # 记录加密数据信息
            logger.debug("=== 加密数据详细信息 ===")
            logger.debug(f"加密数据长度: {len(encrypted_data)} 字节")
            logger.debug(f"加密数据前32字节(hex): {encrypted_data[:32].hex()}")
            logger.debug(f"加密数据后32字节(hex): {encrypted_data[-32:].hex()}")
            
            # 尝试导入私钥
            private_key = None
            errors = []
            
            # 尝试方法1: 使用修正后的PEM
            try:
                logger.debug("尝试导入修正后的私钥...")
                private_key = load_pem_private_key(
                    corrected_pem.encode('utf-8'),
                    password=None,
                    backend=default_backend()
                )
                logger.debug("使用修正后的PEM成功导入私钥")
            except Exception as e:
                errors.append(f"修正后PEM导入失败: {str(e)}")
                # 如果修正后的PEM与原始PEM不同，尝试使用原始PEM
                if corrected_pem != private_key_pem:
                    try:
                        logger.debug("尝试使用原始PEM格式...")
                        private_key = load_pem_private_key(
                            private_key_pem.encode('utf-8'),
                            password=None,
                            backend=default_backend()
                        )
                        logger.debug("使用原始PEM成功导入私钥")
                    except Exception as e2:
                        errors.append(f"原始PEM导入失败: {str(e2)}")
            
            # 如果仍然失败，尝试手动修复常见问题
            if private_key is None:
                # 尝试方法2: 如果END后面没有类型，从BEGIN提取类型并添加
                try:
                    logger.debug("尝试手动修复PEM格式...")
                    header = pem_lines[0]
                    if "BEGIN" in header:
                        match = re.search(r"BEGIN ([^-]+)", header)
                        if match:
                            key_type = match.group(1).strip()
                            footer = pem_lines[-1]
                            if "END" in footer and key_type not in footer:
                                new_footer = f"-----END {key_type}-----"
                                pem_lines[-1] = new_footer
                                manual_pem = '\n'.join(line.strip() for line in pem_lines)
                                logger.debug(f"手动修复后的PEM尾部: {new_footer}")
                                
                                try:
                                    private_key = load_pem_private_key(
                                        manual_pem.encode('utf-8'),
                                        password=None,
                                        backend=default_backend()
                                    )
                                    logger.debug("使用手动修复的PEM成功导入私钥")
                                except Exception as e3:
                                    errors.append(f"手动修复的PEM导入失败: {str(e3)}")
                except Exception as e4:
                    errors.append(f"PEM手动修复过程出错: {str(e4)}")
            
            # 如果所有方法都失败
            if private_key is None:
                logger.error(f"无法导入私钥，尝试了多种方法均失败: {', '.join(errors)}")
                logger.error(f"完整PEM内容:\n{private_key_pem}")
                return None
            
            # 验证私钥类型
            if not isinstance(private_key, rsa.RSAPrivateKey):
                logger.error(f"导入的私钥类型错误: {type(private_key)}")
                raise ValueError("导入的不是RSA私钥")
            
            logger.debug(f"私钥导入成功:")
            logger.debug(f"- 密钥大小: {private_key.key_size} 位")
            max_data_len = private_key.key_size // 8 - 11  # PKCS1v15的最大数据长度
            logger.debug(f"- 最大加密数据长度: {max_data_len} 字节")
            
            if len(encrypted_data) > private_key.key_size // 8:
                logger.error(f"加密数据长度({len(encrypted_data)})超过密钥大小({private_key.key_size // 8})")
                return None
            
            # 解密数据 - 使用OAEP填充
            logger.debug("开始解密数据，尝试多种填充方式...")
            try:
                # 使用PKCS1v15填充
                logger.debug("使用PKCS1v15填充")
                decrypted_data = private_key.decrypt(
                    encrypted_data,
                    padding.PKCS1v15()
                )
                logger.debug("使用PKCS1v15填充解密成功")
            except Exception as e:
                logger.error(f"使用PKCS1v15填充解密失败: {str(e)}")
                # 回退尝试OAEP(SHA-256)
                try:
                    logger.debug("尝试使用OAEP(SHA-256)填充")
                    decrypted_data = private_key.decrypt(
                        encrypted_data,
                        padding.OAEP(
                            mgf=padding.MGF1(algorithm=hashes.SHA256()),
                            algorithm=hashes.SHA256(),
                            label=None
                        )
                    )
                    logger.debug("使用OAEP(SHA-256)填充解密成功")
                except Exception as e2:
                    logger.error(f"所有解密方法均失败: PKCS1v15: {str(e)}, OAEP: {str(e2)}")
                    return None
            
            # 解密成功后记录数据信息
            logger.debug("解密成功:")
            logger.debug(f"- 解密后数据长度: {len(decrypted_data)} 字节")
            logger.debug(f"- 解密后数据前16字节(hex): {decrypted_data[:16].hex()}")
            
            return decrypted_data
                
        except Exception as e:
            logger.error(f"RSA解密失败: {str(e)}")
            return None
    
    def _decrypt_with_aes(self, encrypted_data: Dict[str, str], key: bytes) -> Dict[str, Any]:
        """
        使用AES解密数据
        
        Args:
            encrypted_data: 加密数据对象，包含iv和data字段
            key: AES密钥（字节格式）
            
        Returns:
            Dict[str, Any]: 解密后的JSON对象
        """
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import unpad
            import base64
            import json
            
            # 记录密钥信息
            logger.debug(f"=== AES解密信息 ===")
            logger.debug(f"原始密钥长度: {len(key)} 字节")
            logger.debug(f"原始密钥(hex): {key.hex()}")
            
            # AES密钥必须是16, 24或32字节
            if len(key) != 16 and len(key) != 24 and len(key) != 32:
                logger.warning(f"AES密钥长度({len(key)})不是标准长度(16/24/32)，进行调整")
                
                # 对于长度为54字节的密钥，取前32字节作为AES-256密钥
                if len(key) > 32:
                    key = key[:32]
                    logger.debug(f"截取前32字节作为AES-256密钥")
                elif len(key) < 16:
                    key = key.ljust(16, b'\0')
                    logger.debug(f"填充到16字节作为AES-128密钥")
            
            logger.debug(f"调整后密钥长度: {len(key)} 字节")
            logger.debug(f"调整后密钥(hex): {key.hex()}")
            
            # 从Base64解码IV和加密数据
            iv = base64.b64decode(encrypted_data["iv"])
            ciphertext = base64.b64decode(encrypted_data["data"])
            
            logger.debug(f"IV长度: {len(iv)} 字节")
            logger.debug(f"加密数据长度: {len(ciphertext)} 字节")
            
            # 直接使用字节格式的密钥
            cipher = AES.new(key, AES.MODE_CBC, iv)
            
            # 解密数据
            decrypted_padded = cipher.decrypt(ciphertext)
            logger.debug(f"解密后的填充数据长度: {len(decrypted_padded)} 字节")
            
            # 去除填充
            decrypted = unpad(decrypted_padded, AES.block_size)
            logger.debug(f"解除填充后数据长度: {len(decrypted)} 字节")
            
            # 解析JSON
            json_data = json.loads(decrypted.decode('utf-8'))
            logger.debug(f"解析JSON成功，顶级键: {list(json_data.keys())}")
            
            return json_data
        except Exception as e:
            logger.error(f"AES解密失败: {str(e)}")
            if "key" in locals():
                logger.error(f"AES密钥长度: {len(key)} 字节")
            if "iv" in locals():
                logger.error(f"AES IV长度: {len(iv)} 字节")
            if "ciphertext" in locals():
                logger.error(f"AES加密数据长度: {len(ciphertext)} 字节")
            return None
    
    def _generate_offline_signature(self, data: Dict[str, Any], timestamp: str, secret_key: str) -> str:
        """
        生成离线包签名
        
        Args:
            data: 要签名的数据
            timestamp: 时间戳
            secret_key: 密钥
            
        Returns:
            str: 签名
        """
        import hashlib
        import json
        
        # 将数据转换为JSON字符串，并按键排序
        data_str = json.dumps(data, sort_keys=True)
        
        # 拼接数据、时间戳和密钥
        message = f"{data_str}{timestamp}{secret_key}"
        
        # 使用SHA-256生成签名
        return hashlib.sha256(message.encode()).hexdigest() 