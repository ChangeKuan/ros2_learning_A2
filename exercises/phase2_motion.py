#!/usr/bin/env python3
"""
Phase 2: 基础运动控制 — 头部、手部、行走
Phase 2: Basic Motion Control — Head, Hands, Walking

学习目标 / Learning objectives:
  1. 掌握 SetAction 切换机器人运动模式 / Use SetAction to switch motion modes
  2. 通过 HTTP RPC 控制颈部和手部关节 / Control neck and hand joints via HTTP RPC
  3. 通过 ROS2 Topic 发布行走速度指令 / Publish walking velocity commands via ROS2 Topic

完成标准：执行"问候序列" — 机器人点头 + 右手挥手 + 走两步
Success criteria: execute the "greeting sequence" — robot nods + waves right hand + walks two steps

⚠️  警告：运动控制指令会让机器人真实动作，请确保周围安全空间充足
⚠️  Warning: motion commands cause real robot movement; ensure adequate clearance around the robot.

运行方式 / How to run: python3 phase2_motion.py
"""

import os
import time
from datetime import datetime, timezone

import requests

# export ROBOT_TARGET=sim  (默认/default) 或/or  export ROBOT_TARGET=real
# export ROBOT_ID=0        (默认/default) 多机仿真时指定机器人编号，端口 = 56322 + ROBOT_ID
#                          Specify robot index for multi-robot sim; port = 56322 + ROBOT_ID
# 仿真可用 / Available in sim: SetAction, GetAction, SetNeckCommand, SetHandCommand, walk (all)
_SIM = os.environ.get("ROBOT_TARGET", "sim") == "sim"
MC_IP = "127.0.0.1" if _SIM else "192.168.100.100"
MC_PORT = 56322 + int(os.environ.get("ROBOT_ID", 0)) if _SIM else 56322
print(f"[config] 模式={'仿真' if _SIM else '真机'}  MC={MC_IP}:{MC_PORT}")
# [config] mode=sim/real


def make_header():
    now = datetime.now(timezone.utc)
    return {
        "timestamp": {
            "seconds": int(now.timestamp()),
            "nanos": now.microsecond * 1000,
            "ms_since_epoch": int(now.timestamp() * 1000),
        },
        "control_source": "ControlSource_SAFE",
    }


def rpc(service: str, method: str, payload: dict = None) -> dict:
    url = f"http://{MC_IP}:{MC_PORT}/rpc/{service}/{method}"
    resp = requests.post(
        url, headers={"Content-Type": "application/json"},
        json=payload or {}, timeout=3.0,
    )
    resp.raise_for_status()
    return resp.json()


# ─── 练习 2-1: 切换动作模式 / Exercise 2-1: Switch Action Mode ───────────────
def set_action(action_name: str):
    """
    将机器人切换到指定动作模式
    Switch the robot to the specified action mode.

    常用值 / Common values: "McAction_RL_LOCOMOTION_DEFAULT" (行走模式 / walking mode)
    """
    payload = {
        "command": {
            "action": "McAction_USE_EXT_CMD",
            "ext_action": action_name,
        }
    }
    return rpc("aimdk.protocol.McActionService", "SetAction", payload)


def wait_for_action(target: str, timeout: float = 10.0) -> bool:
    """轮询等待动作模式切换完成 / Poll until the action mode has switched."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = rpc("aimdk.protocol.McActionService", "GetAction")
        if result.get("info", {}).get("current_action") == target:
            return True
        time.sleep(0.5)
    return False


# ─── 练习 2-2: 控制颈部 / Exercise 2-2: Control the Neck ─────────────────────
def set_neck(shake_pos: float = 0.0, nod_pos: float = 0.0):
    """
    shake_pos: 左右摇头，单位 rad，范围约 [-0.6, 0.6]
               Left/right shake, in rad, range ~[-0.6, 0.6]
    nod_pos:   上下点头，单位 rad，范围约 [-0.3, 0.5]
               Up/down nod, in rad, range ~[-0.3, 0.5]
    """
    payload = {
        "header": make_header(),
        "data": {
            "shake": {
                "name": "idx27_head_joint1",
                "position": shake_pos,
                "velocity": 0.0,
                "effort": 0.0,
            },
            "nod": {
                "name": "idx28_head_joint2",
                "position": nod_pos,
                "velocity": 0.0,
                "effort": 0.0,
            },
        },
    }
    return rpc("aimdk.protocol.McMotionService", "SetNeckCommand", payload)


def nod_sequence():
    """点头动作: 低头 → 抬头 → 低头 → 回正 / Nod: bow → raise → bow → return to center"""
    print("  点头中...")  # Nodding...
    set_neck(nod_pos=0.4)
    time.sleep(0.5)
    set_neck(nod_pos=-0.1)
    time.sleep(0.5)
    set_neck(nod_pos=0.4)
    time.sleep(0.5)
    set_neck(nod_pos=0.0)


# ─── 练习 2-3: 控制手部 / Exercise 2-3: Control the Hands ────────────────────
def set_hand(left_positions=None, right_positions=None):
    """
    finger_positions: [thumb0, thumb1, index, middle, ring, pinky]
    范围 / Range: 0 (张开/open) ~ 2000 (握紧/closed)

    TODO: 参考 examples/mc/SetHandCommand.py 补全这个函数
          See examples/mc/SetHandCommand.py to complete this function.
    """
    def finger_data(positions):
        keys = ["thumb_pos_0", "thumb_pos_1", "index_pos", "middle_pos", "ring_pos", "pinky_pos"]
        return {
            "agi_hand": {
                "finger": {
                    "pos": dict(zip(keys, positions)),
                    "toq": {k.replace("pos", "toq"): 0 for k in keys},
                }
            }
        }

    data = {}
    if left_positions:
        data["left"] = finger_data(left_positions)
    if right_positions:
        data["right"] = finger_data(right_positions)

    payload = {"header": make_header(), "data": data}
    return rpc("aimdk.protocol.McMotionService", "SetHandCommand", payload)


def wave_sequence():
    """右手挥手: 张开 → 半握 → 张开 → 半握 → 张开
    Right hand wave: open → half-close → open → half-close → open
    """
    print("  挥手中...")  # Waving...
    open_hand = [0, 0, 0, 0, 0, 0]
    half_close = [1000, 1000, 1000, 1000, 1000, 1000]
    for _ in range(3):
        set_hand(right_positions=open_hand)
        time.sleep(0.3)
        set_hand(right_positions=half_close)
        time.sleep(0.3)
    set_hand(right_positions=open_hand)


# ─── 练习 2-4: 行走指令 (ROS2) / Exercise 2-4: Walking Command (ROS2) ────────
def walk_for_seconds(forward_vel: float, lateral_vel: float, angular_vel: float, duration: float):
    """
    通过 ROS2 Topic 发布行走速度指令 (50Hz)
    Publish walking velocity commands via ROS2 Topic at 50 Hz.

    forward_vel: 前进速度 m/s，正值前进，负值后退
                 Forward speed m/s; positive = forward, negative = backward
    lateral_vel: 侧移速度 m/s / Lateral speed m/s
    angular_vel: 转向角速度 rad/s / Turn angular velocity rad/s

    TODO: 导入 rclpy 和 RosMsgWrapper，创建 Publisher，
          在 duration 时间内以 50Hz 发布速度指令，然后发送停止指令
          Import rclpy and RosMsgWrapper, create a Publisher, publish at 50 Hz
          for `duration` seconds, then send a stop command.

    提示 / Hint: 参考 examples/mc/walk.py / see examples/mc/walk.py
          Topic: /motion/control/locomotion_velocity/pb_3Aaimdk_2Eprotocol_2EMcLocomotionVelocityChannel
          payload JSON: {"data": {"mode": 0, "forward_velocity": X, "lateral_velocity": Y, "angular_velocity": Z}}
    """
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
    from ros2_plugin_proto.msg import RosMsgWrapper

    WALK_TOPIC = "/motion/control/locomotion_velocity/pb_3Aaimdk_2Eprotocol_2EMcLocomotionVelocityChannel"

    class WalkNode(Node):
        def __init__(self):
            super().__init__("walk_node")
            qos = QoSProfile(
                history=QoSHistoryPolicy.KEEP_LAST,
                depth=10,
                reliability=QoSReliabilityPolicy.BEST_EFFORT,
            )
            self.pub = self.create_publisher(RosMsgWrapper, WALK_TOPIC, qos)

        def publish_velocity(self, fwd, lat, ang):
            import json as _json
            cmd = {"data": {"mode": 0, "forward_velocity": fwd,
                            "lateral_velocity": lat, "angular_velocity": ang}}
            msg = RosMsgWrapper()
            msg.serialization_type = "json"
            msg.data = [bytes([b]) for b in _json.dumps(cmd).encode()]
            self.pub.publish(msg)

    rclpy.init()
    node = WalkNode()
    deadline = time.time() + duration
    while time.time() < deadline:
        node.publish_velocity(forward_vel, lateral_vel, angular_vel)
        time.sleep(0.02)  # 50Hz
    node.publish_velocity(0.0, 0.0, 0.0)   # 停止 / Stop
    time.sleep(0.1)
    node.destroy_node()
    rclpy.shutdown()


# ─── 练习 2-5: 键盘实时控制 / Exercise 2-5: Keyboard Real-time Control ────────

# 数字键切换的模式表 key → (中文名, McAction 枚举字符串)
# Number-key mode table: key → (Chinese label, McAction enum string)
ACTION_MODES = {
    '1': ("强化行走",         "McAction_RL_LOCOMOTION_DEFAULT"),
    '2': ("力控站立",         "McAction_STAND_DEFAULT"),
    '3': ("普通行走",         "McAction_LOCOMOTION_DEFAULT"),
    '4': ("强化位控站立",     "McAction_RL_JOINT_DEFAULT"),
    '5': ("强化手臂伺服行走", "McAction_RL_LOCOMOTION_ARM_EXT_JOINT_SERVO"),
    '6': ("全身舞蹈",         "McAction_RL_WHOLE_BODY_DANCE"),
    '0': ("默认模式",         "McAction_DEFAULT"),
}


def keyboard_control():
    """
    键盘实时控制机器人运动，按 q 或 ESC 退出
    Keyboard real-time robot control. Press q or ESC to quit.

    运动 (速度指令) / Motion (velocity commands):
      W/S/A/D : 前进/后退/左平移/右平移 / Forward/backward/left-strafe/right-strafe
      ← / →   : 左转/右转 (角速度) / Turn left/right (angular velocity)
      空格/Space: 立即停止 / Stop immediately

    姿态 (SetAction) / Posture (SetAction):
      ↑ / ↓   : 起立/蹲下 / Stand up / Sit down

    模式切换 (SetAction) / Mode switch (SetAction):
      1  强化行走           McAction_RL_LOCOMOTION_DEFAULT
      2  力控站立           McAction_STAND_DEFAULT
      3  普通行走           McAction_LOCOMOTION_DEFAULT
      4  强化位控站立       McAction_RL_JOINT_DEFAULT
      5  强化手臂伺服行走   McAction_RL_LOCOMOTION_ARM_EXT_JOINT_SERVO
      6  全身舞蹈           McAction_RL_WHOLE_BODY_DANCE
      0  默认模式           McAction_DEFAULT
    """
    import sys
    import select
    import termios
    import threading
    import tty
    import json as _json

    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
    from ros2_plugin_proto.msg import RosMsgWrapper

    WALK_TOPIC = "/motion/control/locomotion_velocity/pb_3Aaimdk_2Eprotocol_2EMcLocomotionVelocityChannel"
    FWD_SPEED = 0.2    # m/s
    LAT_SPEED = 0.2    # m/s
    ANG_SPEED = 0.5    # rad/s
    KEY_TIMEOUT = 0.4  # 超过此时间无按键则自动停止 / Auto-stop if no key pressed within this time

    class WalkNode(Node):
        def __init__(self):
            super().__init__("keyboard_walk_node")
            qos = QoSProfile(
                history=QoSHistoryPolicy.KEEP_LAST,
                depth=10,
                reliability=QoSReliabilityPolicy.BEST_EFFORT,
            )
            self.pub = self.create_publisher(RosMsgWrapper, WALK_TOPIC, qos)

        def publish_velocity(self, fwd, lat, ang):
            cmd = {"data": {"mode": 0, "forward_velocity": fwd,
                            "lateral_velocity": lat, "angular_velocity": ang}}
            msg = RosMsgWrapper()
            msg.serialization_type = "json"
            msg.data = [bytes([b]) for b in _json.dumps(cmd).encode()]
            self.pub.publish(msg)

    def read_key(fd):
        """读取按键，返回字符串或方向键名 UP/DOWN/LEFT/RIGHT
        Read a keypress; return a string or direction name UP/DOWN/LEFT/RIGHT.
        """
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
        """在 raw 模式下安全输出一行（\r\n 代替 \n）
        Safe single-line output in raw terminal mode (uses \r\n instead of \n).
        """
        sys.stdout.write(f"\r{msg}\r\n")
        sys.stdout.flush()

    print("=" * 52)
    print("键盘控制模式  (q / ESC 退出) / Keyboard control mode (q/ESC to quit)")
    print("-" * 52)
    print("  运动/Motion:  W前 S后 A左移 D右移  ←→转向  空格停止")
    print("  姿态/Posture: ↑起立  ↓蹲下")
    print("  模式/Mode:    1强化行走 2力控站立 3普通行走 4强化位控站立")
    print("                5强化手臂伺服行走 6全身舞蹈 0默认模式")
    print("=" * 52)

    rclpy.init()
    node = WalkNode()

    vel = [0.0, 0.0, 0.0]        # [fwd, lat, ang]
    last_key_time = [time.time()]
    running = [True]

    def publish_loop():
        while running[0]:
            if time.time() - last_key_time[0] > KEY_TIMEOUT:
                node.publish_velocity(0.0, 0.0, 0.0)
            else:
                node.publish_velocity(*vel)
            time.sleep(0.02)  # 50 Hz

    pub_thread = threading.Thread(target=publish_loop, daemon=True)
    pub_thread.start()

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            key = read_key(fd)

            # ── 退出 / Quit ────────────────────────────────────
            if key in ('q', 'Q', 'ESC', '\x03'):
                break

            # ── 运动速度 / Velocity ────────────────────────────
            elif key == 'w':
                vel[:] = [FWD_SPEED, 0.0, 0.0]
            elif key == 's':
                vel[:] = [-FWD_SPEED, 0.0, 0.0]
            elif key == 'a':
                vel[:] = [0.0, LAT_SPEED, 0.0]
            elif key == 'd':
                vel[:] = [0.0, -LAT_SPEED, 0.0]
            elif key == 'LEFT':
                vel[:] = [0.0, 0.0, ANG_SPEED]
            elif key == 'RIGHT':
                vel[:] = [0.0, 0.0, -ANG_SPEED]
            elif key == ' ':
                vel[:] = [0.0, 0.0, 0.0]

            # ── 姿态 (SetAction，不影响速度状态) / Posture (does not affect velocity state) ──
            elif key == 'UP':
                log("[姿态] 起立 → McAction_RL_STAND_UP")  # [Posture] Stand up
                set_action("McAction_RL_STAND_UP")
                continue
            elif key == 'DOWN':
                log("[姿态] 蹲下 → McAction_RL_SIT_DOWN")  # [Posture] Sit down
                set_action("McAction_RL_SIT_DOWN")
                continue

            # ── 模式切换 / Mode switch ─────────────────────────
            elif key in ACTION_MODES:
                label, action = ACTION_MODES[key]
                log(f"[模式] [{key}] {label} → {action}")  # [Mode]
                set_action(action)
                continue

            else:
                continue

            last_key_time[0] = time.time()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        running[0] = False
        pub_thread.join(timeout=1.0)
        node.publish_velocity(0.0, 0.0, 0.0)
        node.destroy_node()
        rclpy.shutdown()
        print("\n键盘控制已退出")  # Keyboard control exited


# ─── 综合练习: 问候序列 / Combined Exercise: Greeting Sequence ────────────────
def greeting_sequence():
    """
    完整问候动作 / Full greeting sequence:
    1. 确保在行走模式 / Ensure walking mode
    2. 点头两次 / Nod twice
    3. 右手挥手 / Wave right hand
    4. 前行 1 秒 / Walk forward 1 second
    5. 回正头部 / Return head to center

    TODO: 调用上面的函数组合成完整序列
          Call the functions above to compose the full sequence.
    """
    print("开始问候序列...")  # Starting greeting sequence...

    print("[1] 切换到行走模式")  # [1] Switching to walking mode
    set_action("McAction_RL_LOCOMOTION_DEFAULT")
    if not wait_for_action("McAction_RL_LOCOMOTION_DEFAULT"):
        print("  ❌ 模式切换超时，请检查机器人状态")  # Mode switch timed out; check robot state
        return

    print("[2] 点头")  # [2] Nod
    nod_sequence()
    time.sleep(0.5)

    print("[3] 挥手")  # [3] Wave
    wave_sequence()
    time.sleep(0.5)

    print("[4] 前行 1.5 秒")  # [4] Walk forward 1.5 seconds
    walk_for_seconds(0.15, 0.0, 0.0, 1.5)

    print("[5] 回正头部")  # [5] Return head to center
    set_neck(0.0, 0.0)

    print("问候序列完成 ✓")  # Greeting sequence complete


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "keyboard":
        set_action("McAction_RL_LOCOMOTION_DEFAULT")
        if wait_for_action("McAction_RL_LOCOMOTION_DEFAULT"):
            keyboard_control()
    else:
        greeting_sequence()
