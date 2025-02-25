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

class APIClient:
    """API客户端类"""
    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str,
        timeout: int = 30,
        max_retries: int = 3,
        **model_params
    ):
        self.api_url = api_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.model_params = model_params
        self._session = None
    
    async def _ensure_session(self):
        """确保aiohttp会话已创建"""
        if self._session is None:
            self._session = aiohttp.ClientSession()
    
    async def close(self):
        """关闭会话"""
        if self._session:
            await self._session.close()
            self._session = None
    
    def _prepare_request(self, prompt: str) -> dict:
        """准备请求数据"""
        return {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": True,  # 启用流式输出
            **self.model_params
        }
    
    async def _process_stream(
        self,
        response: aiohttp.ClientResponse
    ) -> AsyncGenerator[str, None]:
        """处理流式响应"""
        async for line in response.content:
            line = line.decode('utf-8').strip()
            if line.startswith('data: '):
                try:
                    data = json.loads(line[6:])
                    if data.get('choices'):
                        content = data['choices'][0].get('delta', {}).get('content', '')
                        if content:
                            yield content
                except json.JSONDecodeError:
                    continue
    
    async def generate(self, prompt: str) -> APIResponse:
        """生成响应"""
        await self._ensure_session()
        start_time = time.time()
        stream_stats = StreamStats(self.model)  # 传入模型名称
        full_response = []
        
        for attempt in range(self.max_retries):
            try:
                async with self._session.post(
                    self.api_url,
                    json=self._prepare_request(prompt),
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        async for chunk in self._process_stream(response):
                            full_response.append(chunk)
                            stream_stats.update(chunk)
                        
                        end_time = time.time()
                        response_text = ''.join(full_response)
                        
                        return APIResponse(
                            success=True,
                            response_text=response_text,
                            tokens_generated=stream_stats.total_tokens,
                            duration=end_time - start_time,
                            start_time=start_time,
                            end_time=end_time,
                            model_name=self.model,
                            stream_stats=stream_stats
                        )
                    else:
                        error_text = await response.text()
                        logger.error(f"API请求失败 (尝试 {attempt + 1}/{self.max_retries}): {error_text}")
                        if attempt == self.max_retries - 1:
                            return APIResponse(
                                success=False,
                                error_msg=f"HTTP {response.status}: {error_text}",
                                duration=time.time() - start_time,
                                start_time=start_time,
                                end_time=time.time()
                            )
            
            except asyncio.TimeoutError:
                logger.error(f"API请求超时 (尝试 {attempt + 1}/{self.max_retries})")
                if attempt == self.max_retries - 1:
                    return APIResponse(
                        success=False,
                        error_msg="请求超时",
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
