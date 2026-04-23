#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
导航点检索引擎
负责加载导航点数据并进行简化的地点名称匹配
"""

import json
import os
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher
import rospy


class WaypointEngine:
    """导航点检索引擎"""
    
    def __init__(self, waypoints_path: str):
        """
        初始化导航点引擎
        
        Args:
            waypoints_path: 导航点JSON文件路径
        """
        self.waypoints_path = waypoints_path
        self.waypoints = []
        self.load_waypoints()
        
        # 同义词映射
        self.synonym_map = {
            "音乐室": "音乐教室",
            "舞蹈室": "舞蹈教室", 
            "数学室": "数学教室",
            "门口": "大门口",
            "入口": "大门口",
            "大门": "大门口"
        }
        
    def load_waypoints(self):
        """加载导航点数据"""
        try:
            if not os.path.exists(self.waypoints_path):
                rospy.logwarn(f"Waypoints file not found: {self.waypoints_path}")
                return
                
            with open(self.waypoints_path, 'r', encoding='utf-8') as f:
                self.waypoints = json.load(f)
                
            rospy.loginfo(f"Loaded {len(self.waypoints)} waypoints")
            
        except Exception as e:
            rospy.logerr(f"Failed to load waypoints: {e}")
            self.waypoints = []
    
    def find_waypoint(self, target_name: str, threshold: float = 0.6) -> Optional[Dict]:
        """
        查找匹配的导航点
        
        Args:
            target_name: 目标地点名称
            threshold: 相似度阈值
            
        Returns:
            Dict: 匹配的导航点信息，包含id, name, position
        """
        if not self.waypoints:
            rospy.logwarn("No waypoints loaded")
            return None
            
        # 标准化目标名称
        normalized_target = self._normalize_name(target_name)
        
        best_match = None
        best_score = 0.0
        
        for waypoint in self.waypoints:
            waypoint_name = waypoint.get('name', '')
            
            # 计算相似度
            score = self._calculate_similarity(normalized_target, waypoint_name)
            
            if score > best_score and score >= threshold:
                best_score = score
                best_match = waypoint
                
        if best_match:
            rospy.loginfo(f"Found waypoint: {best_match['name']} (similarity: {best_score:.2f})")
            return best_match
        else:
            rospy.logwarn(f"No waypoint found for: {target_name}")
            return None
            
    def find_multiple_waypoints(self, target_names: List[str]) -> List[Dict]:
        """
        查找多个导航点
        
        Args:
            target_names: 目标地点名称列表
            
        Returns:
            List[Dict]: 匹配的导航点列表
        """
        results = []
        for name in target_names:
            waypoint = self.find_waypoint(name)
            if waypoint:
                results.append(waypoint)
        return results
        
    def get_all_waypoints(self) -> List[Dict]:
        """获取所有导航点"""
        return self.waypoints
        
    def get_waypoint_names(self) -> List[str]:
        """获取所有导航点名称"""
        return [wp.get('name', '') for wp in self.waypoints]
        
    def _normalize_name(self, name: str) -> str:
        """标准化地点名称"""
        # 去除空白字符
        name = name.strip()
        
        # 应用同义词映射
        if name in self.synonym_map:
            name = self.synonym_map[name]
            
        return name
        
    def _calculate_similarity(self, name1: str, name2: str) -> float:
        """
        计算两个名称的相似度
        
        Args:
            name1: 名称1
            name2: 名称2
            
        Returns:
            float: 相似度分数 (0-1)
        """
        # 完全匹配
        if name1 == name2:
            return 1.0
            
        # 包含关系
        if name1 in name2 or name2 in name1:
            return 0.9
            
        # 序列匹配
        return SequenceMatcher(None, name1, name2).ratio()
        
    def add_waypoint(self, name: str, position: List[float]) -> bool:
        """
        添加新的导航点
        
        Args:
            name: 地点名称
            position: 位置坐标 [x, y, w]
            
        Returns:
            bool: 是否添加成功
        """
        try:
            # 生成新ID
            max_id = max([wp.get('id', 0) for wp in self.waypoints]) if self.waypoints else 0
            new_id = max_id + 1
            
            new_waypoint = {
                "id": new_id,
                "name": name,
                "position": position,
                "timestamp": rospy.Time.now().to_sec()
            }
            
            self.waypoints.append(new_waypoint)
            
            # 保存到文件
            self._save_waypoints()
            
            rospy.loginfo(f"Added waypoint: {name}")
            return True
            
        except Exception as e:
            rospy.logerr(f"Failed to add waypoint: {e}")
            return False
            
    def _save_waypoints(self):
        """保存导航点到文件"""
        try:
            with open(self.waypoints_path, 'w', encoding='utf-8') as f:
                json.dump(self.waypoints, f, ensure_ascii=False, indent=2)
        except Exception as e:
            rospy.logerr(f"Failed to save waypoints: {e}") 