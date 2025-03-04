"""
API客户端模块，负责与模型API通信
"""
import time
import json
import asyncio
import aiohttp
from typing import Dict, Any, Optional, AsyncGenerator
from src.utils.logger import setup_logger
from src.utils.token_counter import token_counter  # 导入token计数器
from src.utils.config import config

logger = setup_logger("api_client")

class StreamStats:
    """流式输出统计"""
    def __init__(self, model_name: str = None):
        self.total_chars = 0
        self.total_tokens = 0
        self.total_time = 0.0
        self.last_update_time = time.time()
        self.current_char_speed = 0.0
        self.current_token_speed = 0.0
        self.char_speeds = []
        self.token_speeds = []
        self.model_name = model_name
    
    def update(self, new_text: str):
        """更新统计信息"""
        current_time = time.time()
        time_diff = current_time - self.last_update_time
        
        if time_diff > 0:
            # 计算新增字符数
            new_chars = len(new_text)
            # 使用tiktoken计算token数
            new_tokens = token_counter.count_tokens(new_text, self.model_name)
            
            # 计算字符速度
            self.current_char_speed = new_chars / time_diff
            self.char_speeds.append(self.current_char_speed)
            
            # 计算token速度
            self.current_token_speed = new_tokens / time_diff
            self.token_speeds.append(self.current_token_speed)
            
            # 更新总计数
            self.total_chars += new_chars
            self.total_tokens += new_tokens
            self.total_time += time_diff
        
        self.last_update_time = current_time
    
    @property
    def avg_char_speed(self) -> float:
        """平均字符生成速度（字符/秒）"""
        if self.total_time > 0:
            return self.total_chars / self.total_time
        return 0.0
    
    @property
    def avg_token_speed(self) -> float:
        """平均token生成速度（token/秒）"""
        if self.total_time > 0:
            return self.total_tokens / self.total_time
        return 0.0

class APIResponse:
    """API响应数据类"""
    def __init__(
        self,
        success: bool,
        response_text: str = "",
        error_msg: str = "",
        tokens_generated: int = 0,
        duration: float = 0.0,
        start_time: float = 0.0,
        end_time: float = 0.0,
        model_name: str = "",
        stream_stats: Optional[StreamStats] = None
    ):
        self.success = success
        self.response_text = response_text
        self.error_msg = error_msg
        self.tokens_generated = tokens_generated
        self.duration = duration
        self.start_time = start_time
        self.end_time = end_time
        self.model_name = model_name
        self.stream_stats = stream_stats
    
    @property
    def generation_speed(self) -> float:
        """计算生成速度（字符/秒）"""
        if self.stream_stats:
            # 使用流式统计的平均速度
            return self.stream_stats.avg_char_speed
        elif self.duration > 0 and self.response_text:
            # 如果没有流式统计，使用总字符数除以总时间
            return len(self.response_text) / self.duration
        return 0.0
    
    @property
    def total_chars(self) -> int:
        """获取总字符数"""
        return len(self.response_text) if self.response_text else 0
    
    @property
    def total_tokens(self) -> int:
        """获取总token数"""
        return self.tokens_generated

class APIClient:
    """API客户端类"""
    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        timeout: int = 10,  # 添加超时参数
        retry_count: int = 1  # 添加重试次数参数
    ):
        # 确保 API URL 格式正确
        self.api_url = api_url.rstrip("/")
        if not self.api_url.endswith("/v1"):
            self.api_url += "/v1"
        self.api_key = api_key
        self.model = model
        
        # 使用传入的超时和重试设置
        self.connect_timeout = timeout
        self.max_retries = retry_count
        
        # 其他参数
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        
        # 模型参数
        self.model_params = {
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p
        }
        
        # 创建异步HTTP会话
        self.session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {api_key}"}
        )
        logger.info(f"初始化 API 客户端: URL={api_url}, model={model}, connect_timeout={self.connect_timeout}, max_retries={self.max_retries}")
    
    async def close(self):
        """关闭客户端会话"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("API客户端会话已关闭")
    
    def _prepare_request(self, prompt: str) -> dict:
        """准备请求数据"""
        # 根据配置决定是否使用流式输出
        use_stream = config.get('openai_api.stream_mode', True)
        
        return {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": use_stream,  # 根据配置决定是否启用流式输出
            **self.model_params  # 只包含支持的参数
        }
    
    async def _process_stream(
        self,
        response: aiohttp.ClientResponse
    ) -> AsyncGenerator[str, None]:
        """处理流式响应"""
        try:
            async for line in response.content:
                line = line.decode('utf-8').strip()
                if line.startswith('data: '):
                    try:
                        data = json.loads(line[6:])
                        if data.get('choices'):
                            # 支持两种格式：delta 和 text
                            content = (
                                data['choices'][0].get('delta', {}).get('content', '') or
                                data['choices'][0].get('text', '')
                            )
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"流式输出处理异常: {e}")
            raise  # 向上传递异常，让generate方法处理
    
    async def generate(self, prompt: str) -> APIResponse:
        """生成响应"""
        start_time = time.time()
        stream_stats = StreamStats(self.model)  # 传入模型名称
        full_response = []
        
        # 根据配置决定是否使用流式输出
        use_stream = config.get('openai_api.stream_mode', True)
        
        for attempt in range(self.max_retries):
            try:
                async with self.session.post(
                    f"{self.api_url}/chat/completions",  # 修改 URL 路径
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": use_stream,  # 根据配置决定是否启用流式输出
                        **self.model_params  # 使用model_params代替直接指定参数
                    },
                    timeout=aiohttp.ClientTimeout(
                        connect=self.connect_timeout,
                        sock_connect=self.connect_timeout,
                        sock_read=None,  # 不限制读取超时
                        total=None  # 不限制总体超时
                    )
                ) as response:
                    if response.status == 200:
                        try:
                            # 根据配置决定处理方式
                            if use_stream:
                                # 流式输出处理
                                async for chunk in self._process_stream(response):
                                    full_response.append(chunk)
                                    stream_stats.update(chunk)
                                
                                end_time = time.time()
                                return APIResponse(
                                    success=True,
                                    response_text="".join(full_response),
                                    tokens_generated=stream_stats.total_tokens,
                                    duration=end_time - start_time,
                                    start_time=start_time,
                                    end_time=end_time,
                                    model_name=self.model,
                                    stream_stats=stream_stats
                                )
                            else:
                                # 非流式输出处理
                                data = await response.json()
                                response_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                                
                                # 估算token数量
                                tokens_generated = token_counter.count_tokens(response_text, self.model)
                                
                                # 更新流统计（虽然不是流式但仍需要计算速度）
                                stream_stats.update(response_text)
                                
                                end_time = time.time()
                                return APIResponse(
                                    success=True,
                                    response_text=response_text,
                                    tokens_generated=tokens_generated,
                                    duration=end_time - start_time,
                                    start_time=start_time,
                                    end_time=end_time,
                                    model_name=self.model,
                                    stream_stats=stream_stats
                                )
                        except Exception as e:
                            logger.error(f"流式输出中断: {e}")
                            # 返回已生成的部分内容，但标记为失败
                            end_time = time.time()
                            response_text = ''.join(full_response)
                            return APIResponse(
                                success=False,
                                response_text=response_text,
                                error_msg=f"流式输出中断: {str(e)}",
                                tokens_generated=stream_stats.total_tokens,
                                duration=end_time - start_time,
                                start_time=start_time,
                                end_time=end_time,
                                model_name=self.model,
                                stream_stats=stream_stats
                            )
                    else:
                        error_text = await response.text()
                        logger.error(f"API请求失败 (尝试 {attempt + 1}/{self.max_retries}): {response.status} - {error_text}")
                        if attempt == self.max_retries - 1:
                            return APIResponse(
                                success=False,
                                error_msg=f"HTTP {response.status}: {error_text}",
                                duration=time.time() - start_time,
                                start_time=start_time,
                                end_time=time.time()
                            )
            
            except asyncio.TimeoutError as e:
                error_msg = "连接超时" if "connect" in str(e) else "请求超时"
                logger.error(f"API{error_msg} (尝试 {attempt + 1}/{self.max_retries})")
                if attempt == self.max_retries - 1:
                    return APIResponse(
                        success=False,
                        error_msg=error_msg,
                        duration=time.time() - start_time,
                        start_time=start_time,
                        end_time=time.time()
                    )
            
            except Exception as e:
                logger.error(f"API请求异常 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    return APIResponse(
                        success=False,
                        error_msg=str(e),
                        duration=time.time() - start_time,
                        start_time=start_time,
                        end_time=time.time()
                    )
            
            # 重试前等待
            if attempt < self.max_retries - 1:
                await asyncio.sleep(1 * (attempt + 1))
        
        return APIResponse(
            success=False,
            error_msg="未知错误",
            duration=time.time() - start_time,
            start_time=start_time,
            end_time=time.time()
        )
