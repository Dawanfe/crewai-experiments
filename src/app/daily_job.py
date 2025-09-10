#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日任务编排（模块化）：
- 生成当日 Markdown（调用 app.reddit_newsletter）
- 基于当日 Markdown 创建飞书文档（调用 app.feishu_doc_manager_final）
- 将 Markdown 内容发送到飞书群（卡片样式，调用 app.send_doc_to_feishu_chat）
- 提交 Markdown 到 git 并推送
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, List


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOC_ROOT = PROJECT_ROOT / "doc"


def run_cmd(cmd: List[str], cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=check)


def today_md_path() -> Path:
    now = time.localtime()
    year = time.strftime("%Y", now)
    month = time.strftime("%m", now)
    date = time.strftime("%Y%m%d", now)
    return DOC_ROOT / year / month / f"{date}.md"


def ensure_markdown_generated(dry_run: bool) -> Path:
    md_path = today_md_path()
    if md_path.exists():
        return md_path
    if dry_run:
        print(f"[dry-run] 将运行 app.reddit_newsletter 以生成 {md_path}")
        return md_path
    print("▶ 生成今日 Markdown ...")
    proc = run_cmd([sys.executable, "-m", "app.reddit_newsletter"], cwd=PROJECT_ROOT, check=False)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise RuntimeError("生成 Markdown 失败（app.reddit_newsletter 返回非零）")
    if not md_path.exists():
        latest = list(DOC_ROOT.rglob("*.md"))
        if not latest:
            raise FileNotFoundError("未找到生成的 Markdown 文件")
        md_path = max(latest, key=lambda p: p.stat().st_mtime)
    print(f"✅ 生成完成: {md_path}")
    return md_path


def create_feishu_document(dry_run: bool) -> None:
    if dry_run:
        print("[dry-run] 将调用 app.feishu_doc_manager_final 创建飞书文档（使用最新 md）")
        return
    print("▶ 创建飞书文档 ...")
    proc = run_cmd([sys.executable, "-m", "app.feishu_doc_manager_final"], cwd=PROJECT_ROOT, check=False)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise RuntimeError("创建飞书文档失败")
    print("✅ 飞书文档创建完毕")


def send_to_feishu_chat(md_path: Path, dry_run: bool) -> None:
    print("▶ 发送到飞书群 ...")
    if dry_run and not md_path.exists():
        print(f"[dry-run] 当日 Markdown 不存在，跳过发送：{md_path}")
        return
    cmd = [
        sys.executable,
        "-m",
        "app.send_doc_to_feishu_chat",
        "--file",
        str(md_path),
        "--format",
        "card",
    ]
    if dry_run:
        cmd.append("--dry-run")
    proc = run_cmd(cmd, cwd=PROJECT_ROOT, check=False)
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        raise RuntimeError("发送到飞书群失败")
    print("✅ 群消息发送完成")


def git_commit_and_push(md_path: Path, dry_run: bool) -> None:
    rel = md_path.relative_to(PROJECT_ROOT)
    print("▶ 提交 Markdown 至 git ...")
    if dry_run:
        print(f"[dry-run] git add {rel}; git commit -m 'Auto: add {rel}'; git push")
        return
    proc_add = run_cmd(["git", "add", str(rel)], cwd=PROJECT_ROOT, check=False)
    if proc_add.returncode != 0:
        print(proc_add.stdout)
        print(proc_add.stderr, file=sys.stderr)
        raise RuntimeError("git add 失败")
    commit_msg = f"Auto: add {rel}"
    proc_commit = run_cmd(["git", "commit", "-m", commit_msg], cwd=PROJECT_ROOT, check=False)
    if proc_commit.returncode != 0:
        if "nothing to commit" in (proc_commit.stdout + proc_commit.stderr):
            print("ℹ️ 无需提交")
        else:
            print(proc_commit.stdout)
            print(proc_commit.stderr, file=sys.stderr)
            raise RuntimeError("git commit 失败")
    proc_push = run_cmd(["git", "push"], cwd=PROJECT_ROOT, check=False)
    if proc_push.returncode != 0:
        print(proc_push.stdout)
        print(proc_push.stderr, file=sys.stderr)
        raise RuntimeError("git push 失败")
    print("✅ 已推送到远端仓库")


def main() -> int:
    parser = argparse.ArgumentParser(description="每日任务编排器（模块化版）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印动作，不执行")
    args = parser.parse_args()

    try:
        md_path = ensure_markdown_generated(args.dry_run)
        create_feishu_document(args.dry_run)
        send_to_feishu_chat(md_path, args.dry_run)
        git_commit_and_push(md_path, args.dry_run)
        print("\n🎯 全部流程完成")
        return 0
    except Exception as e:
        print(f"❌ 失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())


