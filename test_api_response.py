#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import sys

def test_api_usage_field():
    """测试API响应是否包含usage字段"""
    # API配置
    api_url = "http://10.255.0.75:11434/v1/chat/completions"
    api_key = "fwfw"
    
    # 请求头
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # 请求数据
    payload = {
        "model": "llama3:8b-instruct-fp16",
        "messages": [
            {"role": "system", "content": "你是一个有用的助手。"},
            {"role": "user", "content": "你好，请简单介绍一下北京。"}
        ],
        "max_tokens": 500
    }
    
    print("发送API请求到Ollama框架...")
    
    try:
        # 发送请求
        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        
        # 解析响应
        result = response.json()
        
        # 输出完整响应（格式化）
        print("\n完整响应:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # 检查是否包含usage字段
        if "usage" in result:
            usage = result["usage"]
            print("\nAPI响应包含usage字段:")
            print(f"- 输入tokens: {usage.get('prompt_tokens', '未提供')}")
            print(f"- 输出tokens: {usage.get('completion_tokens', '未提供')}")
            print(f"- 总tokens: {usage.get('total_tokens', '未提供')}")
            return True
        else:
            print("\nAPI响应不包含usage字段")
            return False
            
    except Exception as e:
        print(f"请求失败: {str(e)}")
        return False

if __name__ == "__main__":
    test_api_usage_field() 