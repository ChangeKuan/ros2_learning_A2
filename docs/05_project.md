# 综合项目：语音导引接待机器人 (Capstone Project: Voice-Guided Reception Robot)

> 对应代码：`projects/reception_robot/`
> 仿真：`uv run main.py --simulate`（验证逻辑）
> 真机：`export ROBOT_TARGET=real && uv run main.py`
>
> *Code: `projects/reception_robot/`*
> *Simulation: `uv run main.py --simulate` (validates logic)*
> *Real robot: `export ROBOT_TARGET=real && uv run main.py`*

---

## 项目目标 (Project Goal)

构建一个完整的接待机器人程序：

> *Build a complete reception robot program:*

```
[待机 / Standby] 蓝灯呼吸，等待唤醒词 / Blue breathing light, waiting for wake word
   │ 检测到唤醒词 / Wake word detected
   ▼
[问候 / Greeting] 绿灯 + 点头 + TTS "您好，请问去哪里？" / Green light + nod + TTS
   │ TTS 播完 / TTS finished
   ▼
[聆听 / Listening] 等待 ASR 识别目标地点（8秒超时）/ Wait for ASR to recognize destination (8 s timeout)
   │ 识别到关键词 / Keyword recognized
   ▼
[导航 / Navigating] 黄灯 + TTS "好的，带您前往XXX" + PNC 导航 / Yellow light + TTS + PNC navigation
   │ 到达 / Arrived
   ▼
[到达 / Arrived] 青灯 + TTS "已到达" + 挥手动作 / Cyan light + TTS "Arrived" + wave gesture
   │ 完成 / Complete
   ▼
[待机 / Standby] 循环 / Loop
```

---

## 1. 知识点：状态机设计 (State Machine Design)

### 1.1 为什么用状态机？ (Why a State Machine?)

不用状态机，代码会变成一个巨大的 `if/elif` 嵌套：

> *Without a state machine, the code becomes a massive nested `if/elif`:*

```python
# 不好的写法 / Bad approach
while True:
    if wakeup_detected:
        say("你好")
        if asr_result:
            if nav_success:
                ...    # 无限嵌套，难以维护 / Infinite nesting, hard to maintain
```

用**有限状态机（FSM）**，每个状态的逻辑独立，转移关系明确：

> *With a **Finite State Machine (FSM)**, each state's logic is isolated and transitions are explicit:*

```python
class State(Enum):
    IDLE = auto()
    GREETING = auto()
    LISTENING = auto()
    NAVIGATING = auto()
    ARRIVED = auto()
    ERROR = auto()
```

每个 `handle_xxx` 方法封装了对应状态的所有逻辑，互不干扰。

> *Each `handle_xxx` method encapsulates all logic for its state, with no interference between states.*

### 1.2 状态转移图 (State Transition Diagram)

```
┌──────────────────────────────────────────────────────┐
│                                                      │
│  IDLE ──[唤醒词/wake word]──> GREETING ──[完成/done]──> LISTENING   │
│   ▲                                        │         │
│   │                             [识别到目的地/destination recognized] │
│   │                                        │         │
│   │                                        ▼         │
│   │              ARRIVED <──[成功/success]── NAVIGATING      │
│   │                 │                     │          │
│   └──[完成/done]────┘                     │          │
│                                           │          │
│  ERROR <──────────────────────────[失败/超时/fail/timeout]   │
│    │                                                 │
│    └──[恢复/recover]──> IDLE                         │
└──────────────────────────────────────────────────────┘
```

### 1.3 状态机代码结构 (State Machine Code Structure)

```python
class ReceptionRobot:
    def __init__(self, waypoint_map, map_id):
        self.state = State.IDLE          # 当前状态 / Current state
        self.current_task_id = None      # 导航任务 ID / Navigation task ID
        self.target_name = None          # 当前导航目标名称 / Current navigation target name

    def _transition(self, new_state):
        print(f"[状态/State] {self.state.name} → {new_state.name}")
        self.state = new_state

    def handle_idle(self):      # IDLE 状态的逻辑 / IDLE state logic
        ...
    def handle_greeting(self):  # GREETING 状态的逻辑 / GREETING state logic
        ...
    def handle_listening(self, asr_text) -> bool:
        ...
```

---

## 2. 知识点：多线程与 ROS2 (Multi-threading and ROS2)

### 2.1 问题：ROS2 会阻塞主线程 (Problem: ROS2 Blocks the Main Thread)

```python
rclpy.spin(node)   # 这会一直阻塞，你的其他代码无法运行 / This blocks forever; your other code can't run
```

### 2.2 解决方案：后台线程 (Solution: Background Thread)

```python
import threading

executor = rclpy.executors.SingleThreadedExecutor()
executor.add_node(node)

# 把 ROS2 放到后台线程 / Move ROS2 to a background thread
ros_thread = threading.Thread(target=executor.spin, daemon=True)
ros_thread.start()

# 主线程继续运行状态机 / Main thread continues running the state machine
run_main_loop(robot, node)
```

`daemon=True` 表示后台线程，主程序退出时它自动退出，不会让程序卡住。

> *`daemon=True` marks the thread as a daemon — it exits automatically when the main program exits, preventing the program from hanging.*

### 2.3 线程安全：Event (Thread Safety: Event)

ROS2 回调在后台线程里运行，主线程需要知道"收到唤醒词了"。用 `threading.Event` 做信号传递：

> *ROS2 callbacks run in the background thread; the main thread needs to know "a wake word was received." Use `threading.Event` for signaling:*

```python
class ReceptionNode(Node):
    def __init__(self, robot):
        self._wakeup_event = threading.Event()   # 事件标志 / Event flag

    def _on_wakeup(self, msg):
        # 后台线程：收到消息时设置标志 / Background thread: set flag when message arrives
        self._wakeup_event.set()

    def wait_for_wakeup(self, timeout=None) -> bool:
        # 主线程：等待标志被设置 / Main thread: wait for the flag to be set
        triggered = self._wakeup_event.wait(timeout)
        self._wakeup_event.clear()   # 重置，准备下次 / Reset for next use
        return triggered
```

`threading.Event` 是线程安全的，专为这种"一个线程通知另一个线程"的场景设计。

> *`threading.Event` is thread-safe, designed exactly for this "one thread notifies another" pattern.*

---

## 3. 代码详解：`main.py` (Code Walkthrough)

### 3.1 配置区 (Configuration)

```python
WAYPOINT_MAP = {
    # 导航点名称 (ASR 会匹配这些词): 地图导航点 ID
    # Waypoint name (ASR will match these words): map waypoint ID
    "前台": 101,
    "会议室": 202,
    "茶水间": 303,
    "大厅": 404,
}
```

**这是你在真机上必须修改的地方**：把 `point_id` 换成你的地图里实际的 ID（用 Phase 3 学到的 `get_waypoints()` 查）。

> ***This is what you must modify for the real robot**: Replace `point_id` values with the actual IDs from your map (look them up with `get_waypoints()` from Phase 3).*

### 3.2 主循环 (Main Loop)

```python
def run_main_loop(robot, node):
    robot.handle_idle()

    while True:
        current = robot.state

        if current == State.IDLE:
            triggered = node.wait_for_wakeup(timeout=None)   # 无限等待 / Wait indefinitely
            if triggered:
                robot._transition(State.GREETING)

        elif current == State.GREETING:
            robot.handle_greeting()    # 内部会转到 LISTENING / Internally transitions to LISTENING

        elif current == State.LISTENING:
            text = node.wait_for_asr(timeout=8.0)
            if text:
                robot.handle_listening(text)
            else:
                robot._transition(State.IDLE)   # 超时，回待机 / Timeout, return to standby

        elif current == State.NAVIGATING:
            done = robot.handle_navigating()
            if not done:
                time.sleep(1.0)    # 还在走，等 1 秒再查 / Still navigating, wait 1 s and check again

        elif current == State.ARRIVED:
            robot.handle_arrived()   # 内部会转到 IDLE / Internally transitions to IDLE
```

**可读性设计 (Readability design)**：主循环只处理状态转移的"驱动"逻辑，每个状态的具体行为都封装在 `state_machine.py` 里。

> *The main loop only handles the state-transition "driver" logic; each state's concrete behavior is encapsulated in `state_machine.py`.*

### 3.3 ASR 关键词匹配 (ASR Keyword Matching)

```python
def handle_listening(self, asr_text: str) -> bool:
    for name, point_id in self.waypoint_map.items():
        if name in asr_text:          # ← 简单的字符串包含检测 / Simple substring check
            self.target_name = name
            return self._start_navigation(point_id)

    rc.say("抱歉，我没有听清楚，请再说一遍")
    return False
```

这里用的是最简单的关键词匹配：如果 ASR 文本里包含导航点名称（如"茶水间"），就导航过去。

> *This uses the simplest keyword matching: if the ASR text contains a waypoint name (e.g. "茶水间"), navigate there.*

**局限性 (Limitation)**：如果用户说"不去茶水间"，也会触发"茶水间"匹配。可以用更复杂的 NLP 来改进，但对于起步项目，简单匹配够用。

> *Limitation: if the user says "I don't want to go to the pantry," it still matches "pantry." More complex NLP can improve this, but simple matching is sufficient for a starter project.*

### 3.4 模拟模式 (Simulation Mode)

```python
def simulate_mode():
    # 用 mock 函数替换真实 API / Replace real APIs with mock functions
    rc.say = lambda text, **kw: print(f"[TTS] {text}")
    rc.light_standby = lambda: print("[灯光/Light] 蓝色待机 / Blue standby")
    rc.navigate_to = lambda *a, **kw: 999
    rc.get_nav_state = lambda *a: "PncServiceState_SUCCESS"
    ...

    robot = ReceptionRobot(WAYPOINT_MAP, map_id=1)
    # 手动驱动每个状态 / Manually drive each state
    robot._transition(State.GREETING)
    robot.handle_greeting()
    robot.handle_listening("我想去会议室 / I want to go to the meeting room")
    ...
```

**模拟模式的价值 (Value of simulation mode)**：

1. 不需要连接机器人就能验证状态机逻辑 / Validate state machine logic without connecting a robot
2. 可以快速测试边界情况（无效输入、导航失败等）/ Quickly test edge cases (invalid input, navigation failure, etc.)
3. 代码对"真实函数"和"mock 函数"完全透明，这是良好设计的体现 / Code is fully transparent to real vs. mock functions — this reflects good design

---

## 4. 代码详解：`robot_client.py` (Code Walkthrough)

### 4.1 设计理念 (Design Philosophy)

`robot_client.py` 是一个**门面层（Facade）**：它把所有分散的 API 调用收集在一个地方，上层代码（`state_machine.py`, `main.py`）不需要知道任何 IP 地址、端口、协议细节。

> *`robot_client.py` is a **Facade layer**: it collects all scattered API calls in one place, so upper-layer code (`state_machine.py`, `main.py`) doesn't need to know any IP addresses, ports, or protocol details.*

```python
# 好的写法 / Good approach ✓
rc.say("你好")
rc.light_navigating()
rc.navigate_to(map_id, point_id)

# 如果没有 robot_client.py / Without robot_client.py ✗
requests.post("http://192.168.100.110:59301/rpc/aimdk.protocol.TTSService/PlayTTS",
              json={"text": "你好", "priority_level": "INTERACTION_L6", ...})
```

这种分层让你在切换真机/仿真时，只需要改 `config.py` 里的 IP，不用改业务逻辑。

> *This layering means switching between real robot and simulation only requires changing the IP in `config.py`, not touching business logic.*

### 4.2 仿真兼容 (Simulation Compatibility)

```python
def say(text: str, priority: str = "INTERACTION_L6"):
    if SIM:
        print(f"[TTS-仿真/Sim] {text}")   # 仿真时打印代替播音 / Print instead of speaking in sim
        return {}
    payload = { ... }
    return _rpc(NAV_IP, 59301, "aimdk.protocol.TTSService", "PlayTTS", payload)
```

这就是为什么 `--simulate` 模式能在没有机器人的情况下运行——每个不可用的 API 都有一个 fallback。

> *This is why `--simulate` mode works without a robot — every unavailable API has a fallback.*

---

## 5. 实战任务 (Hands-on Tasks)

### 任务 5-A：模拟模式验证 (Task 5-A: Simulate Mode Validation)

```bash
cd projects/reception_robot
uv run main.py --simulate
```

观察每个状态的输出，确认流程正确。

> *Observe the output for each state and confirm the flow is correct.*

### 任务 5-B：修改配置 (Task 5-B: Update Configuration)

编辑 `main.py` 的 `WAYPOINT_MAP`，填入你的真机地图里实际的导航点 ID：

> *Edit `WAYPOINT_MAP` in `main.py` with the actual waypoint IDs from your real robot's map:*

```python
WAYPOINT_MAP = {
    "你的地点名称 / Your location name": 你的point_id,
    ...
}
```

### 任务 5-C：真机运行 (Task 5-C: Run on Real Robot)

```bash
source /opt/ros/humble/setup.bash
export ROBOT_TARGET=real
uv run main.py
```

全程测试：唤醒 → 说出目的地 → 导航 → 到达。

> *Full end-to-end test: wake word → say destination → navigate → arrive.*

### 任务 5-D：改进一：TTS 完成等待 (Task 5-D: Improvement 1 — Wait for TTS)

当前项目用 `time.sleep(3.5)` 等待 TTS 播完。改成订阅 TTS Status Topic，等 `TTS_STATE_FINISHED` 后再继续（参考 `examples/agent/tts_status_topic.py`）。

> *The current project uses `time.sleep(3.5)` to wait for TTS. Change it to subscribe to the TTS Status Topic and wait for `TTS_STATE_FINISHED` before continuing (see `examples/agent/tts_status_topic.py`).*

### 任务 5-E（挑战）：改进二：添加电量低警告 (Task 5-E (Challenge): Improvement 2 — Low Battery Warning)

在 `handle_idle()` 里，每次进入待机时检查电量：

> *In `handle_idle()`, check battery level every time standby is entered:*

- 电量 < 20%：TTS 播报"电量不足，请及时充电"，灯光改为红色闪烁 / Battery < 20%: TTS "Low battery, please charge soon", red blinking light
- 电量 < 10%：返回充电桩（如果地图里有充电桩导航点）/ Battery < 10%: Return to charging station (if a charging waypoint exists on the map)

### 任务 5-F（挑战）：改进三：记录服务日志 (Task 5-F (Challenge): Improvement 3 — Service Logging)

用 Python 的 `logging` 模块，把每次接待的完整流程记录到文件：

> *Use Python's `logging` module to record each complete reception session to a file:*

```
时间 / Time: 2026-06-19 14:30:21
唤醒词 / Wake word: 你好
用户说 / User said: 我要去会议室
目标 / Destination: 会议室 (point_id=202)
导航 / Navigation: 成功，用时 45 秒 / Success, 45 seconds
```

---

## 6. 项目架构总结 (Project Architecture Summary)

```
main.py
  │  启动 ROS2 节点 + 驱动状态机主循环
  │  Starts ROS2 node + drives the state machine main loop
  │
  ├── ReceptionNode (ROS2 节点 / ROS2 node)
  │     │  后台线程运行 / Runs in background thread
  │     ├── 订阅唤醒词 → _wakeup_event.set() / Subscribe to wake word
  │     └── 订阅 ASR → _asr_text = text / Subscribe to ASR result
  │
  └── ReceptionRobot (状态机 / State machine)
        │  主线程运行 / Runs in main thread
        ├── handle_idle()       → 灯光初始化 / Light initialization
        ├── handle_greeting()   → 灯光+动作+TTS / Light + action + TTS
        ├── handle_listening()  → 关键词匹配+导航下发 / Keyword matching + nav submission
        ├── handle_navigating() → 轮询 PNC 状态 / Poll PNC status
        └── handle_arrived()    → 灯光+TTS+挥手 / Light + TTS + wave

robot_client.py (门面层 / Facade layer)
  └── 封装所有 HTTP RPC 调用，屏蔽 IP/端口细节
      Wraps all HTTP RPC calls, hiding IP/port details

config.py
  └── ROBOT_TARGET=sim|real 切换 IP 配置 / Switch IP configuration
```

---

## 7. 扩展方向 (Extension Directions)

完成基础项目后，可以按兴趣深入：

> *After completing the base project, explore further based on your interests:*

| 方向 / Direction | 具体内容 / Details |
|------|---------|
| **更智能的语言理解 / Smarter language understanding** | 接入 Claude API，用 LLM 解析用户意图，不只是关键词匹配 / Integrate the Claude API to use an LLM for intent parsing instead of keyword matching |
| **人脸识别 / Face recognition** | 参考 `examples/agent/get_face_id.py`，识别特定访客 / See `examples/agent/get_face_id.py` to recognize specific visitors |
| **多机协同 / Multi-robot coordination** | 参考 `docs/06_multi_robot.md`，多容器仿真 + 单键盘 Tab 切换控制 / See `docs/06_multi_robot.md` for multi-container simulation + single-keyboard Tab switching |
| **任务引擎 / Task engine** | 参考 `examples/task_engine/`，用官方任务系统管理复杂流程 / See `examples/task_engine/` for the official task system to manage complex flows |
| **传感器融合 / Sensor fusion** | 参考 `examples/sensors/`，利用 RGBD 相机识别障碍物 / See `examples/sensors/` to use the RGBD camera for obstacle recognition |

---

## 8. 完整知识图谱回顾 (Complete Knowledge Map)

```
Phase 1: HTTP RPC ── 读取状态（GetAction, GetJointState, GetBmsState）
         HTTP RPC ── Read state (GetAction, GetJointState, GetBmsState)
           │
Phase 2: 运动控制 ── SetAction + SetNeckCommand + SetHandCommand + ROS2 walk
         Motion control ── SetAction + SetNeckCommand + SetHandCommand + ROS2 walk
           │
Phase 3: 导航 ────── GetCurrentWorkingMap + GetTopoMsgs + PlanningNaviToGoal
         Navigation ── GetCurrentWorkingMap + GetTopoMsgs + PlanningNaviToGoal
           │
Phase 4: 语音交互 ── PlayTTS + 订阅 WakeUpResult + 订阅 AsrResult + SetRgbLight
         Voice ──── PlayTTS + subscribe WakeUpResult + subscribe AsrResult + SetRgbLight
           │
Phase 5: 综合项目 ── 状态机 + 多线程 + 门面层 + 模拟模式
         Capstone ── State machine + multi-threading + facade layer + simulation mode
```

每一层都建立在前一层之上。当你完成项目时，你已经掌握了：

> *Each layer builds on the previous one. When you finish the project, you will have mastered:*

- 机器人软件的通信模式（HTTP RPC + ROS2 Topic）/ Robot software communication patterns (HTTP RPC + ROS2 Topic)
- 数据格式（JSON + Protobuf）/ Data formats (JSON + Protobuf)
- 机器人运动控制基础 / Robot motion control basics
- 自主导航集成 / Autonomous navigation integration
- 语音人机交互 / Voice human-robot interaction
- 状态机软件架构 / State machine software architecture
- 仿真-真机双环境开发流程 / Dual-environment (simulation + real) development workflow
