#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快递派送任务
根据指令将快递送达指定地点
"""

import rospy
from typing import Dict

from tasks.base_task import BaseTask, TaskStatus
from llm.llm_client import LLMClient


class DeliveryTask(BaseTask):
    """快递派送任务"""
    
    def __init__(self, config: Dict, waypoint_engine):
        super().__init__(config, waypoint_engine)
        
        self.llm_client = LLMClient(
            api_key=config['llm']['api_key'],
            api_base=config['llm']['api_base'],
            model=config['llm']['model']
        )
        
        self.task_config = config['tasks']['delivery']
        
    def execute(self, user_input: str) -> Dict:
        """执行快递派送任务"""
        try:
            self.status = TaskStatus.RUNNING
            rospy.loginfo("Starting delivery task")
            
            # 提取目标地点
            target_location = self.llm_client.extract_single_location(user_input)
            if not target_location:
                return {
                    "success": False,
                    "message": "请明确指定快递派送的目标地点。",
                    "task_type": "delivery"
                }
                
            # 直接开始派送任务，无需确认
            self.audio.speak_with_emotion(f"好的，我将把快递送到{target_location}，请稍等。", "happy")
            
            # 导航到目标地点
            nav_success = self.navigate_to_waypoint(target_location)
            if not nav_success:
                return {
                    "success": False,
                    "message": f"无法导航到{target_location}",
                    "task_type": "delivery"
                }
                
            # 到达后确认派送
            self.audio.speak_with_emotion(f"已到达{target_location}，快递已送达！", "happy")
            self.audio.play_sound_effect("success")
            
            self.status = TaskStatus.COMPLETED
            return {
                "success": True,
                "message": f"快递已成功送达{target_location}",
                "task_type": "delivery",
                "destination": target_location
            }
            
        except Exception as e:
            rospy.logerr(f"Error in delivery task: {e}")
            self.status = TaskStatus.FAILED
            return {
                "success": False,
                "message": f"快递派送失败: {e}",
                "task_type": "delivery"
            }
            
    def stop(self):
        super().stop()
        self.audio.speak("快递派送任务已停止。") 