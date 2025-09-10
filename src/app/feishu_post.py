#!/usr/bin/env python3
"""
Feishu/Lark IM post message sender (chat rich-text)

Features
- List chats to obtain chat_id
- Find chat_id by chat name (exact or fuzzy)
- Send rich-text (post) message with optional link, mention, and image

Usage examples
- List first 50 chats:
    python feishu_post.py list-chats --token $FEISHU_TENANT_ACCESS_TOKEN

- Send a basic post to a chat by chat_id:
    python feishu_post.py send \
        --token $FEISHU_TENANT_ACCESS_TOKEN \
        --chat-id oc_xxx \
        --title "通知标题" \
        --text "这是一段文本" \
        --link-text "查看详情" \
        --link-url "https://example.com"

- Send by chat name (will search user's joined chats and pick the best match):
    python feishu_post.py send \
        --token $FEISHU_TENANT_ACCESS_TOKEN \
        --chat-name "项目群A" \
        --title "通知标题" \
        --text "这是一段文本"

- Use a full JSON content payload from file (overrides other content flags):
    python feishu_post.py send \
        --token $FEISHU_TENANT_ACCESS_TOKEN \
        --chat-id oc_xxx \
        --content-file ./post_content.json

Environment
- You can also set FEISHU_TENANT_ACCESS_TOKEN to avoid passing --token

Notes
- The send API requires content to be a JSON string; this script handles re-serialization automatically.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import requests


BASE_URL = "https://open.feishu.cn/open-apis"


class FeishuIMClient:
    def __init__(self, tenant_access_token: str) -> None:
        if not tenant_access_token:
            raise ValueError("tenant_access_token 为空。请通过 --token 或环境变量 FEISHU_TENANT_ACCESS_TOKEN 提供")
        self.tenant_access_token = tenant_access_token
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.tenant_access_token}",
            "Content-Type": "application/json; charset=utf-8",
        })

    def list_chats(self, page_size: int = 50, page_token: Optional[str] = None) -> Dict[str, Any]:
        params = {"page_size": page_size}
        if page_token:
            params["page_token"] = page_token
        url = f"{BASE_URL}/im/v1/chats"
        resp = self._session.get(url, params=params)
        self._ensure_ok(resp)
        return resp.json()

    def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        url = f"{BASE_URL}/im/v1/chats/{chat_id}"
        resp = self._session.get(url)
        self._ensure_ok(resp)
        return resp.json()

    def send_post_message(self, receive_id: str, content_obj: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{BASE_URL}/im/v1/messages"
        params = {"receive_id_type": "chat_id"}
        # API 需要 content 是字符串，这里进行二次序列化
        payload = {
            "receive_id": receive_id,
            "msg_type": "post",
            "content": json.dumps(content_obj, ensure_ascii=False),
        }
        resp = self._session.post(url, params=params, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        self._ensure_ok(resp)
        return resp.json()

    @staticmethod
    def _ensure_ok(resp: requests.Response) -> None:
        try:
            data = resp.json()
        except Exception:
            resp.raise_for_status()
            return
        # Feishu returns {code: 0} on success in many APIs
        if resp.status_code >= 400 or (isinstance(data, dict) and data.get("code") not in (None, 0)):
            # Provide detailed context for troubleshooting
            raise RuntimeError(f"Feishu API error: status={resp.status_code}, body={json.dumps(data, ensure_ascii=False)}")


def build_post_content(
    title: str,
    text: Optional[str] = None,
    link_text: Optional[str] = None,
    link_url: Optional[str] = None,
    at_user_id: Optional[str] = None,
    image_key: Optional[str] = None,
) -> Dict[str, Any]:
    content_lines: List[List[Dict[str, Any]]] = []

    line: List[Dict[str, Any]] = []
    if text:
        line.append({"tag": "text", "text": text + (" " if link_text or link_url else "")})
    if link_text and link_url:
        line.append({"tag": "a", "text": link_text, "href": link_url})
    if line:
        content_lines.append(line)

    if at_user_id:
        content_lines.append([{"tag": "at", "user_id": at_user_id}])

    if image_key:
        content_lines.append([{"tag": "img", "image_key": image_key}])

    if not content_lines:
        # Ensure at least one text line if nothing provided
        content_lines.append([{"tag": "text", "text": ""}])

    return {
        "post": {
            "zh_cn": {
                "title": title,
                "content": content_lines,
            }
        }
    }


def find_chat_id_by_name(client: FeishuIMClient, chat_name: str, page_limit: int = 5) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Find chat by name with a simple best-effort strategy (case-sensitive exact first, then fuzzy).

    Returns (chat_id, item) or (None, None)
    """
    next_token: Optional[str] = None
    matched_exact: Optional[Tuple[str, Dict[str, Any]]] = None
    matched_fuzzy: Optional[Tuple[str, Dict[str, Any]]] = None

    for _ in range(page_limit):
        data = client.list_chats(page_size=50, page_token=next_token)
        items = (data.get("data") or {}).get("items") or []
        for item in items:
            name = item.get("name") or ""
            chat_id = item.get("chat_id")
            if not chat_id:
                continue
            if name == chat_name and not matched_exact:
                matched_exact = (chat_id, item)
            if chat_name in name and not matched_fuzzy:
                matched_fuzzy = (chat_id, item)
        next_token = (data.get("data") or {}).get("page_token")
        if not next_token:
            break

    if matched_exact:
        return matched_exact
    if matched_fuzzy:
        return matched_fuzzy
    return None, None


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Feishu IM 富文本(post)消息工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list-chats command
    list_parser = subparsers.add_parser("list-chats", help="列出加入的群")
    list_parser.add_argument("--token", default=os.getenv("FEISHU_TENANT_ACCESS_TOKEN"), help="tenant_access_token；也可用环境变量 FEISHU_TENANT_ACCESS_TOKEN")
    list_parser.add_argument("--page-size", type=int, default=50, help="每页数量，默认 50")

    # send command
    send_parser = subparsers.add_parser("send", help="发送 post 富文本到群")
    send_parser.add_argument("--token", default=os.getenv("FEISHU_TENANT_ACCESS_TOKEN"), help="tenant_access_token；也可用环境变量 FEISHU_TENANT_ACCESS_TOKEN")
    chat_group = send_parser.add_mutually_exclusive_group(required=True)
    chat_group.add_argument("--chat-id", help="目标群 chat_id")
    chat_group.add_argument("--chat-name", help="目标群名称（将搜索并匹配）")
    send_parser.add_argument("--title", required=True, help="消息标题")
    send_parser.add_argument("--text", help="第一行文本内容")
    send_parser.add_argument("--link-text", help="可选：链接文字")
    send_parser.add_argument("--link-url", help="可选：链接地址，与 --link-text 搭配使用")
    send_parser.add_argument("--at-user-id", help="可选：@用户的 user_id")
    send_parser.add_argument("--image-key", help="可选：图片 image_key")
    send_parser.add_argument("--content-file", help="可选：JSON 文件，作为完整 content 对象（优先级最高）")

    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)

    if args.command == "list-chats":
        client = FeishuIMClient(args.token)
        data = client.list_chats(page_size=args.page_size)
        items = (data.get("data") or {}).get("items") or []
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return 0

    if args.command == "send":
        client = FeishuIMClient(args.token)

        if args.chat_id:
            chat_id = args.chat_id
        else:
            chat_id, item = find_chat_id_by_name(client, args.chat_name)
            if not chat_id:
                print(f"未找到名称包含 '{args.chat_name}' 的群。", file=sys.stderr)
                return 1
            print(f"已匹配群: name='{(item or {}).get('name')}', chat_id='{chat_id}'")

        # Determine content
        if args.content_file:
            with open(args.content_file, "r", encoding="utf-8") as f:
                content_obj = json.load(f)
        else:
            content_obj = build_post_content(
                title=args.title,
                text=args.text,
                link_text=args.link_text,
                link_url=args.link_url,
                at_user_id=args.at_user_id,
                image_key=args.image_key,
            )

        resp = client.send_post_message(chat_id, content_obj)
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return 0

    print("未知命令", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


