#!/usr/bin/env python3
"""
Phase 3: 地图与导航
Phase 3: Map and Navigation

学习目标 / Learning objectives:
  1. 理解拓扑地图 (Topo Map) 和导航点 (Waypoint) 的概念
     Understand topological maps and waypoints
  2. 能查询当前地图和可用导航点 / Query the current map and available waypoints
  3. 能下发导航任务并监控任务状态 / Submit navigation tasks and monitor their state
  4. 能取消进行中的导航任务 / Cancel an in-progress navigation task

完成标准：让机器人导航到地图上一个已标注的点，成功到达后打印 "到达目标"
Success criteria: navigate the robot to a marked waypoint and print "Arrived" on success.

运行方式 / How to run: python3 phase3_navigation.py
"""

import os
import time

import requests

# ⚠ Phase 3 导航功能仿真不可用：仿真容器不含 SLAM / 地图服务
# ⚠ Navigation is not available in sim: the sim container does not include SLAM / map services.
# 请连接真机后设置 / Connect the real robot and set: export ROBOT_TARGET=real
_SIM = os.environ.get("ROBOT_TARGET", "sim") == "sim"
MC_IP = "127.0.0.1" if _SIM else "192.168.100.100"
NAV_IP = "127.0.0.1" if _SIM else "192.168.100.110"
if _SIM:
    print("[config] 仿真模式 — 导航 API 不可用，建议切换 ROBOT_TARGET=real")
    # [config] Sim mode — navigation API unavailable; switch ROBOT_TARGET=real
else:
    print(f"[config] 真机模式  MC={MC_IP}  NAV={NAV_IP}")
    # [config] Real robot mode


def rpc(ip: str, port: int, service: str, method: str, payload: dict = None) -> dict:
    url = f"http://{ip}:{port}/rpc/{service}/{method}"
    resp = requests.post(
        url, headers={"Content-Type": "application/json"},
        json=payload or {}, timeout=5.0,
    )
    resp.raise_for_status()
    return resp.json()


# ─── 练习 3-1: 查询当前地图 / Exercise 3-1: Query Current Map ────────────────
def get_current_map_id() -> int:
    """
    服务: aimdk.protocol.MappingService
    接口: GetCurrentWorkingMap
    端口: 50807

    Service: aimdk.protocol.MappingService
    Method:  GetCurrentWorkingMap
    Port:    50807

    返回当前激活地图的 map_id / Returns the map_id of the currently active map.
    """
    result = rpc(
        NAV_IP, 50807,
        "aimdk.protocol.MappingService", "GetCurrentWorkingMap",
        {"header": {}, "command": "MappingCommand_GET_CURRENT_WORKING_MAP"},
    )
    return result["data"]["map_id"]


# ─── 练习 3-2: 获取拓扑导航点列表 / Exercise 3-2: Get Waypoint List ───────────
def get_waypoints(map_id: int) -> list:
    """
    服务: aimdk.protocol.LocalizationService
    接口: GetTopoMsgs
    端口: 50807

    Service: aimdk.protocol.LocalizationService
    Method:  GetTopoMsgs
    Port:    50807

    返回导航点列表，每个点包含 point_id、name、pose 等字段
    Returns a list of waypoints; each entry includes point_id, name, pose, etc.

    TODO: 补全调用，payload 参考 examples/pnc/pnc_demo.py
          Complete the call; see examples/pnc/pnc_demo.py for the payload.
    """
    result = rpc(
        NAV_IP, 50807,
        "aimdk.protocol.LocalizationService", "GetTopoMsgs",
        {"header": {}, "command": "TopoCommand_GET_TOPO_MSG", "map_id": map_id},
    )
    return result.get("data", {}).get("points", [])


# ─── 练习 3-3: 下发导航任务 / Exercise 3-3: Submit Navigation Task ─────────────
def navigate_to(map_id: int, target_point_id: int, task_id: int = 1) -> int:
    """
    服务: aimdk.protocol.PncService
    接口: PlanningNaviToGoal
    端口: 53176

    Service: aimdk.protocol.PncService
    Method:  PlanningNaviToGoal
    Port:    53176

    返回任务 task_id（用于后续状态查询）
    Returns the task_id for subsequent state queries.

    TODO: 参考 pnc_demo.py 中的 planning_navi_to_goal，补全 payload
          See planning_navi_to_goal in pnc_demo.py and complete the payload.
    注意 / Note: 需要先确保机器人在 McAction_RL_LOCOMOTION_DEFAULT 模式
                 Ensure the robot is in McAction_RL_LOCOMOTION_DEFAULT mode first.
    """
    payload = {
        "header": {"timestamp": {"seconds": 0, "nanos": 0, "ms_since_epoch": 0}, "control_source": 0},
        "task_id": task_id,
        "map_id": map_id,
        "target_id": target_point_id,
        "guide_line_id": 0,
        "ackerman_mode": False,
    }
    result = rpc(NAV_IP, 53176, "aimdk.protocol.PncService", "PlanningNaviToGoal", payload)
    if result.get("state") != "CommonState_SUCCESS":
        raise RuntimeError(f"导航下发失败: {result.get('info', result.get('state'))}")
        # Navigation submission failed
    return result.get("task_id", task_id)


# ─── 练习 3-4: 查询导航任务状态 / Exercise 3-4: Query Navigation Task State ────
def get_nav_state(task_id: int) -> str:
    """
    服务: aimdk.protocol.PncService
    接口: ActionGetState
    端口: 53176

    Service: aimdk.protocol.PncService
    Method:  ActionGetState
    Port:    53176

    返回状态字符串 / Returns a state string:
      PncServiceState_IDLE
      PncServiceState_RUNNING
      PncServiceState_PAUSED
      PncServiceState_SUCCESS
      PncServiceState_FAILED

    TODO: 补全 payload，参考 pnc_demo.py
          Complete the payload; see pnc_demo.py.
    """
    payload = {
        "header": {"timestamp": {"seconds": 0, "nanos": 0, "ms_since_epoch": 0}, "control_source": 0},
        "task_id": task_id,
    }
    result = rpc(NAV_IP, 53176, "aimdk.protocol.PncService", "ActionGetState", payload)
    return result.get("state", "")


# ─── 练习 3-5: 取消导航任务 / Exercise 3-5: Cancel Navigation Task ────────────
def cancel_nav(task_id: int):
    """
    服务: aimdk.protocol.PncService
    接口: ActionCancel

    Service: aimdk.protocol.PncService
    Method:  ActionCancel

    TODO: 补全这个函数 / Complete this function.
    """
    payload = {
        "header": {"timestamp": {"seconds": 0, "nanos": 0, "ms_since_epoch": 0}, "control_source": 0},
        "task_id": task_id,
    }
    result = rpc(NAV_IP, 53176, "aimdk.protocol.PncService", "ActionCancel", payload)
    if result.get("state") != "CommonState_SUCCESS":
        raise RuntimeError(f"取消任务失败: {result.get('message')}")
        # Failed to cancel task


# ─── 综合练习: 交互式导航 / Combined Exercise: Interactive Navigation ──────────
def interactive_navigate():
    """让用户选择地图上的一个导航点，机器人导航过去，实时显示状态
    Let the user choose a waypoint from the map, navigate the robot there,
    and display state in real time.
    """
    print("=" * 50)
    print("Phase 3: 导航练习 / Navigation Exercise")
    print("=" * 50)

    # 1. 获取当前地图 / Get the current map
    map_id = get_current_map_id()
    print(f"\n当前地图 ID: {map_id}")  # Current map ID

    # 2. 显示所有可用导航点 / Show all available waypoints
    points = get_waypoints(map_id)
    if not points:
        print("当前地图没有可用导航点，请先在地图上标注导航点")
        # No waypoints on the current map; please mark some first
        return

    print(f"\n可用导航点 ({len(points)} 个) / Available waypoints:")
    for i, p in enumerate(points):
        print(f"  [{i}] id={p['point_id']:>5}  name={p.get('name', 'unnamed')}")

    # 3. 让用户选择目标点 / Let the user choose a target
    choice = input("\n请输入导航点编号 / Enter waypoint index: ").strip()
    if not choice.isdigit() or int(choice) >= len(points):
        print("无效输入 / Invalid input")
        return

    target = points[int(choice)]
    target_id = target["point_id"]
    target_name = target.get("name", str(target_id))
    print(f"\n目标 / Target: {target_name} (id={target_id})")

    # 4. 下发导航任务 / Submit navigation task
    try:
        task_id = navigate_to(int(map_id), int(target_id))
        print(f"导航任务已下发，task_id={task_id}")  # Navigation task submitted
    except RuntimeError as e:
        print(f"❌ {e}")
        return

    # 5. 监控任务状态 / Monitor task state
    print("\n导航状态 / Navigation state:")
    try:
        while True:
            state = get_nav_state(task_id)
            print(f"  {state}")

            if state == "PncServiceState_SUCCESS":
                print(f"\n✓ 已到达目标 [{target_name}]")  # Arrived at target
                break
            elif state == "PncServiceState_FAILED":
                print("\n❌ 导航失败")  # Navigation failed
                break
            elif state in ("PncServiceState_IDLE", ""):
                print("\n任务已结束")  # Task ended
                break

            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\n中断，正在取消导航任务...")  # Interrupted, cancelling navigation task...
        cancel_nav(task_id)
        print("任务已取消")  # Task cancelled


if __name__ == "__main__":
    interactive_navigate()
