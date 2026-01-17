#!/bin/bash

# 获取脚本所在目录
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# 进入项目目录
cd "$DIR"

echo "🚀 Starting BTC Dashboard..."

# 检查是否已有运行中的实例
PID=$(pgrep -f "python.*app.py")
if [ -n "$PID" ]; then
    echo "⚠️  Found existing instance (PID: $PID). Restarting..."
    kill $PID
    sleep 2
fi

# 启动服务器（后台运行）
/Users/jack/opt/anaconda3/bin/python "$DIR/btc_web/app.py" > "$DIR/btc_web/server.log" 2>&1 &

echo "✅ Server started!"
echo "📊 Opening dashboard in browser..."
sleep 2

# 打开浏览器
open http://127.0.0.1:5050

echo "Running... (Logs in btc_web/server.log)"
