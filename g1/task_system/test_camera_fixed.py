#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试实时图像捕获功能
验证是否能捕获到新的图像帧而不是缓存的旧图像
"""

import rospy
import sys
import os
import time

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(project_root, 'src'))

def test_real_time_capture():
    """测试实时图像捕获"""
    print("🔍 测试实时图像捕获功能...")
    
    try:
        # 初始化ROS节点
        rospy.init_node('test_real_time_capture', anonymous=True)
        print("✅ ROS节点初始化成功")
        
        # 导入相机接口
        from ros_interface.camera_interface import CameraInterface
        
        # 创建相机接口
        print("🔧 创建相机接口...")
        camera = CameraInterface("/camera/color/image_raw")
        
        # 等待相机接口初始化
        print("⏳ 等待相机接口初始化...")
        time.sleep(3)
        
        # 进行多次捕获测试，模拟机器人到达不同位置
        print("\n📷 进行多次图像捕获测试...")
        
        for i in range(3):
            print(f"\n--- 第 {i+1} 次捕获 ---")
            print("🤖 模拟机器人移动到新位置...")
            
            # 模拟机器人移动的时间延迟
            if i > 0:
                time.sleep(2)  # 等待2秒，模拟机器人移动时间
            
            print("📸 开始捕获新图像...")
            capture_start = time.time()
            
            # 捕获图像
            image = camera.capture_image(timeout=10)
            capture_end = time.time()
            
            if image is not None:
                print(f"✅ 图像捕获成功！")
                print(f"   尺寸: {image.shape}")
                print(f"   捕获耗时: {capture_end - capture_start:.2f} 秒")
                
                # 保存图像
                save_path = os.path.join(project_root, "src/utils/image")
                filename = f"real_time_test_{i+1}_{int(time.time())}.jpg"
                success = camera.save_image(image, save_path, filename)
                
                if success:
                    print(f"   ✅ 图像已保存: {filename}")
                else:
                    print(f"   ❌ 图像保存失败")
                    
                # 计算图像的简单特征用于比较
                mean_brightness = image.mean()
                print(f"   图像特征: 平均亮度 = {mean_brightness:.2f}")
                
            else:
                print(f"❌ 第 {i+1} 次图像捕获失败")
                
            # 获取相机状态
            info = camera.get_image_info()
            print(f"   相机状态: 错误计数={info.get('bridge_error_count', 0)}, "
                  f"使用备用转换={info.get('using_alternative_conversion', False)}")
        
        print("\n📊 测试总结:")
        print("如果看到不同的捕获耗时和图像特征，说明捕获的是新图像")
        print("如果所有捕获都是瞬间完成且特征相同，说明返回的是缓存图像")
        
        camera.shutdown()
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_capture_timing():
    """测试捕获时机"""
    print("\n🕐 测试图像捕获时机...")
    
    try:
        from ros_interface.camera_interface import CameraInterface
        camera = CameraInterface("/camera/color/image_raw")
        
        time.sleep(2)  # 等待初始化
        
        print("第一次快速捕获（应该很快）:")
        start = time.time()
        image1 = camera.capture_image(timeout=5)
        end = time.time()
        print(f"耗时: {end - start:.2f} 秒")
        
        print("\n等待3秒后第二次捕获（应该等待新帧）:")
        time.sleep(3)
        start = time.time()
        image2 = camera.capture_image(timeout=5)
        end = time.time()
        print(f"耗时: {end - start:.2f} 秒")
        
        if image1 is not None and image2 is not None:
            # 简单比较图像是否不同
            diff = abs(image1.mean() - image2.mean())
            print(f"两次捕获的图像差异: {diff:.2f}")
            if diff > 1.0:
                print("✅ 捕获到了不同的图像，功能正常")
            else:
                print("⚠️ 两次图像非常相似，可能是相同场景")
        
        camera.shutdown()
        return True
        
    except Exception as e:
        print(f"❌ 时机测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🧪 实时图像捕获测试")
    print("="*50)
    print("此测试将验证系统是否能捕获实时的新图像")
    print("而不是返回程序启动时缓存的旧图像")
    print("="*50)
    
    try:
        # 运行测试
        test1_success = test_real_time_capture()
        test2_success = test_capture_timing()
        
        print("\n" + "="*50)
        print("📊 测试结果")
        print("="*50)
        
        if test1_success and test2_success:
            print("🎉 实时图像捕获测试完成！")
            print("\n💡 关键指标:")
            print("  - 如果捕获耗时 > 0.1秒，说明在等待新帧")
            print("  - 如果图像特征有差异，说明捕获了不同图像")
            print("  - 日志中应该显示 'New image frame captured successfully'")
            print("\n现在机器人到达目标点后应该能捕获到当前位置的实时图像！")
        else:
            print("❌ 测试未完全通过，请检查错误信息")
            
    except KeyboardInterrupt:
        print("\n🛑 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")

if __name__ == "__main__":
    main()
