#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
车辆违停巡检任务
检测车辆违停和车牌识别
"""

import rospy
import time
import os
from typing import Dict, List

from tasks.base_task import BaseTask, TaskStatus
from llm.llm_client import LLMClient


class VehiclePatrolTask(BaseTask):
    """车辆违停巡检任务"""
    
    def __init__(self, config: Dict, waypoint_engine):
        """
        初始化车辆违停巡检任务
        
        Args:
            config: 系统配置
            waypoint_engine: 导航点引擎
        """
        super().__init__(config, waypoint_engine)
        
        # LLM客户端用于提取巡检点
        self.llm_client = LLMClient(
            api_key=config['llm']['api_key'],
            api_base=config['llm']['api_base'],
            model=config['llm']['model']
        )
        
        # 任务特定配置
        self.task_config = config['tasks']['vehicle_patrol']
        self.detection_interval = self.task_config.get('detection_interval', 3)
        
    def execute(self, user_input: str) -> Dict:
        """
        执行车辆违停巡检任务
        
        Args:
            user_input: 用户输入（如"巡检违停车辆"或"检查大门口违停"）
            
        Returns:
            Dict: 执行结果
        """
        try:
            self.status = TaskStatus.RUNNING
            rospy.loginfo("Starting vehicle patrol task")
            
            # 步骤1: 解析巡检点
            patrol_points = self._parse_patrol_points(user_input)
            if not patrol_points:
                return {
                    "success": False,
                    "message": "无法识别巡检点，请明确指定要巡检的位置。",
                    "task_type": "vehicle_patrol"
                }
                
            # 单点巡检表达
            self.audio.speak(f"开始车辆违停巡检，目标地点：{patrol_points[0]}。")
            
            # 步骤2: 执行巡检
            patrol_results = []
            total_violations = 0
            
            for i, point in enumerate(patrol_points, 1):
                rospy.loginfo(f"Patrolling point {i}/{len(patrol_points)}: {point}")
                
                # 单点巡检表达
                self.audio.speak(f"正在巡检地点：{point}")
                
                # 导航到巡检点
                nav_success = self.navigate_to_waypoint(point)
                if not nav_success:
                    result = {
                        "patrol_point": point,
                        "success": False,
                        "error": "导航失败"
                    }
                    patrol_results.append(result)
                    continue
                    
                # 在巡检点进行违停检测
                detection_result = self._patrol_vehicle_violations(point)
                patrol_results.append(detection_result)
                
                # 统计违停数量
                if (detection_result.get("success", False) and 
                    detection_result.get("detection_result", {}).get("detected", False)):
                    total_violations += 1
                
                # 检查是否需要停止
                if self.status == TaskStatus.CANCELLED:
                    break
                    
            # 步骤3: 生成总结报告
            self._generate_patrol_report(patrol_results, total_violations)
            
            # 检查是否有成功的巡检
            successful_patrols = sum(1 for r in patrol_results if r.get("success", False))
            
            if successful_patrols == 0:
                # 所有巡检都失败了
                self.status = TaskStatus.FAILED
                return {
                    "success": False,
                    "message": f"车辆违停巡检失败，所有{len(patrol_results)}个地点都无法到达。",
                    "task_type": "vehicle_patrol",
                    "results": patrol_results,
                    "total_violations": total_violations
                }
            else:
                self.status = TaskStatus.COMPLETED
                return {
                    "success": True,
                    "message": f"车辆违停巡检完成，共巡检{len(patrol_results)}个地点，成功{successful_patrols}个，发现{total_violations}起违停。",
                    "task_type": "vehicle_patrol",
                    "results": patrol_results,
                    "total_violations": total_violations
                }
            
        except Exception as e:
            rospy.logerr(f"Error in vehicle patrol task: {e}")
            self.status = TaskStatus.FAILED
            return {
                "success": False,
                "message": f"车辆违停巡检任务执行失败: {e}",
                "task_type": "vehicle_patrol"
            }
            
    def _parse_patrol_points(self, user_input: str) -> List[str]:
        """
        解析巡检点列表
        
        Args:
            user_input: 用户输入
            
        Returns:
            List[str]: 巡检点列表
        """
        try:
            # 使用LLM提取巡检点名称
            extracted_points = self.llm_client.extract_locations(user_input)
            
            if not extracted_points:
                # 如果没有指定具体地点，使用默认巡检点
                if "所有" in user_input or "全部" in user_input:
                    extracted_points = self.task_config['patrol_points']
                else:
                    return []
                    
            # 验证巡检点是否存在于导航点中
            valid_points = []
            for point in extracted_points:
                waypoint = self.waypoint_engine.find_waypoint(point)
                if waypoint:
                    valid_points.append(waypoint['name'])
                else:
                    rospy.logwarn(f"Patrol point not found in waypoints: {point}")
                    
            return valid_points
            
        except Exception as e:
            rospy.logerr(f"Error parsing patrol points: {e}")
            return []
            
    def _patrol_vehicle_violations(self, patrol_point: str) -> Dict:
        """
        在指定巡检点进行违停检测
        
        Args:
            patrol_point: 巡检点名称
            
        Returns:
            Dict: 巡检结果
        """
        try:
            rospy.loginfo(f"Starting vehicle patrol at: {patrol_point}")
            self.audio.speak(f"到达{patrol_point}，开始违停检测。")
            
            # 步骤1: 停留观察
            rospy.loginfo(f"Observing area for {self.detection_interval} seconds")
            time.sleep(self.detection_interval)
            
            # 步骤2: 捕获图像
            save_path = os.path.join(
                self.config['data_storage']['detection_results_path'],
                'vehicle'
            )
            
            image_path = self.capture_and_save_image(save_path, f"vehicle_{patrol_point}")
            if not image_path:
                return {
                    "patrol_point": patrol_point,
                    "success": False,
                    "error": "图像捕获失败"
                }
                
            # 步骤3: 执行车辆检测
            detection_result = self.run_detection("vehicle_detection", image_path)
            
            # 步骤4: 保存检测结果
            self.save_detection_result(detection_result, "vehicle", patrol_point)
            
            # 步骤5: 处理检测结果
            if detection_result.get("detected", False):
                # 发现违停车辆
                license_plates = detection_result.get("license_plates", [])
                plate_count = detection_result.get("plate_count", 1)
                description = detection_result.get("description", "")
                
                # 详细的语音播报违停信息
                if license_plates and len(license_plates) > 0:
                    # 有识别出的车牌
                    if len(license_plates) == 1:
                        plate_number = license_plates[0]["plate_number"]
                        announcement = f"发现违停车辆，车牌号{plate_number}。"
                    else:
                        plate_numbers = [p["plate_number"] for p in license_plates]
                        plate_list = "、".join(plate_numbers)
                        announcement = f"发现{len(license_plates)}辆违停车辆，车牌号分别是{plate_list}。"
                else:
                    # 检测到车辆但车牌未识别
                    if plate_count > 1:
                        announcement = f"发现{plate_count}辆违停车辆，但车牌号未能识别。"
                    else:
                        announcement = "发现违停车辆，但车牌号未能识别。"
                
                self.audio.speak_with_emotion(announcement, "warning")
                self.audio.play_sound_effect("warning")
                
                # 日志记录所有车牌
                if license_plates:
                    plate_log = ", ".join([f"{p['plate_number']}(置信度:{p['confidence']:.2f})" for p in license_plates])
                    rospy.logwarn(f"Vehicle violations detected at {patrol_point}: {plate_log}")
                else:
                    rospy.logwarn(f"Vehicle violations detected at {patrol_point}: {plate_count} vehicles, plates unrecognized")
                
                # 记录违停车辆信息
                violation_info = {
                    "location": patrol_point,
                    "license_plates": license_plates,  # 所有车牌信息
                    "license_plate": license_plates[0]["plate_number"] if license_plates else "未识别",  # 兼容性
                    "plate_count": plate_count,
                    "description": description,
                    "image_path": image_path
                }
                
                return {
                    "patrol_point": patrol_point,
                    "success": True,
                    "detection_result": detection_result,
                    "violation_info": violation_info,
                    "image_path": image_path
                }
            else:
                # 未发现违停
                self.audio.speak(f"{patrol_point}违停检测完成，未发现违停车辆。")
                rospy.loginfo(f"No vehicle violations at {patrol_point}")
                
                return {
                    "patrol_point": patrol_point,
                    "success": True,
                    "detection_result": detection_result,
                    "image_path": image_path
                }
                
        except Exception as e:
            rospy.logerr(f"Error patrolling vehicles at {patrol_point}: {e}")
            return {
                "patrol_point": patrol_point,
                "success": False,
                "error": str(e)
            }
            
    def _generate_patrol_report(self, patrol_results: List[Dict], total_violations: int):
        """
        生成巡检报告
        
        Args:
            patrol_results: 巡检结果列表
            total_violations: 总违停数量
        """
        try:
            total_points = len(patrol_results)
            successful_patrols = sum(1 for r in patrol_results if r.get("success", False))
            violation_details = []
            
            for result in patrol_results:
                if (result.get("success", False) and 
                    result.get("detection_result", {}).get("detected", False)):
                    violation_info = result.get("violation_info", {})
                    license_plates = violation_info.get("license_plates", [])
                    plate_count = violation_info.get("plate_count", 1)
                    
                    # 为每个检测到的违停记录创建详细信息
                    if license_plates:
                        # 有识别出车牌的情况
                        for plate_info in license_plates:
                            violation_details.append({
                                "location": result["patrol_point"],
                                "license_plate": plate_info["plate_number"],
                                "confidence": plate_info["confidence"],
                                "description": violation_info.get("description", ""),
                                "image_path": violation_info.get("image_path", "")
                            })
                    else:
                        # 检测到车辆但车牌未识别的情况
                        for i in range(plate_count):
                            violation_details.append({
                                "location": result["patrol_point"],
                                "license_plate": "未识别",
                                "confidence": 0.0,
                                "description": violation_info.get("description", ""),
                                "image_path": violation_info.get("image_path", "")
                            })
                    
            # 语音播报总结（单点巡检）
            patrol_point = patrol_results[0].get('patrol_point', '目标地点')
            
            if successful_patrols == 0:
                # 巡检失败
                report_text = f"车辆违停巡检失败，无法到达{patrol_point}。"
                self.audio.speak_with_emotion(report_text, "neutral")
            else:
                # 巡检成功
                if total_violations > 0:
                    # 发现违停
                    violation_count = len(violation_details)
                    if violation_count == 1:
                        violation = violation_details[0]
                        report_text = f"车辆违停巡检完成。在{patrol_point}发现违停车辆{violation['license_plate']}。"
                    else:
                        # 多辆车违停
                        identified_plates = [v['license_plate'] for v in violation_details if v['license_plate'] != '未识别']
                        unidentified_count = sum(1 for v in violation_details if v['license_plate'] == '未识别')
                        
                        if identified_plates and unidentified_count == 0:
                            # 所有车牌都识别出来了
                            plate_list = "、".join(identified_plates)
                            report_text = f"车辆违停巡检完成。在{patrol_point}发现{violation_count}辆违停车辆，车牌号分别是{plate_list}。"
                        elif identified_plates and unidentified_count > 0:
                            # 部分识别
                            plate_list = "、".join(identified_plates)
                            report_text = f"车辆违停巡检完成。在{patrol_point}发现{violation_count}辆违停车辆，已识别车牌号{plate_list}，另有{unidentified_count}辆车牌未识别。"
                        else:
                            # 都未识别
                            report_text = f"车辆违停巡检完成。在{patrol_point}发现{violation_count}辆违停车辆，但车牌号均未识别。"
                    
                    self.audio.speak_with_emotion(report_text, "warning")
                else:
                    # 未发现违停
                    report_text = f"车辆违停巡检完成。{patrol_point}未发现违停车辆。"
                    self.audio.speak_with_emotion(report_text, "happy")
                
            # 保存报告到文件
            import json
            from datetime import datetime
            
            report_data = {
                "timestamp": datetime.now().isoformat(),
                "task_type": "vehicle_patrol",
                "summary": {
                    "total_points": total_points,
                    "successful_patrols": successful_patrols,
                    "total_violations": total_violations
                },
                "detailed_results": patrol_results,
                "violation_details": violation_details
            }
            
            report_dir = os.path.join(
                self.config['data_storage']['detection_results_path'],
                'vehicle'
            )
            os.makedirs(report_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = os.path.join(report_dir, f"vehicle_patrol_report_{timestamp}.json")
            
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
                
            rospy.loginfo(f"Vehicle patrol report saved: {report_path}")
            
        except Exception as e:
            rospy.logerr(f"Error generating vehicle patrol report: {e}")
            
    def stop(self):
        """停止违停巡检任务"""
        super().stop()
        self.audio.speak("车辆违停巡检任务已停止。") 