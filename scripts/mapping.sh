#!/bin/bash

# ======================
# 终端1：启动 fast_lio
# ======================
gnome-terminal -- bash -c "
    source /opt/ros/noetic/setup.bash
    cd ~/navtest_ws && source devel/setup.bash
    roslaunch fast_lio mapping.launch
    exec bash
"

sleep 1

# ======================
# 终端2：启动 livox_ros_driver2
# ======================
gnome-terminal -- bash -c "
    source /opt/ros/noetic/setup.bash
    cd ~/navtest_ws && source devel/setup.bash
    roslaunch livox_ros_driver2 msg_MID360.launch
    exec bash
"

sleep 1

# ======================
# 终端3：启动 conda 环境 + Python 脚本
# ======================
gnome-terminal -- bash -c "
    eval \"\$(conda shell.bash hook)\"
    conda activate task
    cd ~/navtest_ws
    python src/task_system/src/navigation_point_recorder.py
    exec bash
"