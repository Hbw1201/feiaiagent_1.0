# zhipu_agent.py
# -*- coding: utf-8 -*-
"""
智谱AI简单调用封装
- 使用v2接口创建会话
- 使用v3接口调用应用
- 保持同一个conversation_id以维持上下文
"""

import requests
import json
import os

# API地址
OPEN_APP_V3_URL = "https://open.bigmodel.cn/api/llm-application/open/v3/application/invoke"
OPEN_APP_V2_URL = "https://open.bigmodel.cn/api/llm-application/open/v2/application/{app_id}/conversation"

def create_conversation(app_id: str, api_key: str):
    """创建会话，返回conversation_id"""
    url = OPEN_APP_V2_URL.format(app_id=app_id)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': api_key
    }
    
    try:
        response = requests.post(url, headers=headers, json={}, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 200:
                conversation_id = data.get("data", {}).get("conversation_id")
                print(f"[DEBUG] 创建会话成功，ID: {conversation_id}")
                return conversation_id
            else:
                print(f"[DEBUG] 创建会话失败: {data.get('message')}")
                return None
        else:
            print(f"[DEBUG] HTTP错误: {response.status_code}")
            return None
    except Exception as e:
        print(f"[DEBUG] 创建会话异常: {e}")
        return None

def call_zhipu(app_id: str, api_key: str, prompt: str, conversation_id: str):
    """调用智谱AI，返回回复文本"""
    payload = {
        "app_id": int(app_id) if app_id.isdigit() else app_id,
        "conversation_id": conversation_id,
        "stream": False,
        "send_log_event": True,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "value": prompt,
                        "type": "input"
                    }
                ]
            }
        ]
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': api_key
    }
    
    try:
        response = requests.post(OPEN_APP_V3_URL, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            data = response.json()
            print(f"[DEBUG] 智谱AI响应: {json.dumps(data, ensure_ascii=False)[:500]}...")
            
            # 提取问题文本或评估报告
            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                if "finish_reason" in choice and choice["finish_reason"] == "stop":
                    if "messages" in choice and "content" in choice["messages"]:
                        content = choice["messages"]["content"]
                        print(f"[DEBUG] 原始content: {json.dumps(content, ensure_ascii=False)}")
                        
                        # 尝试多种方式提取内容
                        extracted_text = None
                        
                        # 方式1：尝试提取question字段
                        if isinstance(content, dict) and "msg" in content:
                            msg = content["msg"]
                            if isinstance(msg, dict) and "msg" in msg:
                                inner_msg = msg["msg"]
                                if isinstance(inner_msg, dict) and "question" in inner_msg:
                                    extracted_text = inner_msg["question"]
                                    print(f"[DEBUG] 方式1提取到question: {extracted_text}")
                        
                        # 方式2：尝试直接提取content中的文本
                        if not extracted_text and isinstance(content, dict):
                            # 递归搜索所有可能的文本字段
                            def find_text_in_dict(d, depth=0):
                                if depth > 5:  # 防止无限递归
                                    return None
                                for key, value in d.items():
                                    if isinstance(value, str) and len(value) > 10:
                                        # 找到较长的文本，可能是问题或报告
                                        return value
                                    elif isinstance(value, dict):
                                        result = find_text_in_dict(value, depth + 1)
                                        if result:
                                            return result
                                    elif isinstance(value, list):
                                        for item in value:
                                            if isinstance(item, dict):
                                                result = find_text_in_dict(item, depth + 1)
                                                if result:
                                                    return result
                                return None
                            
                            extracted_text = find_text_in_dict(content)
                            if extracted_text:
                                print(f"[DEBUG] 方式2提取到文本: {extracted_text[:100]}...")
                        
                        # 方式3：如果还是没找到，尝试从整个响应中提取
                        if not extracted_text:
                            # 将整个响应转换为字符串，寻找有意义的内容
                            response_str = json.dumps(data, ensure_ascii=False)
                            # 寻找包含"问题"、"报告"、"评估"等关键词的文本
                            import re
                            # 匹配引号内的中文文本
                            chinese_texts = re.findall(r'[""]([^""]*[\u4e00-\u9fa5]+[^""]*)[""]', response_str)
                            print(f"[DEBUG] 正则匹配到的中文文本数量: {len(chinese_texts)}")
                            for i, text in enumerate(chinese_texts):
                                print(f"[DEBUG] 中文文本{i+1}: {text[:100]}...")
                                if len(text) > 20 and any(keyword in text for keyword in ["问题", "报告", "评估", "姓名", "年龄", "症状"]):
                                    extracted_text = text
                                    print(f"[DEBUG] 方式3提取到文本: {extracted_text[:100]}...")
                                    break
                        
                        if extracted_text:
                            print(f"[DEBUG] ✅ 成功提取到文本内容")
                            print(f"[DEBUG] 提取的文本长度: {len(extracted_text)}")
                            print(f"[DEBUG] 提取的文本预览: {extracted_text[:200]}...")
                            return extracted_text, conversation_id
            
            print("[DEBUG] 未找到有效文本，尝试其他解析方式...")
            # 如果上面的解析失败，尝试其他方式
            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                # 打印整个choice结构用于调试
                print(f"[DEBUG] choice结构: {json.dumps(choice, ensure_ascii=False)}")
                
                # 检查是否有错误信息
                if "finish_reason" in choice and choice["finish_reason"] == "error":
                    error_msg = choice.get("error_msg", {})
                    error_code = error_msg.get("code", "unknown")
                    error_text = error_msg.get("msg", "未知错误")
                    print(f"[DEBUG] 检测到错误: code={error_code}, msg={error_text}")
                    
                    # 如果是Agent流程错误，尝试提供更友好的错误信息
                    if "java.lang.IllegalArgumentException" in error_text:
                        if "text cannot be null or blank" in error_text:
                            return f"Agent流程错误：用户回答为空或格式不正确，请重新回答刚才的问题", conversation_id
                        else:
                            return f"Agent流程错误：输入参数无效，请重新回答刚才的问题", conversation_id
                    elif "text cannot be null or blank" in error_text:
                        return f"Agent流程错误：用户回答为空，请重新回答刚才的问题", conversation_id
                    else:
                        return f"Agent流程错误：{error_text}，请重新回答刚才的问题", conversation_id
            
            return "未获取到有效回复", conversation_id
        else:
            print(f"[DEBUG] HTTP错误: {response.status_code}")
            return f"HTTP错误: {response.status_code}", conversation_id
    except Exception as e:
        print(f"[DEBUG] 调用异常: {e}")
        return f"调用异常: {e}", conversation_id

def zhipu_conversation(prompt: str, conversation_id: str = None, app_id: str = None, api_key: str = None):
    """智谱AI对话函数"""
    # 获取配置
    if not app_id:
        try:
            from config import ZHIPU_APP_ID
            app_id = ZHIPU_APP_ID
        except ImportError:
            app_id = os.getenv("ZHIPU_APP_ID")
    
    if not api_key:
        try:
            from config import ZHIPU_API_KEY
            api_key = ZHIPU_API_KEY
        except ImportError:
            api_key = os.getenv("ZHIPU_API_KEY")
    
    if not app_id or not api_key:
        return "缺少配置信息", None
    
    # 如果没有会话ID，创建一个
    if not conversation_id:
        conversation_id = create_conversation(app_id, api_key)
        if not conversation_id:
            return "创建会话失败", None
    
    # 调用智谱AI
    reply, conv_id = call_zhipu(app_id, api_key, prompt, conversation_id)
    return reply, conv_id
