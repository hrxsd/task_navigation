#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
相机接口模块
基于ROS话题进行图像捕获和处理
"""

import rospy
import cv2
import numpy as np
from sensor_msgs.msg import Image
from typing import Optional
import os
from datetime import datetime

# 尝试导入cv_bridge，如果失败则使用备用方案
try:
    from cv_bridge import CvBridge, CvBridgeError
    CV_BRIDGE_AVAILABLE = True
except ImportError as e:
    rospy.logwarn(f"cv_bridge import failed: {e}")
    CV_BRIDGE_AVAILABLE = False
    CvBridgeError = Exception


class CameraInterface:
    """基于ROS话题的相机接口"""
    
    def __init__(self, camera_topic: str = "/camera/image_raw"):
        """
        初始化相机接口
        
        Args:
            camera_topic: 相机图像话题名称
        """
        self.camera_topic = camera_topic
        self.current_image = None
        self.image_received = False
        self.last_image_time = None  # 记录最后一次图像更新时间
        self.bridge_error_count = 0
        self.max_bridge_errors = 3  # 减少到3次，更快切换到备用模式
        self.bridge_disabled = False
        
        # 初始化cv_bridge（如果可用）
        if CV_BRIDGE_AVAILABLE:
            try:
                self.bridge = CvBridge()
                rospy.loginfo("cv_bridge initialized successfully")
            except Exception as e:
                rospy.logwarn(f"cv_bridge initialization failed: {e}")
                self.bridge = None
        else:
            self.bridge = None
            rospy.logwarn("cv_bridge not available, using alternative image conversion")
        
        # 订阅相机话题
        try:
            self.image_subscriber = rospy.Subscriber(
                self.camera_topic, 
                Image, 
                self.image_callback
            )
            rospy.loginfo(f"Camera interface initialized, subscribing to {camera_topic}")
        except Exception as e:
            rospy.logerr(f"Failed to subscribe to camera topic: {e}")
            self.image_subscriber = None
        
    def image_callback(self, msg: Image):
        """
        图像话题回调函数
        
        Args:
            msg: 图像消息
        """
        try:
            cv_image = None
            
            # 如果cv_bridge已被禁用，直接使用备用方法
            if self.bridge_disabled:
                cv_image = self._alternative_image_conversion(msg)
            elif self.bridge is not None:
                try:
                    cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
                except Exception as e:
                    self.bridge_error_count += 1
                    
                    # 只在前几次错误时记录详细信息
                    if self.bridge_error_count <= 2:
                        rospy.logwarn(f"cv_bridge conversion failed (count: {self.bridge_error_count}): {e}")
                    elif self.bridge_error_count == self.max_bridge_errors:
                        rospy.logwarn(f"cv_bridge repeatedly failed, switching to alternative conversion method")
                        self.bridge_disabled = True
                    
                    # 使用备用方法
                    cv_image = self._alternative_image_conversion(msg)
            else:
                # 使用备用转换方法
                cv_image = self._alternative_image_conversion(msg)
            
            if cv_image is not None:
                self.current_image = cv_image
                self.image_received = True
                self.last_image_time = rospy.Time.now()  # 记录图像更新时间
            else:
                rospy.logwarn("Failed to convert image using all available methods")
                
        except Exception as e:
            rospy.logerr(f"Error in image callback: {e}")
            
    def _alternative_image_conversion(self, msg: Image) -> Optional[np.ndarray]:
        """
        备用的图像转换方法（不依赖cv_bridge）
        
        Args:
            msg: ROS图像消息
            
        Returns:
            np.ndarray: 转换后的OpenCV图像，失败则返回None
        """
        try:
            # 支持常见的图像编码格式
            if msg.encoding == "bgr8":
                # BGR8格式，直接转换
                np_arr = np.frombuffer(msg.data, dtype=np.uint8)
                cv_image = np_arr.reshape((msg.height, msg.width, 3))
                return cv_image
                
            elif msg.encoding == "rgb8":
                # RGB8格式，需要转换为BGR
                np_arr = np.frombuffer(msg.data, dtype=np.uint8)
                rgb_image = np_arr.reshape((msg.height, msg.width, 3))
                cv_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)
                return cv_image
                
            elif msg.encoding == "mono8":
                # 单通道灰度图，转换为3通道BGR
                np_arr = np.frombuffer(msg.data, dtype=np.uint8)
                gray_image = np_arr.reshape((msg.height, msg.width))
                cv_image = cv2.cvtColor(gray_image, cv2.COLOR_GRAY2BGR)
                return cv_image
                
            else:
                rospy.logwarn(f"Unsupported image encoding: {msg.encoding}")
                return None
                
        except Exception as e:
            rospy.logerr(f"Alternative image conversion failed: {e}")
            return None
            
    def capture_image(self, timeout: float = 5.0) -> Optional[np.ndarray]:
        """
        捕获新的图像（等待新帧到达）
        
        Args:
            timeout: 等待图像的超时时间（秒）
            
        Returns:
            np.ndarray: 捕获的图像，如果失败则返回None
        """
        # 记录当前时间作为基准
        capture_start_time = rospy.Time.now()
        rospy.loginfo("Waiting for new image frame...")
        
        # 等待新图像到达
        while not rospy.is_shutdown():
            rospy.sleep(0.1)  # 100ms检查间隔
            
            # 检查超时
            if (rospy.Time.now() - capture_start_time).to_sec() > timeout:
                rospy.logwarn("Image capture timeout - no new frame received")
                # 超时情况下，如果有图像就返回当前图像
                if self.current_image is not None:
                    rospy.logwarn("Returning last available image due to timeout")
                    return self.current_image.copy()
                return None
            
            # 检查是否有新图像（基于时间戳）
            if (self.current_image is not None and 
                self.last_image_time is not None and
                self.last_image_time > capture_start_time):
                # 找到了在捕获请求之后更新的图像
                rospy.loginfo("New image frame captured successfully")
                return self.current_image.copy()
            
            # 如果还没有任何图像，但已经接收到图像
            elif self.current_image is not None and self.last_image_time is None:
                rospy.loginfo("First image captured successfully")
                return self.current_image.copy()
                
        rospy.logwarn("Image capture interrupted")
        return None
        
    def _images_equal(self, img1: np.ndarray, img2: np.ndarray) -> bool:
        """
        检查两个图像是否相同（快速比较）
        
        Args:
            img1: 第一个图像
            img2: 第二个图像
            
        Returns:
            bool: 图像是否相同
        """
        try:
            # 快速检查：比较形状
            if img1.shape != img2.shape:
                return False
            
            # 快速检查：比较几个关键像素点
            h, w = img1.shape[:2]
            sample_points = [
                (0, 0), (0, w-1), (h-1, 0), (h-1, w-1),  # 四个角
                (h//2, w//2), (h//4, w//4), (3*h//4, 3*w//4)  # 中心和其他点
            ]
            
            for y, x in sample_points:
                if not np.array_equal(img1[y, x], img2[y, x]):
                    return False
            
            return True
        except Exception:
            return False
            
    def save_image(self, image: np.ndarray, save_path: str, 
                   filename: Optional[str] = None) -> bool:
        """
        保存图像到文件
        
        Args:
            image: 要保存的图像
            save_path: 保存路径
            filename: 文件名，如果为None则自动生成
            
        Returns:
            bool: 是否保存成功
        """
        try:
            # 确保保存目录存在
            os.makedirs(save_path, exist_ok=True)
            
            # 生成文件名
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"image_{timestamp}.jpg"
                
            full_path = os.path.join(save_path, filename)
            
            # 保存图像
            success = cv2.imwrite(full_path, image)
            
            if success:
                rospy.loginfo(f"Image saved to: {full_path}")
                return True
            else:
                rospy.logerr(f"Failed to save image to: {full_path}")
                return False
                
        except Exception as e:
            rospy.logerr(f"Error saving image: {e}")
            return False
            
    def capture_and_save(self, save_path: str, filename: Optional[str] = None,
                        timeout: float = 5.0) -> Optional[str]:
        """
        捕获图像并保存
        
        Args:
            save_path: 保存路径
            filename: 文件名
            timeout: 捕获超时时间
            
        Returns:
            str: 保存的文件路径，如果失败则返回None
        """
        # 捕获图像
        image = self.capture_image(timeout)
        if image is None:
            return None
            
        # 生成文件名
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"capture_{timestamp}.jpg"
            
        # 保存图像
        if self.save_image(image, save_path, filename):
            return os.path.join(save_path, filename)
        else:
            return None
            
    def get_image_info(self) -> dict:
        """
        获取当前图像信息
        
        Returns:
            dict: 图像信息
        """
        if self.current_image is not None:
            height, width, channels = self.current_image.shape
            return {
                "width": width,
                "height": height,
                "channels": channels,
                "dtype": str(self.current_image.dtype),
                "topic": self.camera_topic,
                "image_available": True,
                "bridge_available": CV_BRIDGE_AVAILABLE,
                "bridge_error_count": self.bridge_error_count,
                "bridge_disabled": self.bridge_disabled,
                "using_alternative_conversion": self.bridge_disabled
            }
        else:
            return {
                "topic": self.camera_topic,
                "image_available": False,
                "bridge_available": CV_BRIDGE_AVAILABLE,
                "bridge_error_count": self.bridge_error_count,
                "bridge_disabled": self.bridge_disabled,
                "using_alternative_conversion": self.bridge_disabled
            }
            
    def is_image_available(self) -> bool:
        """
        检查是否有图像可用
        
        Returns:
            bool: 是否有图像可用
        """
        return self.image_received and self.current_image is not None
        
    def reset(self):
        """重置图像状态"""
        self.current_image = None
        self.image_received = False
        
    def shutdown(self):
        """关闭相机接口"""
        rospy.loginfo("Shutting down camera interface")
        if hasattr(self, 'image_subscriber'):
            self.image_subscriber.unregister() 