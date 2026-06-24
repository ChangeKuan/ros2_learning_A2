#!/usr/bin/env python3
"""
Phase 4: 语音与交互 — TTS、唤醒词、RGB 灯光
Phase 4: Voice and Interaction — TTS, Wake Word, RGB Lights

学习目标 / Learning objectives:
  1. 通过 HTTP API 让机器人说话 (TTS) / Make the robot speak via HTTP API (TTS)
  2. 通过 ROS2 Topic 监听唤醒词事件 / Listen for wake word events via ROS2 Topic
  3. 控制 RGB 灯光配合状态反馈 / Control RGB lights for state feedback
  4. 组合成"听到唤醒词 → 改变灯光 + 语音回应"的交互流
     Combine into a "wake word → change lights + speak" interaction flow

完成标准 / Success criteria:
  机器人听到唤醒词后自动说一句话并亮绿灯，5 秒后恢复蓝色待机灯光
  After detecting the wake word, the robot speaks and turns on green light,
  then restores the blue standby light after 5 seconds.

运行方式 / How to run: python3 phase4_voice.py
(需要 ROS2 环境 / Requires ROS2 environment: source /opt/ros/humble/setup.bash)
"""

import os
import time

import requests

# ⚠ Phase 4 语音功能仿真不可用：TTS/ASR/唤醒词/灯光均不在仿真容器内
# ⚠ Voice features are not available in sim: TTS/ASR/wake word/lights are not in the sim container.
# 如需测试 / To test: export ROBOT_TARGET=real  或/or  python3 phase4_voice.py test (HTTP only)
_SIM = os.environ.get("ROBOT_TARGET", "sim") == "sim"
NAV_IP = "127.0.0.1" if _SIM else "192.168.100.110"
if _SIM:
    print("[config] 仿真模式 — TTS/灯光/唤醒词不可用，可运行 'python3 phase4_voice.py test' 测试连通性")
    # [config] Sim mode — TTS/lights/wake word unavailable; run 'python3 phase4_voice.py test' to test connectivity


def rpc(ip: str, port: int, service: str, method: str, payload: dict = None) -> dict:
    url = f"http://{ip}:{port}/rpc/{service}/{method}"
    resp = requests.post(
        url, headers={"Content-Type": "application/json"},
        json=payload or {}, timeout=5.0,
    )
    resp.raise_for_status()
    return resp.json()


# ─── 练习 4-1: TTS 语音播报 / Exercise 4-1: TTS Speech Output ────────────────
def say(text: str, priority: str = "INTERACTION_L6", interrupted: bool = True):
    """
    服务: aimdk.protocol.TTSService
    接口: PlayTTS
    端口: 59301

    Service: aimdk.protocol.TTSService
    Method:  PlayTTS
    Port:    59301

    priority 等级 / Priority levels: INTERACTION_L1 (最低/lowest) ~ INTERACTION_L9 (最高/highest)
    interrupted: True 表示可以被更高优先级打断 / True means higher-priority TTS can interrupt

    TODO: 参考 examples/agent/tts_broadcast.sh 补全
          See examples/agent/tts_broadcast.sh to complete.
    """
    payload = {
        "text": text,
        "priority_level": priority,
        "domain": "example",
        "trace_id": f"phase4_{int(time.time())}",
        "is_interrupted": interrupted,
    }
    return rpc(NAV_IP, 59301, "aimdk.protocol.TTSService", "PlayTTS", payload)


# ─── 练习 4-2: RGB 灯光控制 / Exercise 4-2: RGB Light Control ────────────────
def set_light(red: int, green: int, blue: int, effect: int = 2, control: int = 1):
    """
    服务: aimdk.protocol.HalRgbLightService
    接口: SetRgbLightCommand
    端口: 52893

    Service: aimdk.protocol.HalRgbLightService
    Method:  SetRgbLightCommand
    Port:    52893

    effect: 1=常亮/solid, 2=呼吸/breathing, 3=闪烁/flash
    control: 1=开/on, 0=关/off

    预设场景 / Preset scenes:
      待机蓝/Standby blue:  (0, 80, 255)
      问候绿/Greeting green: (0, 255, 80)
      警告黄/Warning yellow: (255, 200, 0)
      错误红/Error red:      (255, 0, 0)
    """
    payload = {
        "cmd": {
            "red": red, "green": green, "blue": blue,
            "effect": effect, "control": control,
        }
    }
    return rpc(NAV_IP, 52893, "aimdk.protocol.HalRgbLightService", "SetRgbLightCommand", payload)


# ─── 练习 4-3: 监听唤醒词 (ROS2) / Exercise 4-3: Listen for Wake Word (ROS2) ──
def listen_for_wakeup(on_wakeup_callback, timeout: float = 60.0):
    """
    订阅 ROS2 Topic /agent/wakeup/...，监听唤醒词事件
    收到唤醒词后调用 on_wakeup_callback(wakeup_result)

    Subscribe to ROS2 Topic /agent/wakeup/... and listen for wake word events.
    Calls on_wakeup_callback(wakeup_result) when a wake word is detected.

    TODO: 参考 examples/agent/get_wakeup_result.py，
          创建 ROS2 节点订阅唤醒词 Topic，
          在 callback 中调用 on_wakeup_callback
          用 timeout 控制监听时长

          See examples/agent/get_wakeup_result.py:
          create a ROS2 node, subscribe to the wake word topic,
          call on_wakeup_callback in the callback,
          and use timeout to limit listening duration.

    提示 / Hint:
      Topic: /agent/wakeup/pb_3Aaimdk_2Eprotocol_2EWakeUpResult
      Protobuf 类 / Protobuf class: from aimdk.protocol_pb2 import WakeUpResult
    """
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
    from ros2_plugin_proto.msg import RosMsgWrapper
    from aimdk.protocol_pb2 import WakeUpResult

    WAKEUP_TOPIC = "/agent/wakeup/pb_3Aaimdk_2Eprotocol_2EWakeUpResult"

    triggered = {"fired": False}

    class WakeupNode(Node):
        def __init__(self):
            super().__init__("wakeup_listener")
            qos = QoSProfile(
                history=QoSHistoryPolicy.KEEP_LAST, depth=10,
                reliability=QoSReliabilityPolicy.RELIABLE,
                durability=QoSDurabilityPolicy.VOLATILE,
            )
            self.create_subscription(RosMsgWrapper, WAKEUP_TOPIC, self._cb, qos)

        def _cb(self, msg):
            if msg.serialization_type != "pb":
                return
            result = WakeUpResult()
            result.ParseFromString(b"".join(msg.data))
            triggered["fired"] = True
            on_wakeup_callback(result)

    rclpy.init()
    node = WakeupNode()
    executor = rclpy.executors.SingleThreadedExecutor()
    executor.add_node(node)

    deadline = time.time() + timeout
    while time.time() < deadline and not triggered["fired"]:
        executor.spin_once(timeout_sec=0.1)

    node.destroy_node()
    rclpy.shutdown()
    return triggered["fired"]


# ─── 综合练习: 唤醒响应流程 / Combined Exercise: Wake Word Response Flow ────────
def wakeup_response_demo():
    """
    完整交互演示 / Full interaction demo:
    1. 蓝灯待机，等待唤醒词 / Blue light standby, waiting for wake word
    2. 检测到唤醒词 → 绿灯 + TTS 问候 / Wake word detected → green light + TTS greeting
    3. 5 秒后回到蓝灯待机 / Return to blue standby after 5 seconds

    扩展挑战 / Extension challenges:
      - 加入 ASR 结果订阅（参考 examples/agent/get_wakeup_result.py）
        Add ASR result subscription (see examples/agent/get_wakeup_result.py)
      - 根据 ASR 识别结果做不同的语音回复
        Give different voice replies based on ASR recognition results
    """
    print("=" * 50)
    print("Phase 4: 语音交互演示 / Voice Interaction Demo")
    print("=" * 50)

    # 初始状态：蓝色待机 / Initial state: blue standby
    print("\n[待机] 蓝色呼吸灯，等待唤醒词...")  # [Standby] Blue breathing light, waiting for wake word...
    set_light(0, 80, 255, effect=2)

    def on_wakeup(result):
        print(f"\n[唤醒] 收到唤醒事件: {result}")  # [Wake] Wake event received
        # 绿灯表示激活 / Green light = activated
        set_light(0, 255, 80, effect=1)
        # 语音回应 / Voice response
        say("你好，我是 A2，请问有什么需要帮助的？")
        time.sleep(5.0)
        # 恢复蓝色待机 / Restore blue standby
        set_light(0, 80, 255, effect=2)
        print("[待机] 恢复待机状态")  # [Standby] Restored standby state

    triggered = listen_for_wakeup(on_wakeup, timeout=60.0)
    if not triggered:
        print("超时，未检测到唤醒词")  # Timed out, no wake word detected


# ─── 独立测试：直接测试 TTS 和灯光 / Standalone Test: Test TTS and Lights ─────
def test_tts_and_light():
    """不需要 ROS2，直接测试 TTS 和灯光 / Test TTS and lights without ROS2."""
    print("测试 TTS...")  # Testing TTS...
    say("你好，这是一个测试")
    time.sleep(1.0)

    print("测试灯光序列...")  # Testing light sequence...
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (0, 80, 255)]
    for r, g, b in colors:
        set_light(r, g, b, effect=1)
        time.sleep(1.0)

    set_light(0, 80, 255, effect=2)  # 恢复待机 / Restore standby
    print("完成")  # Done


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_tts_and_light()
    else:
        wakeup_response_demo()
