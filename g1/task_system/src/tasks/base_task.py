#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基础任务类
定义所有任务的通用接口和功能
"""

import rospy
import os
import threading
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from enum import Enum

from ros_interface.navigation_controller import NavigationController
try:
    from ros_interface.enhanced_audio_interface import EnhancedAudioInterface as AudioInterface
except ImportError:
    from ros_interface.audio_interface import AudioInterface
from ros_interface.camera_interface import CameraInterface


class TaskStatus(Enum):
    """任务状态枚举"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BaseTask(ABC):
    """基础任务类"""

    def __init__(self, config: Dict, waypoint_engine):
        """
        初始化基础任务
        
        Args:
            config: 配置信息
            waypoint_engine: 导航点引擎
        """
        self.config = config
        self.waypoint_engine = waypoint_engine
        self.status = TaskStatus.IDLE
        self.stop_flag: Optional[threading.Event] = None
        
        # 初始化导航控制器
        self.nav_controller = NavigationController(
            map_frame=config.get('navigation', {}).get('map_frame', 'map'),
            robot_frame=config.get('navigation', {}).get('robot_frame', 'base_link')
        )
        
        # 初始化音频接口
        audio_config = config.get('audio', {})
        if hasattr(AudioInterface, '__name__') and 'Enhanced' in AudioInterface.__name__:
            # 使用增强版音频接口
            self.audio = AudioInterface(
                speech_topic=config.get('ros_topics', {}).get('audio_input', '/audio/speech_recognition'),
                tts_topic=config.get('ros_topics', {}).get('audio_output', '/audio/tts'),
                use_tts=audio_config.get('use_tts', True),
                tts_config=audio_config.get('tts_config', None)
            )
        else:
            # 使用原版音频接口
            self.audio = AudioInterface(
                speech_topic=config.get('ros_topics', {}).get('audio_input', '/audio/speech_recognition'),
                tts_topic=config.get('ros_topics', {}).get('audio_output', '/audio/tts')
            )
        
        # 初始化相机接口
        self.camera = CameraInterface(
            camera_topic=config.get('ros_topics', {}).get('camera', '/camera/color/image_raw')
        )
        
        rospy.loginfo(f"{self.__class__.__name__} initialized")
        
    def set_stop_flag(self, stop_flag: threading.Event):
        """
        设置停止标志
        
        Args:
            stop_flag: 停止标志事件
        """
        self.stop_flag = stop_flag

    @abstractmethod
    def execute(self, user_input: str) -> Dict:
        """
        执行任务（子类需要实现）
        
        Args:
            user_input: 用户输入
            
        Returns:
            Dict: 执行结果，包含success、message等字段
        """
        pass
        
    def navigate_to_waypoint(self, waypoint_name: str) -> bool:
        """
        导航到指定导航点（支持中断）
        
        Args:
            waypoint_name: 导航点名称
            
        Returns:
            bool: 导航是否成功
        """
        try:
            # 查找导航点
            waypoint = self.waypoint_engine.find_waypoint(waypoint_name)
            if not waypoint:
                rospy.logwarn(f"Waypoint not found: {waypoint_name}")
                return False
                
            # 播报导航开始
            self.audio.announce_navigation(waypoint['name'])
            
            # 发送导航目标
            success = self.nav_controller.send_goal(waypoint['position'])
            if not success:
                rospy.logerr(f"Failed to send navigation goal to {waypoint_name}")
                return False
                
            # 可中断的导航等待
            rospy.loginfo(f"Navigating to {waypoint_name}...")
            result = self._wait_for_navigation_with_interruption()
            
            if result:
                self.audio.announce_arrival(waypoint['name'])
                rospy.loginfo(f"Successfully reached {waypoint_name}")
                return True
            else:
                rospy.logwarn(f"Navigation to {waypoint_name} failed or was cancelled")
                return False
                
        except Exception as e:
            rospy.logerr(f"Error navigating to {waypoint_name}: {e}")
            return False
            
    def _wait_for_navigation_with_interruption(self, check_interval: float = 0.2) -> bool:
        """
        等待导航完成，支持中断检查（更频繁的检查）
        
        Args:
            check_interval: 检查间隔时间（秒），降低到0.2秒提高响应速度
            
        Returns:
            bool: 导航是否成功完成
        """
        try:
            last_status_check = time.time()
            
            while self.nav_controller.is_navigating:
                # 检查停止标志 - 最高优先级
                if self.stop_flag and self.stop_flag.is_set():
                    rospy.loginfo("Navigation interrupted by stop flag - immediate cancellation")
                    self.nav_controller.cancel_navigation()
                    return False
                
                # 检查任务状态
                if self.status == TaskStatus.CANCELLED:
                    rospy.loginfo("Navigation interrupted by task cancellation")
                    self.nav_controller.cancel_navigation()
                    return False
                
                # 每秒检查一次导航状态，避免频繁调用
                current_time = time.time()
                if current_time - last_status_check >= 1.0:
                    try:
                        nav_status = self.nav_controller.get_navigation_status()
                        rospy.logdebug(f"Navigation status: {nav_status}")
                        
                        # 检查move_base状态
                        if not self.nav_controller.is_navigating:
                            state = self.nav_controller.move_base_client.get_state()
                            from actionlib_msgs.msg import GoalStatus
                            
                            if state == GoalStatus.SUCCEEDED:
                                rospy.loginfo("Navigation completed successfully")
                                return True
                            elif state in [GoalStatus.PREEMPTED, GoalStatus.RECALLED]:
                                rospy.loginfo("Navigation was cancelled")
                                return False
                            elif state == GoalStatus.ABORTED:
                                rospy.logwarn("Navigation was aborted by move_base")
                                return False
                            else:
                                rospy.logwarn(f"Navigation ended with unexpected state: {state}")
                                return False
                        
                        last_status_check = current_time
                        
                    except Exception as e:
                        rospy.logdebug(f"Error checking navigation status: {e}")
                
                # 短暂等待后再次检查
                time.sleep(check_interval)
            
            # 如果走到这里，说明导航已经不在进行中了
            rospy.loginfo("Navigation loop exited, checking final state...")
            
            try:
                state = self.nav_controller.move_base_client.get_state()
                from actionlib_msgs.msg import GoalStatus
                
                if state == GoalStatus.SUCCEEDED:
                    return True
                else:
                    rospy.logwarn(f"Navigation ended with state: {state}")
                    return False
            except Exception as e:
                rospy.logwarn(f"Error getting final navigation state: {e}")
                return False
            
        except Exception as e:
            rospy.logerr(f"Error in navigation waiting: {e}")
            self.nav_controller.cancel_navigation()
            return False
            
    def capture_and_save_image(self, save_path: str, prefix: str = "task", delay: float = 1.0) -> Optional[str]:
        """
        捕获并保存图像
        
        Args:
            save_path: 保存路径
            prefix: 文件名前缀
            delay: 延迟时间（秒），默认1秒
            
        Returns:
            str: 保存的文件路径，失败则返回None
        """
        try:
            # 等待指定时间，确保机器人稳定
            rospy.loginfo(f"Waiting {delay} seconds before capturing image...")
            time.sleep(delay)
            
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}_{timestamp}.jpg"
            
            file_path = self.camera.capture_and_save(save_path, filename)
            if file_path:
                rospy.loginfo(f"Image saved: {file_path}")
                return file_path
            else:
                rospy.logwarn("Failed to capture and save image")
                return None
                
        except Exception as e:
            rospy.logerr(f"Error capturing image: {e}")
            return None
            
    def run_detection(self, detection_type: str, image_path: str) -> Dict:
        """
        运行实际的检测功能
        
        Args:
            detection_type: 检测类型 ("student_behavior", "vehicle_detection")
            image_path: 图像路径
            
        Returns:
            Dict: 检测结果
        """
        try:
            # 导入detector模块
            import sys
            import os
            detector_dir = os.path.join(os.path.dirname(__file__), '../utils')
            if detector_dir not in sys.path:
                sys.path.append(detector_dir)
            
            from detector import UniversalDetector
            
            # 根据检测类型选择合适的模型
            if detection_type == "student_behavior":
                # 使用行为检测模型
                model_path = os.path.join(detector_dir, 'models/class/best_class.engine')
                detector = UniversalDetector(model_path, enable_ocr=False)
                
                # 执行检测
                results = detector.detect_image(image_path, conf_threshold=0.25)
                
                if results and len(results) > 0:
                    # 找到置信度最高的检测结果
                    best_result = max(results, key=lambda x: x.get('confidence', 0))
                    behavior = best_result.get('behavior', 'unknown')
                    confidence = best_result.get('confidence', 0)
                    
                    # 根据行为类型生成描述
                    behavior_descriptions = {
                        'sleep': '检测到学生睡觉',
                        'using phone': '检测到学生玩手机',
                        'hand-raising': '检测到学生举手',
                        'reading': '检测到学生阅读',
                        'writing': '检测到学生写字',
                        'bowing the head': '检测到学生低头',
                        'leaning over the table': '检测到学生趴桌子'
                    }
                    
                    description = behavior_descriptions.get(behavior, f'检测到学生行为：{behavior}')
                    
                    return {
                        "detected": True,
                        "behavior": behavior,
                        "confidence": confidence,
                        "description": description
                    }
                else:
                    return {
                        "detected": False,
                        "behavior": "normal",
                        "confidence": 0.95,
                        "description": "学生行为正常"
                    }
                    
            elif detection_type == "vehicle_detection":
                # 使用车牌检测模型
                model_path = os.path.join(detector_dir, 'models/carplate/best_chepai.engine')
                detector = UniversalDetector(model_path, enable_ocr=True)
                
                # 执行检测
                results = detector.detect_image(image_path, conf_threshold=0.25)
                
                if results and len(results) > 0:
                    # 处理所有检测到的车牌
                    detected_plates = []
                    total_confidence = 0
                    
                    for result in results:
                        plate_number = result.get('plate_number', '未识别')
                        confidence = result.get('confidence', 0)
                        
                        if plate_number and plate_number != '未识别':
                            detected_plates.append({
                                "plate_number": plate_number,
                                "confidence": confidence
                            })
                            total_confidence += confidence
                    
                    if detected_plates:
                        # 有识别出的车牌
                        plate_count = len(detected_plates)
                        avg_confidence = total_confidence / plate_count
                        
                        # 生成车牌列表描述
                        if plate_count == 1:
                            plate_list = detected_plates[0]["plate_number"]
                            description = f"检测到违停车辆，车牌号：{plate_list}"
                        else:
                            plate_numbers = [p["plate_number"] for p in detected_plates]
                            plate_list = "、".join(plate_numbers)
                            description = f"检测到{plate_count}辆违停车辆，车牌号：{plate_list}"
                        
                        return {
                            "detected": True,
                            "vehicle_type": "car",
                            "license_plates": detected_plates,  # 所有车牌列表
                            "license_plate": detected_plates[0]["plate_number"],  # 保持兼容性
                            "plate_count": plate_count,
                            "confidence": avg_confidence,
                            "description": description
                        }
                    else:
                        # 检测到车辆但车牌未识别
                        return {
                            "detected": True,
                            "vehicle_type": "car",
                            "license_plates": [],
                            "license_plate": "未识别",
                            "plate_count": len(results),
                            "confidence": sum(r.get('confidence', 0) for r in results) / len(results),
                            "description": f"检测到{len(results)}辆违停车辆，但车牌号未识别"
                        }
                else:
                    return {
                        "detected": False,
                        "description": "未检测到违停车辆"
                    }
            else:
                return {
                    "detected": False,
                    "error": f"Unknown detection type: {detection_type}"
                }
                
        except Exception as e:
            rospy.logerr(f"Detection error: {e}")
            return {
                "detected": False,
                "error": f"Detection failed: {str(e)}"
            }
            
    def save_detection_result(self, result: Dict, task_type: str, location: str) -> bool:
        """
        保存检测结果
        
        Args:
            result: 检测结果
            task_type: 任务类型
            location: 检测位置
            
        Returns:
            bool: 是否保存成功
        """
        try:
            import json
            import os
            from datetime import datetime
            
            # 准备保存数据
            save_data = {
                "timestamp": datetime.now().isoformat(),
                "task_type": task_type,
                "location": location,
                "detection_result": result
            }
            
            # 统一保存到data/detection_results目录下
            base_data_dir = os.path.join(os.path.dirname(__file__), '../../data/detection_results')
            
            if task_type == "vehicle":
                save_dir = os.path.join(base_data_dir, 'vehicle')
            elif task_type == "classroom":
                save_dir = os.path.join(base_data_dir, 'classroom')
            else:
                save_dir = os.path.join(base_data_dir, task_type)
            
            os.makedirs(save_dir, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if task_type == "vehicle":
                filename = f"vehicle_patrol_{location}_{timestamp}.json"
            else:
                filename = f"{task_type}_{location}_{timestamp}.json"
            file_path = os.path.join(save_dir, filename)
            
            # 保存到文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
                
            rospy.loginfo(f"Detection result saved: {file_path}")
            return True
            
        except Exception as e:
            rospy.logerr(f"Error saving detection result: {e}")
            return False
            
    def stop(self):
        """停止任务"""
        rospy.loginfo(f"Stopping {self.__class__.__name__}")
        self.status = TaskStatus.CANCELLED
        
        # 设置停止标志（优先级最高，确保循环能立即检测到）
        if self.stop_flag:
            self.stop_flag.set()
        
        # 取消导航（如果正在进行）
        if hasattr(self, 'nav_controller') and self.nav_controller.is_navigating:
            rospy.loginfo(f"Cancelling navigation from {self.__class__.__name__}")
            self.nav_controller.cancel_navigation()
        elif hasattr(self, 'nav_controller'):
            rospy.logdebug(f"No active navigation to cancel in {self.__class__.__name__}")
            
    def get_status(self) -> Dict:
        """获取任务状态"""
        return {
            "task_class": self.__class__.__name__,
            "status": self.status.value,
            "navigation_status": self.nav_controller.get_navigation_status() if hasattr(self, 'nav_controller') else None
        }
        
    def shutdown(self):
        """关闭任务"""
        rospy.loginfo(f"Shutting down {self.__class__.__name__}")
        
        if hasattr(self, 'nav_controller'):
            self.nav_controller.shutdown()
        if hasattr(self, 'camera'):
            self.camera.shutdown()
        if hasattr(self, 'audio'):
            self.audio.shutdown() 