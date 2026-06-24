#!/bin/bash
# 在容器内运行：用 tmux 启动三个仿真服务
# 不要在宿主机上直接运行，请通过 enter_and_start.sh 调用

SESSION="a2sim"

# 如果 tmux session 已存在则先杀掉
tmux kill-session -t "$SESSION" 2>/dev/null || true

echo "正在启动仿真服务..."
echo ""

# 创建新 session，第一个窗口：Mujoco 仿真引擎
tmux new-session -d -s "$SESSION" -n "mujoco" -x 220 -y 50
tmux send-keys -t "$SESSION:mujoco" \
    "cd /home/agi/a2_simulation/mujoco_sim_ultra_2.0/bin && echo '[窗口1] Mujoco 仿真引擎' && ./start_a2_t2d0_ultra.sh" \
    Enter

# 等待 Mujoco 部分启动
sleep 3

# 第二个窗口：Motion Control
tmux new-window -t "$SESSION" -n "motion_ctrl"
tmux send-keys -t "$SESSION:motion_ctrl" \
    "cd /home/agi/a2_simulation/motion_control_ultra_2.0.19/scripts/motion_control && echo '[窗口2] Motion Control' && AGIBOT_ROBOT_MODEL=A2_T2D0_FLAGSHIP AGIBOT_ROBOT_FORM=with_casing ./start_motion_control.sh" \
    Enter

sleep 3

# 第三个窗口：Motion Player
tmux new-window -t "$SESSION" -n "motion_player"
tmux send-keys -t "$SESSION:motion_player" \
    "cd /home/agi/a2_simulation/motion_player_ultra_2.0.19/scripts/motion_player && echo '[窗口3] Motion Player (MQTT警告正常)' && ./start_motion_player.sh" \
    Enter

sleep 2

# 第四个窗口：预留的交互终端（用于运行 SetAction.py、walk.py 等）
tmux new-window -t "$SESSION" -n "dev"
tmux send-keys -t "$SESSION:dev" \
    "cd /home/agi/a2_simulation/tools-ultra/mc && source /home/agi/a2_simulation/ros2_plugin_proto_x86_64/share/ros2_plugin_proto/local_setup.bash && echo '[窗口4] 开发终端 — 等待 MC 就绪后自动站立...'" \
    Enter
tmux send-keys -t "$SESSION:dev" \
    "python3 -c \"
import time, requests, json
from datetime import datetime
url_check = 'http://127.0.0.1:56322/rpc/aimdk.protocol.McActionService/GetAvailableActions'
url_set   = 'http://127.0.0.1:56322/rpc/aimdk.protocol.McActionService/SetAction'
headers   = {'Content-Type': 'application/json'}
for _ in range(60):
    try:
        requests.post(url_check, headers=headers, json={}, timeout=1).raise_for_status()
        break
    except:
        time.sleep(1)
now = datetime.utcnow()
payload = {'header': {'timestamp': {'seconds': int(now.timestamp()), 'nanos': 0, 'ms_since_epoch': int(now.timestamp()*1000)}, 'control_source': 'ControlSource_SAFE'}, 'command': {'action': 'McAction_USE_EXT_CMD', 'ext_action': 'RL_JOINT_DEFAULT'}}
r = requests.post(url_set, headers=headers, json=payload)
print('自动站立:', json.dumps(r.json(), ensure_ascii=False))
\" && echo '[窗口4] 开发终端 — 可在此运行 SetAction.py、walk.py 等'" \
    Enter

echo ""
echo "====================================================="
echo "  三个仿真服务已启动（tmux session: $SESSION）"
echo "====================================================="
echo ""
echo "操作指引（等待约 10 秒服务就绪后执行）:"
echo ""
echo "  [窗口4 — 开发终端]"
echo "  步骤1: python3 SetAction.py    # 选择 RL_JOINT_DEFAULT (站立)"
echo "  步骤2: python3 SetAction.py    # 选择 RL_LOCOMOTION_DEFAULT (行走)"
echo "  步骤3: python3 walk.py         # 测试行走"
echo ""
echo "  切换 tmux 窗口: Ctrl+B 然后按窗口编号 (0/1/2/3)"
echo "  退出 tmux:       Ctrl+B 然后 D"
echo ""
echo "从宿主机连接仿真（MC 服务): ROBOT_TARGET=sim python3 ..."
echo ""

# 切换到第四个窗口（开发终端）
tmux attach -t "$SESSION:dev"
