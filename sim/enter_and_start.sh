#!/bin/bash
# 进入容器并用 tmux 自动启动三个仿真服务
# 用法: ./enter_and_start.sh

CONTAINER="a2-ultra-sim"

# 确认容器正在运行
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "容器未运行，请先执行 ./start_sim.sh"
    exit 1
fi

# 把启动脚本复制进容器
docker cp "$(dirname "$0")/sim_services.sh" "$CONTAINER":/tmp/sim_services.sh
docker exec "$CONTAINER" chmod +x /tmp/sim_services.sh

# 以 root 安装依赖并打补丁
docker exec -u root "$CONTAINER" bash -c "
    which tmux &>/dev/null || apt-get install -y tmux -q
    sed -i 's/pos = \"0 0 [0-9.]*\"/pos = \"0 0 1\"/' \
        /home/agi/a2_simulation/mujoco_sim_ultra_2.0/resources/a2_t2d0_ultra/mujoco/body/torso.xml
"

docker exec -it "$CONTAINER" bash -c "bash /tmp/sim_services.sh"
