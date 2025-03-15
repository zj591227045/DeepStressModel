import asyncio
import logging
import os
import json
import random
logging.basicConfig(level=logging.INFO)

from src.data.dataset_manager import dataset_manager
from src.benchmark.benchmark_manager import BenchmarkManager

async def run_test():
    # 创建BenchmarkManager实例，设置API密钥
    bm = BenchmarkManager({})
    bm.api_key = "test_api_key"  # 设置测试API密钥
    
    # 创建测试数据集
    test_data = []
    for i in range(100):
        test_data.append({
            "id": f"test-{i}",
            "text": f"这是测试输入 {i}",
            "expected_output": f"这是期望输出 {i}"
        })
    
    # 保存测试数据集
    os.makedirs("data/benchmark/datasets", exist_ok=True)
    test_dataset_path = "data/benchmark/datasets/test_dataset.json"
    with open(test_dataset_path, "w", encoding="utf-8") as f:
        json.dump({"version": "test-1.0.0", "data": test_data}, f, ensure_ascii=False, indent=2)
    
    # 使用dataset_manager加载测试数据集
    success = dataset_manager.load_benchmark_dataset(test_dataset_path)
    if not success:
        print("加载数据集失败")
        return
    
    print("数据集加载成功，开始运行基准测试...")
    
    # 运行基准测试
    result = await bm.run_benchmark({
        'model': 'Test Model', 
        'precision': 'FP16', 
        'model_params': 7, 
        'concurrency': 5  # 设置并发数为5
    })
    
    if result.get("status") == "error":
        print(f"测试失败: {result.get('message')}")
        return
    
    print(f"测试完成，生成了 {len(result.get('test_results', []))} 个结果")
    print(f"总耗时: {result.get('total_duration', 0):.2f}秒")
    print(f"平均TPS: {result.get('avg_tps', 0):.2f}")
    
if __name__ == "__main__":
    asyncio.run(run_test())
