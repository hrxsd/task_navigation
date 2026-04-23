#include <ros/ros.h>
#include <tf/transform_listener.h>
#include <tf/transform_broadcaster.h>

int main(int argc, char** argv)
{
    ros::init(argc, argv, "base_link_flat_publisher");
    ros::NodeHandle nh;

    tf::TransformListener tf_listener;
    tf::TransformBroadcaster tf_broadcaster;

    std::string target_frame = "map";         // 你参考的全局坐标系
    std::string source_frame = "base_link";   // 原始机器人底盘 frame
    std::string flat_frame   = "base_link_flat"; // 新的平面化 frame 名称

    ros::Rate rate(30.0); // 30Hz 发布
    while (ros::ok())
    {
        tf::StampedTransform transform;
        try
        {
            // 获取 map -> base_link 的 TF
            tf_listener.lookupTransform(target_frame, source_frame, ros::Time(0), transform);

            // 提取平移
            tf::Vector3 origin = transform.getOrigin();
            origin.setZ(0.0); // 固定 Z=0

            // 提取旋转，只保留 yaw
            double roll, pitch, yaw;
            tf::Matrix3x3(transform.getRotation()).getRPY(roll, pitch, yaw);
            tf::Quaternion flat_q;
            flat_q.setRPY(0.0, 0.0, yaw); // R,P 固定为 0，只保留 Yaw

            // 生成新的 transform
            tf::Transform flat_transform;
            flat_transform.setOrigin(origin);
            flat_transform.setRotation(flat_q);

            // 发布 map -> base_link_flat
            tf_broadcaster.sendTransform(
                tf::StampedTransform(flat_transform, ros::Time::now(), target_frame, flat_frame)
            );
        }
        catch (tf::TransformException &ex)
        {
            ROS_WARN_THROTTLE(1.0, "TF lookup failed: %s", ex.what());
        }

        rate.sleep();
    }

    return 0;
}