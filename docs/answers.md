# 实战任务参考答案 (Reference Answers for Hands-on Tasks)

> 每道题先给答案，再给简短说明。观察类任务（只需运行程序回答问题）标注"观察题"，答案因环境而异。
>
> *Each problem shows the answer first, then a brief explanation. Observation tasks (run the program and answer questions) are marked "observation task" — answers depend on your environment.*

---

## Phase 1：基础通信 (Basic Communication)

### 任务 1-A：理解输出（观察题）(Task 1-A: Understanding Output — Observation Task)

运行 `uv run exercises/phase1_basics.py` 后观察：

> *Run `uv run exercises/phase1_basics.py` and observe:*

- **仿真默认动作模式 / Default sim action mode**：`McAction_ZERO_TORQUE`（零力矩，机器人倒在地上 / Zero torque; robot lies flat on the ground）
- **关节数量 / Joint count**：通常 28 个（腿部 12 + 臂部 14 + 头部 2，具体视固件版本）/ Usually 28 (legs 12 + arms 14 + head 2; varies by firmware)
- **position 不为 0 的关节 / Joints with non-zero position**：在真正静止站立前，几乎全部为 0；如果仿真已经站立，髋关节和膝关节会有非零值（约 ±0.1~0.5 rad）/ Nearly all are 0 before standing; once standing, hip and knee joints show non-zero values (~±0.1–0.5 rad)

---

### 任务 1-B：手写 `get_available_actions()` (Task 1-B: Implement `get_available_actions()`)

```python
def get_available_actions() -> list:
    result = rpc(MC_IP, 56322, "aimdk.protocol.McActionService", "GetAvailableActions")
    actions = result.get("actions", [])
    return [a.get("action", str(a)) for a in actions]
```

在 `main()` 末尾加上调用 / Add the call at the end of `main()`:

```python
print("\n[5] 可用动作列表:")
for action in get_available_actions():
    print(f"  {action}")
```

**说明 (Explanation)**：响应体的顶层字段是 `actions`，里面是对象列表，每个对象有 `action` 字段存储动作名称字符串。用 `.get("action", str(a))` 防止结构变化时报错。

> *The top-level field in the response is `actions`, which is a list of objects each with an `action` field containing the action name string. Use `.get("action", str(a))` to avoid errors if the structure changes.*

---

### 任务 1-C：position 绝对值最大的 3 个关节 (Task 1-C: Top 3 Joints by Absolute Position)

在 `print_joint_summary` 末尾追加 / Append to `print_joint_summary`:

```python
def print_joint_summary(joint_state: dict):
    joints = joint_state.get("states", [])
    for j in joints:
        name = j.get("name", "?")
        pos = j.get("position", 0.0)
        print(f"  {name:<35}: {pos:+.4f} rad")

    # 找出绝对值最大的 3 个关节 / Find the 3 joints with largest absolute position
    top3 = sorted(joints, key=lambda j: abs(j.get("position", 0)), reverse=True)[:3]
    print("\n  [Top 3 position 绝对值最大的关节 / Joints with largest absolute position]")
    for j in top3:
        print(f"  {j.get('name', '?'):<35}: {j.get('position', 0):+.4f} rad")
```

---

### 任务 1-D：连续监控 (Task 1-D: Continuous Monitoring)

```python
import time

def monitor_joint(joint_name: str = "idx07_left_knee_pitch", interval: float = 1.0):
    print(f"监控关节: {joint_name}  (Ctrl+C 停止)")  # Monitoring joint (Ctrl+C to stop)
    print(f"{'时间':>10}  {'position':>10}")
    try:
        while True:
            joints = get_joint_state().get("states", [])
            target = next((j for j in joints if j.get("name") == joint_name), None)
            if target:
                ts = time.strftime("%H:%M:%S")
                print(f"{ts:>10}  {target['position']:>+10.4f}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n监控结束")  # Monitoring stopped

if __name__ == "__main__":
    monitor_joint()
```

**说明 (Explanation)**：`next(..., None)` 在列表里找第一个匹配的关节，找不到返回 None 而不是抛异常。在 tmux 另一个窗口切换动作模式后可以看到关节值变化。

> *`next(..., None)` finds the first matching joint in the list, returning None instead of raising an exception if not found. Switch action modes in another tmux window to observe joint value changes.*

---

## Phase 2：基础运动控制 (Basic Motion Control)

### 任务 2-A：验证仿真（观察题）(Task 2-A: Verify Simulation — Observation Task)

```bash
export ROBOT_TARGET=sim
uv run exercises/phase2_motion.py
```

在 Mujoco 窗口观察：机器人应依次做出点头、挥手、前行动作。如果机器人没有站起来，先切换到 `McAction_RL_JOINT_DEFAULT` 再等待。

> *Observe in the Mujoco window: the robot should perform nodding, waving, and walking in sequence. If the robot hasn't stood up, first switch to `McAction_RL_JOINT_DEFAULT` and wait.*

---

### 任务 2-B：石头剪刀布 (Task 2-B: Rock Paper Scissors)

```python
def rock_paper_scissors():
    ROCK  = [2000, 2000, 2000, 2000, 2000, 2000]   # 石头：全握 / Rock: all closed
    SCISS = [2000, 2000, 0, 0, 2000, 2000]          # 剪刀：食指+中指伸出 / Scissors: index+middle extended
    PAPER = [0, 0, 0, 0, 0, 0]                      # 布：全张开 / Paper: all open

    print("石头...")  # Rock...
    set_hand(right_positions=ROCK)
    time.sleep(1.0)

    print("剪刀...")  # Scissors...
    set_hand(right_positions=SCISS)
    time.sleep(1.0)

    print("布！")  # Paper!
    set_hand(right_positions=PAPER)
    time.sleep(1.0)

    set_hand(right_positions=PAPER)   # 保持张开状态结束 / End with open hand
```

**说明 (Explanation)**：`index_pos=0, middle_pos=0` 让食指和中指伸出，其余握紧就是剪刀。`thumb_pos_0/1` 是拇指两节，剪刀时也握紧比较自然。

> *`index_pos=0, middle_pos=0` extends the index and middle fingers; the rest closed makes scissors. `thumb_pos_0/1` are the two thumb joints; keeping them closed looks natural for scissors.*

---

### 任务 2-C：转圈 (Task 2-C: Walk in a Circle)

```python
def walk_in_circle(radius: float, speed: float, duration: float):
    """
    radius:   圆半径（米）/ Circle radius (meters)
    speed:    线速度（m/s）/ Linear speed (m/s)
    duration: 持续时间（秒）/ Duration (seconds)
    圆周运动公式：角速度 ω = v / r
    Circular motion formula: angular velocity ω = v / r
    """
    angular_vel = speed / radius
    print(f"转圈: 半径={radius}m  线速度={speed}m/s  角速度={angular_vel:.2f}rad/s")
    walk_for_seconds(speed, 0.0, angular_vel, duration)
```

调用示例 / Example call:
```python
walk_in_circle(radius=1.0, speed=0.15, duration=10.0)   # 半径 1m 的圆 / 1m radius circle
```

**说明 (Explanation)**：`angular_velocity` 正值左转，负值右转，和 `forward_velocity` 同时发送就是弧形路径。`ω = v / r` 是刚体圆周运动的基本关系式。

> *Positive `angular_velocity` turns left, negative turns right. Sending it together with `forward_velocity` produces a curved path. `ω = v / r` is the fundamental circular motion relationship.*

---

### 任务 2-D：安全包装 (Task 2-D: Safety Wrapper)

```python
def set_neck(shake_pos: float = 0.0, nod_pos: float = 0.0):
    SHAKE_LIMIT = (-0.6, 0.6)
    NOD_LIMIT   = (-0.3, 0.5)

    if not (SHAKE_LIMIT[0] <= shake_pos <= SHAKE_LIMIT[1]):
        print(f"  [警告] shake_pos={shake_pos:.3f} 超出范围 {SHAKE_LIMIT}，已拦截")
        # [Warning] shake_pos out of range, blocked
        return
    if not (NOD_LIMIT[0] <= nod_pos <= NOD_LIMIT[1]):
        print(f"  [警告] nod_pos={nod_pos:.3f} 超出范围 {NOD_LIMIT}，已拦截")
        # [Warning] nod_pos out of range, blocked
        return

    payload = {
        "header": make_header(),
        "data": {
            "shake": {"name": "idx27_head_joint1", "position": shake_pos,
                      "velocity": 0.0, "effort": 0.0},
            "nod":   {"name": "idx28_head_joint2", "position": nod_pos,
                      "velocity": 0.0, "effort": 0.0},
        },
    }
    return rpc("aimdk.protocol.McMotionService", "SetNeckCommand", payload)
```

**说明 (Explanation)**：把范围常量提取到函数顶部而不是硬编码在判断里，这样以后修改范围只改一处。

> *Extracting the limit constants to the top of the function rather than hardcoding them in the conditions means you only need to change them in one place.*

---

## Phase 3：地图与导航 (Map and Navigation)

### 任务 3-A：探索地图（观察题）(Task 3-A: Explore the Map — Observation Task)

```python
map_id = get_current_map_id()
points = get_waypoints(map_id)
print(f"当前地图 ID: {map_id}，共 {len(points)} 个导航点\n")
# Current map ID: {map_id}, total {len(points)} waypoints
for p in points:
    print(f"  point_id={p['point_id']:>5}  name={p.get('name', '(未命名)')}")
    # point_id, name (or "(unnamed)")
```

记录输出中的 `point_id` 和 `name`，后续任务会用到。

> *Record the `point_id` and `name` from the output — you'll need them for later tasks.*

---

### 任务 3-B：往返导航 (Task 3-B: Back-and-forth Navigation)

```python
import itertools

def round_trip(map_id: int, point_a: int, point_b: int, pause: float = 3.0):
    """在两个导航点之间循环往返 / Loop back and forth between two waypoints"""
    task_counter = itertools.count(1)

    for target in itertools.cycle([point_a, point_b]):
        task_id = next(task_counter)
        print(f"\n[导航] → point_id={target}  task_id={task_id}")
        try:
            navigate_to(map_id, target, task_id)
            wait_until_done(task_id)
            print(f"[到达] point_id={target}，等待 {pause} 秒...")
            # [Arrived] waiting {pause} seconds...
            time.sleep(pause)
        except KeyboardInterrupt:
            print("\n取消导航...")  # Cancelling navigation...
            cancel_nav(task_id)
            break


def wait_until_done(task_id: int, poll_interval: float = 1.0):
    while True:
        state = get_nav_state(task_id)
        if state == "PncServiceState_SUCCESS":
            print(f"  [完成] task_id={task_id}")  # [Done]
            return True
        elif state in ("PncServiceState_FAILED", "PncServiceState_IDLE", ""):
            print(f"  [失败] state={state}")  # [Failed]
            return False
        time.sleep(poll_interval)
```

---

### 任务 3-C：超时处理 (Task 3-C: Timeout Handling)

```python
def wait_with_timeout(task_id: int, timeout: float = 60.0) -> str:
    """
    返回值: "success" / "failed" / "timeout"
    Return value: "success" / "failed" / "timeout"
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = get_nav_state(task_id)

        if state == "PncServiceState_SUCCESS":
            return "success"
        elif state in ("PncServiceState_FAILED", "PncServiceState_IDLE", ""):
            return "failed"
        # RUNNING / PAUSED: 继续等待 / Keep waiting
        time.sleep(1.0)

    # 超时：主动取消 / Timeout: cancel proactively
    print(f"  [超时] {timeout}s 内未到达，取消任务")
    # [Timeout] Not arrived within {timeout}s, cancelling task
    cancel_nav(task_id)
    return "timeout"
```

调用 / Usage:
```python
result = wait_with_timeout(task_id, timeout=60.0)
if result == "timeout":
    print("导航超时，请检查路径是否被堵塞")
    # Navigation timed out, check if the path is blocked
```

---

### 任务 3-D：按名称导航 (Task 3-D: Navigate by Name)

```python
def navigate_by_name(destination: str, map_id: int = None, task_id: int = 1) -> bool:
    """
    按导航点名称导航，自动查找对应 point_id。
    找不到时打印友好提示并返回 False。

    Navigate to a waypoint by name, automatically resolving to point_id.
    Prints a friendly message and returns False if not found.
    """
    if map_id is None:
        map_id = get_current_map_id()

    points = get_waypoints(map_id)
    matches = [p for p in points if p.get("name") == destination]

    if not matches:
        available = [p.get("name", "?") for p in points]
        print(f"  [错误] 找不到导航点 "{destination}"")  # [Error] Waypoint not found
        print(f"  可用导航点: {available}")  # Available waypoints
        return False

    point_id = matches[0]["point_id"]
    print(f"  [导航] {destination}（point_id={point_id}）")  # [Navigating]
    navigate_to(map_id, point_id, task_id)
    return True
```

**说明 (Explanation)**：先过滤出名称匹配的列表，找不到时打印所有可用名称让用户对照。如果地图里有重名导航点，取第一个（实际工程里应该要求名称唯一）。

> *Filter to matching names first; if none found, print all available names so the user can compare. If the map has duplicate names, take the first match (real projects should enforce unique names).*

---

## Phase 4：语音与交互 (Voice and Interaction)

### 任务 4-A：纯 HTTP 测试（观察题）(Task 4-A: Pure HTTP Test — Observation Task)

```bash
export ROBOT_TARGET=real
uv run exercises/phase4_voice.py test
```

成功标准：机器人扬声器发出声音 + 胸部 RGB 灯变色。如果 TTS 无声，检查音量设置；如果灯不变色，确认 RGB 服务端口 52893 可达。

> *Success criteria: the robot speaker makes a sound and the chest RGB light changes color. If TTS is silent, check the volume setting; if the light doesn't change, confirm that RGB service port 52893 is reachable.*

---

### 任务 4-B：唤醒词触发序列 (Task 4-B: Wake Word Trigger Sequence)

```python
import datetime

def on_wakeup_with_time(result):
    # 1. 红灯闪两下（确认收到）/ Red light flashes twice (confirm receipt)
    for _ in range(2):
        set_light(255, 0, 0, effect=3)   # 红色闪烁 / Red flash
        time.sleep(0.5)

    # 2. 播报当前时间 / Announce current time
    now = datetime.datetime.now()
    time_str = now.strftime("%H点%M分")
    say(f"现在是{time_str}")
    time.sleep(4.0)   # 等待 TTS 播完 / Wait for TTS to finish

    # 3. 恢复蓝色待机 / Restore blue standby
    set_light(0, 80, 255, effect=2)

listen_for_wakeup(on_wakeup_with_time, timeout=60.0)
```

**说明 (Explanation)**：`strftime("%H点%M分")` 生成中文时间字符串，TTS 能正常朗读。等待时间根据文字长度估算，精确做法见任务 4-D。

> *`strftime("%H点%M分")` generates a Chinese time string that TTS can read naturally. The sleep time is estimated from text length; see Task 4-D for a precise approach.*

---

### 任务 4-C：按时间问候 (Task 4-C: Time-based Greeting)

```python
def on_wakeup_greeting(result):
    hour = datetime.datetime.now().hour

    if 6 <= hour < 12:
        greeting = "早上好！"    # Good morning!
    elif 12 <= hour < 18:
        greeting = "下午好！"    # Good afternoon!
    elif 18 <= hour < 24:
        greeting = "晚上好！"    # Good evening!
    else:
        greeting = "你好！"      # Hello! (midnight to 6am)

    set_light(0, 255, 80, effect=1)
    say(greeting)
    time.sleep(3.0)
    set_light(0, 80, 255, effect=2)

listen_for_wakeup(on_wakeup_greeting, timeout=60.0)
```

---

### 任务 4-D：等待 TTS 完成 (Task 4-D: Wait for TTS Completion)

```python
import threading
import uuid

def say_and_wait(text: str, timeout: float = 10.0):
    """发送 TTS 并等待播放完成（或超时）/ Send TTS and wait for playback to finish (or timeout)"""
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy

    TTS_STATUS_TOPIC = "/interaction/tts_status/pb_3Aaimdk_2Eprotocol_2ETTSStatus"
    trace_id = str(uuid.uuid4())[:8]   # 唯一请求 ID / Unique request ID
    done_event = threading.Event()

    class TtsWatcher(Node):
        def __init__(self):
            super().__init__("tts_watcher")
            qos = QoSProfile(
                reliability=QoSReliabilityPolicy.RELIABLE,
                durability=QoSDurabilityPolicy.VOLATILE,
                history=QoSHistoryPolicy.KEEP_LAST,
                depth=10,
            )
            self.create_subscription(
                __import__("ros2_plugin_proto.msg", fromlist=["RosMsgWrapper"]).RosMsgWrapper,
                TTS_STATUS_TOPIC,
                self._cb,
                qos,
            )

        def _cb(self, msg):
            from aimdk.protocol.interaction import tts_pb2
            raw = b"".join(msg.data)
            status = tts_pb2.TTSStatus()
            status.ParseFromString(raw)
            if status.trace_id == trace_id and status.state == "TTS_STATE_FINISHED":
                done_event.set()

    # 先发 TTS 请求 / Send TTS request first
    say(text, trace_id=trace_id)

    # 再订阅状态 Topic / Then subscribe to status topic
    rclpy.init()
    node = TtsWatcher()
    executor = rclpy.executors.SingleThreadedExecutor()
    executor.add_node(node)

    deadline = time.time() + timeout
    while time.time() < deadline and not done_event.is_set():
        executor.spin_once(timeout_sec=0.1)

    node.destroy_node()
    rclpy.shutdown()

    if not done_event.is_set():
        print(f"  [TTS] 超时（{timeout}s），继续执行")
        # [TTS] Timed out, continuing
```

**说明 (Explanation)**：关键是先发 TTS 再开始监听，否则消息可能在订阅建立前就已经发出（VOLATILE durability 不保留历史）。用 `trace_id` 匹配是必须的，否则会响应其他来源的 TTS。

> *Critically, send TTS first, then start listening. Otherwise the message may be emitted before the subscription is established (VOLATILE durability does not retain history). Matching by `trace_id` is essential, or you'll respond to TTS from other sources.*

---

## Phase 5：综合项目 (Capstone Project)

### 任务 5-A：模拟模式验证（观察题）(Task 5-A: Simulate Mode Validation — Observation Task)

```bash
cd projects/reception_robot
uv run main.py --simulate
```

应该看到控制台依次打印各状态的 `[TTS]`、`[灯光]` 前缀输出，说明状态机逻辑正确。如果没有任何状态转移输出，检查 `simulate_mode()` 是否正确替换了 `rc.*` 方法。

> *You should see `[TTS]` and `[灯光]` (light) prefixed output in the console as each state runs, confirming the state machine logic is correct. If there's no state transition output, check whether `simulate_mode()` correctly replaces the `rc.*` methods.*

---

### 任务 5-B：修改配置 (Task 5-B: Modify Configuration)

编辑 `projects/reception_robot/main.py` / Edit `projects/reception_robot/main.py`:

```python
# 用 Phase 3 查到的真实 point_id 替换这里的数字
# Replace these numbers with the real point_ids from your Phase 3 map query
WAYPOINT_MAP = {
    "前台":   101,   # ← 替换成你的地图里"前台"的 point_id / Replace with your map's "reception" point_id
    "会议室": 202,   # ← 同上 / Same
    "茶水间": 303,
    "大厅":   404,
}
```

验证步骤：先用 Phase 3 的代码打印出所有导航点，把 `name` 和 `point_id` 对应关系填进来。

> *Validation: first use the Phase 3 code to print all waypoints, then fill in the `name` → `point_id` mappings.*

---

### 任务 5-C：真机运行（操作题）(Task 5-C: Run on Real Robot — Hands-on Task)

```bash
source /opt/ros/humble/setup.bash
export ROBOT_TARGET=real
cd projects/reception_robot
uv run main.py
```

测试流程 / Test procedure:
1. 确认蓝灯呼吸（待机状态）/ Confirm blue breathing light (standby state)
2. 说出唤醒词 / Speak the wake word
3. 绿灯亮起，机器人问"请问去哪里？" / Green light; robot asks "Where would you like to go?"
4. 说出目的地（例如"我要去会议室"）/ Speak the destination (e.g., "I want to go to the meeting room")
5. 机器人导航前往，到达后播报"已到达" / Robot navigates there; announces "Arrived" on completion

---

### 任务 5-D：TTS 完成等待 (Task 5-D: Wait for TTS Completion)

在 `projects/reception_robot/robot_client.py` 里把 `say()` + `time.sleep()` 替换为 `say_and_wait()`（参考任务 4-D 实现，或直接复用 Phase 4 的函数）。

> *In `projects/reception_robot/robot_client.py`, replace `say()` + `time.sleep()` with `say_and_wait()` (see Task 4-D implementation, or reuse the Phase 4 function directly).*

在 `state_machine.py` 的 `handle_greeting()` 里 / In `handle_greeting()` in `state_machine.py`:

```python
# 改前 / Before
rc.say("您好，请问去哪里？")
time.sleep(3.5)

# 改后 / After
rc.say_and_wait("您好，请问去哪里？", timeout=8.0)
```

**效果 (Effect)**：机器人说完话才进入 LISTENING 状态，避免还在说话就开始听 ASR 结果。

> *The robot enters LISTENING state only after it finishes speaking, avoiding ASR listening while the TTS is still playing.*

---

### 任务 5-E：电量低警告 (Task 5-E: Low Battery Warning)

在 `state_machine.py` 的 `handle_idle()` 里加检查 / Add a check in `handle_idle()` in `state_machine.py`:

```python
CHARGER_POINT_ID = 999   # 替换成地图里充电桩的 point_id，没有则设 None
                          # Replace with the charger point_id in your map; set None if unavailable

def handle_idle(self):
    # 检查电量 / Check battery level
    bms = rc.get_battery_state()
    soc = bms.get("bms_state", {}).get("soc", 100.0)

    if soc < 10 and CHARGER_POINT_ID:
        rc.set_light(255, 0, 0, effect=3)
        rc.say("电量严重不足，正在返回充电")  # Battery critically low, returning to charge
        time.sleep(3.0)
        task_id = rc.navigate_to(self.map_id, CHARGER_POINT_ID)
        self._wait_nav(task_id)
        return
    elif soc < 20:
        rc.set_light(255, 0, 0, effect=3)
        rc.say("电量不足，请及时充电")  # Battery low, please charge soon
        time.sleep(3.0)

    # 正常待机 / Normal standby
    rc.light_standby()
    self._transition(State.IDLE)
```

---

### 任务 5-F：记录服务日志 (Task 5-F: Log Service Records)

在 `projects/reception_robot/main.py` 顶部加 / Add at the top of `projects/reception_robot/main.py`:

```python
import logging
from datetime import datetime

logging.basicConfig(
    filename="reception.log",
    level=logging.INFO,
    format="%(message)s",
)

def log_session(wake_word, user_said, destination, point_id, nav_result, elapsed):
    logging.info(
        f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"唤醒词: {wake_word}\n"
        f"用户说: {user_said}\n"
        f"目标: {destination} (point_id={point_id})\n"
        f"导航: {nav_result}，用时 {elapsed:.0f} 秒\n"
        + "-" * 40
    )
    # Fields: Time, Wake word, User said, Destination, Navigation result + duration
```

在 `handle_arrived()` 或导航完成后调用 `log_session()`。关键信息在状态机实例变量里：`self.wake_word`、`self.asr_text`、`self.target_name` 等，根据实际字段名调整。

> *Call `log_session()` in `handle_arrived()` or after navigation completes. Key info lives in the state machine instance variables: `self.wake_word`, `self.asr_text`, `self.target_name`, etc. Adjust to match actual field names.*
