from .translations import TRANSLATIONS, LANGUAGES, DEFAULT_LANGUAGE
from PyQt6.QtCore import QObject, pyqtSignal


class LanguageManager(QObject):
    language_changed = pyqtSignal(str)  # 语言改变时发出信号
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """初始化语言管理器"""
        self.default_language = DEFAULT_LANGUAGE
        self.current_language = self.default_language
        
        # 定义支持的语言列表和显示名称
        self.supported_languages = LANGUAGES
        
        # 初始化语言包
        self.translations = TRANSLATIONS
    
    def set_language(self, language_code):
        """设置当前语言"""
        if language_code in self.supported_languages:
            self.current_language = language_code
            self.language_changed.emit(language_code)
            return True
        return False
    
    def get_current_language(self):
        """获取当前语言代码"""
        return self.current_language
    
    def get_current_language_name(self):
        """获取当前语言名称"""
        return self.supported_languages.get(self.current_language, "")
    
    def get_supported_languages(self):
        """获取支持的语言列表"""
        return self.supported_languages
    
    def get_text(self, key):
        """获取指定键的翻译文本"""
        if key in self.translations.get(self.current_language, {}):
            return self.translations[self.current_language][key]
        elif key in self.translations.get(self.default_language, {}):
            return self.translations[self.default_language][key]
        else:
            return key  # 如果没有找到翻译，返回原始键
    
    @property
    def available_languages(self):
        """获取所有可用的语言"""
        return self.supported_languages 