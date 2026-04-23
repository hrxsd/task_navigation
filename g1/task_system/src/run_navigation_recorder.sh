#!/bin/bash

# 导航点记录程序启动脚本

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 切换到脚本目录
cd "$SCRIPT_DIR"

# 检查Python文件是否存在
if [ ! -f "navigation_point_recorder.py" ]; then
    echo "Error: navigation_point_recorder.py not found in $SCRIPT_DIR"
    exit 1
fi

# 设置可执行权限
chmod +x navigation_point_recorder.py

echo "Starting Navigation Point Recorder..."
echo "Press Ctrl+C to stop the program and save the recorded points."
echo ""

# 运行程序
python3 navigation_point_recorder.py 