import asyncio
from src.benchmark.benchmark_manager import BenchmarkManager

async def test():
    print("开始测试BenchmarkManager的get_offline_package方法...")
    bm = BenchmarkManager({})
    bm.api_key = 'test_api_key'
    
    # 先初始化
    success = await bm.initialize_async()
    if not success:
        print("初始化失败！")
        return
    
    # 测试获取离线包
    try:
        result = await bm.get_offline_package(dataset_id="1")
        if result:
            print("获取离线包成功！")
        else:
            print("获取离线包失败！")
    except Exception as e:
        print(f"获取离线包出错：{str(e)}")

if __name__ == "__main__":
    asyncio.run(test()) 