import re; f=open("src/benchmark/benchmark_manager.py","r"); content=f.read(); f.close(); content=re.sub(r"
\s{10,}self\._update_progress\({
", "
        self._update_progress({
", content); content=re.sub(r"
            # 尝试加载标准测试数据集
            self\._load_standard_benchmark_dataset\(\)", "", content); content=re.sub(r"
    def _load_standard_benchmark_dataset.*?def _generate_hardware_fingerprint", "
    def _generate_hardware_fingerprint", content, flags=re.DOTALL); f=open("src/benchmark/benchmark_manager.py","w"); f.write(content); f.close(); print("修复完成")
