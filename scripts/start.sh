#!/bin/bash

# ======================
# 终端1：启动 nav_test.launch
# ======================
gnome-terminal -- bash -c "
    source /opt/ros/noetic/setup.bash
    cd ~/navtest_ws && source devel/setup.bash
    roslaunch navigation nav_test.launch
    exec bash
"

sleep 3

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
# 终端3：conda 环境 + go2_base_control.sh
# ======================
gnome-terminal -- bash -c "
    eval \"\$(conda shell.bash hook)\"
    conda activate task
    cd ~/navtest_ws
    ./src/go2_base_controller/loco/go2_base_control.sh start
    exec bash
"

sleep 1

# ======================
# 终端4：conda 环境 + main_system.py
# ======================
gnome-terminal -- bash -c "
    eval \"\$(conda shell.bash hook)\"
    conda activate task
    cd ~/navtest_ws
    python src/task_system/src/voice_integrated_system.py
    exec bash
"
