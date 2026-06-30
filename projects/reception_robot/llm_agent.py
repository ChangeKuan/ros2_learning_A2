#!/usr/bin/env python3.14
"""
LLM 驱动的机器人智能代理（ReAct 模式 + Function Calling 组合）
LLM-driven robot intelligent agent (ReAct + Function Calling combined).

架构 / Architecture:
  外层 ReAct 循环 — LLM 边推理边执行，感知每步结果后决定下一步
  Outer ReAct loop — LLM reasons and acts, observes each result before next step

  内层 Function Calling — 每个 Action 映射到 tools.py 中的具体机器人 API 调用
  Inner Function Calling — each Action maps to a concrete robot API call in tools.py

运行前提 / Prerequisites:
  pip install openai
  export MIMO_API_KEY=your-xiaomi-mimo-api-key
  export MIMO_MODEL=mimo-v2.5
  python3.14 llm_agent.py "送我去会议室"

模拟模式（不需要机器人）/ Simulate mode (no robot needed):
  export ROBOT_TARGET=sim
  python3.14 llm_agent.py "你好，请问可以送我去会议室吗？"
"""
import json
import os
import sys

import openai

from tools import TOOL_SCHEMAS, execute_tool

SYSTEM_PROMPT = """你是 A2 智元接待机器人的 AI 大脑，负责接待访客并引导他们前往目的地。
You are the AI brain of the A2 AgiBot reception robot, responsible for receiving visitors and guiding them to their destination.

你通过调用工具控制机器人的动作、语音和灯光。接待访客的标准流程：
You control the robot's actions, voice, and lights by calling tools. Standard reception workflow:
1. set_light(greeting) + do_action(nod) — 开启绿灯并点头
2. speak(问候语) — 用中文问候访客
3. get_battery() — 如果任务需要导航，先检查电量
4. 电量 < 20% 时，speak 告知访客机器人需要充电，拒绝导航
5. set_light(navigating) + navigate_to_waypoint() — 开启黄灯并导航
6. set_light(arrived) + do_action(wave) + speak(到达提示) — 到达后挥手告别

规则 / Rules:
- 始终用中文与访客交流 / Always communicate with visitors in Chinese
- 每次 navigate_to_waypoint 前必须先 set_light(navigating) / Always set navigating light before navigation
- 导航失败时 set_light(error) 并告知访客 / On navigation failure, set error light and inform visitor
- 如果访客要去的地点不在地图上，先 list_waypoints() 获取完整列表再回应 / If destination unknown, list_waypoints() first
"""


def run(user_input: str, max_steps: int = 15) -> str:
    """
    接受自然语言指令，启动 ReAct 循环控制机器人。
    Accept a natural language instruction; run the ReAct loop to control the robot.

    每轮循环:
      1. LLM 推理 (Thought) → 输出工具调用 (Action)
      2. execute_tool() 执行 → 返回观察结果 (Observation)
      3. 观察结果追加到消息历史 → 进入下一轮
    Each loop iteration:
      1. LLM reasons (Thought) → outputs tool call (Action)
      2. execute_tool() runs → returns observation (Observation)
      3. Observation appended to message history → next iteration

    Returns the LLM's final text reply when finish_reason == "stop".
    """
    miro_api_key = os.environ.get("MIMO_API_KEY")
    if not miro_api_key:
        raise SystemExit("请先设置 MIMO_API_KEY 环境变量")

    model_name = os.environ.get("MIMO_MODEL", "mimo-v2.5")
    client = openai.OpenAI(
        api_key=miro_api_key,
        base_url="https://api.xiaomimimo.com/v1",
    )
    messages = [{"role": "user", "content": user_input}]

    for step in range(1, max_steps + 1):
        response = client.chat.completions.create(
            model=model_name,
            max_tokens=1024,
            tools=TOOL_SCHEMAS,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        )

        msg = response.choices[0].message
        tool_calls = msg.tool_calls or []
        text_content = msg.content or ""

        # 打印推理过程（仅控制台，访客不可见）/ Print reasoning (console only, not for visitor)
        if text_content.strip():
            print(f"\n[推理 step={step}] {text_content.strip()}")  # [Reasoning]

        # 任务结束：LLM 输出纯文本，没有工具调用 / Task done: LLM outputs text with no tool calls
        if not tool_calls:
            final = text_content.strip() or "任务已完成"  # Task complete
            print(f"\n{'='*50}")
            print(f"[机器人对指令的理解 / Robot understanding]")  # Robot's final understanding
            print(f"  原始指令: {user_input}")   # Original instruction
            print(f"  最终回复: {final}")         # Final response
            print(f"{'='*50}")
            return final

        # ── 内层 Function Calling：执行本轮所有工具调用 ─────────────────────────
        # Inner Function Calling: execute all tool calls this round
        tool_results = []
        for tc in tool_calls:
            args = json.loads(tc.function.arguments)
            print(f"\n[工具调用 step={step}] {tc.function.name}({args})")  # [Tool call]
            obs = execute_tool(tc.function.name, args)
            print(f"[观察] {obs}")  # [Observation]
            tool_results.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": obs,
            })

        # 把本轮 assistant 回复 + 工具结果追加到历史，进入下一轮推理
        # Append this round's assistant reply + tool results to history; next reasoning step
        messages.append({
            "role": "assistant",
            "content": text_content,
            "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in tool_calls
            ],
        })
        messages.extend(tool_results)

    return f"已达到最大步骤数（{max_steps} 步），任务未完成"
    # Reached max steps; task incomplete


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]).strip() or "你好，请问可以送我去会议室吗？"
    print(f"用户指令 / User instruction: {prompt}")
    print("=" * 50)
    run(prompt)
