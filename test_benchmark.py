import asyncio
import logging
from src.data.dataset_manager import dataset_manager
from src.benchmark.benchmark_manager import BenchmarkManager

logging.basicConfig(level=logging.INFO)

async def run_test():
    # 初始化BenchmarkManager
    bm = BenchmarkManager()
    await bm.initialize_async()
    
    # 获取离线包
    await bm.get_offline_package(dataset_id="1")
    
    # 运行基准测试
    result = await bm.run_benchmark(
        model="Test Model",
        precision="FP16",
        api_url="http://10.255.0.75:11434/v1/chat/completions",
        model_params={
            "test": True,
            "model": "llama3:8b-instruct-fp16",
        },
        concurrency=30,
        test_mode=1, 
        use_gpu=True
    )
    
    # 打印测试结果
    print(f"测试结果状态: {result['status']}")
    print(f"数据集版本: {result.get('dataset_version', '未知')}")
    print(f"结果保存路径: {result.get('result_path', '未知')}")
    print(f"UI数据集结构: {result.get('datasets', {}).keys()}")

    # 关闭资源
    bm.cleanup()

if __name__ == "__main__":
    asyncio.run(run_test())
