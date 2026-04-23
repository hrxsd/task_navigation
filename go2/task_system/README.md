# G1 智能任务系统

基于G1人形机器人的多功能任务执行系统，支持校园巡检、车辆违停识别、快递派送、校园导引和课堂助手等多种应用场景。

## 功能特性

### 🎯 五大核心任务

1. **教室巡检** - 检查学生行为（睡觉、玩手机等）
2. **车辆违停巡检** - 识别违停车辆和车牌号
3. **快递派送** - 自动导航到指定地点派送物品
4. **校园导引** - 引导用户到达目标教室或地点
5. **课堂助手** - 智能问答交互，配合手臂动作

### 🧠 智能特性

- **自然语言理解** - 使用LLM进行意图识别和任务分析
- **智能导航** - 基于导航点的路径规划和避障
- **视觉检测** - 集成YOLO模型进行实时目标检测（待训练）
- **语音交互** - 支持语音输入输出（当前为终端模拟）
- **手臂动作** - 配合对话进行手势表达

## 系统架构

```
task_system/
├── src/                    # 源代码
│   ├── core/              # 核心模块
│   │   ├── task_manager.py    # 任务管理器
│   │   └── waypoint_engine.py # 导航点引擎
│   ├── tasks/             # 具体任务实现
│   │   ├── classroom_patrol_task.py
│   │   ├── vehicle_patrol_task.py
│   │   ├── delivery_task.py
│   │   ├── guide_task.py
│   │   └── assistant_task.py
│   ├── llm/               # LLM接口
│   ├── ros_interface/     # ROS接口
│   ├── prompts/          # 提示词模板
│   └── main_system.py    # 主程序入口
├── config/               # 配置文件
├── data/                # 数据存储
│   ├── waypoints/       # 导航点数据
│   ├── detection_results/ # 检测结果
│   └── logs/           # 日志文件
└── run_task_system.sh  # 启动脚本
```

## 快速开始

### 环境要求

- Ubuntu 18.04/20.04
- ROS Melodic/Noetic
- Python 3.6+
- G1机器人硬件

### 依赖安装

```bash
# ROS依赖
sudo apt-get install ros-$ROS_DISTRO-move-base
sudo apt-get install ros-$ROS_DISTRO-cv-bridge

# Python依赖
pip3 install openai pyyaml opencv-python numpy
```

### 启动系统

```bash
# 进入task_system目录
cd g1/task_system

# 启动系统
./run_task_system.sh
```

### 配置说明

编辑 `config/task_config.yaml` 来配置系统参数：

```yaml
# LLM配置
llm:
  api_key: "your-openai-api-key"
  api_base: "https://api.openai.com/v1"
  model: "gpt-4"

# 任务配置
tasks:
  classroom_patrol:
    enabled: true
    default_classrooms: ["音乐教室", "舞蹈教室", "数学教室"]
    
# 导航点数据路径
database:
  waypoints_path: "./data/waypoints/navigation_points.json"
```

## 使用示例

### 任务指令示例

```bash
# 教室巡检
"巡检所有教室"
"检查音乐教室的学生行为"

# 车辆违停巡检  
"检查违停车辆"
"巡视大门口停车情况"

# 快递派送
"把快递送到音乐教室"
"派送包裹到大门口"

# 校园导引
"带我去数学教室"
"导引到大门口"

# 课堂助手
"我有个数学问题"
"和我聊聊"
```

### 系统命令

```bash
# 查看系统状态
status

# 查看可用导航点
waypoints

# 取消当前任务
cancel

# 退出系统
quit
```

## 导航点管理

导航点数据存储在 `data/waypoints/navigation_points.json`：

```json
[
  {
    "id": 1,
    "name": "音乐教室",
    "position": [1.39, 0.06, 0.19],
    "timestamp": 1754536431.48
  }
]
```

可以使用导航点记录器添加新的导航点：

```bash
cd g1/task_system/src
python3 navigation_point_recorder.py
```

## 开发说明

### 添加新任务

1. 继承 `BaseTask` 类
2. 实现 `execute()` 方法
3. 在 `TaskManager` 中注册新任务
4. 更新提示词模板

### 扩展LLM功能

1. 在 `llm/llm_client.py` 添加新方法
2. 在 `prompts/` 目录添加对应提示词
3. 在 `_load_prompts()` 方法中加载

### 集成硬件

- 相机：修改 `ros_interface/camera_interface.py`
- 音频：修改 `ros_interface/audio_interface.py`  
- 手臂：使用 `g1_base_controller/arm/arm_controller.py`

## 技术特点

### 模块化设计
- 清晰的模块分离
- 统一的任务接口
- 可扩展的架构

### 智能决策
- LLM驱动的意图识别
- 上下文感知的任务执行
- 多模态信息融合

### 鲁棒性
- 完善的错误处理
- 任务状态管理
- 优雅的降级机制

## 故障排除

### 常见问题

1. **ROS连接失败**
   - 检查ROS环境是否正确sourced
   - 确认roscore已启动

2. **导航失败**
   - 检查move_base是否运行
   - 验证导航点坐标是否正确

3. **LLM API错误**
   - 验证API密钥是否有效
   - 检查网络连接

4. **相机无图像**
   - 确认相机话题是否发布
   - 检查相机硬件连接

### 日志查看

```bash
# ROS日志
roslog show

# 系统日志
tail -f data/logs/task_system.log
```

## 贡献指南

欢迎提交Issue和Pull Request来完善这个项目。

## 许可证

MIT License

## 联系方式

如有问题，请联系开发团队。 