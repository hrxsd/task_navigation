#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
任务管理器
负责任务意图识别、任务调度和执行
"""

import os
import sys
import json
import yaml
import rospy
import threading
from typing import Dict, Optional, List
from enum import Enum

from llm.llm_client import LLMClient
from tasks.classroom_patrol_task import ClassroomPatrolTask
from tasks.vehicle_patrol_task import VehiclePatrolTask
from tasks.delivery_task import DeliveryTask
from tasks.guide_task import GuideTask
from tasks.assistant_task import AssistantTask
from core.waypoint_engine import WaypointEngine


class TaskType(Enum):
    """任务类型枚举"""
    CLASSROOM_PATROL = "classroom_patrol"
    VEHICLE_PATROL = "vehicle_patrol"
    DELIVERY = "delivery"
    GUIDE = "guide"
    ASSISTANT = "assistant"
    UNKNOWN = "unknown"


class TaskStatus(Enum):
    """任务状态枚举"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskManager:
    """任务管理器"""
    
    def __init__(self, config_path: str):
        """
        初始化任务管理器
        
        Args:
            config_path: 配置文件路径
        """
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
            
        # 初始化核心组件
        self.llm_client = LLMClient(
            api_key=self.config['llm']['api_key'],
            api_base=self.config['llm']['api_base'],
            model=self.config['llm']['model']
        )
        self.waypoint_engine = WaypointEngine(
            self.config['database']['waypoints_path']
        )
        
        # 任务管理状态
        self.current_task: Optional = None
        self.current_task_type: Optional[TaskType] = None
        self.task_status = TaskStatus.IDLE
        self.task_thread: Optional[threading.Thread] = None
        self.stop_flag = threading.Event()  # 添加停止标志
        
        # 交互式任务支持
        self.is_interactive_task = False
        self.interactive_input_queue = []
        self.interactive_lock = threading.Lock()
        
        # 初始化任务执行器
        self.task_executors = {}
        self._init_task_executors()
        
        rospy.loginfo("Task Manager initialized")
        
    def _init_task_executors(self):
        """初始化所有任务执行器"""
        try:
            self.task_executors = {
                TaskType.CLASSROOM_PATROL: ClassroomPatrolTask(
                    self.config, self.waypoint_engine
                ),
                TaskType.VEHICLE_PATROL: VehiclePatrolTask(
                    self.config, self.waypoint_engine
                ),
                TaskType.DELIVERY: DeliveryTask(
                    self.config, self.waypoint_engine
                ),
                TaskType.GUIDE: GuideTask(
                    self.config, self.waypoint_engine
                ),
                TaskType.ASSISTANT: AssistantTask(
                    self.config, self.waypoint_engine
                )
            }
            rospy.loginfo("Task executors initialized")
            
        except Exception as e:
            rospy.logerr(f"Error initializing task executors: {e}")
            self.task_executors = {}

    def process_user_input(self, user_input: str) -> Dict:
        """
        处理用户输入
        
        Args:
            user_input: 用户输入文本
            
        Returns:
            Dict: 处理结果
        """
        try:
            # 检查是否是交互式任务的输入
            if self.is_interactive_task and self.task_status == TaskStatus.RUNNING:
                rospy.loginfo(f"Processing interactive input for {self.current_task_type.value}")
                self._handle_interactive_input(user_input)
                return {
                    "success": True,
                    "message": "交互输入已处理",
                    "task_type": "interactive_input"
                }
            
            # 检查是否有正在运行的任务
            if self.task_status == TaskStatus.RUNNING:
                return {
                    "success": False,
                    "message": "有任务正在执行中，请先取消当前任务或等待完成",
                    "task_type": "conflict"
                }
            
            # 分析任务意图
            task_type = self.analyze_task_intent(user_input)
            
            if task_type == TaskType.UNKNOWN:
                return {
                    "success": False,
                    "message": "无法识别您的请求，请尝试更明确的表达",
                    "task_type": "unknown"
                }
            
            # 检查是否是交互式任务
            if task_type == TaskType.ASSISTANT:
                return self._execute_interactive_task(task_type, user_input)
            else:
                return self._execute_task_async(task_type, user_input)
            
        except Exception as e:
            rospy.logerr(f"Error processing user input: {e}")
            return {
                "success": False,
                "message": f"处理请求时发生错误: {e}",
                "task_type": "error"
            }
            
    def analyze_task_intent(self, user_input: str) -> TaskType:
        """
        分析任务意图
        
        Args:
            user_input: 用户输入
            
        Returns:
            TaskType: 识别的任务类型
        """
        try:
            # 使用LLM分析意图
            intent = self.llm_client.analyze_task_intent(user_input)
            
            # 映射到任务类型
            task_mapping = {
                "classroom_patrol": TaskType.CLASSROOM_PATROL,
                "vehicle_patrol": TaskType.VEHICLE_PATROL,
                "delivery": TaskType.DELIVERY,
                "guide": TaskType.GUIDE,
                "assistant": TaskType.ASSISTANT
            }
            
            task_type = task_mapping.get(intent.lower(), TaskType.UNKNOWN)
            rospy.loginfo(f"Analyzed task intent: {task_type.value}")
            
            return task_type
            
        except Exception as e:
            rospy.logerr(f"Error analyzing task intent: {e}")
            return TaskType.UNKNOWN
            
    def _execute_task_async(self, task_type: TaskType, user_input: str) -> Dict:
        """
        异步执行任务
        
        Args:
            task_type: 任务类型
            user_input: 用户输入
            
        Returns:
            Dict: 初始响应
        """
        try:
            # 获取任务执行器
            executor = self.task_executors.get(task_type)
            if not executor:
                return {
                    "success": False,
                    "message": f"任务执行器 {task_type.value} 不存在"
                }
            
            # 重置停止标志
            self.stop_flag.clear()
            
            # 更新任务状态
            self.current_task = executor
            self.current_task_type = task_type
            self.task_status = TaskStatus.RUNNING
            
            # 设置停止标志给任务
            if hasattr(executor, 'set_stop_flag'):
                executor.set_stop_flag(self.stop_flag)
            
            rospy.loginfo(f"Starting task asynchronously: {task_type.value}")
            
            # 在新线程中执行任务
            self.task_thread = threading.Thread(
                target=self._task_execution_worker,
                args=(executor, user_input),
                daemon=True
            )
            self.task_thread.start()
            
            return {
                "success": True,
                "message": f"开始执行{task_type.value}任务",
                "task_type": task_type.value
            }
            
        except Exception as e:
            rospy.logerr(f"Error starting async task {task_type.value}: {e}")
            self.task_status = TaskStatus.FAILED
            return {
                "success": False,
                "message": f"启动任务时发生错误: {e}"
            }
    
    def _task_execution_worker(self, executor, user_input: str):
        """
        任务执行工作线程
        
        Args:
            executor: 任务执行器
            user_input: 用户输入
        """
        try:
            rospy.loginfo(f"Executing task in worker thread: {self.current_task_type.value}")
            
            # 执行任务
            result = executor.execute(user_input)
            
            # 检查是否被取消
            if self.stop_flag.is_set():
                self.task_status = TaskStatus.CANCELLED
                rospy.loginfo(f"Task {self.current_task_type.value} was cancelled")
            else:
                # 更新状态
                if result.get("success", False):
                    self.task_status = TaskStatus.COMPLETED
                    rospy.loginfo(f"Task {self.current_task_type.value} completed successfully")
                else:
                    self.task_status = TaskStatus.FAILED
                    rospy.logwarn(f"Task {self.current_task_type.value} failed")
                    
        except Exception as e:
            rospy.logerr(f"Error in task execution worker: {e}")
            self.task_status = TaskStatus.FAILED
        finally:
            # 清理
            if self.task_status != TaskStatus.CANCELLED:
                self.current_task = None
                self.current_task_type = None

    def _handle_interactive_input(self, user_input: str):
        """处理交互式任务的用户输入"""
        with self.interactive_lock:
            self.interactive_input_queue.append(user_input)
            rospy.loginfo(f"Added interactive input to queue: {user_input}")
    
    def get_interactive_input(self, timeout: float = 30.0) -> Optional[str]:
        """
        获取交互式输入（供交互式任务调用）
        
        Args:
            timeout: 超时时间
            
        Returns:
            str: 用户输入，超时返回None
        """
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            with self.interactive_lock:
                if self.interactive_input_queue:
                    user_input = self.interactive_input_queue.pop(0)
                    rospy.loginfo(f"Retrieved interactive input: {user_input}")
                    return user_input
            
            # 检查停止标志
            if self.stop_flag.is_set():
                rospy.loginfo("Interactive input interrupted by stop flag")
                return None
            
            time.sleep(0.1)
        
        rospy.loginfo("Interactive input timeout")
        return None
    
    def _execute_interactive_task(self, task_type: TaskType, user_input: str) -> Dict:
        """
        执行交互式任务
        
        Args:
            task_type: 任务类型
            user_input: 用户输入
            
        Returns:
            Dict: 初始响应
        """
        try:
            # 获取任务执行器
            executor = self.task_executors.get(task_type)
            if not executor:
                return {
                    "success": False,
                    "message": f"任务执行器 {task_type.value} 不存在"
                }
            
            # 设置交互式任务标志
            self.is_interactive_task = True
            
            # 重置停止标志和交互队列
            self.stop_flag.clear()
            with self.interactive_lock:
                self.interactive_input_queue.clear()
            
            # 更新任务状态
            self.current_task = executor
            self.current_task_type = task_type
            self.task_status = TaskStatus.RUNNING
            
            # 设置停止标志给任务
            if hasattr(executor, 'set_stop_flag'):
                executor.set_stop_flag(self.stop_flag)
            
            # 设置任务管理器引用给交互式任务
            if hasattr(executor, 'set_task_manager'):
                executor.set_task_manager(self)
            
            rospy.loginfo(f"Starting interactive task: {task_type.value}")
            
            # 在新线程中执行任务
            self.task_thread = threading.Thread(
                target=self._interactive_task_worker,
                args=(executor, user_input),
                daemon=True
            )
            self.task_thread.start()
            
            return {
                "success": True,
                "message": f"开始执行{task_type.value}任务",
                "task_type": task_type.value
            }
            
        except Exception as e:
            rospy.logerr(f"Error starting interactive task {task_type.value}: {e}")
            self.task_status = TaskStatus.FAILED
            self.is_interactive_task = False
            return {
                "success": False,
                "message": f"启动任务时发生错误: {e}"
            }
    
    def _interactive_task_worker(self, executor, user_input: str):
        """
        交互式任务执行工作线程
        
        Args:
            executor: 任务执行器
            user_input: 用户输入
        """
        try:
            rospy.loginfo(f"Executing interactive task in worker thread: {self.current_task_type.value}")
            
            # 执行任务
            result = executor.execute(user_input)
            
            # 检查是否被取消
            if self.stop_flag.is_set():
                self.task_status = TaskStatus.CANCELLED
                rospy.loginfo(f"Interactive task {self.current_task_type.value} was cancelled")
            else:
                # 更新状态
                if result.get("success", False):
                    self.task_status = TaskStatus.COMPLETED
                    rospy.loginfo(f"Interactive task {self.current_task_type.value} completed successfully")
                else:
                    self.task_status = TaskStatus.FAILED
                    rospy.logwarn(f"Interactive task {self.current_task_type.value} failed")
                    
        except Exception as e:
            rospy.logerr(f"Error in interactive task execution worker: {e}")
            self.task_status = TaskStatus.FAILED
        finally:
            # 清理交互式任务状态
            self.is_interactive_task = False
            with self.interactive_lock:
                self.interactive_input_queue.clear()
            
            # 清理任务状态
            if self.task_status != TaskStatus.CANCELLED:
                self.current_task = None
                self.current_task_type = None

    def stop_current_task(self) -> bool:
        """
        停止当前任务
        
        Returns:
            bool: 是否成功停止
        """
        try:
            if self.current_task and self.task_status == TaskStatus.RUNNING:
                rospy.loginfo(f"Stopping current task: {self.current_task_type.value}")
                
                # 1. 立即设置停止标志
                self.stop_flag.set()
                
                # 2. 立即调用任务的停止方法（包含导航取消）
                if hasattr(self.current_task, 'stop'):
                    self.current_task.stop()
                
                # 3. 检查导航是否还在进行，如果是则强制取消
                if hasattr(self.current_task, 'nav_controller') and self.current_task.nav_controller.is_navigating:
                    rospy.loginfo("Force cancelling remaining navigation from task manager")
                    self.current_task.nav_controller.cancel_navigation()
                
                # 4. 清理交互式任务状态
                if self.is_interactive_task:
                    self.is_interactive_task = False
                    with self.interactive_lock:
                        self.interactive_input_queue.clear()
                    rospy.loginfo("Cleared interactive task state")
                
                # 5. 更新任务状态为已取消
                self.task_status = TaskStatus.CANCELLED
                
                # 6. 等待任务线程结束（缩短超时时间）
                if self.task_thread and self.task_thread.is_alive():
                    rospy.loginfo("Waiting for task thread to terminate...")
                    self.task_thread.join(timeout=2.0)
                    if self.task_thread.is_alive():
                        rospy.logwarn("Task thread did not terminate within timeout, but navigation should be stopped")
                
                # 7. 清理状态
                self.current_task = None
                self.current_task_type = None
                self.task_thread = None
                
                rospy.loginfo("Task stopped successfully")
                return True
            
            rospy.loginfo("No running task to stop")
            return False
            
        except Exception as e:
            rospy.logerr(f"Error stopping current task: {e}")
            return False
            
    def get_status(self) -> Dict:
        """
        获取任务管理器状态
        
        Returns:
            Dict: 状态信息
        """
        return {
            "current_task": self.current_task_type.value if self.current_task else None,
            "task_status": self.task_status.value,
            "available_tasks": list(self.task_executors.keys()),
            "waypoints_count": len(self.waypoint_engine.get_all_waypoints())
        }
        
    def get_available_waypoints(self) -> List[str]:
        """获取可用导航点列表"""
        return self.waypoint_engine.get_waypoint_names()
        
    def shutdown(self):
        """关闭任务管理器"""
        rospy.loginfo("Shutting down task manager...")
        
        # 停止当前任务
        if self.current_task:
            self.stop_current_task()
            
        # 关闭各任务执行器
        for executor in self.task_executors.values():
            if hasattr(executor, 'shutdown'):
                executor.shutdown()
                
        rospy.loginfo("Task manager shutdown complete") 