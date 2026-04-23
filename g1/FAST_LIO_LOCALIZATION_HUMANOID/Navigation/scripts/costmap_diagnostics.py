#!/usr/bin/env python3
# coding: utf-8

import rospy
import rosgraph
import tf
from nav_msgs.srv import GetMap
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import PoseWithCovarianceStamped
import rosnode
import rostopic
import rosparam

from std_srvs.srv import Empty
import time

CHECK_INTERVAL = 5  # 每几秒检查一次

def topic_exists(topic_name):
    pubs, subs = rostopic.get_topic_list()
    return any(topic == topic_name for topic, _ in pubs + subs)

def tf_available(target_frame, source_frame):
    listener = tf.TransformListener()
    try:
        listener.waitForTransform(target_frame, source_frame, rospy.Time(0), rospy.Duration(2.0))
        return True
    except tf.Exception:
        return False

def get_param_safe(param_name, default=None):
    try:
        return rospy.get_param(param_name)
    except KeyError:
        return default

def check_costmap(ns="/move_base/local_costmap"):
    # 1. 检查costmap node是否存在
    node_name = ns + "/costmap"
    node_list = rosnode.get_node_names()
    if not any(ns in n for n in node_list):
        rospy.logwarn(f"[WARN] Costmap node not found under namespace: {node_name}")
        return

    # 2. 检查 topic 是否存在
    if not topic_exists(ns + "/costmap"):
        rospy.logwarn(f"[WARN] Topic {ns}/costmap not found.")
    else:
        rospy.loginfo(f"[OK] Topic {ns}/costmap exists.")

    if not topic_exists(ns + "/inflated_obstacles"):
        rospy.logwarn(f"[WARN] Topic {ns}/inflated_obstacles not found.")
    else:
        rospy.loginfo(f"[OK] Topic {ns}/inflated_obstacles exists.")

    # 3. 检查 TF frame
    global_frame = get_param_safe(ns + "/global_frame", "map")
    robot_base_frame = get_param_safe(ns + "/robot_base_frame", "base_link")

    if tf_available(global_frame, robot_base_frame):
        rospy.loginfo(f"[OK] TF available between {global_frame} and {robot_base_frame}")
    else:
        rospy.logerr(f"[ERROR] TF transform not available between {global_frame} and {robot_base_frame}")

    # 4. 检查参数
    rolling_window = get_param_safe(ns + "/rolling_window", False)
    update_freq = get_param_safe(ns + "/update_frequency", -1)
    publish_freq = get_param_safe(ns + "/publish_frequency", -1)
    width = get_param_safe(ns + "/width", -1)
    height = get_param_safe(ns + "/height", -1)

    rospy.loginfo(f"[PARAM] rolling_window: {rolling_window}")
    rospy.loginfo(f"[PARAM] update_frequency: {update_freq} Hz")
    rospy.loginfo(f"[PARAM] publish_frequency: {publish_freq} Hz")
    rospy.loginfo(f"[PARAM] width x height: {width} x {height}")

    # 5. 检查是否有costmap数据发布
    try:
        msg = rospy.wait_for_message(ns + "/costmap", OccupancyGrid, timeout=2.0)
        rospy.loginfo(f"[OK] Costmap received: resolution={msg.info.resolution}, size={msg.info.width}x{msg.info.height}")
    except rospy.ROSException:
        rospy.logerr(f"[ERROR] No messages on {ns}/costmap within timeout.")

    rospy.loginfo("-------- 诊断完成 --------")

def main():
    rospy.init_node("costmap_diagnostics", anonymous=True)
    ns = rospy.get_param("~namespace", "/move_base/local_costmap")
    rospy.loginfo(f"[*] Starting costmap diagnostics for namespace: {ns}")

    rate = rospy.Rate(1.0 / CHECK_INTERVAL)
    while not rospy.is_shutdown():
        try:
            check_costmap(ns)
        except Exception as e:
            rospy.logerr(f"[EXCEPTION] {e}")
        rate.sleep()

if __name__ == "__main__":
    main()
