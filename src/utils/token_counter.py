"""
Token计数工具模块
"""
import tiktoken
from typing import Optional, Dict
from src.utils.logger import setup_logger
from src.utils.config import config

logger = setup_logger("token_counter")

class TokenCounter:
    """Token计数器类"""
    
    _instance = None
    _encoders = {}
    
    # 模型编码器映射配置
    MODEL_ENCODERS = {
        # OpenAI模型
        "gpt-4": "gpt-4",
        "gpt-3.5": "gpt-3.5-turbo",
        # Qwen系列模型
        "qwen": "cl100k_base",
        # Claude系列模型
        "claude": "cl100k_base",
        # LLaMA系列模型
        "llama": "cl100k_base",
        # Baichuan系列模型
        "baichuan": "cl100k_base",
        # 默认编码器
        "default": "cl100k_base"
    }
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TokenCounter, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self._default_model = "cl100k_base"
            self._load_custom_encoders()
    
    def _load_custom_encoders(self):
        """从配置文件加载自定义编码器配置"""
        try:
            custom_encoders = config.get("tokenizer.model_encoders", {})
            if custom_encoders:
                self.MODEL_ENCODERS.update(custom_encoders)
                logger.info("已加载自定义编码器配置")
        except Exception as e:
            logger.error(f"加载自定义编码器配置失败: {e}")
    
    def add_model_encoder(self, model_name: str, encoder_name: str):
        """添加新的模型编码器映射
        
        Args:
            model_name: 模型名称或前缀
            encoder_name: 编码器名称
        """
        try:
            # 验证编码器是否有效
            tiktoken.get_encoding(encoder_name)
            
            # 更新映射
            self.MODEL_ENCODERS[model_name.lower()] = encoder_name
            
            # 清除已缓存的编码器（如果存在）
            if model_name in self._encoders:
                del self._encoders[model_name]
            
            # 更新配置文件
            custom_encoders = config.get("tokenizer.model_encoders", {})
            custom_encoders[model_name] = encoder_name
            config.set("tokenizer.model_encoders", custom_encoders)
            
            logger.info(f"已添加模型编码器映射: {model_name} -> {encoder_name}")
            return True
        except Exception as e:
            logger.error(f"添加模型编码器映射失败: {e}")
            return False
    
    def remove_model_encoder(self, model_name: str):
        """移除模型编码器映射"""
        try:
            model_name = model_name.lower()
            if model_name in self.MODEL_ENCODERS:
                del self.MODEL_ENCODERS[model_name]
            
            if model_name in self._encoders:
                del self._encoders[model_name]
            
            # 更新配置文件
            custom_encoders = config.get("tokenizer.model_encoders", {})
            if model_name in custom_encoders:
                del custom_encoders[model_name]
                config.set("tokenizer.model_encoders", custom_encoders)
            
            logger.info(f"已移除模型编码器映射: {model_name}")
            return True
        except Exception as e:
            logger.error(f"移除模型编码器映射失败: {e}")
            return False
    
    def get_encoder(self, model_name: str) -> tiktoken.Encoding:
        """获取指定模型的编码器"""
        try:
            if model_name not in self._encoders:
                # 查找匹配的编码器配置
                encoder_name = None
                model_lower = model_name.lower()
                
                # 精确匹配
                if model_lower in self.MODEL_ENCODERS:
                    encoder_name = self.MODEL_ENCODERS[model_lower]
                else:
                    # 前缀匹配
                    for prefix, enc in self.MODEL_ENCODERS.items():
                        if model_lower.startswith(prefix.lower()):
                            encoder_name = enc
                            break
                
                # 如果没有找到匹配的编码器，使用默认编码器
                if not encoder_name:
                    encoder_name = self.MODEL_ENCODERS["default"]
                
                # 创建编码器实例
                try:
                    if encoder_name in ["gpt-4", "gpt-3.5-turbo"]:
                        self._encoders[model_name] = tiktoken.encoding_for_model(encoder_name)
                    else:
                        self._encoders[model_name] = tiktoken.get_encoding(encoder_name)
                except Exception as e:
                    logger.error(f"创建编码器失败: {e}，使用默认编码器")
                    self._encoders[model_name] = tiktoken.get_encoding(self._default_model)
                
                logger.info(f"为模型 {model_name} 创建编码器 ({encoder_name})")
            
            return self._encoders[model_name]
        except Exception as e:
            logger.error(f"获取编码器失败: {e}")
            return tiktoken.get_encoding(self._default_model)
    
    def get_available_encoders(self) -> Dict[str, str]:
        """获取当前可用的模型编码器映射"""
        return self.MODEL_ENCODERS.copy()
    
    def count_tokens(self, text: str, model_name: Optional[str] = None) -> int:
        """计算文本的token数量"""
        try:
            encoder = self.get_encoder(model_name or self._default_model)
            return len(encoder.encode(text))
        except Exception as e:
            logger.error(f"计算token数量失败: {e}")
            return len(text.split())
    
    def count_tokens_batch(self, texts: list[str], model_name: Optional[str] = None) -> list[int]:
        """批量计算多个文本的token数量"""
        return [self.count_tokens(text, model_name) for text in texts]

# 全局单例实例
token_counter = TokenCounter() 