#!/bin/bash

# G1 Task System Launcher
# G1 任务系统启动脚本

echo "🤖 Starting G1 Task System..."
echo "正在启动 G1 任务系统..."

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Please install Python3."
    exit 1
fi

# 检查ROS环境
if [ -z "$ROS_PACKAGE_PATH" ]; then
    echo "⚠️  Warning: ROS environment not detected. Attempting to source ROS..."
    if [ -f "/opt/ros/noetic/setup.bash" ]; then
        source /opt/ros/noetic/setup.bash
        echo "✅ ROS Noetic sourced"
    elif [ -f "/opt/ros/melodic/setup.bash" ]; then
        source /opt/ros/melodic/setup.bash  
        echo "✅ ROS Melodic sourced"
    else
        echo "❌ ROS not found. Please install and source ROS."
        exit 1
    fi
fi

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
SYSTEM_DIR="$SCRIPT_DIR/src"
CONFIG_FILE="$SCRIPT_DIR/config/task_config.yaml"

# 检查配置文件
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# 检查导航点文件
WAYPOINTS_FILE="$SCRIPT_DIR/data/waypoints/navigation_points.json"
if [ ! -f "$WAYPOINTS_FILE" ]; then
    echo "❌ Waypoints file not found: $WAYPOINTS_FILE"
    echo "请确保导航点文件存在: $WAYPOINTS_FILE"
    exit 1
fi

# 设置Python路径
export PYTHONPATH="$SYSTEM_DIR:$PYTHONPATH"

echo "📁 System directory: $SYSTEM_DIR"
echo "⚙️  Configuration file: $CONFIG_FILE"
echo "📍 Waypoints file: $WAYPOINTS_FILE"
echo ""

# 启动系统
cd "$SYSTEM_DIR"
python3 main_system.py "$CONFIG_FILE"

echo "🛑 Task System stopped."
echo "任务系统已停止。" 