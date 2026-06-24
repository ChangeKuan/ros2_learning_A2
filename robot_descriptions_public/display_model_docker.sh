#!/bin/bash
# 用 Docker 运行 RViz 可视化机器人模型（宿主机无需安装 ROS2）
# 用法:
#   ./display_model_docker.sh                  # 基础模型（无手指）
#   ./display_model_docker.sh with_finger      # 带手指模型

IMAGE="robot-rviz:latest"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 首次运行时构建本地镜像（含 joint_state_publisher_gui / xacro）
if ! docker image inspect "$IMAGE" &>/dev/null; then
    echo "首次运行：构建 RViz 镜像（约 3-5 分钟）..."
    docker build -t "$IMAGE" -f "$SCRIPT_DIR/docker/Dockerfile.rviz" "$SCRIPT_DIR/docker"
fi

if [[ "$1" == "with_finger" ]]; then
    URDF="model_with_finger.urdf"
else
    URDF="model.urdf"
fi

# 允许 Docker 访问 X11
xhost +local:docker 2>/dev/null || true

echo "镜像: $IMAGE"
echo "URDF: $URDF"
echo ""
echo "首次运行会拉取镜像（约 3 GB）并编译包，约需 2-5 分钟。后续运行会复用缓存。"
echo ""

docker run --rm -it \
    --net=host \
    -e DISPLAY="$DISPLAY" \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    -v "$SCRIPT_DIR":/ws/src/robot_descriptions_public:ro \
    -v robot_rviz_build:/ws/build \
    -v robot_rviz_install:/ws/install \
    -v robot_rviz_log:/ws/log \
    "$IMAGE" \
    bash -c "
        source /opt/ros/jazzy/setup.bash && \
        cd /ws && \
        colcon build --packages-up-to robot_descriptions_public --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release 2>&1 | grep -E 'Summary|ERROR|error' && \
        source install/setup.bash && \
        ros2 launch robot_descriptions_public display.launch.py urdf:=$URDF
    "
