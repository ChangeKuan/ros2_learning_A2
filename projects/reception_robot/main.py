#!/usr/bin/env python3
"""
接待机器人 — 主程序
Reception Robot — Main Program

功能 / Features:
  1. 待机，等待唤醒词 (小爱同学 / 你好小爱 等) / Standby, waiting for wake word
  2. 唤醒后问候，询问目的地 / Greet after wake, ask for destination
  3. 监听 ASR 识别结果，匹配地图导航点 / Listen for ASR result, match to map waypoint
  4. 导航到目标地点，到达后挥手告别 / Navigate to destination, wave goodbye on arrival
  5. 自动回到待机状态 / Automatically return to standby

运行前提 / Prerequisites:
  - 机器人已上线并连接同一网段 / Robot is online and on the same network
  - ROS2 环境已 source / ROS2 environment sourced: source /opt/ros/humble/setup.bash
  - SDK 已安装 / SDK installed:
    pip install ../../agibot_a2_aimdk-dev2.0/prebuilt/a2_aimdk-2.0.0-py3-none-any.whl

运行方式 / How to run:
  python3 main.py

快速测试（不需要机器人，模拟模式）/ Quick test (no robot needed, simulate mode):
  python3 main.py --simulate
"""

import sys
import time
import threading

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from ros2_plugin_proto.msg import RosMsgWrapper
from aimdk.protocol_pb2 import WakeUpResult, AsrResult

import robot_client as rc
from state_machine import ReceptionRobot, State

# ── 配置: 修改为你地图上实际的导航点 ─────────────────────────────────────────
# Configuration: update to match the actual waypoints on your map
WAYPOINT_MAP = {
    # 导航点名称 (ASR 会匹配这些词): 地图导航点 ID
    # Waypoint name (ASR will match these words): map waypoint ID
    "前台": 101,
    "会议室": 202,
    "茶水间": 303,
    "大厅": 404,
}

WAKEUP_TOPIC = "/agent/wakeup/pb_3Aaimdk_2Eprotocol_2EWakeUpResult"
ASR_TOPIC = "/agent/asr_result/pb_3Aaimdk_2Eprotocol_2EAsrResult"


class ReceptionNode(Node):
    """ROS2 节点：监听唤醒词和 ASR 结果
    ROS2 node: listen for wake word and ASR results.
    """

    def __init__(self, robot: ReceptionRobot):
        super().__init__("reception_robot")
        self.robot = robot
        self._wakeup_event = threading.Event()
        self._asr_text = None
        self._asr_event = threading.Event()

        qos_reliable = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST, depth=10,
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.VOLATILE,
        )
        qos_best_effort = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST, depth=10,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
        )

        self.create_subscription(RosMsgWrapper, WAKEUP_TOPIC, self._on_wakeup, qos_reliable)
        self.create_subscription(RosMsgWrapper, ASR_TOPIC, self._on_asr, qos_best_effort)
        self.get_logger().info("接待机器人节点已启动")  # Reception robot node started

    def _on_wakeup(self, msg):
        if msg.serialization_type != "pb":
            return
        result = WakeUpResult()
        result.ParseFromString(b"".join(msg.data))
        self.get_logger().info(f"检测到唤醒词: {result}")  # Wake word detected
        self._wakeup_event.set()

    def _on_asr(self, msg):
        if msg.serialization_type != "pb":
            return
        result = AsrResult()
        result.ParseFromString(b"".join(msg.data))
        text = result.text.strip()
        if text:
            self.get_logger().info(f"ASR 识别: {text}")  # ASR recognized
            self._asr_text = text
            self._asr_event.set()

    def wait_for_wakeup(self, timeout=None) -> bool:
        """阻塞等待唤醒词，返回是否触发
        Block until a wake word is detected; returns whether it was triggered.
        """
        triggered = self._wakeup_event.wait(timeout)
        self._wakeup_event.clear()
        return triggered

    def wait_for_asr(self, timeout=8.0) -> str | None:
        """阻塞等待 ASR 结果，返回识别文本或 None
        Block until an ASR result arrives; returns the recognized text or None.
        """
        self._asr_event.clear()
        self._asr_text = None
        got = self._asr_event.wait(timeout)
        return self._asr_text if got else None


def run_main_loop(robot: ReceptionRobot, node: ReceptionNode):
    """主循环：驱动状态机 / Main loop: drive the state machine"""
    robot.handle_idle()

    while True:
        current = robot.state

        if current == State.IDLE:
            print("[主循环] 等待唤醒词 (Ctrl+C 退出)...")  # [Main loop] Waiting for wake word (Ctrl+C to quit)...
            triggered = node.wait_for_wakeup(timeout=None)
            if triggered:
                robot._transition(State.GREETING)

        elif current == State.GREETING:
            robot.handle_greeting()
            # handle_greeting 内部会转到 LISTENING / handle_greeting transitions to LISTENING internally

        elif current == State.LISTENING:
            print("[主循环] 等待语音指令 (8秒超时)...")  # [Main loop] Waiting for voice command (8s timeout)...
            text = node.wait_for_asr(timeout=8.0)
            if text:
                recognized = robot.handle_listening(text)
                if not recognized:
                    # 未识别到目的地，继续等待 / Destination not recognized; keep waiting
                    pass
            else:
                rc.say("您没有说话，已回到待机状态")  # No speech detected; returning to standby
                robot._transition(State.IDLE)
                robot.handle_idle()

        elif current == State.NAVIGATING:
            done = robot.handle_navigating()
            if not done:
                time.sleep(1.0)

        elif current == State.ARRIVED:
            robot.handle_arrived()
            # handle_arrived 内部会转到 IDLE / handle_arrived transitions to IDLE internally
            robot.handle_idle()

        elif current == State.ERROR:
            robot.handle_idle()


def simulate_mode():
    """模拟模式：不连接机器人，验证状态机逻辑
    Simulate mode: verify state machine logic without connecting to a robot.
    """
    print("=" * 50)
    print("模拟模式 (不连接机器人) / Simulate mode (no robot connection)")
    print("=" * 50)

    # 替换 robot_client 函数为 mock / Replace robot_client functions with mocks
    rc.say = lambda text, **kw: print(f"[TTS] {text}")
    rc.light_standby = lambda: print("[灯光] 蓝色待机")     # [Light] Blue standby
    rc.light_greeting = lambda: print("[灯光] 绿色问候")     # [Light] Green greeting
    rc.light_navigating = lambda: print("[灯光] 黄色导航")   # [Light] Yellow navigating
    rc.light_arrived = lambda: print("[灯光] 青色到达")      # [Light] Cyan arrived
    rc.light_error = lambda: print("[灯光] 红色错误")        # [Light] Red error
    rc.set_neck = lambda **kw: None
    rc.set_hand = lambda **kw: None
    rc.set_action = lambda x: None
    rc.wait_for_action = lambda x, **kw: True
    rc.navigate_to = lambda *a, **kw: 999
    rc.get_nav_state = lambda *a: "PncServiceState_SUCCESS"
    rc.cancel_nav = lambda *a: None

    robot = ReceptionRobot(WAYPOINT_MAP, map_id=1)
    robot.handle_idle()

    print("\n--- 模拟唤醒 / Simulate wake word ---")
    robot._transition(State.GREETING)
    robot.handle_greeting()

    print("\n--- 模拟 ASR: '我想去会议室' / Simulate ASR: 'I want to go to the meeting room' ---")
    robot.handle_listening("我想去会议室")

    print("\n--- 模拟导航状态轮询 / Simulate navigation state poll ---")
    robot.handle_navigating()

    print("\n--- 到达 / Arrived ---")
    robot.handle_arrived()

    print("\n模拟完成 / Simulation complete")


def main():
    if "--simulate" in sys.argv:
        simulate_mode()
        return

    # 获取当前地图 ID / Get current map ID
    try:
        map_id = rc.get_current_map_id()
        print(f"当前地图 ID: {map_id}")  # Current map ID
    except rc.RobotAPIError as e:
        print(f"无法连接机器人: {e}")  # Unable to connect to robot
        print("提示: 使用 --simulate 参数进行模拟测试")  # Tip: use --simulate for offline testing
        sys.exit(1)

    robot = ReceptionRobot(WAYPOINT_MAP, map_id)

    rclpy.init()
    node = ReceptionNode(robot)
    executor = rclpy.executors.SingleThreadedExecutor()
    executor.add_node(node)

    # 在后台线程运行 ROS2 executor / Run ROS2 executor in a background thread
    ros_thread = threading.Thread(target=executor.spin, daemon=True)
    ros_thread.start()

    try:
        run_main_loop(robot, node)
    except KeyboardInterrupt:
        print("\n收到退出信号")  # Exit signal received
    finally:
        rc.light_standby()
        if robot.current_task_id:
            try:
                rc.cancel_nav(robot.current_task_id)
            except rc.RobotAPIError:
                pass
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
