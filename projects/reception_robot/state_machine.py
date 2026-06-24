#!/usr/bin/env python3
"""
接待机器人状态机
Reception Robot State Machine

状态流转 / State transitions:
  IDLE ──(唤醒词/wake word)──> GREETING ──(TTS 完成/TTS done)──> LISTENING
  LISTENING ──(识别目标/destination recognized)──> NAVIGATING ──(到达/arrived)──> ARRIVED ──> IDLE
  NAVIGATING ──(失败/取消 / failed/cancelled)──> IDLE
  任意状态 ──(错误/error)──> ERROR ──> IDLE
"""

import time
from enum import Enum, auto

import robot_client as rc


class State(Enum):
    IDLE = auto()          # 蓝灯待机，等待唤醒 / Blue light standby, waiting for wake word
    GREETING = auto()      # 绿灯，播报问候语 / Green light, playing greeting TTS
    LISTENING = auto()     # 等待 ASR 识别出目标地点 / Waiting for ASR to recognize destination
    NAVIGATING = auto()    # 黄灯，机器人行进中 / Yellow light, robot navigating
    ARRIVED = auto()       # 青灯，播报到达提示 + 挥手 / Cyan light, arrival TTS + wave
    ERROR = auto()         # 红灯，播报错误信息 / Red light, error TTS


class ReceptionRobot:
    def __init__(self, waypoint_map: dict[str, int], map_id: int):
        """
        waypoint_map: 目的地名称 → 导航点 ID 的映射
                      e.g. {"前台": 101, "会议室A": 202, "茶水间": 303}

                      Destination name → waypoint ID mapping.
                      e.g. {"Reception": 101, "Meeting Room A": 202, "Pantry": 303}

        map_id:       当前激活地图 ID / ID of the currently active map
        """
        self.waypoint_map = waypoint_map
        self.map_id = map_id
        self.state = State.IDLE
        self.current_task_id = None
        self.target_name = None

    # ── 状态转移 / State Transition ────────────────────────────────────────────
    def _transition(self, new_state: State):
        print(f"[状态] {self.state.name} → {new_state.name}")  # [State]
        self.state = new_state

    # ── 各状态的执行逻辑 / Per-state Handler Logic ─────────────────────────────
    def handle_idle(self):
        """待机：蓝灯 + 等待唤醒词 / Standby: blue light + wait for wake word"""
        rc.light_standby()
        rc.set_neck(0.0, 0.0)   # 头部归位 / Return head to center
        print("[待机] 等待唤醒词...")  # [Standby] Waiting for wake word...
        # 唤醒检测由 main.py 驱动，此处仅设置初始状态
        # Wake detection is driven by main.py; this only sets the initial state

    def handle_greeting(self):
        """问候：绿灯 + 点头 + TTS / Greeting: green light + nod + TTS"""
        rc.light_greeting()

        # 点头动作 / Nod sequence
        rc.set_neck(nod=0.3)
        time.sleep(0.4)
        rc.set_neck(nod=0.0)
        time.sleep(0.2)
        rc.set_neck(nod=0.3)
        time.sleep(0.4)
        rc.set_neck(nod=0.0)

        rc.say("您好！我是 A2 接待机器人，请告诉我您要去哪里？")
        time.sleep(3.5)
        self._transition(State.LISTENING)

    def handle_listening(self, asr_text: str) -> bool:
        """
        解析 ASR 文本，匹配目的地
        返回 True 表示成功识别并发起导航，False 表示未识别

        Parse ASR text and match a destination.
        Returns True if a destination was recognized and navigation started; False otherwise.
        """
        for name, point_id in self.waypoint_map.items():
            if name in asr_text:
                self.target_name = name
                print(f"[识别] 目的地: {name} (point_id={point_id})")  # [Recognized] Destination
                return self._start_navigation(point_id)

        rc.say("抱歉，我没有听清楚，请再说一遍")  # Sorry, I didn't catch that; please repeat.
        return False

    def _start_navigation(self, point_id: int) -> bool:
        rc.say(f"好的，带您前往{self.target_name}，请跟我来")  # OK, leading you to {dest}, please follow me.
        rc.light_navigating()

        # 确保在行走模式 / Ensure walking mode is active
        if not rc.wait_for_action("McAction_RL_LOCOMOTION_DEFAULT"):
            rc.set_action("McAction_RL_LOCOMOTION_DEFAULT")
            if not rc.wait_for_action("McAction_RL_LOCOMOTION_DEFAULT"):
                self._handle_error("无法切换到行走模式")  # Failed to switch to walking mode
                return False

        try:
            self.current_task_id = rc.navigate_to(self.map_id, point_id)
            self._transition(State.NAVIGATING)
            return True
        except rc.RobotAPIError as e:
            self._handle_error(str(e))
            return False

    def handle_navigating(self) -> bool:
        """
        轮询导航状态
        返回 True 表示导航结束（成功或失败），False 表示仍在进行

        Poll navigation state.
        Returns True when navigation has ended (success or failure); False if still in progress.
        """
        state = rc.get_nav_state(self.current_task_id)

        if state == "PncServiceState_SUCCESS":
            self._transition(State.ARRIVED)
            return True
        elif state == "PncServiceState_FAILED":
            self._handle_error("导航失败，请检查路径是否畅通")  # Navigation failed; check if path is clear
            return True
        elif state in ("PncServiceState_IDLE", ""):
            self._handle_error("导航任务异常终止")  # Navigation task terminated unexpectedly
            return True

        return False   # RUNNING / PAUSED，继续等待 / Keep waiting

    def handle_arrived(self):
        """到达：青灯 + TTS + 挥手 / Arrived: cyan light + TTS + wave"""
        rc.light_arrived()
        rc.say(f"已到达{self.target_name}，祝您一切顺利！")  # Arrived at {dest}; have a great time!

        # 挥手动作 / Wave sequence
        open_hand = [0, 0, 0, 0, 0, 0]
        half_close = [1000, 1000, 1000, 1000, 1000, 1000]
        for _ in range(3):
            rc.set_hand(right=open_hand)
            time.sleep(0.3)
            rc.set_hand(right=half_close)
            time.sleep(0.3)
        rc.set_hand(right=open_hand)

        time.sleep(2.0)
        self.current_task_id = None
        self.target_name = None
        self._transition(State.IDLE)

    def _handle_error(self, message: str):
        print(f"[错误] {message}")  # [Error]
        rc.light_error()
        rc.say(f"遇到问题：{message}")  # Encountered a problem: {message}
        if self.current_task_id:
            try:
                rc.cancel_nav(self.current_task_id)
            except rc.RobotAPIError:
                pass
            self.current_task_id = None
        self.target_name = None
        time.sleep(2.0)
        self._transition(State.IDLE)
