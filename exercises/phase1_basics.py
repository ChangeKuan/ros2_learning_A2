#!/usr/bin/env python3
"""
Phase 1: 基础通信 — 读取机器人状态
Phase 1: Basic Communication — Reading Robot State

学习目标 / Learning objectives:
  1. 理解 SDK 的 HTTP RPC 通信模式 / Understand the SDK's HTTP RPC communication pattern
  2. 能从不同服务读取机器人状态 / Read robot state from different services
  3. 掌握请求头 (header) 的构造方式 / Master how to construct the request header

完成标准：能打印出机器人当前的系统状态、电量、动作模式、关节状态
Success criteria: print the robot's current system state, battery level, action mode, and joint state

运行方式（需连接机器人网络）/ How to run (requires robot network connection):
  python3 phase1_basics.py
"""

import json
import os
from datetime import datetime, timezone

import requests

# 切换仿真/真机 / Switch between sim and real robot:
#   export ROBOT_TARGET=sim  或/or  export ROBOT_TARGET=real
# 仿真可用 / Available in sim: GetAction, GetJointState, SetNeckCommand, SetHandCommand, walk
# 仿真不可用 / Not available in sim: BMS (battery), SystemState, navigation, TTS, lights
_SIM = os.environ.get("ROBOT_TARGET", "sim") == "sim"
MC_IP = "127.0.0.1" if _SIM else "192.168.100.100"
NAV_IP = "127.0.0.1" if _SIM else "192.168.100.110"
print(f"[config] 模式={'仿真' if _SIM else '真机'}  MC={MC_IP}  NAV={NAV_IP}")
# [config] mode=sim/real


def make_header():
    """构造标准请求头，所有带 header 的接口都用这个
    Build the standard request header used by all header-bearing endpoints.
    """
    now = datetime.now(timezone.utc)
    return {
        "timestamp": {
            "seconds": int(now.timestamp()),
            "nanos": now.microsecond * 1000,
            "ms_since_epoch": int(now.timestamp() * 1000),
        },
        "control_source": "ControlSource_SAFE",
    }


def rpc(ip: str, port: int, service: str, method: str, payload: dict = None) -> dict:
    """通用 HTTP RPC 调用封装 / Generic HTTP RPC call wrapper"""
    url = f"http://{ip}:{port}/rpc/{service}/{method}"
    resp = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json=payload or {},
        timeout=3.0,
    )
    resp.raise_for_status()
    return resp.json()


# ─── 练习 1-1: 读取系统状态 / Exercise 1-1: Read System State ─────────────────
def get_system_state() -> dict:
    """
    服务: aimdk.protocol.SystemService
    接口: GetSystemState
    端口: 51011  IP: NAV_IP

    Service: aimdk.protocol.SystemService
    Method:  GetSystemState
    Port:    51011  IP: NAV_IP

    ⚠ 仿真不可用：SystemService 不在仿真容器内
    ⚠ Not available in sim: SystemService is not inside the simulation container.
    """
    if _SIM:
        print("  [仿真] SystemService 不可用，跳过")  # [sim] SystemService unavailable, skipping
        return {}
    result = rpc(NAV_IP, 51011, "aimdk.protocol.SystemService", "GetSystemState")
    return result


# ─── 练习 1-2: 读取电池状态 / Exercise 1-2: Read Battery State ───────────────
def get_battery_state() -> dict:
    """
    服务: aimdk.protocol.HalBmsService
    接口: GetBmsState
    端口: 56421  IP: MC_IP

    Service: aimdk.protocol.HalBmsService
    Method:  GetBmsState
    Port:    56421  IP: MC_IP

    返回字段参考 / Key response fields: soc (battery %), voltage, current, temperature

    ⚠ 仿真不可用：BMS 硬件不存在于仿真容器中
    ⚠ Not available in sim: BMS hardware does not exist in the simulation container.
    """
    if _SIM:
        print("  [仿真] BMS 不可用，返回模拟数据")  # [sim] BMS unavailable, returning mock data
        return {"bms_state": {"soc": 85.0, "voltage": 48.0, "current": -2.5, "temperature": 30.0}}
    result = rpc(MC_IP, 56421, "aimdk.protocol.HalBmsService", "GetBmsState")
    return result


# ─── 练习 1-3: 读取当前动作模式 / Exercise 1-3: Read Current Action Mode ──────
def get_current_action() -> str:
    """
    服务: aimdk.protocol.McActionService
    接口: GetAction
    端口: 56322  IP: MC_IP

    Service: aimdk.protocol.McActionService
    Method:  GetAction
    Port:    56322  IP: MC_IP

    常见动作模式 / Common action modes:
      McAction_RL_LOCOMOTION_DEFAULT  — 强化学习行走 / Reinforcement-learning walking
      McAction_ZERO_TORQUE            — 零力矩（上电初始）/ Zero torque (power-on default)
      McAction_STAND_READY            — 准备站立 / Ready to stand
    """
    # TODO: 调用 McActionService/GetAction，返回 info.current_action 字段
    # Call McActionService/GetAction and return the info.current_action field
    result = rpc(MC_IP, 56322, "aimdk.protocol.McActionService", "GetAction")
    return result.get("info", {}).get("current_action", "unknown")


# ─── 练习 1-4: 读取关节状态 / Exercise 1-4: Read Joint State ─────────────────
def get_joint_state() -> dict:
    """
    服务: aimdk.protocol.McDataService
    接口: GetJointState
    端口: 56322  IP: MC_IP

    Service: aimdk.protocol.McDataService
    Method:  GetJointState
    Port:    56322  IP: MC_IP

    返回各关节的 position / velocity / effort
    Returns position / velocity / effort for each joint.
    """
    # TODO: 调用 McDataService/GetJointState，需要传 header
    # Call McDataService/GetJointState; a header is required
    result = rpc(
        MC_IP, 56322, "aimdk.protocol.McDataService", "GetJointState",
        {"header": make_header()},
    )
    return result


# ─── 挑战题: 解析关节状态 / Challenge: Parse Joint State ──────────────────────
def print_joint_summary(joint_state: dict):
    """
    TODO: 从 joint_state 中提取每个关节的名称和当前位置 (position)，
    格式化打印如下:
      idx01_left_hip_yaw     :  0.012 rad
      idx02_left_hip_roll    : -0.003 rad
      ...
    提示: 关节数据在 joint_state["states"] 列表里

    Extract each joint's name and current position from joint_state and print:
      idx01_left_hip_yaw     :  0.012 rad
    Hint: joint data is in the joint_state["states"] list.
    """
    joints = joint_state.get("states", [])
    for j in joints:
        name = j.get("name", "?")
        pos = j.get("position", 0.0)
        print(f"  {name:<35}: {pos:+.4f} rad")

def get_available_actions() -> list:
    """
    服务: McActionService
    接口: GetAvailableActions
    返回所有可用的动作名称列表

    Service: McActionService
    Method:  GetAvailableActions
    Returns a list of all available action name strings.

    提示: 参考 examples/mc/GetAvailableCommands.py
    Hint: see examples/mc/GetAvailableCommands.py
    """
    # 你的代码 / Your code here
    actions = rpc(MC_IP, 56322, "aimdk.protocol.McActionService", "GetAvailableActions")
    return actions.get("actions", []) if isinstance(actions, dict) else []

def main():
    print("=" * 50)
    print("Phase 1: 基础状态读取 / Basic State Readout")
    print("=" * 50)

    print("\n[1] 系统状态 / System state:")
    state = get_system_state()
    print(json.dumps(state, indent=2, ensure_ascii=False))

    print("\n[2] 电池状态 / Battery state:")
    batt = get_battery_state()
    print(json.dumps(batt, indent=2, ensure_ascii=False))

    print("\n[3] 当前动作模式 / Current action mode:")
    action = get_current_action()
    print(f"  {action}")

    print("\n[4] 关节状态摘要 / Joint state summary:")
    joints = get_joint_state()
    print_joint_summary(joints)

    print("\n[挑战题] 可用动作列表 / [Challenge] Available action list:")
    actions = get_available_actions()
    for a in actions:
        print(f"  {a}")


if __name__ == "__main__":
    main()
