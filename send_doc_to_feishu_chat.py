#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 doc 目录下最新的 Markdown 内容发送到飞书群聊。

用法示例：
  python3 send_doc_to_feishu_chat.py --dry-run
  python3 send_doc_to_feishu_chat.py --chat-id oc_xxx
  python3 send_doc_to_feishu_chat.py --file doc/2025/9/20250909.md --chat-id oc_xxx
  python3 send_doc_to_feishu_chat.py --format card   # 保留Markdown样式（默认）

依赖：requests
  pip3 install requests
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

import requests


CONFIG_PATH = "config.json"


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    data = {"app_id": app_id, "app_secret": app_secret}
    resp = requests.post(url, headers=headers, json=data, timeout=15)
    result = resp.json()
    if result.get("code") == 0:
        return result["tenant_access_token"]
    raise RuntimeError(f"获取tenant_access_token失败: {result}")


def find_latest_markdown(doc_dir: str = "doc") -> Optional[str]:
    doc_path = Path(doc_dir)
    if not doc_path.exists():
        return None
    md_files = list(doc_path.rglob("*.md"))
    if not md_files:
        return None
    latest = max(md_files, key=lambda p: p.stat().st_mtime)
    return str(latest)


def chunk_text(text: str, max_len: int = 8000) -> List[str]:
    # 尽量按换行安全切分，避免截断代码块/链接
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    for line in text.splitlines(True):  # 保留换行符
        line_len = len(line)
        if current_len + line_len <= max_len:
            current.append(line)
            current_len += line_len
        else:
            if current:
                chunks.append("".join(current))
            # 如果单行就超过限制，强制硬切
            if line_len > max_len:
                start = 0
                while start < line_len:
                    end = min(start + max_len, line_len)
                    chunks.append(line[start:end])
                    start = end
                current = []
                current_len = 0
            else:
                current = [line]
                current_len = line_len
    if current:
        chunks.append("".join(current))
    return chunks


def send_text_message_to_chat(tenant_token: str, chat_id: str, text: str) -> None:
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
    headers = {
        "Authorization": f"Bearer {tenant_token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload = {
        "receive_id": chat_id,
        "msg_type": "text",
        "content": json.dumps({"text": text}),
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=20)
    try:
        data = resp.json()
    except Exception:
        data = {"status": resp.status_code, "text": resp.text[:200]}
    if resp.status_code != 200 or data.get("code") not in (0, None):
        raise RuntimeError(f"发送消息失败: status={resp.status_code}, data={data}")


def send_interactive_markdown_to_chat(tenant_token: str, chat_id: str, markdown: str) -> None:
    """发送互动卡片，使用 lark_md 渲染 Markdown，保留标题/链接/列表样式"""
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
    headers = {
        "Authorization": f"Bearer {tenant_token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    card = {
        "config": {"wide_screen_mode": True},
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": markdown}}
        ]
    }
    payload = {
        "receive_id": chat_id,
        "msg_type": "interactive",
        "content": json.dumps(card, ensure_ascii=False),
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=20)
    try:
        data = resp.json()
    except Exception:
        data = {"status": resp.status_code, "text": resp.text[:200]}
    if resp.status_code != 200 or data.get("code") not in (0, None):
        raise RuntimeError(f"发送互动卡片失败: status={resp.status_code}, data={data}")


def transform_markdown_for_card(markdown: str) -> str:
    """将 Markdown 转为飞书 lark_md 友好格式：
    - 将 #/##/### 标题转为加粗行（保留原有超链接）
    - 保留以 '- ' 开头的无序列表
    - 规范空行，避免连续多空行
    """
    lines: List[str] = []
    prev_blank = False
    for raw in markdown.splitlines():
        line = raw.rstrip()
        stripped = line.lstrip()
        if not stripped:
            if not prev_blank:
                lines.append("")
                prev_blank = True
            continue
        prev_blank = False
        # 标题：以一个或多个 # 开头
        if stripped.startswith('#'):
            # 去掉起始 # 和空格
            title = stripped.lstrip('#').strip()
            if title:
                lines.append(f"**{title}**")
            else:
                lines.append("")
            continue
        # 其他行直接保留
        lines.append(line)
    # 合并为文本
    text = "\n".join(lines)
    # 飞书 lark_md 不支持标题语法，但支持列表；保证 '- ' 前有换行
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="发送 doc 下 Markdown 到飞书群聊")
    parser.add_argument("--file", dest="file", help="指定要发送的 Markdown 文件路径")
    parser.add_argument("--chat-id", dest="chat_id", help="飞书群聊 chat_id，留空则读取 config.feishu.default_chat_id")
    parser.add_argument("--doc-dir", dest="doc_dir", default="doc", help="Markdown 根目录，默认 doc")
    parser.add_argument("--dry-run", action="store_true", help="仅打印将要发送的内容，不实际发送")
    parser.add_argument("--format", dest="fmt", choices=["text", "card"], default="card", help="发送格式：text 或 card(保留Markdown样式)")
    args = parser.parse_args()

    if not os.path.exists(CONFIG_PATH):
        print(f"未找到配置文件: {CONFIG_PATH}")
        return 1

    config = load_config(CONFIG_PATH)
    feishu_cfg = config.get("feishu", {})
    app_id = feishu_cfg.get("app_id")
    app_secret = feishu_cfg.get("app_secret")
    default_chat_id = feishu_cfg.get("default_chat_id") or ""

    chat_id = args.chat_id or default_chat_id

    md_file = args.file or find_latest_markdown(args.doc_dir)
    if not md_file or not os.path.exists(md_file):
        print("未找到要发送的 Markdown 文件。")
        return 1

    with open(md_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 清理文末可能残留的独立代码围栏，避免出现单独的 ``` 行
    content_lines = content.rstrip().splitlines()
    while content_lines and content_lines[-1].strip() in ("```", "'''"):
        content_lines.pop()
    cleaned_content = "\n".join(content_lines)

    # 统一增加标题与末尾链接（去掉 @ 前缀）
    title_line = "**今日资讯已送达**" if args.fmt == "card" else "今日资讯已送达"
    footer_line = "往期内容请查看 https://ksmoe124x4.feishu.cn/wiki/VGz8w3AOfinJi0kazZOc8Eb9nlb"
    content_with_header_footer = f"{title_line}\n\n{cleaned_content}\n\n{footer_line}\n"

    if args.fmt == "card":
        content_to_send = transform_markdown_for_card(content_with_header_footer)
    else:
        content_to_send = content_with_header_footer

    chunks = chunk_text(content_to_send, max_len=8000 if (not args.fmt or args.fmt == "card") else 2800)

    if args.dry_run:
        print(f"[dry-run] 将发送到 chat_id={chat_id or '(未设置)'}，文件: {md_file}")
        print(f"[dry-run] 分段数量: {len(chunks)}，格式: {args.fmt}")
        for idx, ck in enumerate(chunks, 1):
            print("-" * 30)
            print(f"[chunk {idx}]\n{ck}")
        return 0

    if not chat_id:
        print("未提供 chat_id。请使用 --chat-id 或在 config.json 的 feishu.default_chat_id 中配置。")
        return 1

    if not app_id or not app_secret:
        print("config.json 中缺少 feishu.app_id 或 feishu.app_secret。")
        return 1

    try:
        tenant_token = get_tenant_access_token(app_id, app_secret)
    except Exception as e:
        print(f"获取租户token失败: {e}")
        return 1

    for idx, ck in enumerate(chunks, 1):
        try:
            if args.fmt == "card":
                # 多段时分多张卡片
                header = f"(第{idx}/{len(chunks)}段)\n" if len(chunks) > 1 else ""
                send_interactive_markdown_to_chat(tenant_token, chat_id, header + ck)
            else:
                prefix = f"(第{idx}/{len(chunks)}段)\n" if len(chunks) > 1 else ""
                send_text_message_to_chat(tenant_token, chat_id, prefix + ck)
            print(f"已发送第 {idx}/{len(chunks)} 段")
        except Exception as e:
            print(f"发送第 {idx} 段失败: {e}")
            return 1

    print(f"✅ 已将 {md_file} 内容发送到群聊 {chat_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


