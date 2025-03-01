from .translations import TRANSLATIONS, LANGUAGES, DEFAULT_LANGUAGE
from PyQt6.QtCore import QObject, pyqtSignal


class LanguageManager(QObject):
    language_changed = pyqtSignal(str)  # 语言改变时发出信号
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._current_language = DEFAULT_LANGUAGE
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            super().__init__()
            self._initialized = True
    
    @property
    def current_language(self):
        return self._current_language
    
    def set_language(self, language_code):
        if language_code in TRANSLATIONS:
            self._current_language = language_code
            self.language_changed.emit(language_code)
    
    def get_text(self, key):
        """获取当前语言的翻译文本"""
        return TRANSLATIONS[self._current_language].get(key, key)
    
    @property
    def available_languages(self):
        """获取所有可用的语言"""
        return LANGUAGES 