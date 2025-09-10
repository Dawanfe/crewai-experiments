#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试简单的飞书块创建
"""

import json
import requests
from feishu_doc_manager_final import FeishuDocManagerWorking

def test_simple_block():
    """测试创建简单的文本块"""
    manager = FeishuDocManagerWorking()
    
    # 创建文档
    doc_token = manager.create_document("测试文档")
    
    # 获取根块ID
    root_block_id = manager.get_document_root_block(doc_token)
    if not root_block_id:
        print("❌ 无法获取根块ID")
        return
    
    print(f"🔍 根块ID: {root_block_id}")
    
    # 创建最简单的文本块
    simple_block = {
        "block_type": 2,  # 尝试块类型2
        "text": {
            "elements": [{
                "text_run": {
                    "content": "这是一个简单的测试文本"
                }
            }]
        }
    }
    
    # 尝试插入单个块
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{root_block_id}/children"
    headers = {
        "Authorization": f"Bearer {manager.tenant_access_token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    data = {
        "children": [simple_block]
    }
    
    print(f"🔍 请求URL: {url}")
    print(f"🔍 请求数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
    
    response = requests.post(url, headers=headers, json=data)
    
    print(f"🔍 响应状态码: {response.status_code}")
    print(f"🔍 响应内容: {response.text}")
    
    if response.status_code == 200:
        result = response.json()
        if result.get("code") == 0:
            print("✅ 成功创建文本块!")
        else:
            print(f"❌ 创建失败: {result}")
    else:
        print(f"❌ 请求失败: {response.status_code}")

if __name__ == "__main__":
    test_simple_block()
