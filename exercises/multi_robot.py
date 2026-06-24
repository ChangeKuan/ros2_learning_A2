#!/usr/bin/env python3
"""
多机器人控制示例
Multi-Robot Control Example

前提 / Prerequisites: 先运行 ./sim/start_multi_sim.sh [N] 启动 N 台仿真机器人
                      First run ./sim/start_multi_sim.sh [N] to start N simulation robots.

运行 / Run:
  python3 exercises/multi_robot.py              # 动作演示（2 台）/ Action demo (2 robots)
  NUM_ROBOTS=3 python3 exercises/multi_robot.py # 动作演示（3 台）/ Action demo (3 robots)
  python3 exercises/multi_robot.py keyboard     # 单键盘 Tab 切换控制 / Single-keyboard Tab switching

说明 / Notes:
  每台机器人 MC HTTP 端口 = 56322 + robot_id
  Each robot's MC HTTP port = 56322 + robot_id

  SetAction / SetNeck / SetHand 均通过 HTTP RPC，无需 ROS2 域配置
  SetAction / SetNeck / SetHand all use HTTP RPC; no ROS2 domain configuration needed.

  行走指令 (WASD) 通过子进程 + ROS_DOMAIN_ID 隔离，需要 rclpy 可用
  Walking commands (WASD) use subprocess + ROS_DOMAIN_ID isolation; requires rclpy.
"""

import os
import subprocess
import time
import threading
from datetime import datetime, timezone

import requests


# ── Robot 客户端 / Robot Client ───────────────────────────────────────────────

class Robot:
    """单台机器人的 HTTP RPC 控制封装 / HTTP RPC control wrapper for a single robot"""

    BASE_PORT = 56322

    def __init__(self, robot_id: int):
        self.robot_id = robot_id
        self.port = self.BASE_PORT + robot_id
        self._base = f"http://127.0.0.1:{self.port}/rpc"

    def __repr__(self):
        return f"Robot({self.robot_id}, port={self.port})"

    def rpc(self, service: str, method: str, payload: dict = None) -> dict:
        url = f"{self._base}/{service}/{method}"
        resp = requests.post(
            url, headers={"Content-Type": "application/json"},
            json=payload or {}, timeout=3.0,
        )
        resp.raise_for_status()
        return resp.json()

    def ping(self) -> bool:
        try:
            self.rpc("aimdk.protocol.McActionService", "GetAvailableActions")
            return True
        except Exception:
            return False

    def set_action(self, action_name: str) -> dict:
        return self.rpc("aimdk.protocol.McActionService", "SetAction", {
            "command": {"action": "McAction_USE_EXT_CMD", "ext_action": action_name}
        })

    def get_action(self) -> str:
        result = self.rpc("aimdk.protocol.McActionService", "GetAction")
        return result.get("info", {}).get("current_action", "unknown")

    def set_neck(self, shake: float = 0.0, nod: float = 0.0) -> dict:
        now = datetime.now(timezone.utc)
        header = {
            "timestamp": {
                "seconds": int(now.timestamp()),
                "nanos": now.microsecond * 1000,
                "ms_since_epoch": int(now.timestamp() * 1000),
            },
            "control_source": "ControlSource_SAFE",
        }
        return self.rpc("aimdk.protocol.McMotionService", "SetNeckCommand", {
            "header": header,
            "data": {
                "shake": {"name": "idx27_head_joint1", "position": shake, "velocity": 0.0, "effort": 0.0},
                "nod":   {"name": "idx28_head_joint2", "position": nod,   "velocity": 0.0, "effort": 0.0},
            },
        })


# ── 多机编排工具 / Multi-Robot Orchestration Tools ────────────────────────────

def wait_ready(robots: list, timeout: float = 30.0) -> list:
    """等待所有机器人就绪，返回在线机器人列表
    Wait for all robots to be ready; returns the list of online robots.
    """
    print(f"等待 {len(robots)} 台机器人就绪（最多 {timeout:.0f}s）...")
    # Waiting for {N} robots to be ready (up to {timeout}s)...
    deadline = time.time() + timeout
    ready = [False] * len(robots)
    while time.time() < deadline:
        for i, robot in enumerate(robots):
            if not ready[i]:
                ready[i] = robot.ping()
        if all(ready):
            break
        time.sleep(1.0)

    online = []
    for robot, ok in zip(robots, ready):
        status = "✓" if ok else "✗"
        print(f"  {status} {robot}")
        if ok:
            online.append(robot)
    return online


def parallel(robots: list, fn, *args, **kwargs):
    """对多台机器人并行执行同一函数 / Execute the same function on multiple robots in parallel."""
    threads = [threading.Thread(target=fn, args=(r, *args), kwargs=kwargs) for r in robots]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


# ── 动作示例 / Action Demos ───────────────────────────────────────────────────

def demo_synchronized_nod(robots: list):
    """所有机器人同时点头 / All robots nod simultaneously."""
    print(f"\n[同步点头] {len(robots)} 台同时执行...")  # [Sync nod] executing simultaneously
    def nod(robot):
        for pos in [0.4, -0.1, 0.4, 0.0]:
            robot.set_neck(nod=pos)
            time.sleep(0.5)
    parallel(robots, nod)
    print("[同步点头] 完成")  # [Sync nod] Done


def demo_sequential_nod(robots: list):
    """机器人依次点头（接力式）/ Robots nod one after another (relay style)."""
    print(f"\n[接力点头] {len(robots)} 台依次执行...")  # [Relay nod] executing one by one
    for robot in robots:
        print(f"  Robot {robot.robot_id} ...")
        robot.set_neck(nod=0.4)
        time.sleep(0.4)
        robot.set_neck(nod=0.0)
        time.sleep(0.2)
    print("[接力点头] 完成")  # [Relay nod] Done


def demo_wave_pattern(robots: list):
    """波浪式摇头（每台机器人错开相位）/ Wave shake with phase offset per robot."""
    print(f"\n[波浪摇头] {len(robots)} 台错相执行...")  # [Wave shake] phase-offset execution
    n = len(robots)
    steps = 16
    period = 2.0

    def wave(robot, phase_offset):
        import math
        for step in range(steps):
            t = step / steps * period
            angle = 0.5 * math.sin(2 * math.pi * t / period + phase_offset)
            robot.set_neck(shake=angle)
            time.sleep(period / steps)
        robot.set_neck(shake=0.0)

    threads = [
        threading.Thread(target=wave, args=(r, 2 * 3.14159 * i / n))
        for i, r in enumerate(robots)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print("[波浪摇头] 完成")  # [Wave shake] Done


# ── 键盘控制 / Keyboard Control ──────────────────────────────────────────────

# 子进程脚本：在指定 ROS_DOMAIN_ID 下发布行走速度指令
# Subprocess script: publish walking velocity commands under the specified ROS_DOMAIN_ID.
# 通过 python3 -c <script> fwd lat ang dur 调用，env 中设置 ROS_DOMAIN_ID
# Invoked via python3 -c <script> fwd lat ang dur; ROS_DOMAIN_ID is set in env.
_WALK_SCRIPT = r"""
import sys, time, json
try:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, QoSHistoryPolicy, QoSReliabilityPolicy
    from ros2_plugin_proto.msg import RosMsgWrapper
except ImportError:
    sys.exit(0)

TOPIC = "/motion/control/locomotion_velocity/pb_3Aaimdk_2Eprotocol_2EMcLocomotionVelocityChannel"

class _W(Node):
    def __init__(self):
        super().__init__("walk_multi")
        qos = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST, depth=10,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
        )
        self.pub = self.create_publisher(RosMsgWrapper, TOPIC, qos)

    def send(self, fwd, lat, ang):
        cmd = {"data": {"mode": 0, "forward_velocity": fwd,
                        "lateral_velocity": lat, "angular_velocity": ang}}
        msg = RosMsgWrapper()
        msg.serialization_type = "json"
        msg.data = [bytes([b]) for b in json.dumps(cmd).encode()]
        self.pub.publish(msg)

fwd, lat, ang, dur = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
rclpy.init()
node = _W()
deadline = time.time() + dur
while time.time() < deadline:
    node.send(fwd, lat, ang)
    time.sleep(0.02)
node.send(0, 0, 0)
time.sleep(0.1)
node.destroy_node()
rclpy.shutdown()
"""

_ACTION_MODES = {
    '1': ("强化行走",         "McAction_RL_LOCOMOTION_DEFAULT"),
    '2': ("力控站立",         "McAction_STAND_DEFAULT"),
    '3': ("普通行走",         "McAction_LOCOMOTION_DEFAULT"),
    '4': ("强化位控站立",     "McAction_RL_JOINT_DEFAULT"),
    '5': ("强化手臂伺服行走", "McAction_RL_LOCOMOTION_ARM_EXT_JOINT_SERVO"),
    '6': ("全身舞蹈",         "McAction_RL_WHOLE_BODY_DANCE"),
    '0': ("默认模式",         "McAction_DEFAULT"),
}


def multi_keyboard_control(robots: list):
    """
    单键盘控制多台机器人，Tab 键切换目标机器人
    Single-keyboard control for multiple robots; Tab switches the target robot.

    Tab      : 循环切换目标机器人 / Cycle through target robots
    W/S/A/D  : 前/后/左移/右移（子进程 ROS2 发布，需 rclpy 可用）
               Forward/back/left-strafe/right-strafe (subprocess ROS2 publish; requires rclpy)
    ←/→      : 左转/右转 / Turn left/right
    空格/Space: 立即停止行走 / Stop walking immediately
    ↑/↓      : 起立/蹲下（SetAction via HTTP）/ Stand up / Sit down (SetAction via HTTP)
    1~6      : 切换动作模式（SetAction via HTTP）/ Switch action mode (SetAction via HTTP)
    0        : 默认模式 / Default mode
    q / ESC  : 退出 / Quit
    """
    import sys
    import select
    import termios
    import tty

    if not robots:
        print("没有可用机器人")  # No robots available
        return

    FWD_SPEED = 0.2
    LAT_SPEED = 0.2
    ANG_SPEED = 0.5
    KEY_TIMEOUT = 0.4   # 单次行走子进程持续时间（秒）/ Duration of each walk subprocess (seconds)

    active_idx = [0]    # 当前选中机器人的下标（列表以便闭包写入）/ Current selected robot index (list for closure write)
    broadcast  = [False]  # 广播模式：True 时所有按键同时发给全体机器人 / Broadcast mode: True sends keys to all robots

    def cur() -> Robot:
        return robots[active_idx[0]]

    def targets() -> list:
        return robots if broadcast[0] else [cur()]

    def read_key(fd):
        ch = os.read(fd, 1)
        if ch != b'\x1b':
            return ch.decode('utf-8', errors='ignore')
        ready, _, _ = select.select([fd], [], [], 0.05)
        if not ready:
            return 'ESC'
        ch2 = os.read(fd, 1)
        if ch2 != b'[':
            return 'ESC'
        ready, _, _ = select.select([fd], [], [], 0.05)
        if not ready:
            return 'ESC'
        ch3 = os.read(fd, 1)
        return {'A': 'UP', 'B': 'DOWN', 'C': 'RIGHT', 'D': 'LEFT'}.get(ch3.decode(), 'ESC')

    def log(msg):
        sys.stdout.write(f"\r{msg}\r\n")
        sys.stdout.flush()

    def status():
        if broadcast[0]:
            bar = "  ".join(f"【R{r.robot_id}:{r.port}】" for r in robots)
            hint = "广播全体 · b单选 · q退出"  # Broadcast all · b=single · q=quit
        else:
            bar = "  ".join(
                f"【R{r.robot_id}:{r.port}】" if i == active_idx[0] else f" R{r.robot_id}:{r.port} "
                for i, r in enumerate(robots)
            )
            hint = "Tab切换 · b广播 · q退出"  # Tab=switch · b=broadcast · q=quit
        sys.stdout.write(f"\r  {bar}  | {hint}  ")
        sys.stdout.flush()

    _ROS2_SETUP = (
        "source /opt/ros/humble/setup.bash 2>/dev/null; "
        "source /home/agi/a2_simulation/ros2_plugin_proto_x86_64/share/ros2_plugin_proto/local_setup.bash 2>/dev/null; "
    )

    def spawn_walk(fwd: float, lat: float, ang: float, duration: float = KEY_TIMEOUT + 0.05):
        """在子进程中以对应 ROS_DOMAIN_ID 发布行走速度指令
        Publish walking velocity commands in a subprocess using the appropriate ROS_DOMAIN_ID.
        """
        for r in targets():
            env = os.environ.copy()
            env['ROS_DOMAIN_ID'] = str(r.robot_id)
            script = _ROS2_SETUP + f"python3 -c {__import__('shlex').quote(_WALK_SCRIPT)} {fwd} {lat} {ang} {duration}"
            subprocess.Popen(
                ['bash', '-c', script],
                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )

    print("=" * 58)
    print("多机器人键盘控制  (Tab 切换 · b 广播 · q 退出)")
    print("Multi-robot keyboard control  (Tab=switch · b=broadcast · q=quit)")
    print("-" * 58)
    print("  运动/Motion: W前 S后 A左移 D右移  ←→转向  空格停止")
    print("  姿态/Posture: ↑起立  ↓蹲下")
    print("  模式/Mode: 1强化行走 2力控站立 3普通行走 4强化位控站立")
    print("             5强化手臂伺服行走 6全身舞蹈 0默认模式")
    print("  b: 切换「单选」/「广播全体」模式 / Toggle single/broadcast mode")
    print("=" * 58)
    status()

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            key = read_key(fd)
            r = cur()

            if key in ('q', 'Q', 'ESC', '\x03'):
                break

            elif key == '\t':
                active_idx[0] = (active_idx[0] + 1) % len(robots)
                status()

            elif key in ('b', 'B'):
                broadcast[0] = not broadcast[0]
                status()

            elif key == 'w':
                spawn_walk(FWD_SPEED, 0.0, 0.0)
            elif key == 's':
                spawn_walk(-FWD_SPEED, 0.0, 0.0)
            elif key == 'a':
                spawn_walk(0.0, LAT_SPEED, 0.0)
            elif key == 'd':
                spawn_walk(0.0, -LAT_SPEED, 0.0)
            elif key == 'LEFT':
                spawn_walk(0.0, 0.0, ANG_SPEED)
            elif key == 'RIGHT':
                spawn_walk(0.0, 0.0, -ANG_SPEED)
            elif key == ' ':
                spawn_walk(0.0, 0.0, 0.0, 0.1)

            elif key == 'UP':
                who = "全体" if broadcast[0] else f"R{r.robot_id}"
                log(f"[{who}] 站立停止 (RL_JOINT_DEFAULT)")  # Stand/stop
                parallel(targets(), lambda rb: rb.set_action("McAction_RL_JOINT_DEFAULT"))
                status()
            elif key == 'DOWN':
                who = "全体" if broadcast[0] else f"R{r.robot_id}"
                log(f"[{who}] 蹲下 (RL_SIT_DOWN)")  # Sit down
                parallel(targets(), lambda rb: rb.set_action("McAction_RL_SIT_DOWN"))
                status()

            elif key in _ACTION_MODES:
                label, action = _ACTION_MODES[key]
                who = "全体" if broadcast[0] else f"R{r.robot_id}"
                log(f"[{who}] {label} → {action}")
                parallel(targets(), lambda rb, a=action: rb.set_action(a))
                status()

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        print("\n\n键盘控制已退出")  # Keyboard control exited


# ── 主程序 / Main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys as _sys

    N = int(os.environ.get("NUM_ROBOTS", 2))
    robots = [Robot(robot_id=i) for i in range(N)]

    print(f"多机器人控制  ({N} 台)  端口 {robots[0].port}~{robots[-1].port}")
    print(f"Multi-robot control  ({N} robots)  ports {robots[0].port}~{robots[-1].port}")
    print()

    online = wait_ready(robots, timeout=30.0)
    if not online:
        print("\n没有在线的机器人，请先启动仿真:")  # No online robots; start the simulation first:
        print("  ./sim/start_multi_sim.sh")
        _sys.exit(1)

    print(f"\n{len(online)} / {N} 台在线")  # {N} robots online

    if len(_sys.argv) > 1 and _sys.argv[1] == "keyboard":
        # 单键盘 Tab 切换控制 / Single-keyboard Tab-switch control
        print("先切换到行走模式...")  # Switching to walking mode first...
        parallel(online, lambda r: r.set_action("McAction_RL_LOCOMOTION_DEFAULT"))
        time.sleep(2.0)
        multi_keyboard_control(online)
    else:
        # 动作演示 / Action demo
        parallel(online, lambda r: r.set_action("McAction_RL_LOCOMOTION_DEFAULT"))
        time.sleep(2.0)

        demo_synchronized_nod(online)
        time.sleep(0.5)

        demo_sequential_nod(online)
        time.sleep(0.5)

        demo_wave_pattern(online)

        print("\n还原姿态...")  # Restoring posture...
        parallel(online, lambda r: r.set_neck(0.0, 0.0))
        print("完成")  # Done
