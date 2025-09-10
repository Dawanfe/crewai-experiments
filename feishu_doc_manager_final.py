#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书文档管理器 - 工作版本
使用正确的飞书API实现文档创建和内容插入
"""

import json
import os
import re
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import requests
from pathlib import Path


class FeishuDocManagerWorking:
    """飞书文档管理器 - 工作版本"""
    
    def __init__(self, config_path: str = "config.json"):
        """初始化飞书文档管理器"""
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        self.feishu_config = self.config['feishu']
        self.app_id = self.feishu_config['app_id']
        self.app_secret = self.feishu_config['app_secret']
        self.space_id = self.feishu_config['space_id']
        self.parent_node_token = self.feishu_config.get('parent_node_token', '')
        self.title_prefix = self.feishu_config.get('title_prefix', 'AINews')
        
        self.tenant_access_token = None
        
    def get_tenant_access_token(self) -> str:
        """获取tenant_access_token"""
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {
            "Content-Type": "application/json; charset=utf-8"
        }
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        
        if result.get("code") == 0:
            self.tenant_access_token = result["tenant_access_token"]
            return self.tenant_access_token
        else:
            raise Exception(f"获取tenant_access_token失败: {result}")
    
    def create_document(self, title: str) -> str:
        """创建飞书文档"""
        if not self.tenant_access_token:
            self.get_tenant_access_token()
        
        url = "https://open.feishu.cn/open-apis/docx/v1/documents"
        headers = {
            "Authorization": f"Bearer {self.tenant_access_token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        data = {
            "title": title,
            "folder_token": self.parent_node_token if self.parent_node_token else None
        }
        
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        
        if result.get("code") == 0:
            doc_token = result["data"]["document"]["document_id"]
            print(f"✅ 成功创建文档: {title}")
            print(f"📄 文档ID: {doc_token}")
            return doc_token
        else:
            raise Exception(f"创建文档失败: {result}")
    
    def markdown_to_feishu_blocks(self, markdown_content: str) -> List[Dict[str, Any]]:
        """将Markdown内容转换为飞书块格式"""
        blocks = []
        lines = markdown_content.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # 空行
            if not line:
                i += 1
                continue
            
            # 标题处理
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                title_text = line.lstrip('# ').strip()
                
                # 处理链接格式 [text](url)
                title_text, links = self._extract_links(title_text)
                
                block = {
                    "block_type": 2,  # 使用块类型2
                    "text": {
                        "elements": [{
                            "text_run": {
                                "content": title_text
                            }
                        }]
                    }
                }
                
                # 如果有链接，添加链接元素
                if links:
                    block["text"]["elements"] = self._create_text_elements_with_links(title_text, links)
                
                blocks.append(block)
            
            # 列表项处理
            elif line.startswith('- '):
                list_items = []
                current_item = line[2:].strip()
                
                # 处理链接
                current_item, links = self._extract_links(current_item)
                
                # 收集连续列表项
                while i < len(lines) and lines[i].strip().startswith('- '):
                    item_text = lines[i].strip()[2:].strip()
                    item_text, item_links = self._extract_links(item_text)
                    list_items.append((item_text, item_links))
                    i += 1
                
                # 创建列表块
                for item_text, item_links in list_items:
                    list_block = {
                        "block_type": 2,  # 使用块类型2
                        "text": {
                            "elements": [{
                                "text_run": {
                                    "content": f"• {item_text}"  # 添加列表符号
                                }
                            }]
                        }
                    }
                    
                    # 如果有链接，添加链接元素
                    if item_links:
                        list_block["text"]["elements"] = self._create_text_elements_with_links(item_text, item_links)
                    
                    blocks.append(list_block)
                
                i -= 1  # 回退一行，因为外层循环会+1
            
            # 代码块处理
            elif line.startswith('```'):
                code_content = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_content.append(lines[i])
                    i += 1
                
                if code_content:
                    code_content_str = '\n'.join(code_content)
                    code_block = {
                        "block_type": 2,  # 使用块类型2
                        "text": {
                            "elements": [{
                                "text_run": {
                                    "content": f"```\n{code_content_str}\n```"  # 添加代码块标记
                                }
                            }]
                        }
                    }
                    blocks.append(code_block)
            
            # 普通段落
            else:
                paragraph_text = line
                paragraph_text, links = self._extract_links(paragraph_text)
                
                paragraph_block = {
                    "block_type": 2,  # 使用块类型2
                    "text": {
                        "elements": [{
                            "text_run": {
                                "content": paragraph_text
                            }
                        }]
                    }
                }
                
                # 如果有链接，添加链接元素
                if links:
                    paragraph_block["text"]["elements"] = self._create_text_elements_with_links(paragraph_text, links)
                
                blocks.append(paragraph_block)
            
            i += 1
        
        return blocks
    
    def _extract_links(self, text: str) -> tuple:
        """提取文本中的链接，返回(纯文本, 链接列表)"""
        # 匹配 [text](url) 格式的链接
        link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        links = []
        clean_text = text
        
        for match in re.finditer(link_pattern, text):
            link_text = match.group(1)
            link_url = match.group(2)
            links.append((link_text, link_url))
            # 将链接替换为纯文本
            clean_text = clean_text.replace(match.group(0), link_text)
        
        return clean_text, links
    
    def _create_text_elements_with_links(self, text: str, links: List[tuple]) -> List[Dict[str, Any]]:
        """创建包含链接的文本元素"""
        elements = []
        current_text = text
        
        for link_text, link_url in links:
            # 找到链接文本在原文中的位置
            link_start = current_text.find(link_text)
            if link_start > 0:
                # 添加链接前的文本
                elements.append({
                    "text_run": {
                        "content": current_text[:link_start]
                    }
                })
            
            # 添加链接
            elements.append({
                "text_run": {
                    "content": link_text,
                    "text_element_style": {
                        "link": {
                            "url": link_url
                        }
                    }
                }
            })
            
            # 更新剩余文本
            current_text = current_text[link_start + len(link_text):]
        
        # 添加剩余文本
        if current_text:
            elements.append({
                "text_run": {
                    "content": current_text
                }
            })
        
        return elements
    
    def insert_blocks_to_document(self, doc_token: str, blocks: List[Dict[str, Any]]) -> bool:
        """将块插入到飞书文档中 - 使用嵌套块创建API"""
        if not self.tenant_access_token:
            self.get_tenant_access_token()
        
        # 首先获取文档的根块ID
        root_block_id = self.get_document_root_block(doc_token)
        if not root_block_id:
            print("❌ 无法获取文档根块ID")
            return False
        
        print(f"🔍 找到根块ID: {root_block_id}")
        
        # 使用嵌套块创建API：批量创建子块
        success_count = 0
        
        # 分批处理，每批最多10个块
        batch_size = 10
        for i in range(0, len(blocks), batch_size):
            batch_blocks = blocks[i:i + batch_size]
            
            try:
                # 使用嵌套块创建API
                url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{root_block_id}/children"
                headers = {
                    "Authorization": f"Bearer {self.tenant_access_token}",
                    "Content-Type": "application/json; charset=utf-8"
                }
                
                # 构建请求数据
                data = {
                    "children": batch_blocks
                }
                
                response = requests.post(url, headers=headers, json=data)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("code") == 0:
                        batch_success = len(batch_blocks)
                        success_count += batch_success
                        print(f"✅ 成功插入第 {i//batch_size + 1} 批块 ({batch_success}个块)")
                    else:
                        print(f"❌ 插入第 {i//batch_size + 1} 批块失败: {result}")
                else:
                    print(f"❌ 插入第 {i//batch_size + 1} 批块失败，状态码: {response.status_code}")
                    print(f"响应内容: {response.text[:200]}...")
                
                # 避免请求过于频繁
                time.sleep(0.2)
                
            except Exception as e:
                print(f"❌ 插入第 {i//batch_size + 1} 批块时发生错误: {e}")
                continue
        
        if success_count > 0:
            print(f"✅ 成功插入 {success_count}/{len(blocks)} 个块")
            return success_count == len(blocks)
        else:
            print("❌ 没有成功插入任何块")
            return False
    
    def get_document_root_block(self, doc_token: str) -> Optional[str]:
        """获取文档的根块ID"""
        if not self.tenant_access_token:
            self.get_tenant_access_token()
        
        # 使用文档块列表API获取根块
        url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks"
        headers = {
            "Authorization": f"Bearer {self.tenant_access_token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        try:
            response = requests.get(url, headers=headers)
            
            print(f"🔍 获取文档块列表响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"🔍 获取文档块列表响应: {result}")
                
                if result.get("code") == 0:
                    # 获取根块信息
                    items = result.get("data", {}).get("items", [])
                    if items:
                        root_block = items[0]  # 第一个块就是根块
                        print(f"🔍 根块信息: {root_block}")
                        return root_block.get("block_id")
                    else:
                        print("❌ 未找到根块信息")
                else:
                    print(f"❌ 获取文档块列表失败: {result}")
            else:
                print(f"❌ 获取文档块列表失败，状态码: {response.status_code}")
                print(f"响应内容: {response.text[:500]}...")
                
        except Exception as e:
            print(f"❌ 获取文档块列表时发生错误: {e}")
        
        return None
    
    def get_latest_markdown_file(self, doc_dir: str = "doc") -> Optional[str]:
        """获取doc目录下最新的Markdown文件"""
        doc_path = Path(doc_dir)
        if not doc_path.exists():
            return None
        
        md_files = list(doc_path.rglob("*.md"))
        if not md_files:
            return None
        
        # 按修改时间排序，返回最新的
        latest_file = max(md_files, key=lambda x: x.stat().st_mtime)
        return str(latest_file)
    
    def process_latest_markdown(self) -> str:
        """处理最新的Markdown文件并创建飞书文档"""
        # 获取最新Markdown文件
        latest_md = self.get_latest_markdown_file()
        if not latest_md:
            raise Exception("未找到任何Markdown文件")
        
        print(f"📖 找到最新Markdown文件: {latest_md}")
        
        # 读取Markdown内容
        with open(latest_md, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        
        # 生成文档标题
        file_name = Path(latest_md).stem
        doc_title = f"{self.title_prefix}_{file_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 创建飞书文档
        doc_token = self.create_document(doc_title)
        
        # 转换Markdown为飞书块
        print("🔄 正在转换Markdown为飞书块格式...")
        blocks = self.markdown_to_feishu_blocks(markdown_content)
        print(f"✅ 转换完成，共生成 {len(blocks)} 个块")
        
        # 插入块到文档
        print("📝 正在将内容插入到飞书文档...")
        success = self.insert_blocks_to_document(doc_token, blocks)
        
        if success:
            print(f"🎉 成功处理Markdown文件并创建飞书文档!")
            print(f"📄 文档ID: {doc_token}")
            return doc_token
        else:
            # 即使部分失败，也返回文档ID
            print(f"⚠️ 部分内容插入失败，但文档已创建")
            print(f"📄 文档ID: {doc_token}")
            return doc_token
    
    def create_simple_document_with_content(self, title: str, content: str) -> str:
        """创建包含内容的简单飞书文档"""
        # 创建文档
        doc_token = self.create_document(title)
        
        # 转换内容为块
        blocks = self.markdown_to_feishu_blocks(content)
        
        # 插入块
        success = self.insert_blocks_to_document(doc_token, blocks)
        
        if success:
            print(f"🎉 成功创建包含内容的飞书文档!")
            return doc_token
        else:
            print(f"⚠️ 部分内容插入失败，但文档已创建")
            return doc_token


def main():
    """主函数"""
    try:
        # 初始化飞书文档管理器
        manager = FeishuDocManagerWorking()
        
        # 处理最新Markdown文件
        doc_token = manager.process_latest_markdown()
        
        print(f"\n🎯 任务完成!")
        print(f"📄 飞书文档ID: {doc_token}")
        print(f"🔗 文档链接: https://bytedance.feishu.cn/docx/{doc_token}")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
