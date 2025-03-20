#!/usr/bin/env python3
"""
测试字符生成速度计算的脚本
"""
import json
import os
import sys
import glob
from pathlib import Path

def main():
    """主函数"""
    # 获取用户主目录下的.deepstressmodel/benchmark_results目录
    home_dir = os.path.expanduser("~")
    benchmark_dir = os.path.join(home_dir, ".deepstressmodel", "benchmark_results")
    
    # 检查目录是否存在
    if not os.path.exists(benchmark_dir):
        print(f"基准测试结果目录不存在: {benchmark_dir}")
        return 1
    
    # 获取最新的json文件
    json_files = glob.glob(os.path.join(benchmark_dir, "benchmark_result_*.json"))
    if not json_files:
        print("未找到基准测试结果文件")
        return 1
    
    # 按修改时间排序，获取最新的文件
    latest_file = max(json_files, key=os.path.getmtime)
    print(f"分析最新的基准测试结果: {latest_file}")
    
    # 读取JSON文件
    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"读取基准测试结果文件失败: {e}")
        return 1
    
    # 提取关键指标
    print("\n===== 字符生成速度分析 =====")
    
    # 获取总字符数和总时间
    total_chars = data.get("total_chars", 0)
    total_time = data.get("total_time", 0)
    
    # 计算真实的字符生成速度
    real_char_speed = total_chars / total_time if total_time > 0 else 0
    
    # 获取当前使用的字符生成速度
    current_avg_gen_speed = data.get("avg_gen_speed", data.get("avg_throughput", 0))
    
    # 获取数据集级别的字符生成速度
    datasets = data.get("datasets", {})
    for dataset_name, dataset_stats in datasets.items():
        dataset_total_chars = dataset_stats.get("total_chars", dataset_stats.get("total_bytes", 0))
        dataset_total_time = dataset_stats.get("total_time", 0)
        dataset_real_char_speed = dataset_total_chars / dataset_total_time if dataset_total_time > 0 else 0
        dataset_avg_gen_speed = dataset_stats.get("avg_gen_speed", dataset_stats.get("avg_generation_speed", 0))
        
        print(f"\n数据集: {dataset_name}")
        print(f"总字符数: {dataset_total_chars}")
        print(f"总时间: {dataset_total_time:.2f}秒")
        print(f"真实字符生成速度: {dataset_real_char_speed:.2f}字符/秒")
        print(f"当前字符生成速度: {dataset_avg_gen_speed:.2f}字符/秒")
        print(f"差异: {abs(dataset_real_char_speed - dataset_avg_gen_speed):.2f}字符/秒")
    
    print("\n总体统计:")
    print(f"总字符数: {total_chars}")
    print(f"总时间: {total_time:.2f}秒")
    print(f"真实字符生成速度: {real_char_speed:.2f}字符/秒")
    print(f"当前字符生成速度: {current_avg_gen_speed:.2f}字符/秒")
    print(f"差异: {abs(real_char_speed - current_avg_gen_speed):.2f}字符/秒")
    
    # 判断修改是否成功
    if abs(real_char_speed - current_avg_gen_speed) < 0.01:
        print("\n[成功] 字符生成速度计算已修正!")
    else:
        print("\n[警告] 字符生成速度计算仍有差异，需要进一步检查")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 