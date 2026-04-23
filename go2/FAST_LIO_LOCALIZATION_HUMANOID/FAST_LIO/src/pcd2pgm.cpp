#include <ros/ros.h>

#include <nav_msgs/OccupancyGrid.h>
#include <nav_msgs/GetMap.h>

#include <sensor_msgs/PointCloud2.h>
#include <pcl/io/pcd_io.h>
#include <pcl_conversions/pcl_conversions.h>

#include <pcl/point_types.h>
#include <pcl/filters/passthrough.h>  //直通滤波器头文件
#include <pcl/filters/voxel_grid.h>  //体素滤波器头文件
#include <pcl/filters/statistical_outlier_removal.h>   //统计滤波器头文件
#include <pcl/filters/conditional_removal.h>    //条件滤波器头文件
#include <pcl/filters/radius_outlier_removal.h>   //半径滤波器头文件
#include <pcl/common/common.h>
#include <pcl/common/pca.h>
#include <pcl/common/transforms.h>

#include <Eigen/Dense>

std::string file_directory;
std::string file_name;
std::string pcd_file;

std::string map_topic_name;

const std::string pcd_format = ".pcd";

nav_msgs::OccupancyGrid map_topic_msg;

double thre_z_min = 0.1;
double thre_z_max = 1.0;
int flag_pass_through = 0;

double grid_x = 0.1;
double grid_y = 0.1;
double grid_z = 0.1;

double map_resolution = 0.05;

double thre_radius = 0.1;

pcl::PointCloud<pcl::PointXYZ>::Ptr cloud_after_PassThrough(new pcl::PointCloud<pcl::PointXYZ>);
pcl::PointCloud<pcl::PointXYZ>::Ptr cloud_after_Radius(new pcl::PointCloud<pcl::PointXYZ>);
pcl::PointCloud<pcl::PointXYZ>::Ptr pcd_cloud(new pcl::PointCloud<pcl::PointXYZ>);

void PassThroughFilter(const double& thre_low, const double& thre_high, const bool& flag_in);
void RadiusOutlierFilter(const pcl::PointCloud<pcl::PointXYZ>::Ptr& pcd_cloud, const double &radius, const int &thre_count);
void SetMapTopicMsg(const pcl::PointCloud<pcl::PointXYZ>::Ptr cloud, nav_msgs::OccupancyGrid& msg);

/// 自动矫正点云到水平面
pcl::PointCloud<pcl::PointXYZ>::Ptr AlignCloudToXYPlane(const pcl::PointCloud<pcl::PointXYZ>::Ptr& cloud_in)
{
    pcl::PointCloud<pcl::PointXYZ>::Ptr cloud_out(new pcl::PointCloud<pcl::PointXYZ>);

    if (cloud_in->empty())
    {
        ROS_WARN("Input cloud is empty!");
        return cloud_out;
    }

    // 1. 计算协方差矩阵 & 特征值分解
    Eigen::Vector4f centroid;
    pcl::compute3DCentroid(*cloud_in, centroid);

    Eigen::Matrix3f covariance;
    pcl::computeCovarianceMatrixNormalized(*cloud_in, centroid, covariance);

    Eigen::SelfAdjointEigenSolver<Eigen::Matrix3f> solver(covariance);
    Eigen::Matrix3f eig_vectors = solver.eigenvectors();  // 特征向量（列向量）
    Eigen::Vector3f eig_values = solver.eigenvalues();

    // 2. 找到最小特征值对应的特征向量 → 地面法向量
    int min_index;
    eig_values.minCoeff(&min_index);
    Eigen::Vector3f normal = eig_vectors.col(min_index);

    // 确保法向量朝上（正 z）
    if (normal(2) < 0)
        normal = -normal;

    // 3. 计算旋转矩阵：把 normal 转到 (0,0,1)
    Eigen::Vector3f target(0.0, 0.0, 1.0);
    Eigen::Vector3f axis = normal.cross(target);
    double angle = acos(normal.dot(target) / (normal.norm() * target.norm()));

    Eigen::Matrix3f rotation = Eigen::Matrix3f::Identity();
    if (axis.norm() > 1e-6)  // 避免除零
    {
        axis.normalize();
        rotation = Eigen::AngleAxisf(angle, axis);
    }

    // 4. 构造齐次变换矩阵
    Eigen::Affine3f transform = Eigen::Affine3f::Identity();
    transform.linear() = rotation;

    // 5. 应用旋转到点云
    pcl::transformPointCloud(*cloud_in, *cloud_out, transform);

    ROS_INFO("Aligned cloud to XY plane. Rotation angle: %.3f deg", angle * 180.0 / M_PI);

    return cloud_out;
}


int main(int argc, char** argv)
{
   ros::init(argc, argv, "pcl_filters");
   ros::NodeHandle nh;
   ros::NodeHandle private_nh("~");

   ros::Rate loop_rate(1.0);

   private_nh.param("file_directory", file_directory, std::string("/home/unitree/navtest_ws/src/FAST_LIO_LOCALIZATION_HUMANOID/FAST_LIO/PCD/"));
   ROS_INFO("*** file_directory = %s ***\n", file_directory.c_str());

   private_nh.param("file_name", file_name, std::string("scans"));
   ROS_INFO("*** file_name = %s ***\n", file_name.c_str());

   pcd_file = file_directory + file_name + pcd_format;
   ROS_INFO("*** pcd_file = %s ***\n", pcd_file.c_str());

   private_nh.param("thre_z_min", thre_z_min, 0.1);
   private_nh.param("thre_z_max", thre_z_max, 3.0);
   private_nh.param("flag_pass_through", flag_pass_through, 0);
   private_nh.param("grid_x", grid_x, 0.05);
   private_nh.param("grid_y", grid_y, 0.05);
   private_nh.param("grid_z", grid_z, 0.1);
   private_nh.param("thre_radius", thre_radius, 0.5);
   private_nh.param("map_resolution", map_resolution, 0.05);
   private_nh.param("map_topic_name", map_topic_name, std::string("map"));

   ros::Publisher map_topic_pub = nh.advertise<nav_msgs::OccupancyGrid>(map_topic_name, 1);

   if (pcl::io::loadPCDFile<pcl::PointXYZ> (pcd_file, *pcd_cloud) == -1)
   {
     PCL_ERROR ("Couldn't read file: %s \n", pcd_file.c_str());
     return (-1);
   }

   std::cout << "初始点云数据点数：" << pcd_cloud->points.size() << std::endl;

   // 自动矫正点云到水平
   pcd_cloud = AlignCloudToXYPlane(pcd_cloud);

   PassThroughFilter(thre_z_min, thre_z_max, bool(flag_pass_through));

   //   RadiusOutlierFilter(cloud_after_PassThrough, 0.1, 10);
   //   SetMapTopicMsg(cloud_after_Radius, map_topic_msg);

   SetMapTopicMsg(cloud_after_PassThrough, map_topic_msg);

   while(ros::ok())
   {
     map_topic_pub.publish(map_topic_msg);

     loop_rate.sleep();

     ros::spinOnce();
   }

   return 0;
}


void PassThroughFilter(const double &thre_low, const double &thre_high, const bool &flag_in)
{
    pcl::PassThrough<pcl::PointXYZ> passthrough;
    passthrough.setInputCloud(pcd_cloud);
    passthrough.setFilterFieldName("z");
    passthrough.setFilterLimits(thre_low, thre_high);
    passthrough.setFilterLimitsNegative(flag_in);
    passthrough.filter(*cloud_after_PassThrough);
    std::cout << "直通滤波后点云数据点数：" << cloud_after_PassThrough->points.size() << std::endl;
}

void RadiusOutlierFilter(const pcl::PointCloud<pcl::PointXYZ>::Ptr& pcd_cloud0, const double &radius, const int &thre_count)
{
    pcl::RadiusOutlierRemoval<pcl::PointXYZ> radiusoutlier;
    radiusoutlier.setInputCloud(pcd_cloud0);
    radiusoutlier.setRadiusSearch(radius);
    radiusoutlier.setMinNeighborsInRadius(thre_count);

    radiusoutlier.filter(*cloud_after_Radius);
    std::cout << "半径滤波后点云数据点数：" << cloud_after_Radius->points.size() << std::endl;
}

void SetMapTopicMsg(const pcl::PointCloud<pcl::PointXYZ>::Ptr cloud, nav_msgs::OccupancyGrid& msg)
{
  msg.header.seq = 0;
  msg.header.stamp = ros::Time::now();
  msg.header.frame_id = "map";

  msg.info.map_load_time = ros::Time::now();
  msg.info.resolution = map_resolution;

  double x_min, x_max, y_min, y_max;

  if(cloud->points.empty())
  {
    ROS_WARN("pcd is empty!\n");
    return;
  }

  for(int i = 0; i < cloud->points.size() - 1; i++)
  {
    if(i == 0)
    {
      x_min = x_max = cloud->points[i].x;
      y_min = y_max = cloud->points[i].y;
    }

    double x = cloud->points[i].x;
    double y = cloud->points[i].y;

    if(x < x_min) x_min = x;
    if(x > x_max) x_max = x;

    if(y < y_min) y_min = y;
    if(y > y_max) y_max = y;
  }

  msg.info.origin.position.x = x_min;
  msg.info.origin.position.y = y_min;
  msg.info.origin.position.z = 0.0;
  msg.info.origin.orientation.x = 0.0;
  msg.info.origin.orientation.y = 0.0;
  msg.info.origin.orientation.z = 0.0;
  msg.info.origin.orientation.w = 1.0;

  msg.info.width = int((x_max - x_min) / map_resolution);
  msg.info.height = int((y_max - y_min) / map_resolution);

  msg.data.resize(msg.info.width * msg.info.height);
  msg.data.assign(msg.info.width * msg.info.height, 0);

  ROS_INFO("data size = %d\n", (int)msg.data.size());

  for(int iter = 0; iter < cloud->points.size(); iter++)
  {
    int i = int((cloud->points[iter].x - x_min) / map_resolution);
    if(i < 0 || i >= msg.info.width) continue;

    int j = int((cloud->points[iter].y - y_min) / map_resolution);
    if(j < 0 || j >= msg.info.height - 1) continue;

    msg.data[i + j * msg.info.width] = 100;
  }
}
