#!/bin/bash
# 启动多台机器人仿真（每台独立容器，隔离 IPC + ROS2 域）
# 用法: ./start_multi_sim.sh [N] [--gpu]
#   N: 机器人数量（默认 2，最多 8）
#
# 每台机器人分配:
#   容器名: a2-sim-0, a2-sim-1, ...
#   MC HTTP 端口: 56322, 56323, ...  (宿主机直接访问)
#   ROS_DOMAIN_ID: 0, 1, ...         (ROS2 话题隔离)
#
# 停止所有: docker rm -f $(docker ps -aq --filter 'name=a2-sim-')

set -e

IMAGE="tongyong-public-cn-shanghai.cr.volces.com/aima-public/a2-simulator:v2.0"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── 解析参数 ──────────────────────────────────────────────────────────────────
N=2
GPU_FLAG=""
for arg in "$@"; do
    if [[ "$arg" == "--gpu" ]]; then
        GPU_FLAG="--gpu"
    elif [[ "$arg" =~ ^[0-9]+$ ]]; then
        N=$arg
    fi
done

if (( N < 1 || N > 8 )); then
    echo "错误: 机器人数量须在 1~8 之间"
    exit 1
fi

# ── 1. 登录镜像仓库 ───────────────────────────────────────────────────────────
echo "[1/4] 登录镜像仓库..."
docker login tongyong-public-cn-shanghai.cr.volces.com \
    -u crrobot@aima-public-reader -p Aima123456 2>/dev/null || true

# ── 2. 拉取镜像 ───────────────────────────────────────────────────────────────
if ! docker image inspect "$IMAGE" &>/dev/null; then
    echo "[2/4] 拉取镜像（约 5-10 GB，请耐心等待）..."
    docker pull "$IMAGE"
else
    echo "[2/4] 镜像已存在，跳过拉取"
fi

# ── 3. X11 访问权限 ───────────────────────────────────────────────────────────
echo "[3/4] 配置 X11..."
if [[ -z "$DISPLAY" && "$XDG_SESSION_TYPE" == "wayland" ]]; then
    export DISPLAY=:0
fi
xhost +local:docker 2>/dev/null || xhost +SI:localuser:root 2>/dev/null || true

# ── 4. 逐台启动容器 ───────────────────────────────────────────────────────────
echo "[4/4] 启动 $N 台机器人容器..."
echo ""

for i in $(seq 0 $((N-1))); do
    CONTAINER="a2-sim-$i"
    MC_PORT=$((56322 + i))
    ROS_DOMAIN=$i

    echo "  [Robot $i] 容器=$CONTAINER  MC端口=$MC_PORT  ROS_DOMAIN=$ROS_DOMAIN"

    # 清理旧容器
    docker rm -f "$CONTAINER" 2>/dev/null || true

    GPU_ARGS=()
    [[ -n "$GPU_FLAG" ]] && GPU_ARGS=(--gpus all -e NVIDIA_VISIBLE_DEVICES=all -e NVIDIA_DRIVER_CAPABILITIES=all)

    # 启动容器:
    #   --net=host       HTTP RPC 直接访问（端口通过 MC 配置区分）
    #   不加 --ipc=host  每个容器独立 Iceoryx IPC 命名空间
    #   不加 --pid=host  每个容器独立 PID 命名空间，iox-roudi 互不干扰
    docker run -d \
        --name="$CONTAINER" \
        --privileged \
        --net=host \
        --shm-size=512m \
        --cpuset-cpus="4-15" \
        -e DISPLAY="$DISPLAY" \
        -e ROBOT_ID="$i" \
        -e MC_PORT="$MC_PORT" \
        -e ROS_DOMAIN_ID="$ROS_DOMAIN" \
        -v /tmp/.X11-unix:/tmp/.X11-unix:rw,z \
        -v /run/dbus/system_bus_socket:/run/dbus/system_bus_socket:ro \
        -v /home/sucre/Code/robot:/home/sucre/Code/robot:z \
        "${GPU_ARGS[@]}" \
        "$IMAGE" sleep infinity

    # 安装 tmux，应用 torso 高度补丁，写入 ROS2 source 到 .bashrc
    docker exec -u root "$CONTAINER" bash -c "
        which tmux &>/dev/null || apt-get install -y tmux -q 2>/dev/null
        sed -i 's/pos = \"0 0 [0-9.]*\"/pos = \"0 0 1\"/' \
            /home/agi/a2_simulation/mujoco_sim_ultra_2.0/resources/a2_t2d0_ultra/mujoco/body/torso.xml
        grep -q 'ros/humble/setup.bash' /root/.bashrc 2>/dev/null || \
            echo 'source /opt/ros/humble/setup.bash' >> /root/.bashrc
        grep -q 'ros2_plugin_proto' /root/.bashrc 2>/dev/null || \
            echo 'source /home/agi/a2_simulation/ros2_plugin_proto_x86_64/share/ros2_plugin_proto/local_setup.bash' >> /root/.bashrc
    "
    docker exec "$CONTAINER" bash -c "
        grep -q 'ros/humble/setup.bash' ~/.bashrc 2>/dev/null || \
            echo 'source /opt/ros/humble/setup.bash' >> ~/.bashrc
        grep -q 'ros2_plugin_proto' ~/.bashrc 2>/dev/null || \
            echo 'source /home/agi/a2_simulation/ros2_plugin_proto_x86_64/share/ros2_plugin_proto/local_setup.bash' >> ~/.bashrc
    "

    # 复制启动脚本并后台运行
    docker cp "$SCRIPT_DIR/multi_sim_services.sh" "$CONTAINER":/tmp/multi_sim_services.sh
    docker exec -u root "$CONTAINER" chmod +x /tmp/multi_sim_services.sh
    docker exec -d "$CONTAINER" bash -c \
        "ROBOT_ID=$i MC_PORT=$MC_PORT ROS_DOMAIN_ID=$ROS_DOMAIN bash /tmp/multi_sim_services.sh"

done

echo ""
echo "============================================================"
echo "  $N 台机器人仿真已启动，等待约 15 秒服务就绪"
echo "============================================================"
echo ""
printf "  %-8s %-20s %-12s\n" "Robot" "MC HTTP 端口" "ROS_DOMAIN_ID"
printf "  %-8s %-20s %-12s\n" "-----" "------------" "-------------"
for i in $(seq 0 $((N-1))); do
    printf "  %-8s %-20s %-12s\n" "Robot $i" "127.0.0.1:$((56322+i))" "$i"
done
echo ""
echo "Python 控制:"
echo "  python3 exercises/multi_robot.py          # 多机演示"
echo "  ROBOT_ID=0 python3 exercises/phase2_motion.py  # 单独控制 Robot 0"
echo "  ROBOT_ID=1 python3 exercises/phase2_motion.py  # 单独控制 Robot 1"
echo ""
echo "进入容器终端:"
for i in $(seq 0 $((N-1))); do
    echo "  docker exec -it a2-sim-$i bash -c 'tmux attach -t a2sim-r$i'"
done
echo ""
echo "停止所有:"
echo "  docker rm -f \$(docker ps -aq --filter 'name=a2-sim-')"
