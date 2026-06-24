#!/bin/bash
# 启动 A2 仿真环境
# 用法: ./start_sim.sh [--gpu]
#
# 前提:
#   - Linux x86_64，已安装 Docker
#   - X11 或 Wayland（Wayland 需 XWayland 在跑，Fedora 默认已启动）

set -e

IMAGE="tongyong-public-cn-shanghai.cr.volces.com/aima-public/a2-simulator:v2.0"
CONTAINER="a2-ultra-sim"

# ── 1. 登录镜像仓库 ───────────────────────────────────────────────────────────
echo "[1/4] 登录镜像仓库..."
docker login tongyong-public-cn-shanghai.cr.volces.com \
    -u crrobot@aima-public-reader \
    -p Aima123456

# ── 2. 拉取镜像（已存在则跳过）────────────────────────────────────────────────
if ! docker image inspect "$IMAGE" &>/dev/null; then
    echo "[2/4] 拉取镜像（约 5-10 GB，请耐心等待）..."
    docker pull "$IMAGE"
else
    echo "[2/4] 镜像已存在，跳过拉取"
fi

# ── 3. 允许 Docker 访问 X Window ──────────────────────────────────────────────
echo "[3/4] 配置 X11 访问权限..."
# Wayland 下 $DISPLAY 指向 XWayland，默认 :0；若未设置则手动补充
if [[ -z "$DISPLAY" && "$XDG_SESSION_TYPE" == "wayland" ]]; then
    export DISPLAY=:0
fi
xhost +local:docker 2>/dev/null || xhost +SI:localuser:root 2>/dev/null || true

# ── 4. 启动容器 ───────────────────────────────────────────────────────────────
echo "[4/4] 启动容器..."

# 先清理同名旧容器
docker rm -f "$CONTAINER" 2>/dev/null || true

if [[ "$1" == "--gpu" ]]; then
    echo "  使用 GPU 模式"
    docker run -it \
        --name="$CONTAINER" \
        --gpus all \
        --privileged \
        --net=host \
        --ipc=host \
        --pid=host \
        --cpuset-cpus="4-15" \
        -e DISPLAY="$DISPLAY" \
        -e NVIDIA_VISIBLE_DEVICES=all \
        -e NVIDIA_DRIVER_CAPABILITIES=all \
        -v /tmp/.X11-unix:/tmp/.X11-unix:rw,z \
        -v /run/dbus/system_bus_socket:/run/dbus/system_bus_socket:ro \
        -v /home/sucre/Code/robot:/home/sucre/Code/robot:z \
        -d "$IMAGE"
else
    docker run -it \
        --name="$CONTAINER" \
        --privileged \
        --net=host \
        --ipc=host \
        --pid=host \
        --cpuset-cpus="4-15" \
        -e DISPLAY="$DISPLAY" \
        -v /tmp/.X11-unix:/tmp/.X11-unix:rw,z \
        -v /run/dbus/system_bus_socket:/run/dbus/system_bus_socket:ro \
        -v /home/sucre/Code/robot:/home/sucre/Code/robot:z \
        -d "$IMAGE"
fi

echo ""
echo "容器已启动: $CONTAINER"
echo ""
echo "下一步：在容器内启动仿真服务"
echo "  ./enter_and_start.sh          # 用 tmux 自动启动三个服务"
echo "  docker exec -it $CONTAINER /bin/bash   # 或手动进入"
