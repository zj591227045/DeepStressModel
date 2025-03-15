import asyncio
from src.benchmark.benchmark_manager import BenchmarkManager

async def test():
    print("开始测试BenchmarkManager的initialize_async方法...")
    bm = BenchmarkManager({})
    bm.api_key = 'test_api_key'
    success = await bm.initialize_async()
    if success:
        print("初始化成功！")
    else:
        print("初始化失败！")

if __name__ == "__main__":
    asyncio.run(test()) 