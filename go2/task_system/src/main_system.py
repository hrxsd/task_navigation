#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Task System - Main Entry Point
任务系统主程序入口
"""

import os
import sys
import json
import yaml
import rospy
from typing import Dict

from core.task_manager import TaskManager


class TaskSystem:
    """任务系统主类"""

    def __init__(self, config_path: str):
        """初始化任务系统"""
        self.config_path = config_path
        
        # 初始化ROS节点
        rospy.init_node('task_system_node', anonymous=True)
        rospy.loginfo("Task System Starting...")
        
        # 初始化任务管理器
        self.task_manager = TaskManager(config_path)
        
        rospy.loginfo("Task System initialized successfully")
        
    def run(self):
        """运行主循环"""
        print("\n" + "="*50)
        print("🤖 G1 智能任务系统")
        print("="*50)
        print("支持的任务类型:")
        print("1. 教室巡检 - 检查学生行为")
        print("2. 车辆违停巡检 - 识别违停车辆")
        print("3. 快递派送 - 送达指定地点")
        print("4. 校园导引 - 引导到目标位置")
        print("5. 课堂助手 - 智能问答交互")
        print("\n特殊命令:")
        print("- 'status': 查看系统状态")
        print("- 'waypoints': 查看可用导航点")
        print("- 'cancel': 取消当前任务")
        print("- 'quit/exit': 退出系统")
        print("="*50 + "\n")
        
        while not rospy.is_shutdown():
            try:
                # 获取用户输入
                user_input = input("请输入您的指令: ").strip()
                
                # 处理特殊命令
                if user_input.lower() in ['quit', 'exit', '退出']:
                    print("正在关闭任务系统...")
                    self.shutdown()
                    break
                
                if user_input.lower() == 'status':
                    self._print_status()
                    continue
                
                if user_input.lower() == 'waypoints':
                    self._print_waypoints()
                    continue
                
                if user_input.lower() == 'cancel':
                    self._cancel_current_task()
                    continue
                
                if not user_input:
                    continue
                
                # 处理任务请求
                print(f"\n处理指令: {user_input}")
                result = self.task_manager.process_user_input(user_input)
                
                # 显示结果
                self._print_result(result)
                
                # 如果任务开始执行，提供相应提示
                if result.get("success", False) and result.get("task_type") != "conflict":
                    if result.get("task_type") == "assistant":
                        print("💡 提示: 课堂助手已启动，可以直接输入问题进行对话，输入 'cancel' 取消任务")
                    else:
                        print("💡 提示: 任务执行期间可以输入 'cancel' 取消任务")
                
                # 如果是交互输入处理，不显示额外提示
                if result.get("task_type") == "interactive_input":
                    continue
                
            except KeyboardInterrupt:
                print("\n正在关闭任务系统...")
                self.shutdown()
                break
            except Exception as e:
                rospy.logerr(f"Error in main loop: {e}")
                print(f"发生错误: {e}")
    
    def _print_status(self):
        """打印系统状态"""
        status = self.task_manager.get_status()
        
        print("\n" + "-"*30)
        print("📊 系统状态")
        print("-"*30)
        print(f"当前任务: {status.get('current_task', '无')}")
        print(f"任务状态: {status.get('task_status', '空闲')}")
        print(f"可用任务: {len(status.get('available_tasks', []))}")
        print(f"导航点数量: {status.get('waypoints_count', 0)}")
        print("-"*30 + "\n")
        
    def _print_waypoints(self):
        """打印可用导航点"""
        waypoints = self.task_manager.get_available_waypoints()
        
        print("\n" + "-"*30)
        print("📍 可用导航点")
        print("-"*30)
        for i, waypoint in enumerate(waypoints, 1):
            print(f"{i}. {waypoint}")
        print("-"*30 + "\n")
        
    def _cancel_current_task(self):
        """取消当前任务"""
        print("🛑 正在取消当前任务...")
        success = self.task_manager.stop_current_task()
        if success:
            print("✅ 当前任务已取消，机器人已停止移动")
            
            # 短暂等待确保所有系统都收到了停止信号
            import time
            time.sleep(0.5)
            
            # 显示当前状态
            status = self.task_manager.get_status()
            print(f"📊 系统状态: {status.get('task_status', '未知')}")
        else:
            print("ℹ️ 没有正在执行的任务")
            
    def _print_result(self, result: Dict):
        """打印任务执行结果"""
        print("\n" + "="*40)
        print("📋 执行结果")
        print("="*40)
        
        success = result.get("success", False)
        message = result.get("message", "无消息")
        task_type = result.get("task_type", "unknown")
        
        status_emoji = "✅" if success else "❌"
        print(f"状态: {status_emoji} {'成功' if success else '失败'}")
        print(f"任务类型: {task_type}")
        print(f"消息: {message}")
        
        # 显示额外信息
        if "results" in result:
            results = result["results"]
            print(f"详细结果: 共处理{len(results)}项")
            
        if "destination" in result:
            print(f"目标地点: {result['destination']}")
            
        if "total_violations" in result:
            print(f"违停检测: {result['total_violations']}起")
            
        if "interaction_count" in result:
            print(f"交互次数: {result['interaction_count']}次")
            
        print("="*40 + "\n")
    
    def shutdown(self):
        """关闭系统"""
        try:
            if hasattr(self, 'task_manager'):
                self.task_manager.shutdown()
            rospy.signal_shutdown("User requested shutdown")
            print("任务系统已关闭")
        except Exception as e:
            rospy.logerr(f"Error during shutdown: {e}")


def main():
    """主函数"""
    # 获取配置文件路径
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        # 默认配置文件路径
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '../config/task_config.yaml'
        )
    
    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}")
        sys.exit(1)
    
    try:
        # 创建并运行系统
        system = TaskSystem(config_path)
        system.run()
    except rospy.ROSInterruptException:
        pass
    except Exception as e:
        print(f"❌ 系统启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 