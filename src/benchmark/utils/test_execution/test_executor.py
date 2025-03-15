"""
测试执行模块，负责执行基准测试
"""
import time
import asyncio
import traceback
from typing import Dict, List, Any, Callable
from src.utils.logger import setup_logger
from src.utils.token_counter import token_counter

# 设置日志记录器
logger = setup_logger("test_executor")

async def execute_test(test_data: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    执行测试
    
    Args:
        test_data: 测试数据
        config: 测试配置
        
    Returns:
        List[Dict[str, Any]]: 测试结果
    """
    #######################################################################
    # 重要提示: 本函数及其下游process_item函数中，模型名称必须使用
    # model_config["model"]字段，而不是model_config["name"]字段!
    # model_config["name"]字段只用于UI显示，不能用于API调用。
    # 使用错误的字段会导致API请求404错误，如:
    # "model \"ollama-llama3:8b-instruct-fp16\" not found"
    #######################################################################
    
    # 获取API URL - 关键修改
    api_url = config.get("api_url")
    if not api_url:
        logger.error("缺少API URL，无法执行测试")
        raise ValueError("缺少API URL，无法执行测试")
    
    # 确保URL包含完整路径
    if not "chat/completions" in api_url:
        # 如果URL不以/结尾，添加/
        if not api_url.endswith("/"):
            api_url += "/"
        
        # 标准化URL格式
        if api_url.endswith("v1/"):
            # URL已经正确格式化为v1/
            pass
        elif "/v1/v1/" in api_url:
            # 修复重复的v1
            api_url = api_url.replace("/v1/v1/", "/v1/")
        elif "/v1" in api_url and not api_url.endswith("v1/"):
            # 确保v1路径正确格式化
            parts = api_url.split("/v1")
            api_url = parts[0] + "/v1/"
        
        # 添加chat/completions路径
        api_url += "chat/completions"
    
    logger.info(f"开始测试，目标API URL: {api_url}")
    
    # 从config中获取其他参数
    model_config = config.get("model_config", {})
    precision = config.get("precision", "FP16")
    use_gpu = config.get("use_gpu", True)
    running = config.get("running", True)  # 测试是否在运行的标志
    
    # 这里是测试执行的具体逻辑
    results = []
    total_items = 0
    
    # 记录测试数据类型以便调试
    logger.debug(f"测试数据类型: {type(test_data).__name__}")
    
    # 检查test_data是否为字典或列表，并相应处理
    if isinstance(test_data, dict):
        # 如果是字典，尝试访问可能的数据字段
        logger.debug(f"测试数据是字典类型，键值: {list(test_data.keys())}")
        
        if "data" in test_data and isinstance(test_data["data"], list):
            test_items = test_data["data"]
            total_items = len(test_items)
            logger.info(f"从字典数据集中提取到 {total_items} 条测试项")
        elif "version" in test_data and "file_path" in test_data:
            logger.debug(f"检测到数据集引用格式: version={test_data.get('version')}, file_path={test_data.get('file_path')}")
            
            # 处理离线包格式
            logger.info("检测到离线包格式，尝试提取测试数据")
            try:
                from src.data.dataset_manager import dataset_manager
                offline_data = dataset_manager.get_offline_dataset_data()
                if offline_data and isinstance(offline_data, list):
                    test_items = offline_data
                    total_items = len(test_items)
                    logger.info(f"从离线数据集中提取到 {total_items} 条测试项")
                else:
                    logger.error("无法从离线包中提取有效测试数据")
                    test_items = []
                    total_items = 0
            except Exception as e:
                logger.error(f"处理离线包数据失败: {e}")
                test_items = []
                total_items = 0
        else:
            # 无法识别的字典格式
            logger.error(f"无法识别的测试数据格式，键值: {list(test_data.keys())}")
            test_items = []
            total_items = 0
    elif isinstance(test_data, list):
        # 如果直接是列表，直接使用
        test_items = test_data
        total_items = len(test_items)
        logger.info(f"直接使用列表数据集，包含 {total_items} 条测试项")
    else:
        # 无法处理的数据类型
        logger.error(f"无法处理的测试数据类型: {type(test_data)}")
        test_items = []
        total_items = 0
    
    if total_items == 0:
        logger.warning("没有有效的测试数据，返回空结果")
        return results

    # 获取配置中的并发数，默认为1（顺序执行）
    concurrency = config.get("concurrency", 1)
    try:
        # 从全局配置获取默认并发数
        from src.utils.config import config as global_config
        default_concurrency = global_config.get("test.default_concurrency", 1)
        max_concurrency = global_config.get("test.max_concurrency", 9999)
        # 如果未指定并发数，使用默认值
        if concurrency <= 0:
            concurrency = default_concurrency
        # 限制最大并发数
        concurrency = min(concurrency, max_concurrency)
    except Exception as e:
        logger.warning(f"获取并发设置失败，使用默认值1: {e}")
        concurrency = 1

    logger.info(f"测试将使用并发数: {concurrency}")
    
    # 导入需要的模块用于API调用
    import aiohttp
    import json
    
    # 创建一个执行单个测试项的协程函数
    async def process_item(index, item):
        if not running:
            return None
        
        try:
            # 确保item是字典类型
            if not isinstance(item, dict):
                logger.warning(f"跳过非字典类型的测试项 #{index}: {type(item)}")
                return None
            
            # 获取测试输入
            input_text = item.get("text", item.get("input", ""))
            item_id = item.get("id", f"item-{index}")
            
            # 记录开始时间
            start_time = time.time()
            
            #######################################################################
            # 重要提示: API请求中的模型名称必须使用model_config["model"]字段
            # 而不是model_config["name"]字段!
            # 使用错误的字段会导致API请求404错误
            #######################################################################
            
            # 获取正确的模型名称 - 从model_config["model"]中获取，而不是使用默认的model参数或name字段
            model_config = config.get("model_config", {})
            
            # 优先使用model_config中的model字段 - 不要使用name字段，否则会导致API调用失败
            if model_config and "model" in model_config:
                model_name = model_config["model"]
                logger.info(f"使用model_config['model']作为模型名称: {model_name}")
            else:
                # 后备使用config中的model参数
                model_name = config.get("model", "gpt-3.5-turbo")
                logger.warning(f"未找到model_config['model']，使用默认model参数: {model_name}")
            
            # 确保不误用name字段
            if model_config and "name" in model_config and "model" not in model_config:
                logger.warning(f"警告: model_config中存在'name'字段({model_config['name']})，但找不到'model'字段。'name'字段是展示用的，不能用于API调用!")
                
            request_data = {
                "model": model_name,  # 使用正确的模型名称，不要使用model_config["name"]
                "messages": [
                    {"role": "user", "content": input_text}
                ],
                "temperature": model_config.get("temperature", 0.7) if model_config else 0.7
            }
            
            # 如果配置中有其他参数，也加入请求
            if model_config:
                if "max_tokens" in model_config:
                    request_data["max_tokens"] = model_config["max_tokens"]
                if "top_p" in model_config:
                    request_data["top_p"] = model_config["top_p"]
            
            # 记录更详细的API调用信息 - 添加这部分日志
            logger.info(f"测试项 #{index} 调用API: URL={api_url}, 模型={model_name}")
            logger.debug(f"测试项 #{index} 请求头: {{'Content-Type': 'application/json'}}")
            # 仅记录请求体的摘要，避免日志过大
            content_summary = input_text[:50] + "..." if len(input_text) > 50 else input_text
            # 添加更详细的请求信息
            logger.debug(f"测试项 #{index} 完整请求数据: model={model_name}, temperature={request_data.get('temperature')}, max_tokens={request_data.get('max_tokens')}, top_p={request_data.get('top_p')}")
            logger.debug(f"测试项 #{index} 请求体摘要: 模型={model_name}, 输入={content_summary}")
            
            logger.debug(f"测试项 #{index} 发送请求: {input_text[:50]}...")
            
            # 实际调用API
            async with aiohttp.ClientSession() as session:
                try:
                    # 记录更详细的API调用信息
                    logger.debug(f"测试项 #{index} 发送请求到: {api_url}")
                    logger.debug(f"测试项 #{index} 请求数据: {json.dumps(request_data)[:100]}...")
                    
                    async with session.post(
                        api_url, 
                        json=request_data,
                        headers={"Content-Type": "application/json"},
                        timeout=30  # 设置超时时间为30秒
                    ) as response:
                        # 记录结束时间
                        end_time = time.time()
                        latency = end_time - start_time
                        
                        # 计算吞吐量（字符数/秒）
                        input_length = len(input_text)
                        throughput = input_length / latency if latency > 0 else 0
                        
                        if response.status == 200:
                            # 成功获取响应
                            response_data = await response.json()
                            
                            # 提取模型输出
                            output_text = ""
                            if "choices" in response_data and len(response_data["choices"]) > 0:
                                output_text = response_data["choices"][0].get("message", {}).get("content", "")
                            
                            logger.debug(f"测试项 #{index} 收到响应: 状态码={response.status}, 延迟={latency:.4f}秒")
                            
                            # 使用token_counter计算token数量
                            input_tokens = token_counter.count_tokens(input_text, model_name)
                            output_tokens = token_counter.count_tokens(output_text, model_name)
                            total_tokens = input_tokens + output_tokens
                            
                            # 计算基于token的吞吐量（tokens/秒）
                            token_throughput = total_tokens / latency if latency > 0 else 0
                            
                            # 构造测试结果
                            return {
                                "id": item_id,
                                "input": input_text,
                                "output": output_text,
                                "expected_output": item.get("expected_output", ""),
                                "latency": latency,
                                "throughput": throughput,  # 保留原有的字符吞吐量
                                "token_throughput": token_throughput,  # 添加基于token的吞吐量
                                "input_tokens": input_tokens,
                                "output_tokens": output_tokens,
                                "tokens": total_tokens,
                                "status": "success",
                                "timestamp": int(time.time() * 1000)
                            }
                        else:
                            # API调用失败 - 添加更详细的错误日志
                            error_text = await response.text()
                            logger.warning(f"测试项 #{index} API调用失败: URL={api_url}, 状态码={response.status}, 错误={error_text}")
                            return {
                                "id": item_id,
                                "input": input_text,
                                "error": f"API调用失败: 状态码={response.status}, 错误={error_text}",
                                "latency": latency,
                                "throughput": 0,
                                "status": "error",
                                "timestamp": int(time.time() * 1000)
                            }
                except asyncio.TimeoutError:
                    # 超时错误 - 添加更详细的错误日志
                    logger.warning(f"测试项 #{index} API调用超时: URL={api_url}, 超时阈值=30秒")
                    return {
                        "id": item_id,
                        "input": input_text,
                        "error": "API调用超时",
                        "latency": 30.0,  # 使用超时时间作为延迟
                        "throughput": 0,
                        "status": "timeout",
                        "timestamp": int(time.time() * 1000)
                    }
                except Exception as e:
                    # 其他异常 - 添加更详细的错误日志
                    logger.error(f"测试项 #{index} 请求异常: URL={api_url}, 错误类型={type(e).__name__}, 错误={str(e)}")
                    return {
                        "id": item_id,
                        "input": input_text,
                        "error": f"请求异常: {str(e)}",
                        "latency": time.time() - start_time,
                        "throughput": 0,
                        "status": "error",
                        "timestamp": int(time.time() * 1000)
                    }
        except Exception as e:
            logger.error(f"处理测试项 #{index} 失败: {e}")
            logger.error(traceback.format_exc())
            return {
                "id": item.get("id", f"item-{index}"),
                "input": item.get("text", item.get("input", "")),
                "error": str(e),
                "latency": 0,
                "throughput": 0,
                "status": "error",
                "timestamp": int(time.time() * 1000)
            }

    # 采用分批执行的方式，避免一次创建过多协程
    # 使用设置的并发数，但确保不超过测试项总数
    batch_size = min(concurrency, total_items)  
    # 如果批次大小较大，设置一个合理的进度更新频率
    update_frequency = min(batch_size, max(1, total_items // 5))  # 确保至少5次进度更新
    logger.info(f"使用实际并发数: {batch_size}, 进度更新频率: 每处理 {update_frequency} 个项目")
    completed = 0
    valid_results = []
    
    # 获取进度回调函数
    progress_callback = config.get("progress_callback")
    
    # 在开始执行测试前先更新一次进度为1%，确保显示"测试进行中"状态
    if progress_callback:
        progress_callback({
            "progress": 1,  # 设为1%而不是0%，确保显示"测试进行中"
            "current_item": 0,
            "total_items": total_items,
            "latency": 0,
            "throughput": 0,
            "total_time": 0,
            "total_tokens": 0,
            "total_bytes": 0,
            "token_throughput": 0
        })

    # 记录开始时间
    start_time = time.time()

    # 分批处理所有测试项
    for batch_start in range(0, total_items, batch_size):
        if not running:
            logger.info("测试已停止，中断执行")
            break
            
        batch_end = min(batch_start + batch_size, total_items)
        batch_items = test_items[batch_start:batch_end]
        batch_indices = list(range(batch_start, batch_end))
        
        logger.info(f"处理批次 {batch_start//batch_size + 1}/{(total_items-1)//batch_size + 1}, 项目范围: {batch_start+1}-{batch_end}")
        
        # 如果批次大小较大，则分段处理并更新进度
        if batch_size > update_frequency:
            for segment_start in range(0, len(batch_items), update_frequency):
                segment_end = min(segment_start + update_frequency, len(batch_items))
                segment_items = batch_items[segment_start:segment_end]
                segment_indices = batch_indices[segment_start:segment_end]
                
                # 创建当前段的所有测试协程
                tasks = [process_item(i, item) for i, item in zip(segment_indices, segment_items)]
                
                # 并发执行当前段的所有测试
                segment_results = await asyncio.gather(*tasks)
                
                # 过滤掉None结果并添加到结果列表
                segment_valid_results = [r for r in segment_results if r is not None]
                valid_results.extend(segment_valid_results)
                
                # 更新完成数量
                completed += len(segment_valid_results)
                
                # 更新总体进度
                progress = completed / total_items * 100
                
                # 如果有进度回调，更新进度
                if progress_callback:
                    progress_callback({
                        "progress": progress,
                        "current_item": completed,
                        "total_items": total_items,
                        "latency": sum(r.get("latency", 0) for r in segment_valid_results) / len(segment_valid_results) if segment_valid_results else 0,
                        "throughput": sum(r.get("throughput", 0) for r in segment_valid_results) / len(segment_valid_results) if segment_valid_results else 0,
                        "total_time": time.time() - start_time,
                        "total_tokens": sum(r.get("tokens", 0) for r in segment_valid_results) if segment_valid_results else 0,
                        "total_bytes": sum(len(r.get("input", "")) for r in segment_valid_results) if segment_valid_results else 0,
                        "token_throughput": sum(r.get("token_throughput", 0) for r in segment_valid_results) / len(segment_valid_results) if segment_valid_results else 0
                    })
                
                logger.info(f"完成段 {segment_start//update_frequency + 1}/{(len(batch_items)-1)//update_frequency + 1}, 总进度: {progress:.1f}%")
        else:
            # 创建当前批次的所有测试协程
            tasks = [process_item(i, item) for i, item in zip(batch_indices, batch_items)]
            
            # 并发执行当前批次的所有测试
            batch_results = await asyncio.gather(*tasks)
            
            # 过滤掉None结果并添加到结果列表
            batch_valid_results = [r for r in batch_results if r is not None]
            valid_results.extend(batch_valid_results)
            
            # 更新完成数量
            completed += len(batch_valid_results)
            
            # 更新总体进度
            progress = completed / total_items * 100
            
            # 如果有进度回调，更新进度
            if progress_callback:
                progress_callback({
                    "progress": progress,
                    "current_item": completed,
                    "total_items": total_items,
                    "latency": sum(r.get("latency", 0) for r in batch_valid_results) / len(batch_valid_results) if batch_valid_results else 0,
                    "throughput": sum(r.get("throughput", 0) for r in batch_valid_results) / len(batch_valid_results) if batch_valid_results else 0,
                    "total_time": time.time() - start_time,
                    "total_tokens": sum(r.get("tokens", 0) for r in batch_valid_results) if batch_valid_results else 0,
                    "total_bytes": sum(len(r.get("input", "")) for r in batch_valid_results) if batch_valid_results else 0,
                    "token_throughput": sum(r.get("token_throughput", 0) for r in batch_valid_results) / len(batch_valid_results) if batch_valid_results else 0
                })
            
            logger.info(f"完成批次 {batch_start//batch_size + 1}/{(total_items-1)//batch_size + 1}, 进度: {progress:.1f}%")
    
    return valid_results

def calculate_metrics(test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    计算性能指标
    
    Args:
        test_results: 测试结果
        
    Returns:
        Dict[str, Any]: 性能指标
    """
    if not test_results:
        return {
            "throughput": 0,
            "latency": 0,
            "gpu_utilization": 0,
            "memory_utilization": 0
        }
    
    # 计算平均延迟和吞吐量
    latencies = [result.get("latency", 0) for result in test_results]
    throughputs = [result.get("throughput", 0) for result in test_results]
    
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    avg_throughput = sum(throughputs) / len(throughputs) if throughputs else 0
    
    # 获取GPU利用率
    gpu_utilization = 0
    memory_utilization = 0
    
    try:
        from src.monitor.gpu_monitor import gpu_monitor
        gpu_stats = gpu_monitor.get_stats()
        if gpu_stats and hasattr(gpu_stats, 'gpus') and gpu_stats.gpus:
            # 计算所有GPU的平均利用率
            gpu_utilization = sum(gpu.get("util", 0) for gpu in gpu_stats.gpus) / len(gpu_stats.gpus)
            # 计算所有GPU的平均显存利用率
            memory_utilization = sum(
                gpu.get("memory_used", 0) / max(gpu.get("memory_total", 1), 1) * 100 
                for gpu in gpu_stats.gpus
            ) / len(gpu_stats.gpus)
    except Exception as e:
        logger.error(f"计算GPU指标失败: {str(e)}")
    
    return {
        "throughput": avg_throughput,
        "latency": avg_latency,
        "gpu_utilization": gpu_utilization,
        "memory_utilization": memory_utilization
    } 