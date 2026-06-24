#!/bin/bash
# 一键停止 A2 仿真环境
# 用法: ./stop_sim.sh

CONTAINER="a2-ultra-sim"
SESSION="a2sim"

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "容器未运行，无需操作"
    exit 0
fi

echo "[1/2] 停止容器内仿真服务（tmux session: $SESSION）..."
docker exec "$CONTAINER" tmux kill-session -t "$SESSION" 2>/dev/null && echo "  tmux session 已终止" || echo "  session 不存在，跳过"

echo "[2/2] 停止并移除容器..."
docker rm -f "$CONTAINER"

echo ""
echo "仿真已完全停止"
