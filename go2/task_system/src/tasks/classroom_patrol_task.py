#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
教室巡检任务
检查学生行为（睡觉、玩手机等）
"""

import rospy
import time
import os
from typing import Dict, List

from tasks.base_task import BaseTask, TaskStatus
from llm.llm_client import LLMClient


class ClassroomPatrolTask(BaseTask):
    """教室巡检任务"""
    
    def __init__(self, config: Dict, waypoint_engine):
        """
        初始化教室巡检任务
        
        Args:
            config: 系统配置
            waypoint_engine: 导航点引擎
        """
        super().__init__(config, waypoint_engine)
        
        # LLM客户端用于提取目标教室
        self.llm_client = LLMClient(
            api_key=config['llm']['api_key'],
            api_base=config['llm']['api_base'],
            model=config['llm']['model']
        )
        
        # 任务特定配置
        self.task_config = config['tasks']['classroom_patrol']
        self.detection_interval = self.task_config.get('detection_interval', 5)
        
    def execute(self, user_input: str) -> Dict:
        """
        执行教室巡检任务
        
        Args:
            user_input: 用户输入（如"巡检所有教室"或"巡检音乐教室和数学教室"）
            
        Returns:
            Dict: 执行结果
        """
        try:
            self.status = TaskStatus.RUNNING
            rospy.loginfo("Starting classroom patrol task")
            
            # 步骤1: 解析目标教室
            target_classrooms = self._parse_target_classrooms(user_input)
            if not target_classrooms:
                return {
                    "success": False,
                    "message": "无法识别目标教室，请明确指定要巡检的教室。",
                    "task_type": "classroom_patrol"
                }
                
            # 单点巡检表达
            self.audio.speak(f"开始教室巡检任务，目标教室：{target_classrooms[0]}。")
            
            # 步骤2: 执行巡检
            patrol_results = []
            
            for i, classroom in enumerate(target_classrooms, 1):
                rospy.loginfo(f"Patrolling classroom {i}/{len(target_classrooms)}: {classroom}")
                
                # 导航到教室
                nav_success = self.navigate_to_waypoint(classroom)
                if not nav_success:
                    result = {
                        "classroom": classroom,
                        "success": False,
                        "error": "导航失败"
                    }
                    patrol_results.append(result)
                    continue
                    
                # 在教室进行检测
                detection_result = self._patrol_classroom(classroom)
                patrol_results.append(detection_result)
                
                # 检查是否需要停止
                if self.status == TaskStatus.CANCELLED or (self.stop_flag and self.stop_flag.is_set()):
                    rospy.loginfo("Classroom patrol task stopped")
                    break
                    
            # 步骤3: 生成总结报告
            self._generate_patrol_report(patrol_results)
            
            # 检查是否有成功的巡检
            successful_patrols = sum(1 for r in patrol_results if r.get("success", False))
            
            if successful_patrols == 0:
                # 所有巡检都失败了
                self.status = TaskStatus.FAILED
                return {
                    "success": False,
                    "message": f"教室巡检失败，所有{len(patrol_results)}个教室都无法到达。",
                    "task_type": "classroom_patrol",
                    "results": patrol_results
                }
            else:
                self.status = TaskStatus.COMPLETED
                return {
                    "success": True,
                    "message": f"教室巡检完成，共巡检{len(patrol_results)}个教室，成功{successful_patrols}个。",
                    "task_type": "classroom_patrol",
                    "results": patrol_results
                }
            
        except Exception as e:
            rospy.logerr(f"Error in classroom patrol task: {e}")
            self.status = TaskStatus.FAILED
            return {
                "success": False,
                "message": f"教室巡检任务执行失败: {e}",
                "task_type": "classroom_patrol"
            }
            
    def _parse_target_classrooms(self, user_input: str) -> List[str]:
        """
        解析目标教室列表
        
        Args:
            user_input: 用户输入
            
        Returns:
            List[str]: 目标教室列表
        """
        try:
            # 使用LLM提取教室名称
            extracted_classrooms = self.llm_client.extract_locations(user_input)
            
            if not extracted_classrooms:
                # 如果没有指定具体教室，使用默认教室列表
                if "所有" in user_input or "全部" in user_input:
                    extracted_classrooms = self.task_config['default_classrooms']
                else:
                    return []
                    
            # 验证教室是否存在于导航点中
            valid_classrooms = []
            for classroom in extracted_classrooms:
                waypoint = self.waypoint_engine.find_waypoint(classroom)
                if waypoint:
                    valid_classrooms.append(waypoint['name'])
                else:
                    rospy.logwarn(f"Classroom not found in waypoints: {classroom}")
                    
            return valid_classrooms
            
        except Exception as e:
            rospy.logerr(f"Error parsing target classrooms: {e}")
            return []
            
    def _patrol_classroom(self, classroom: str) -> Dict:
        """
        在指定教室进行巡检
        
        Args:
            classroom: 教室名称
            
        Returns:
            Dict: 巡检结果
        """
        try:
            rospy.loginfo(f"Starting patrol in classroom: {classroom}")
            
            # 步骤1: 停留观察
            rospy.loginfo(f"Observing classroom for {self.detection_interval} seconds")
            time.sleep(self.detection_interval)
            
            # 步骤2: 捕获图像
            save_path = os.path.join(
                self.config['data_storage']['detection_results_path'],
                'classroom'
            )
            
            image_path = self.capture_and_save_image(save_path, f"classroom_{classroom}")
            if not image_path:
                return {
                    "classroom": classroom,
                    "success": False,
                    "error": "图像捕获失败"
                }
                
            # 步骤3: 执行行为检测
            detection_result = self.run_detection("student_behavior", image_path)
            
            # 步骤4: 保存检测结果
            self.save_detection_result(detection_result, "classroom", classroom)
            
            # 步骤5: 记录检测结果（不进行语音播报）
            if detection_result.get("detected", False):
                behavior = detection_result.get("behavior", "unknown")
                description = detection_result.get("description", "")
                
                # 只有睡觉或玩手机才算异常行为
                if behavior in ['sleep', 'using phone']:
                    rospy.logwarn(f"Abnormal behavior detected in {classroom}: {behavior}")
                else:
                    rospy.loginfo(f"Normal classroom activity in {classroom}: {behavior}")
            else:
                rospy.loginfo(f"Normal behavior in {classroom}")
                
            return {
                "classroom": classroom,
                "success": True,
                "detection_result": detection_result,
                "image_path": image_path
            }
            
        except Exception as e:
            rospy.logerr(f"Error patrolling classroom {classroom}: {e}")
            return {
                "classroom": classroom,
                "success": False,
                "error": str(e)
            }
            
    def _generate_patrol_report(self, patrol_results: List[Dict]):
        """
        生成巡检报告
        
        Args:
            patrol_results: 巡检结果列表
        """
        try:
            total_classrooms = len(patrol_results)
            successful_patrols = sum(1 for r in patrol_results if r.get("success", False))
            abnormal_behaviors = []
            
            for result in patrol_results:
                if (result.get("success", False) and 
                    result.get("detection_result", {}).get("detected", False)):
                    abnormal_behaviors.append({
                        "classroom": result["classroom"],
                        "behavior": result["detection_result"].get("behavior", "unknown"),
                        "description": result["detection_result"].get("description", "")
                    })
                    
            # 报告总结（单点巡检）
            classroom_name = patrol_results[0].get('classroom', '教室')
            
            if successful_patrols == 0:
                # 巡检失败
                report_text = f"教室巡检失败，无法到达{classroom_name}。"
            else:
                # 巡检成功
                if abnormal_behaviors:
                    # 发现异常行为
                    behavior = abnormal_behaviors[0]  # 单点只有一个结果
                    report_text = f"教室巡检完成。{classroom_name}发现{behavior['description']}。"
                else:
                    # 行为正常
                    report_text = f"教室巡检完成。{classroom_name}学生行为正常。"
                
            
            # 保存报告到文件
            import json
            import os
            from datetime import datetime
            
            report_data = {
                "timestamp": datetime.now().isoformat(),
                "task_type": "classroom_patrol",
                "summary": {
                    "total_classrooms": total_classrooms,
                    "successful_patrols": successful_patrols,
                    "abnormal_behaviors_count": len(abnormal_behaviors)
                },
                "detailed_results": patrol_results,
                "abnormal_behaviors": abnormal_behaviors
            }
            
            report_dir = os.path.join(
                self.config['data_storage']['detection_results_path'],
                'classroom'
            )
            os.makedirs(report_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = os.path.join(report_dir, f"patrol_report_{timestamp}.json")
            
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
                
            rospy.loginfo(f"Patrol report saved: {report_path}")
            
        except Exception as e:
            rospy.logerr(f"Error generating patrol report: {e}")
            
    def stop(self):
        """停止巡检任务"""
        super().stop()
        self.audio.speak("教室巡检任务已停止。") 