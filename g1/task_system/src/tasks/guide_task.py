#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
校园导引任务
引导用户到达指定教室或地点
"""

import rospy
from typing import Dict

from tasks.base_task import BaseTask, TaskStatus
from llm.llm_client import LLMClient


class GuideTask(BaseTask):
    """校园导引任务"""
    
    def __init__(self, config: Dict, waypoint_engine):
        super().__init__(config, waypoint_engine)
        
        self.llm_client = LLMClient(
            api_key=config['llm']['api_key'],
            api_base=config['llm']['api_base'],
            model=config['llm']['model']
        )
        
        self.task_config = config['tasks']['guide']
        
    def execute(self, user_input: str) -> Dict:
        """执行校园导引任务"""
        try:
            self.status = TaskStatus.RUNNING
            rospy.loginfo("Starting guide task")
            
            # 提取目标地点
            target_location = self.llm_client.extract_single_location(user_input)
            if not target_location:
                return {
                    "success": False,
                    "message": "请明确指定要前往的地点。",
                    "task_type": "guide"
                }
                
            # 确认导引目标
            self.audio.speak_with_emotion(f"好的，我将带您前往{target_location}，请跟我来。", "happy")
            
            # if self.task_config.get('step_by_step', True):
                # self.audio.speak("导引过程中我会提供路线指示，请注意跟随。")
                
            # 开始导航
            nav_success = self.navigate_to_waypoint(target_location)
            if not nav_success:
                return {
                    "success": False,
                    "message": f"无法导航到{target_location}",
                    "task_type": "guide"
                }
                
            # 到达目标
            self.audio.speak_with_emotion(f"我们已经到达{target_location}了！", "excited")
            
            self.status = TaskStatus.COMPLETED
            return {
                "success": True,
                "message": f"已成功导引到{target_location}",
                "task_type": "guide",
                "destination": target_location
            }
            
        except Exception as e:
            rospy.logerr(f"Error in guide task: {e}")
            self.status = TaskStatus.FAILED
            return {
                "success": False,
                "message": f"导引任务失败: {e}",
                "task_type": "guide"
            }
            
    def stop(self):
        super().stop()
        self.audio.speak("导引任务已停止，感谢您的使用。") 