# 简介
实现了宇树人形机器人G1edu与机器狗Go2Edu的二次开发，满足校园巡检，课堂助手，车辆违停识别，快递派送，校园导引五个场景的需求。

- 车辆违规报警功能：基于YOLO目标检测和PaddleOCR车牌识别的违停监控系统。通过LLM解析巡检点位，机器人自主导航至目标区域，检测违停车辆并识别车牌号码。支持多车牌同时识别，实时语音播报违停信息，并生成包含时间戳、位置、车牌信息的JSON格式检测报告。

- 快递派送功能：集成自然语言处理和自主导航的智能配送服务。系统通过LLM客户端解析用户指令中的目标地点，结合waypoint引擎进行路径规划，实现机器人自主导航到指定位置。配备多模态反馈机制，包括情感化语音提示和成功音效，同时支持实时任务状态监控和异常处理。

- 课堂巡检功能：通过YOLO模型检测学生睡觉、玩手机等异常行为，对教室环境进行智能监控。系统支持多教室批量巡检，自动生成包含异常行为详情、图像证据和统计数据的巡检报告。

- 课堂教学助手：通过集成LLM客户端实现自然语言问答，配合G1机械臂控制器执行启动挥手、告别飞吻等情感化手势。支持多轮对话交互，具备退出指令识别和会话管理功能。

- 校园导引：基于语义理解和自主导航的智能引路系统。通过LLM提取用户目标地点，结合waypoint引擎和A*+DWA算法实现路径规划。提供实时语音引导和情感化交互反馈，支持动态路径调整和异常处理。


# 安装
## 1. 硬件相关依赖
- g1 edu机器人或go2 edu机器人
- mid360激光雷达
- 扬声器、麦克风
## 2. 软件相关依赖
系统需求：Ubuntu20.04+ROS Noetic
第三方依赖库或工具（3rdparty）可在网盘获取：https://pan.quark.cn/s/f8e989c3894f?pwd=p5fb
提取码：p5fb
### 2.1 Cmake
需要升级cmake版本到3.20.1，这里采用源码安装

```bash
cd 3rdparty/cmake-3.20.1
./configure
make
sudo make install
```
然后终端输入`cmake --version`来查看是否正确安装。

### 2.2 Open3D
重定位模块需要用到open3d库，同样选择源码安装方式。安装方式参考：https://www.open3d.org/docs/0.14.1/compilation.html

机器人内置的Jetson nx为ARM架构，安装时直接看ARM support-Building Open3D directly（Open3D是0.14.1版本）

```bash
cd 3rdparty/Open3D-0.14.1
./utils/install_deps_ubuntu.sh
mkdir build && cd build
cmake -DBUILD_CUDA_MODULE=OFF -DBUILD_GUI=OFF ..
make -j6
sudo make install
```
如果在编译时遇到`could not find python3…`等报错，参考链接https://melonedo.github.io/2024/05/11/CMake-FindPython.html手动指定python路径。

### 1.3 move_base & map_server

```bash
sudo apt install ros-noetic-move-base ros-noetic-map-server
sudo apt install ros-noetic-global-planner ros-noetic-dwa-local-planner
```

### 1.4 Miniconda
miniconda安装参考https://www.anaconda.com/docs/getting-started/miniconda/install#aws-graviton2%2Farm64
安装完以后创建conda环境
```bash
conda create -n task python=3.8
```
### 1.5 unitree_sdk2_python
参考宇树官方GitHub安装
```bash
conda activate task
```
https://github.com/unitreerobotics/unitree_sdk2_python

### 1.6 cudnn 
cudnn安装参考https://blog.csdn.net/sinat_34774688/article/details/134790187
直接看3.配置cuda环境变量和4.配置cudnn的内容

### 1.7 pytorch & torchvision

安装参考https://forums.developer.nvidia.com/t/pytorch-for-jetson/72048

```bash
cd 3rdparty
conda activate task
sudo apt-get install python3-pip libopenblas-base libopenmpi-dev libomp-dev
pip install 'Cython<3'
pip install numpy torch-2.1.0a0+41361538.nv23.06-cp38-cp38-linux_aarch64.whl
sudo apt-get install libjpeg-dev zlib1g-dev libpython3-dev libopenblas-dev libavcodec-dev libavformat-dev libswscale-dev
cd 3rdparty/torchvision
conda activate task
export BUILD_VERSION=0.16.1
python setup.py install --user
pip uninstall urllib3
pip install urllib3==1.26.18
```
如果在执行`python setup.py install --user`卡住，说明内存不够，参考https://blog.csdn.net/Z960515/article/details/148791456添加交换空间

```bash
# 创建交换空间
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 永久添加交换空间（可选）
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

验证安装

```python
>>> import torch
>>> print(torch.__version__)
>>> print('CUDA available: ' + str(torch.cuda.is_available()))
>>> print('cuDNN version: ' + str(torch.backends.cudnn.version()))
>>> a = torch.cuda.FloatTensor(2).zero_()
>>> print('Tensor a = ' + str(a))
>>> b = torch.randn(2).cuda()
>>> print('Tensor b = ' + str(b))
>>> c = a + b
>>> print('Tensor c = ' + str(c))
>>> import torchvision
>>> print(torchvision.__version__)
```

### 1.8 tensorrt
宇树自带的出厂镜像应该已经安装了tensorrt及其python版本，只需将tensorrt python包复制到虚拟环境python安装包目录下

### 1.9 Livox-SDK2
按照https://github.com/Livox-SDK/Livox-SDK2的指引安装。

### 1.10 Livox-SDK & livox_ros_driver (for Fast_Lio)

由于fast_lio首先必须支持 Livox 系列激光雷达，因此必须安装 livox_ros_driver。
按照 Livox-SDK 和 livox_ros_driver的指引安装。

### 1.11 其他第三方库安装
```bash
sudo apt-get install tesseract-ocr
sudo apt-get install libasound-dev portaudio19-dev libportaudio2 libportaudiocpp0 libxml2-dev libxslt-dev
conda activate task
pip install -r requirements.txt
```
## 2. 编译
创建ros工作空间（go2和g1分别代表不同的机型，区别在于控制指令和规划器参数的不同编辑的时候复制对应机型下的文件到ros工作空间的src目录下即可）：

```bash
#Source livox_ros_driver before every build
cd ~/ws_livox/
source devel/setup.bash

#Build
mkdir -p ~/task_nav_ws/src
cd ~/task_nav_ws/src
# 复制对应机型的代码
cd ~/task_nav_ws
catkin_make -DROS_EDITION=ROS1
```
如果编译过程中出现`pose6D`相关报错，重新运行`catkin_make -DROS_EDITION=ROS1`即可

## 3. 参数配置
### 3.1 livox_ros_driver2
保证激光雷达ip地址正确。参考宇树G1激光雷达例程.
如果要修改激光雷达点云和imu的外参，在`livox_ros_driver2/config/MID360_config.json`中修改`extrinsic_parameter`即可。
### 3.2 fast-lio
默认的参数就OK，如要修改，参考FAST_LIO.
### 3.3 open3d_loc
将建好的点云地图放在data文件夹，修改`open3d_loc/launch/open3d_loc_g1.launch`中的`path_map`参数为正确的文件路径。支持ply和pcd。
```xml
<param name="path_map" type="string" value="$(find open3d_loc)/../data/map.ply" />
```

# 使用
## 1. 远程进入机器人桌面
首次远控：远控端安装nomachine，将显卡欺骗器插入扩展坞中。在nomachine中添加设备（注意需要提前得知机器人连接的wifi的ip地址），名字随便起，宇树默认用户名unitree，密码123。
之后直接打开nomachine双击设备连接即可（如果ip地址变化需要重复首次远控步骤）。

## 2. 建图
```bash
cd navtest_ws
./mapping.sh
```
用遥控器操控机器人在环境里走一圈，在后续要巡检的地方短按遥控器A键保存点位信息。巡检点会保存在`/src/task_system/data/waypoints/navigation_waypoints.json`文件中，后续可对巡检点改名。注意，改名后需要在`/src/task_system/src/prompt/location_extraction.txt`中把同样的地点名添加上。
建图完成后退出，点云地图自动保存到`/FAST_LIO/PCD`下。后面需要使用cloudcompare对点云地图进行微调，使点云地图的地面尽量和XOY平面贴合。流程如下视频：


https://github.com/user-attachments/assets/fafb983e-9fe5-4b78-bfb1-6693de80ddb4


完成后将点云文件保存到`/src/FAST_LIO_LOCALIZATION_HUMANOID/Navigation/config/map`文件夹下，改名为`map.pcd`，同时复制一份到`/src/FAST_LIO_LOCALIZATION_HUMANOID/data`中，然后用以下命令将3d点云转化为2d栅格地图：
```bash
cd navtest_ws
source devel/setup.bash
roslaunch fast_lio saver.launch
```
2D栅格地图地图的处理：由于建图有误差，最好对2D栅格地图处理一下
安装kolourpaint
```bash
sudo apt install kolourpaint
```
使用kolourpaint进行多余点的擦除等操作。

## 3. 任务执行
### 3.1 检查麦克风/扬声器设备
进入设置里的声音设备，确保输入输出设备正确。
### 3.2 启动相机驱动节点
进入终端（快捷键`ctrl+alt+t`），进入后按2然后回车进入ros环境。运行以下指令
```bash
roslaunch realsense2_camera rs_camera.launch
```
### 3.3 启动主系统
新开一个终端（快捷键`ctrl+alt+t`），进入后按2然后回车进入ros环境。运行以下指令
```bash
cd navtest_ws
./start.sh
```
会开启4个终端，前两个为定位导航模块，第三个是机器人本体控制模块，第四个是任务调度模块。
短按遥控器L1键开始录音，再短按L1结束录音，语音识别后机器人就可以根据指令完成不同的任务。
指令类型：
- 课堂助手：先说“课堂助手”进入课堂交互模式，然后再提问，如果要退出课堂交互模式，需要说“再见”或“结束交互”。
- 课堂巡检：指令为“去xxx教室检查”。关键词“教室”。
- 车辆违停巡检：指令为“去xxx检查违停车辆”。关键词“车辆”“违规停放”。
- 快递配送：指令为“把快递送到xxx地”。关键词“快递”。
- 导引：指令为“带我去xxx地”。关键词“带我去”。
如果要中途中止任务，需要在终端输入cancel结束任务，再下发新的指令。
巡检任务的报告保存在/src/task_system/data/detection_results中，分为课堂巡检任务和违停巡检任务两种。
如果要自定义课堂助手风格和自定义问题，修改/src/task_system/src/prompt/assistant_response.txt，按照里面的格式修改即可。
## 4. 修改导航速度
配置文件位于`src/FAST_LIO_LOCALIZATION_HUMANOID/Navigation/config/dwa_local_planner_params.yaml`
调整`acc_lim_x`和`max_vel_x`以达到最佳效果
另外，适当调整（增加yaw_goal_tolerance和xy_goal_tolerance）可以改善机器人在目标点周围震荡找不到停不下来的情况，但增加太大会影响导航精度。

## 5. 单独调试导航系统
```bash
# 启动导航系统
cd navtest_ws
source devel/setup.bash
roslaunch navigation nav_test.launch
# 启动激光雷达驱动
cd navtest_ws
source devel/setup.bash
roslaunch livox_ros_driver2 msg_MID360.launch
# 启动控制器
cd navtest_ws
conda activate task
./src/g1_base_controller/loco/g1_base_control.sh start
```
用2d nav goal工具发布目标点，轻按鼠标左键选择位置，按住不动选择位姿。
