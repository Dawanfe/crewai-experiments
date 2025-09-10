#!/bin/zsh
set -euo pipefail

PLIST_SRC="$(cd "$(dirname "$0")"/.. && pwd)/com.crewai.dailyjob.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.crewai.dailyjob.plist"

mkdir -p "$HOME/Library/LaunchAgents"
cp -f "$PLIST_SRC" "$PLIST_DST"

# 重新加载 launchd 任务
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"
launchctl list | grep -q "com.crewai.dailyjob" && echo "Loaded com.crewai.dailyjob"

echo "安装完成。可用以下命令手动触发："
echo "  launchctl start com.crewai.dailyjob"

