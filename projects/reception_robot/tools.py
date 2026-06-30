"""
机器人工具集：将 robot_client API 封装为 LLM 可调用的工具
Robot tools: wrap robot_client APIs as LLM-callable tools.

每个工具对应 OpenAI function calling 格式的 schema + execute_tool() 中的执行逻辑
Each tool has an OpenAI function calling schema + matching branch in execute_tool().
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import robot_client as rc

# 与 main.py 保持一致，真机上应改为 rc.get_current_map_id() 的返回值
# Keep in sync with main.py; on real robot use rc.get_current_map_id()
WAYPOINT_MAP: dict[str, int] = {
    "前台": 101,
    "会议室": 202,
    "茶水间": 303,
    "大厅": 404,
}
MAP_ID: int = 1

# ── OpenAI function calling schemas ──────────────────────────────────────────

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "speak",
            "description": "让机器人用 TTS 播报文字 / Make the robot speak text via TTS",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "要播报的文字 / Text to speak"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_battery",
            "description": "查询机器人当前电量百分比 / Query robot battery level (returns 0-100)",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_waypoints",
            "description": "列出所有可导航的地点名称 / List all navigable waypoint names",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "navigate_to_waypoint",
            "description": (
                "导航机器人到指定地点，阻塞直到到达或失败（最长 120 秒）"
                " / Navigate robot to a named location; blocks until arrival or failure (max 120s)"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "waypoint_name": {
                        "type": "string",
                        "description": "目标地点名称，必须是 list_waypoints 返回的名称之一 / Must be a name from list_waypoints",
                    },
                },
                "required": ["waypoint_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "do_action",
            "description": "让机器人执行肢体动作 / Make the robot perform a body gesture",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["nod", "wave"],
                        "description": "nod=点头问候 / nod greeting  wave=挥手告别 / wave goodbye",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_light",
            "description": "设置机器人 RGB 灯光预设状态 / Set robot RGB light to a preset state",
            "parameters": {
                "type": "object",
                "properties": {
                    "preset": {
                        "type": "string",
                        "enum": ["standby", "greeting", "navigating", "arrived", "error"],
                        "description": "灯光预设 / Light preset",
                    },
                },
                "required": ["preset"],
            },
        },
    },
]

# ── 执行器 / Tool executor ─────────────────────────────────────────────────────

def execute_tool(name: str, args: dict) -> str:
    """
    执行工具调用，返回观察结果字符串（供 LLM 在下一轮推理中使用）
    Execute a tool call; return an observation string for the LLM's next reasoning step.
    """
    try:
        if name == "speak":
            rc.say(args["text"])
            return f"已播报: {args['text']}"  # Spoken

        elif name == "get_battery":
            level = rc.get_battery_level()
            return f"当前电量: {level:.0f}%"  # Current battery level

        elif name == "list_waypoints":
            names = list(WAYPOINT_MAP.keys())
            return f"可用地点: {', '.join(names)}"  # Available waypoints

        elif name == "navigate_to_waypoint":
            wname = args["waypoint_name"]
            point_id = WAYPOINT_MAP.get(wname)
            if point_id is None:
                available = ", ".join(WAYPOINT_MAP.keys())
                return f"错误：地点 '{wname}' 不在地图上，可用地点: {available}"
                # Error: location not found on map

            # 切换到行走模式 / Switch to walking mode
            if not rc.wait_for_action("McAction_RL_LOCOMOTION_DEFAULT", timeout=5.0):
                rc.set_action("McAction_RL_LOCOMOTION_DEFAULT")
                if not rc.wait_for_action("McAction_RL_LOCOMOTION_DEFAULT", timeout=10.0):
                    return "错误：无法切换到行走模式"  # Error: failed to switch to walking mode

            task_id = rc.navigate_to(MAP_ID, point_id)

            # 轮询直到导航结束 / Poll until navigation ends
            deadline = time.time() + 120.0
            while time.time() < deadline:
                state = rc.get_nav_state(task_id)
                if state == "PncServiceState_SUCCESS":
                    return f"已到达 {wname}"  # Arrived at
                elif state == "PncServiceState_FAILED":
                    return f"导航失败，无法到达 {wname}，请检查路径是否畅通"  # Navigation failed
                elif state in ("PncServiceState_IDLE", ""):
                    return "导航任务异常终止"  # Navigation ended unexpectedly
                time.sleep(1.0)

            rc.cancel_nav(task_id)
            return f"导航超时（120s），已取消前往 {wname} 的任务"  # Navigation timed out; cancelled

        elif name == "do_action":
            action = args["action"]
            if action == "nod":
                for _ in range(2):
                    rc.set_neck(nod=0.3)
                    time.sleep(0.4)
                    rc.set_neck(nod=0.0)
                    time.sleep(0.2)
                return "完成点头动作"  # Nod complete

            elif action == "wave":
                open_hand = [0, 0, 0, 0, 0, 0]
                half_close = [1000, 1000, 1000, 1000, 1000, 1000]
                for _ in range(3):
                    rc.set_hand(right=open_hand)
                    time.sleep(0.3)
                    rc.set_hand(right=half_close)
                    time.sleep(0.3)
                rc.set_hand(right=open_hand)
                return "完成挥手动作"  # Wave complete

            return f"未知动作: {action}"  # Unknown action

        elif name == "set_light":
            presets = {
                "standby": rc.light_standby,
                "greeting": rc.light_greeting,
                "navigating": rc.light_navigating,
                "arrived": rc.light_arrived,
                "error": rc.light_error,
            }
            presets[args["preset"]]()
            return f"灯光已设为 {args['preset']}"  # Light set to

        return f"未知工具: {name}"  # Unknown tool

    except rc.RobotAPIError as e:
        return f"机器人 API 错误: {e}"  # Robot API error
