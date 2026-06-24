#!/usr/bin/env python3
"""
所有 HTTP RPC 调用的统一封装层
Unified wrapper layer for all HTTP RPC calls.
"""

import time
from datetime import datetime, timezone

import requests
from config import MC_IP, NAV_IP, SIM


class RobotAPIError(Exception):
    pass


def _rpc(ip: str, port: int, service: str, method: str, payload: dict = None) -> dict:
    url = f"http://{ip}:{port}/rpc/{service}/{method}"
    try:
        resp = requests.post(
            url, headers={"Content-Type": "application/json"},
            json=payload or {}, timeout=5.0,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        raise RobotAPIError(f"{service}/{method} failed: {e}") from e


def _header():
    now = datetime.now(timezone.utc)
    return {
        "timestamp": {
            "seconds": int(now.timestamp()),
            "nanos": now.microsecond * 1000,
            "ms_since_epoch": int(now.timestamp() * 1000),
        },
        "control_source": "ControlSource_SAFE",
    }


# ── System ─────────────────────────────────────────────────────────────────
def get_system_state() -> dict:
    if SIM:
        return {}   # 仿真不可用 / Not available in sim
    return _rpc(NAV_IP, 51011, "aimdk.protocol.SystemService", "GetSystemState")


def get_battery_level() -> float:
    """返回电量百分比 0~100 (仿真返回固定值 85.0)
    Return battery percentage 0~100 (simulation returns fixed value 85.0).
    """
    if SIM:
        return 85.0
    result = _rpc(MC_IP, 56421, "aimdk.protocol.HalBmsService", "GetBmsState")
    return result.get("bms_state", {}).get("soc", 0.0)


# ── Motion Control ─────────────────────────────────────────────────────────
def get_action() -> str:
    result = _rpc(MC_IP, 56322, "aimdk.protocol.McActionService", "GetAction")
    return result.get("info", {}).get("current_action", "")


def set_action(action_name: str):
    payload = {"command": {"action": "McAction_USE_EXT_CMD", "ext_action": action_name}}
    return _rpc(MC_IP, 56322, "aimdk.protocol.McActionService", "SetAction", payload)


def wait_for_action(target: str, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if get_action() == target:
            return True
        time.sleep(0.5)
    return False


def set_neck(shake: float = 0.0, nod: float = 0.0):
    """shake: 左右 [-0.6, 0.6]  nod: 低头/抬头 [-0.3, 0.5]
    shake: left/right [-0.6, 0.6]  nod: bow/raise [-0.3, 0.5]
    """
    payload = {
        "header": _header(),
        "data": {
            "shake": {"name": "idx27_head_joint1", "position": shake, "velocity": 0.0, "effort": 0.0},
            "nod": {"name": "idx28_head_joint2", "position": nod, "velocity": 0.0, "effort": 0.0},
        },
    }
    return _rpc(MC_IP, 56322, "aimdk.protocol.McMotionService", "SetNeckCommand", payload)


def set_hand(left=None, right=None):
    """positions: [thumb0, thumb1, index, middle, ring, pinky], 0=张开/open, 2000=握紧/closed"""
    def _finger(pos):
        keys = ["thumb_pos_0", "thumb_pos_1", "index_pos", "middle_pos", "ring_pos", "pinky_pos"]
        toq_keys = ["thumb_toq_0", "thumb_toq_1", "index_toq", "middle_toq", "ring_toq", "pinky_toq"]
        return {
            "agi_hand": {
                "finger": {
                    "pos": dict(zip(keys, pos)),
                    "toq": {k: 0 for k in toq_keys},
                }
            }
        }

    data = {}
    if left:
        data["left"] = _finger(left)
    if right:
        data["right"] = _finger(right)
    return _rpc(MC_IP, 56322, "aimdk.protocol.McMotionService", "SetHandCommand",
                {"header": _header(), "data": data})


# ── Navigation (仿真不可用，需真机 / Not available in sim; requires real robot) ──
def get_current_map_id() -> int:
    if SIM:
        raise RobotAPIError("导航服务在仿真中不可用，请设置 ROBOT_TARGET=real")
        # Navigation service not available in sim; set ROBOT_TARGET=real
    result = _rpc(
        NAV_IP, 50807, "aimdk.protocol.MappingService", "GetCurrentWorkingMap",
        {"header": {}, "command": "MappingCommand_GET_CURRENT_WORKING_MAP"},
    )
    return result["data"]["map_id"]


def get_waypoints(map_id: int) -> list:
    result = _rpc(
        NAV_IP, 50807, "aimdk.protocol.LocalizationService", "GetTopoMsgs",
        {"header": {}, "command": "TopoCommand_GET_TOPO_MSG", "map_id": map_id},
    )
    return result.get("data", {}).get("points", [])


def navigate_to(map_id: int, point_id: int, task_id: int = 1) -> int:
    payload = {
        "header": {"timestamp": {"seconds": 0, "nanos": 0, "ms_since_epoch": 0}, "control_source": 0},
        "task_id": task_id,
        "map_id": map_id,
        "target_id": point_id,
        "guide_line_id": 0,
        "ackerman_mode": False,
    }
    result = _rpc(NAV_IP, 53176, "aimdk.protocol.PncService", "PlanningNaviToGoal", payload)
    if result.get("state") != "CommonState_SUCCESS":
        raise RobotAPIError(f"导航下发失败: {result.get('info', result.get('state'))}")
        # Navigation submission failed
    return result.get("task_id", task_id)


def get_nav_state(task_id: int) -> str:
    payload = {
        "header": {"timestamp": {"seconds": 0, "nanos": 0, "ms_since_epoch": 0}, "control_source": 0},
        "task_id": task_id,
    }
    result = _rpc(NAV_IP, 53176, "aimdk.protocol.PncService", "ActionGetState", payload)
    return result.get("state", "")


def cancel_nav(task_id: int):
    payload = {
        "header": {"timestamp": {"seconds": 0, "nanos": 0, "ms_since_epoch": 0}, "control_source": 0},
        "task_id": task_id,
    }
    _rpc(NAV_IP, 53176, "aimdk.protocol.PncService", "ActionCancel", payload)


# ── Voice & Light (仿真不可用，需真机 / Not available in sim; requires real robot) ──
def say(text: str, priority: str = "INTERACTION_L6"):
    if SIM:
        print(f"[TTS-仿真] {text}")  # [TTS-sim]
        return {}
    payload = {
        "text": text,
        "priority_level": priority,
        "domain": "reception_robot",
        "trace_id": f"rr_{int(time.time())}",
        "is_interrupted": True,
    }
    return _rpc(NAV_IP, 59301, "aimdk.protocol.TTSService", "PlayTTS", payload)


def set_light(r: int, g: int, b: int, effect: int = 2):
    """effect: 1=常亮/solid, 2=呼吸/breathing, 3=闪烁/flash"""
    if SIM:
        names = {2: "呼吸", 1: "常亮", 3: "闪烁"}
        print(f"[灯光-仿真] RGB({r},{g},{b}) {names.get(effect,'')}")  # [light-sim]
        return {}
    payload = {"cmd": {"red": r, "green": g, "blue": b, "effect": effect, "control": 1}}
    return _rpc(NAV_IP, 52893, "aimdk.protocol.HalRgbLightService", "SetRgbLightCommand", payload)


# 预设灯光 / Preset light states
def light_standby():
    set_light(0, 80, 255, effect=2)      # 蓝色呼吸 — 待机 / Blue breathing — standby

def light_greeting():
    set_light(0, 255, 80, effect=1)      # 绿色常亮 — 问候中 / Green solid — greeting

def light_navigating():
    set_light(255, 200, 0, effect=2)     # 黄色呼吸 — 导航中 / Yellow breathing — navigating

def light_arrived():
    set_light(0, 200, 255, effect=3)     # 青色闪烁 — 到达 / Cyan flash — arrived

def light_error():
    set_light(255, 0, 0, effect=3)       # 红色闪烁 — 错误 / Red flash — error
