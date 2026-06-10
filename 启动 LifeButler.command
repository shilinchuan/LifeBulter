#!/bin/zsh

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  osascript -e 'display alert "LifeButler 无法启动" message "未找到 .venv/bin/python。请先在终端进入 LifeButler 目录，创建虚拟环境并安装 requirements.txt。" as warning' >/dev/null 2>&1
  echo "LifeButler 无法启动：未找到 .venv/bin/python"
  echo
  echo "请先执行："
  echo "  cd \"$SCRIPT_DIR\""
  echo "  python3 -m venv .venv"
  echo "  source .venv/bin/activate"
  echo "  pip install -r requirements.txt"
  echo
  echo "按任意键关闭此窗口..."
  read -k 1
  exit 1
fi

echo "Starting LifeButler..."
echo "Project: $SCRIPT_DIR"
echo "Python:  $PYTHON_BIN"
echo
echo "退出方式：在这个 Terminal 窗口按 Ctrl+C，或使用系统托盘菜单的“退出”。"
echo

exec "$PYTHON_BIN" "$SCRIPT_DIR/main.py"
