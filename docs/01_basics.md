# Phase 1：基础通信 — 读取机器人状态 (Basic Communication — Reading Robot State)

> 对应练习文件：`exercises/phase1_basics.py`
> 仿真可用：GetAction ✓，GetJointState ✓，BMS ✗（返回模拟值），SystemState ✗
>
> *Exercise file: `exercises/phase1_basics.py`*
> *Simulation support: GetAction ✓, GetJointState ✓, BMS ✗ (returns mock values), SystemState ✗*

---

## 学习目标 (Learning Objectives)

完成本节后，你能：

> *After completing this section, you will be able to:*

1. 说清楚 HTTP RPC 的请求-响应流程 / Explain the HTTP RPC request–response flow
2. 理解 `header` 字段的作用和构造方式 / Understand the role and structure of the `header` field
3. 从 5 个不同服务读取机器人状态 / Read robot state from 5 different services
4. 解析并格式化打印 JSON 响应 / Parse and pretty-print JSON responses

---

## 1. 知识点：HTTP RPC 通信模式 (HTTP RPC Communication Pattern)

### 1.1 为什么用 HTTP？ (Why HTTP?)

机器人内部有多个独立进程（运动控制、导航、语音…），它们需要被外部程序调用。HTTP 是最通用的选择：

> *The robot runs multiple independent processes (motion control, navigation, voice…) that need to be called by external programs. HTTP is the most universal choice:*

- 任何语言都能发 HTTP 请求 / Any language can send HTTP requests
- 调试简单（curl 就能测）/ Easy to debug (testable with curl)
- 无状态，每次请求独立 / Stateless — each request is independent

### 1.2 请求的完整结构 (Full Request Structure)

```python
import requests

url = "http://127.0.0.1:56322/rpc/aimdk.protocol.McActionService/GetAction"
#      ─────────────  ─────  ──── ──────────────────────────────  ─────────
#      协议+IP        端口   固定  服务全名（包含包名）              方法名
#      protocol+IP    port   fixed full service name (with package) method

response = requests.post(
    url,
    headers={"Content-Type": "application/json"},
    json={},        # 请求体，空 dict 表示无参数 / request body, empty dict = no params
    timeout=3.0,    # 超时时间（秒）/ timeout in seconds
)
response.raise_for_status()   # 非 200 状态码抛异常 / raises on non-200 status
result = response.json()      # 解析 JSON 响应 / parse JSON response
```

### 1.3 `header` 字段是什么？ (What is the `header` field?)

很多接口的请求体里有一个 `header` 字段：

> *Many API request bodies include a `header` field:*

```json
{
    "header": {
        "timestamp": {
            "seconds": 1718765432,
            "nanos": 123000000,
            "ms_since_epoch": 1718765432123
        },
        "control_source": "ControlSource_SAFE"
    }
}
```

**`timestamp` 的三个子字段描述同一时刻，三者冗余但各有用途：**

> ***The three `timestamp` sub-fields all describe the same moment — redundant but each has its purpose:***

| 字段 / Field | 类型 / Type | 含义 / Meaning |
|------|------|------|
| `seconds` | int | Unix 时间戳，精确到秒 / Unix timestamp in seconds |
| `nanos` | int | 当前秒内的纳秒偏移（0 ~ 999,999,999）。Python `datetime` 精度为微秒，所以末三位永远是 `000` / Nanosecond offset within the current second. Python `datetime` is microsecond-precision, so the last 3 digits are always `000` |
| `ms_since_epoch` | int | Unix 时间戳，精确到毫秒（= `seconds × 1000 + nanos ÷ 1,000,000`）/ Unix timestamp in milliseconds |

机器人用 `timestamp` 判断指令是否过期 — 如果收到一条时间戳比当前时间早很多的指令，说明网络严重延迟，会丢弃该指令。

> *The robot uses `timestamp` to detect stale commands — if a command's timestamp is much older than the current time, it means severe network delay and the command is discarded.*

**`control_source` 可选值 (Possible values for `control_source`)：**

| 值 / Value | 含义 / Meaning |
|----|------|
| `"ControlSource_SAFE"` | 外部开发接口（本课程始终用这个）/ External developer interface (always use this in this course) |
| `"ControlSource_AUTO"` | 自主导航/任务系统 / Autonomous navigation/task system |
| `"ControlSource_MANUAL"` | 手柄/遥控器 / Gamepad/remote controller |

多个控制源同时发送指令时，机器人内部做仲裁，低优先级的指令会被忽略。

> *When multiple control sources send commands simultaneously, the robot arbitrates internally and ignores lower-priority commands.*

**规律 (Rule)**：只读接口（Get 类）大多不需要 header；写入/控制接口（Set 类）需要。

> *Read-only interfaces (Get methods) mostly don't need a header; write/control interfaces (Set methods) do.*

### 1.4 如何查找可用服务和方法 (How to Find Available Services and Methods)

URL 里的 `{服务名}` 和 `{方法名}` 从哪里知道？**答案就在 SDK 的 `.proto` 文件里。**

> *Where do you find the `{service}` and `{method}` names for the URL? **The answer is in the SDK's `.proto` files.***

所有 proto 文件在：`agibot_a2_aimdk-dev2.0/protocol/protobuf/aimdk/protocol/`

> *All proto files are in: `agibot_a2_aimdk-dev2.0/protocol/protobuf/aimdk/protocol/`*

每个文件的格式固定 (Each file follows this fixed format)：

```proto
service McActionService {
  rpc SetAction(McActionRequest) returns (CommonResponse);
  rpc GetAction(CommonRequest) returns (McActionResponse);
  rpc GetAvailableActions(CommonRequest) returns (AvailableActionsResponse);
}
```

- `service` 后面的名字 → URL 里的 `{服务名}` / Name after `service` → `{service}` in the URL
- `rpc` 后面的名字 → URL 里的 `{方法名}` / Name after `rpc` → `{method}` in the URL

**按功能关键词查找 (Search by keyword)**：

```bash
PROTO_DIR=agibot_a2_aimdk-dev2.0/protocol/protobuf

# 搜索包含关键词的方法名 / Search for method names containing a keyword
grep -r "rpc.*Walk\|rpc.*Move" $PROTO_DIR --include="*.proto"

# 找到文件后查看该服务的全部方法 / Then view all methods in that service
cat $PROTO_DIR/aimdk/protocol/mc/action/mc_action_service.proto
```

**常用服务的 proto 文件位置 (Proto file locations for common services)**：

| 服务 / Service | 文件（相对 `protocol/protobuf/aimdk/protocol/`）/ File |
|------|------|
| McActionService | `mc/action/mc_action_service.proto` |
| McMotionService | `mc/motion/mc_motion_service.proto` |
| McDataService | `mc/data/mc_data_service.proto` |
| PncService | `pnc/pnc_service.proto` |
| TTSService | `interaction/tts_service.proto` |
| HalBmsService | `hal/bms/hal_bms_service.proto` |

---

## 2. 代码详解：`phase1_basics.py` (Code Walkthrough)

### 2.1 通用 RPC 封装函数 (Generic RPC wrapper)

```python
def rpc(ip: str, port: int, service: str, method: str, payload: dict = None) -> dict:
    url = f"http://{ip}:{port}/rpc/{service}/{method}"
    resp = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json=payload or {},
        timeout=3.0,
    )
    resp.raise_for_status()
    return resp.json()
```

这个函数把重复的部分抽出来，以后调用任何接口都只需要：

> *This function factors out the repetitive boilerplate. Any API call then becomes simply:*

```python
result = rpc(MC_IP, 56322, "aimdk.protocol.McDataService", "GetJointState", {"header": make_header()})
```

### 2.2 获取当前动作模式 (Get Current Action Mode)

```python
def get_current_action() -> str:
    result = rpc(MC_IP, 56322, "aimdk.protocol.McActionService", "GetAction")
    return result.get("info", {}).get("current_action", "unknown")
```

**响应结构（真实返回示例）/ Response structure (real example)**：
```json
{
    "info": {
        "current_action": "McAction_ZERO_TORQUE",
        "target_action": "McAction_ZERO_TORQUE"
    }
}
```

**`info` 的字段含义 (Field meanings in `info`)**：

| 字段 / Field | 含义 / Meaning |
|------|------|
| `current_action` | 机器人**当前正在执行**的动作模式 / The action mode the robot **is currently executing** |
| `target_action` | 机器人**目标**动作模式（切换过程中两者不同，稳定后相同）/ The **target** action mode (differs from current during transitions, equal when stable) |

`result.get("info", {}).get("current_action", "unknown")` 是 Python 的安全访问链：

> *`result.get("info", {}).get("current_action", "unknown")` is Python's safe chained access:*

- 如果 `result` 没有 `"info"` 键，返回 `{}` / If `result` has no `"info"` key, returns `{}`
- 如果 `{}` 没有 `"current_action"`，返回 `"unknown"` / If `{}` has no `"current_action"`, returns `"unknown"`
- 避免了 `KeyError` / Avoids `KeyError`

### 2.3 全部动作模式含义 (All Action Modes Explained)

`GetAvailableActions` 返回的是不带前缀的短名（如 `RL_LOCOMOTION_DEFAULT`），`SetAction` 发送时需要加上 `McAction_` 前缀（如 `McAction_RL_LOCOMOTION_DEFAULT`）。

> *`GetAvailableActions` returns short names without the prefix (e.g. `RL_LOCOMOTION_DEFAULT`). `SetAction` requires the `McAction_` prefix (e.g. `McAction_RL_LOCOMOTION_DEFAULT`).*

动作模式按功能分为六类 (Action modes are grouped into six categories):

#### 基础姿态 (Basic Postures)

| 动作名（短）/ Short name | 含义 / Meaning |
|---|---|
| `DEFAULT` | 上电默认姿态，各关节归零位 / Default power-on posture, all joints at zero |
| `CURLED_UP` | 蜷缩姿态，四肢收拢贴近躯干，用于狭窄空间或搬运保护 / Curled posture, limbs tucked close to the torso for tight spaces or transport protection |
| `PACKAGE_SIT` | 打包坐姿，专为装箱运输设计的紧凑坐姿 / Compact seated posture designed for boxing/transport |
| `STAND_UP` | 非 RL 站起（固定轨迹，速度较慢）/ Non-RL stand-up (fixed trajectory, slower) |
| `SIT_DOWN` | 非 RL 坐下（固定轨迹）/ Non-RL sit-down (fixed trajectory) |

#### RL 站立 / 坐下 (RL Stand / Sit)

> `RL_` 前缀表示由强化学习策略驱动，能在不平整地面上保持平衡，比固定轨迹更鲁棒。
>
> *The `RL_` prefix means driven by a reinforcement-learning policy, capable of maintaining balance on uneven ground and more robust than fixed trajectories.*

| 动作名（短）/ Short name | 含义 / Meaning |
|---|---|
| `RL_JOINT_DEFAULT` | 关节归零位并上电，**仿真启动后第一步** / Zero joints and power on — **first step after sim starts** |
| `RL_STAND_UP` | RL 驱动的站起动作 / RL-driven stand-up action |
| `RL_SIT_DOWN` | RL 驱动的坐下动作 / RL-driven sit-down action |
| `RL_STAND_UP_POWER_OFF` | 站起后立即关闭电机 / Stand up then immediately cut motor power |
| `RL_STAND_UP_PREP_POWER_OFF` | 站起准备阶段，为后续断电做姿态预调整 / Stand-up prep phase to adjust posture before powering off |
| `RL_SIT_DOWN_POWER_OFF` | RL 坐下后关闭电机（**正常关机流程**）/ RL sit-down then cut power (**normal shutdown procedure**) |
| `RL_SIT_DOWN_PASSIVE_POWER_OFF` | 被动坐下后断电，断电失联时的保护动作 / Passive sit-down then power off — protective action on connection loss |

#### RL 行走 (RL Walking)

| 动作名（短）/ Short name | 含义 / Meaning |
|---|---|
| `RL_LOCOMOTION_DEFAULT` | **最常用**，标准 RL 行走，接受前进/侧移/转向速度指令 / **Most common** — standard RL walking, accepts forward/lateral/angular velocity commands |
| `RL_LOCOMOTION_EXT_ONLINE_PLANNING` | RL 行走 + 外部在线路径规划 / RL walking + external online path planning |

#### RL 行走 + 上肢控制 (RL Walking + Upper-Body Control)

> 下肢继续行走，上肢同时接受额外指令，用于"走路同时操作手臂"的场景。
>
> *The lower body continues walking while the upper body accepts additional commands — for scenarios like walking while operating the arms.*

| 动作名（短）/ Short name | 含义 / Meaning |
|---|---|
| `RL_LOCOMOTION_ARM_EXT_JOINT_SERVO` | 行走 + 手臂关节外部伺服 / Walking + external arm joint servo |
| `RL_LOCOMOTION_ARM_EXT_PLANNING_MOVE` | 行走 + 手臂轨迹规划 / Walking + arm trajectory planning |
| `RL_LOCOMOTION_ARM_EXT_COLLISON_ESCAPE` | 行走 + 手臂碰撞逃脱 / Walking + arm collision escape |

#### RL 全身协调控制 (RL Whole-Body Coordination)

> 下肢不再独立行走，全身关节统一受控，适合原地做复杂全身动作。
>
> *The legs no longer walk independently; all joints are controlled as a unit — suited for complex whole-body movements in place.*

| 动作名（短）/ Short name | 含义 / Meaning |
|---|---|
| `RL_WHOLE_BODY_EXT_JOINT_SERVO` | 全身关节外部伺服 / Whole-body external joint servo |
| `RL_WHOLE_BODY_EXT_ONLINE_PLANNING` | 全身在线轨迹规划 / Whole-body online trajectory planning |
| `RL_WHOLE_BODY_DANCE` | 内置舞蹈动作播放模式 / Built-in dance playback mode |

#### 被动上肢模式 (Passive Upper-Body Mode)

> 下肢站立固定，上肢进入被动/柔顺模式。
>
> *The lower body stands stationary; the upper body enters a passive/compliant mode.*

| 动作名（短）/ Short name | 含义 / Meaning |
|---|---|
| `PASSIVE_UPPER_BODY_JOINT_SERVO` | 上肢关节外部伺服（下肢站立保持）/ Upper-body external joint servo (legs hold standing) |
| `PASSIVE_UPPER_BODY_PLANNING_MOVE` | 上肢轨迹规划 / Upper-body trajectory planning |
| `PASSIVE_UPPER_BODY_ONLINE_PLANNING` | 上肢在线实时规划 / Upper-body online real-time planning |
| `PASSIVE_UPPER_BODY_COLLISON_ESCAPE` | 上肢碰撞逃脱 / Upper-body collision escape |

#### 移动平台模式 (Mobile Platform Mode)

> 机器人搭载轮式底盘（移动平台）时使用。
>
> *Used when the robot is mounted on a wheeled base (mobile platform).*

| 动作名（短）/ Short name | 含义 / Meaning |
|---|---|
| `MOBILE_PLATFORM_STAND_UP` | 从移动平台底座站起 / Stand up from the mobile platform base |
| `MOBILE_PLATFORM_SIT_DOWN` | 坐下并固定到移动平台底座 / Sit down and dock to the mobile platform |

---

**三组关键词速记 (Quick keyword reference)**：

| 关键词 / Keyword | 含义 / Meaning |
|---|---|
| `RL_` | 强化学习策略驱动，比固定轨迹更稳健 / RL-policy-driven, more robust than fixed trajectories |
| `_EXT_JOINT_SERVO` | 外部直接指定关节角度（低层控制）/ External direct joint-angle specification (low-level control) |
| `_EXT_PLANNING_MOVE` / `_ONLINE_PLANNING` | 外部指定末端目标，规划器自动算关节（高层控制）/ External end-effector goal, planner computes joints (high-level control) |
| `_POWER_OFF` | 动作完成后自动关电机 / Automatically cut motor power after the action |
| `PASSIVE_UPPER_BODY_` | 下肢固定站立，只控上肢 / Legs hold standing, upper body only |

### 2.4 读取关节状态 (Read Joint State)

```python
def get_joint_state() -> dict:
    result = rpc(
        MC_IP, 56322, "aimdk.protocol.McDataService", "GetJointState",
        {"header": make_header()},
    )
    return result
```

**响应结构（`McJointStatesResponse`）/ Response structure**：
```json
{
    "states": [
        {
            "name": "idx01_left_hip_yaw",
            "sequence": 1234,
            "position": 0.0012,
            "velocity": -0.001,
            "effort": 0.023
        }
    ]
}
```

**每个关节对象的字段 (Fields of each joint object)**：

| 字段 / Field | 单位 / Unit | 含义 / Meaning |
|------|------|------|
| `name` | — | 关节唯一名称 / Unique joint name |
| `sequence` | — | 消息序号，每次更新递增 / Message sequence number, increments each update |
| `position` | rad / m | 当前关节角度或位移 / Current joint angle or displacement |
| `velocity` | rad/s 或 m/s | 当前关节角速度或线速度 / Current joint angular or linear velocity |
| `effort` | N·m / N | 当前输出力矩或力 / Current output torque or force |

> **注意 (Note)**：顶层字段是 `states`（不是 `data.joints`），直接 `result.get("states", [])` 取列表。
>
> *The top-level field is `states` (not `data.joints`); use `result.get("states", [])` to get the list.*

---

## 3. 机器人内部板子与通信架构 (Internal Boards and Communication Architecture)

### 3.1 两块计算板 (Two Compute Boards)

真机内部有两块独立的计算板，通过机器人内部以太网互联，各自暴露不同的 HTTP 服务：

> *The real robot has two independent compute boards connected by an internal Ethernet, each exposing different HTTP services:*

```
┌─────────────────────────────────────────────────────────────┐
│                       你的开发代码 / Your code               │
└───────────────┬─────────────────────────┬───────────────────┘
                │ HTTP RPC                │ HTTP RPC
                ▼                         ▼
┌──────────────────────────┐   ┌──────────────────────────────┐
│     运动控制板（MC）      │   │      导航计算板（NAV）         │
│  Motion Control (MC)     │   │  Navigation (NAV)            │
│   192.168.100.100        │   │   192.168.100.110            │
│                          │   │                              │
│  • 全身关节控制           │   │  • 路径规划 / 导航            │
│    Full-body joint ctrl  │   │    Path planning / navigation│
│  • 动作模式切换           │   │  • 建图 / 定位               │
│    Action mode switching │   │    Mapping / localization    │
│  • 关节状态读取           │   │  • 任务引擎 / Task engine    │
│    Joint state reading   │   │  • TTS 语音合成 / TTS        │
│  • 电池 BMS 监控          │   │  • RGB 灯光 / RGB lights     │
│    Battery BMS monitoring│   │  • 系统状态 / System state   │
└──────────┬───────────────┘   └──────────────┬───────────────┘
           │                                  │
           └──────────── 内部以太网 ───────────┘
                    (Internal Ethernet)
```

**两板分工原则 (Division of responsibility)**：
- **MC 板（.100）**：管"动"——关节、力矩、姿态，一切物理运动 / Handles "motion" — joints, torque, posture, all physical movement
- **NAV 板（.110）**：管"脑"——路径规划、任务调度、语音、感知 / Handles "brain" — path planning, task scheduling, voice, perception

### 3.2 端口与服务速查表 (Port and Service Quick Reference)

**MC 板（`192.168.100.100` / 仿真 `127.0.0.1`）/ MC board**

| 功能 / Function | 端口 / Port | 服务 / Service | 仿真可用 / Sim |
|------|------|------|----------|
| 动作控制 / Action control | 56322 | McActionService | ✓ |
| 运动指令 / Motion commands | 56322 | McMotionService | ✓ |
| 数据读取 / Data reading | 56322 | McDataService | ✓ |
| 电量 BMS / Battery BMS | 56421 | HalBmsService | ✗ |

**NAV 板（`192.168.100.110` / 仿真 `127.0.0.1`）/ NAV board**

| 功能 / Function | 端口 / Port | 服务 / Service | 仿真可用 / Sim |
|------|------|------|----------|
| 系统状态 / System state | 51011 | SystemService | ✗ |
| 建图 / 定位 / Mapping/Localization | 50807 | MappingService / LocalizationService | ✗ |
| 路径规划 / Path planning | 53176 | PncService | ✗ |
| 任务引擎 / Task engine | 57881 | TaskEngineService | ✗ |
| TTS 语音 / TTS | 59301 | TTSService | ✗ |
| RGB 灯光 / RGB lights | 52893 | HalRgbLightService | ✗ |

> 记忆技巧 (Memory tip)：**`.100` 管运动，`.110` 管导航和交互** / `.100` handles motion, `.110` handles navigation and interaction. 仿真只起了 MC 服务，NAV 板的功能在仿真里全部不可用。/ The simulation only starts MC services; all NAV board features are unavailable in simulation.

---

## 4. 实战任务 (Hands-on Tasks)

按顺序完成，每完成一个用 `uv run exercises/phase1_basics.py` 验证：

> *Complete in order, verify each with `uv run exercises/phase1_basics.py`:*

### 任务 1-A：理解输出 (Task 1-A: Understand the Output)
运行练习文件，观察输出。回答：

> *Run the exercise file and observe the output. Answer:*

- 仿真启动后机器人默认动作模式是什么？/ What is the default action mode after simulation starts?
- 有多少个关节？/ How many joints are there?
- 哪些关节的 position 不为 0？/ Which joints have a non-zero position?

### 任务 1-B：手写一个新函数 (Task 1-B: Write a New Function)
在 `phase1_basics.py` 末尾添加一个函数，读取可用动作列表：

> *Add a function at the end of `phase1_basics.py` to read the available action list:*

```python
def get_available_actions() -> list:
    """
    服务: McActionService / Service: McActionService
    接口: GetAvailableActions / Method: GetAvailableActions
    返回所有可用的动作名称列表 / Returns a list of all available action names
    提示: 参考 examples/mc/GetAvailableCommands.py / Hint: see examples/mc/GetAvailableCommands.py
    """
    # 你的代码 / Your code here
    pass
```

验证 (Verify)：打印出所有可用动作，应该能看到 `McAction_RL_LOCOMOTION_DEFAULT` 等。

> *Print all available actions; you should see `McAction_RL_LOCOMOTION_DEFAULT` etc.*

### 任务 1-C：分析关节数据 (Task 1-C: Analyze Joint Data)
扩展 `print_joint_summary`，找出 **position 绝对值最大的 3 个关节**，打印它们的名称和值。

> *Extend `print_joint_summary` to find the **3 joints with the largest absolute position value** and print their names and values.*

提示 (Hint)：
```python
joints = joint_state.get("states", [])
sorted_joints = sorted(joints, key=lambda j: abs(j.get("position", 0)), reverse=True)
```

### 任务 1-D（挑战）：连续监控 (Task 1-D (Challenge): Continuous Monitoring)
写一个循环，每秒读一次关节状态，打印某一个关节的 position 变化。
手动在 tmux 切换动作模式，观察关节值如何变化。

> *Write a loop that reads joint state every second and prints one joint's position change. Manually switch action modes in tmux and observe how the joint values change.*

---

## 5. 常见错误 (Common Errors)

### `ConnectionRefusedError`
```
requests.exceptions.ConnectionRefusedError: [Errno 111] Connection refused
```
**原因 (Cause)**：仿真服务未启动，或 IP 错误。/ Simulation not started, or wrong IP.
**检查 (Check)**：`curl http://127.0.0.1:56322/rpc/aimdk.protocol.McActionService/GetAction -X POST -d '{}'`

### `KeyError: 'info'`
```python
result["info"]["current_action"]  # KeyError: 'info'
```
**原因 (Cause)**：服务还在启动中，返回了空响应。/ Service is still starting up and returned an empty response.
**修复 (Fix)**：用 `.get()` 代替 `[]`，或加重试逻辑。/ Use `.get()` instead of `[]`, or add retry logic.

### `Timeout`
**原因 (Cause)**：网络延迟或服务卡住。/ Network delay or service hung.
**修复 (Fix)**：增大 `timeout` 参数，检查服务是否正常运行。/ Increase the `timeout` parameter and check that the service is running.

---

## 6. 本节要点总结 (Summary)

```
HTTP RPC = POST 请求到固定格式的 URL
         = POST request to a fixed-format URL
请求体   = JSON，有的接口需要 header（时间戳+控制源）
         = JSON body; some interfaces require a header (timestamp + control_source)
响应体   = JSON，用 .get() 安全访问嵌套字段
         = JSON response; use .get() for safe nested access
仿真IP   = 127.0.0.1，真机 MC = 192.168.100.100
Sim IP   = 127.0.0.1, real MC = 192.168.100.100
```

**下一节预告 (Next)**: 学会读状态之后，我们开始**写指令**——控制机器人的头部、手部和步行。

> *Now that you can read state, we start **sending commands** — controlling the robot's head, hands, and walking.*
