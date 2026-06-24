#!/bin/bash
# 在容器内运行：用 tmux 启动仿真三服务（支持多机器人隔离）
# 通过环境变量接收参数:
#   ROBOT_ID      机器人编号（0, 1, 2...）  默认 0
#   MC_PORT       MC HTTP 端口              默认 56322
#   ROS_DOMAIN_ID ROS2 DDS 域编号           默认 0
#
# 不要在宿主机直接运行，请通过 start_multi_sim.sh 调用

ROBOT_ID=${ROBOT_ID:-0}
MC_PORT=${MC_PORT:-56322}
ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}

SESSION="a2sim-r${ROBOT_ID}"

# 清理已有同名 session
tmux kill-session -t "$SESSION" 2>/dev/null || true

echo "Robot $ROBOT_ID: 补丁 MC HTTP 端口 → $MC_PORT"
# 每个容器有独立的写时复制层，这里修改只影响本容器
find /home/agi/a2_simulation/motion_control_ultra_2.0.19/config -name '*.yaml' \
    -exec sed -i "s/listen_port: 56322/listen_port: $MC_PORT/g" {} \;

echo "Robot $ROBOT_ID: 启动 tmux session $SESSION  (ROS_DOMAIN=$ROS_DOMAIN_ID)"
echo ""

# ── 窗口 1: Mujoco 仿真引擎 ──────────────────────────────────────────────────
tmux new-session -d -s "$SESSION" -n "mujoco" -x 220 -y 50
tmux send-keys -t "$SESSION:mujoco" \
    "cd /home/agi/a2_simulation/mujoco_sim_ultra_2.0/bin && \
     echo '[Robot $ROBOT_ID] Mujoco 仿真引擎' && \
     ROS_DOMAIN_ID=$ROS_DOMAIN_ID ./start_a2_t2d0_ultra.sh" \
    Enter

sleep 3

# ── 窗口 2: Motion Control ────────────────────────────────────────────────────
tmux new-window -t "$SESSION" -n "motion_ctrl"
tmux send-keys -t "$SESSION:motion_ctrl" \
    "cd /home/agi/a2_simulation/motion_control_ultra_2.0.19/scripts/motion_control && \
     echo '[Robot $ROBOT_ID] Motion Control (MC端口: $MC_PORT)' && \
     ROS_DOMAIN_ID=$ROS_DOMAIN_ID \
     AGIBOT_ROBOT_MODEL=A2_T2D0_FLAGSHIP \
     AGIBOT_ROBOT_FORM=with_casing \
     ./start_motion_control.sh" \
    Enter

sleep 3

# ── 窗口 3: Motion Player ─────────────────────────────────────────────────────
tmux new-window -t "$SESSION" -n "motion_player"
tmux send-keys -t "$SESSION:motion_player" \
    "cd /home/agi/a2_simulation/motion_player_ultra_2.0.19/scripts/motion_player && \
     echo '[Robot $ROBOT_ID] Motion Player (MQTT警告正常)' && \
     ROS_DOMAIN_ID=$ROS_DOMAIN_ID ./start_motion_player.sh" \
    Enter

sleep 2

# ── 窗口 4: 开发终端（等待 MC 就绪后自动站立）────────────────────────────────
tmux new-window -t "$SESSION" -n "dev"
tmux send-keys -t "$SESSION:dev" \
    "source /home/agi/a2_simulation/ros2_plugin_proto_x86_64/share/ros2_plugin_proto/local_setup.bash && \
     export ROS_DOMAIN_ID=$ROS_DOMAIN_ID && \
     echo '[Robot $ROBOT_ID] 开发终端 — 等待 MC 就绪 (port $MC_PORT)...'" \
    Enter

tmux send-keys -t "$SESSION:dev" \
    "python3 -c \"
import time, requests, json
from datetime import datetime

MC_PORT = $MC_PORT
url_check = f'http://127.0.0.1:{MC_PORT}/rpc/aimdk.protocol.McActionService/GetAvailableActions'
url_set   = f'http://127.0.0.1:{MC_PORT}/rpc/aimdk.protocol.McActionService/SetAction'
headers   = {'Content-Type': 'application/json'}

for _ in range(60):
    try:
        requests.post(url_check, headers=headers, json={}, timeout=1).raise_for_status()
        print(f'Robot $ROBOT_ID: MC 就绪')
        break
    except:
        time.sleep(1)

now = datetime.utcnow()
payload = {
    'header': {
        'timestamp': {'seconds': int(now.timestamp()), 'nanos': 0, 'ms_since_epoch': int(now.timestamp()*1000)},
        'control_source': 'ControlSource_SAFE'
    },
    'command': {'action': 'McAction_USE_EXT_CMD', 'ext_action': 'RL_JOINT_DEFAULT'}
}
r = requests.post(url_set, headers=headers, json=payload)
print(f'Robot $ROBOT_ID 自动站立:', json.dumps(r.json(), ensure_ascii=False))
\"" \
    Enter

echo ""
echo "Robot $ROBOT_ID 仿真服务已在后台启动"
echo "  tmux session : $SESSION"
echo "  MC HTTP 端口  : $MC_PORT"
echo "  ROS_DOMAIN_ID : $ROS_DOMAIN_ID"
echo ""
echo "  进入终端: docker exec -it a2-sim-$ROBOT_ID bash"
echo "            tmux attach -t $SESSION"
