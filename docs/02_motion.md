# Phase 2：基础运动控制 — 头部、手部、行走 (Basic Motion Control — Head, Hands, Walking)

> 对应练习文件：`exercises/phase2_motion.py`
> 仿真全部可用 ✓（仿真里可以在 Mujoco 窗口看到机器人真实运动）
>
> *Exercise file: `exercises/phase2_motion.py`*
> *All features available in simulation ✓ (you can see the robot move in the Mujoco window)*

---

## 学习目标 (Learning Objectives)

完成本节后，你能：

> *After completing this section, you will be able to:*

1. 理解动作模式（Action）状态机的概念 / Understand the concept of the action-mode state machine
2. 用 HTTP API 控制颈部和手部关节 / Control neck and hand joints via the HTTP API
3. 用 ROS2 Topic 以 50Hz 发布行走速度指令 / Publish walking velocity commands at 50 Hz via ROS2 Topic
4. 组合成一个完整的"问候序列" / Combine the above into a complete "greeting sequence"

---

## 1. 知识点：动作模式状态机 (Action-Mode State Machine)

### 1.1 为什么需要"模式"？ (Why Do We Need "Modes"?)

机器人的各个模块（行走、臂部规划、动作播放…）会互相竞争控制权。如果同时有多个模块发指令，机器人会不知道听谁的。

> *The robot's various modules (walking, arm planning, action playback…) compete for control. If multiple modules send commands simultaneously, the robot doesn't know which to follow.*

**解决方案 (Solution)**：设计一个全局状态机，机器人在任意时刻只处于一种"模式"，只有对应模式的指令才被执行。

> *Design a global state machine. The robot is always in exactly one "mode" at any moment, and only commands for that mode are executed.*

```
上电 (Power on)
 │
 ▼
ZERO_TORQUE          ← 电机不通电，机器人瘫软 / Motors off, robot limp
 │  SetAction → RL_JOINT_DEFAULT
 ▼
STAND_READY          ← 电机上电，保持站立姿态 / Motors on, holding stand posture
 │  SetAction → RL_LOCOMOTION_DEFAULT
 ▼
RL_LOCOMOTION_DEFAULT  ← 可以行走、接受速度指令 / Can walk, accepts velocity commands ← 最常用 / Most common
 │  SetAction → RL_LOCOMOTION_ARM_EXT_JOINT_SERVO
 ▼
ARM_EXT_JOINT_SERVO    ← 行走 + 手臂关节伺服控制 / Walking + arm joint servo control
```

**`SetAction` 的请求体字段 (Request body fields for `SetAction`)**：

```json
{
    "command": {
        "action": "McAction_USE_EXT_CMD",
        "ext_action": "McAction_RL_LOCOMOTION_DEFAULT"
    }
}
```

| 字段 / Field | 含义 / Meaning |
|------|------|
| `command.action` | 固定填 `"McAction_USE_EXT_CMD"` / Always set to `"McAction_USE_EXT_CMD"` |
| `command.ext_action` | 实际目标模式名称 / The actual target mode name |

两个字段的设计原因：`action` 是一个枚举（内部模式），`McAction_USE_EXT_CMD` 是其中一个值，意思是"把控制权交给外部命令"。`ext_action` 才是真正的目标。这是一种两层间接设计，让外部控制和内部模式保持分离。

> *Reason for two fields: `action` is an internal mode enum; `McAction_USE_EXT_CMD` is one value meaning "delegate control to an external command." `ext_action` is the real target. This two-level indirection keeps external control separate from internal mode.*

**关键理解 (Key insight)**：`SetAction` 是一个**异步请求**。你发完指令后，机器人需要时间完成切换（有时候需要几秒）。所以你需要轮询 `GetAction` 来确认切换完成：

> *`SetAction` is an **asynchronous request**. The robot needs time to complete the transition (sometimes several seconds). You must poll `GetAction` to confirm the switch is done:*

```python
def wait_for_action(target: str, timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if get_action() == target:
            return True      # 切换完成 / Transition complete
        time.sleep(0.5)
    return False             # 超时 / Timed out
```

### 1.2 仿真里的初始状态 (Initial State in Simulation)

仿真启动后，机器人默认是 `ZERO_TORQUE`（倒在地上）。你需要：

> *After the simulation starts, the robot defaults to `ZERO_TORQUE` (lying on the ground). You need to:*

1. `SetAction → RL_JOINT_DEFAULT`（先站起来 / First, stand up）
2. 等待仿真里机器人站稳 / Wait for the robot to stabilize in simulation
3. `SetAction → RL_LOCOMOTION_DEFAULT`（切换到行走模式 / Switch to walking mode）

---

## 2. 知识点：关节控制基础 (Joint Control Basics)

### 2.1 关节坐标系 (Joint Coordinate Frame)

机器人身体定义了一个坐标系：

> *The robot body defines a coordinate frame:*

```
        Z（上 / up）
        │
        │
        └────── X（前 / forward）
       /
      Y（左 / left）
```

关节的旋转轴（Pitch / Roll / Yaw）含义 (Rotation axis meanings):

| 轴 / Axis | 旋转平面 / Rotation plane | 头部举例 / Head example |
|----|---------|---------|
| Pitch | X-Z 平面（前后）/ XZ plane (fore-aft) | 点头（低头/抬头）/ Nodding (down/up) |
| Roll | Y-Z 平面（左右倾）/ YZ plane (side tilt) | 侧头 / Head tilt |
| Yaw | X-Y 平面（水平转）/ XY plane (horizontal) | 摇头（左右转）/ Head turn (left/right) |

### 2.2 颈部关节参数 (Neck Joint Parameters)

`SetNeckCommand` 的请求体（对应 proto `NeckCommandRequest`）/ Request body for `SetNeckCommand`：

```json
{
    "header": { "..." : "..." },
    "data": {
        "shake": {
            "name": "idx27_head_joint1",
            "position": 0.0,
            "velocity": 0.0,
            "effort": 0.0
        },
        "nod": {
            "name": "idx28_head_joint2",
            "position": 0.0,
            "velocity": 0.0,
            "effort": 0.0
        }
    }
}
```

**`data` 的字段 (Fields in `data`)**：

| 字段 / Field | 关节 / Joint | 旋转方向 / Rotation direction |
|------|------|---------|
| `shake` | `idx27_head_joint1` | 左右摇头（Yaw 轴），范围约 [-0.6, 0.6] rad / Head yaw (left/right), range ~[-0.6, 0.6] rad |
| `nod` | `idx28_head_joint2` | 上下点头（Pitch 轴），范围约 [-0.3, 0.5] rad（负=抬头，正=低头）/ Head pitch (up/down), range ~[-0.3, 0.5] rad (negative=up, positive=down) |

**每个关节对象的字段（`JointCommand`）/ Fields of each joint object**：

| 字段 / Field | 单位 / Unit | 含义 / Meaning |
|------|------|------|
| `name` | — | 关节名称，必须与硬件名称完全一致 / Joint name, must exactly match the hardware name |
| `position` | rad | 目标位置，控制器会规划运动到这里 / Target position; the controller plans motion toward this |
| `velocity` | rad/s | 目标速度，通常设 `0.0` / Target velocity; usually set to `0.0` |
| `effort` | N·m | 目标力矩，通常设 `0.0` / Target torque; usually set to `0.0` |

**单位 (Units)**：弧度（rad）。转换公式 (Conversion formula):

```
度数 → 弧度：  rad = deg × π / 180
弧度 → 度数：  deg = rad × 180 / π
Degrees to radians:  rad = deg × π / 180
Radians to degrees:  deg = rad × 180 / π
```

常用对照 (Common values):

| 度数 / Degrees | 弧度 / Radians |
|------|------|
| 30°  | π/6 ≈ 0.524 |
| 45°  | π/4 ≈ 0.785 |
| 90°  | π/2 ≈ 1.571 |
| 180° | π ≈ 3.142 |
| 360° | 2π ≈ 6.283 |

### 2.3 手部关节参数 (Hand Joint Parameters)

手部比颈部复杂，有 6 个自由度（每只手 6 个手指关节）：

> *The hand is more complex than the neck, with 6 degrees of freedom (6 finger joints per hand):*

`SetHandCommand` 的 `data` 字段 / The `data` field for `SetHandCommand`:

```json
{
    "left": {
        "agi_hand": {
            "finger": {
                "pos": {
                    "thumb_pos_0": 0,
                    "thumb_pos_1": 0,
                    "index_pos": 0,
                    "middle_pos": 0,
                    "ring_pos": 0,
                    "pinky_pos": 0
                },
                "toq": {
                    "thumb_toq_0": 0,
                    "thumb_toq_1": 0,
                    "index_toq": 0,
                    "middle_toq": 0,
                    "ring_toq": 0,
                    "pinky_toq": 0
                }
            }
        }
    },
    "right": { "..." : "..." }
}
```

**`pos` 的字段（位置，整数 0~2000）/ `pos` fields (position, integer 0–2000)**：

| 字段 / Field | 手指 / Finger | 0 | 2000 |
|------|------|---|------|
| `thumb_pos_0` | 拇指基节 / Thumb proximal | 张开 / Open | 握紧 / Closed |
| `thumb_pos_1` | 拇指末节 / Thumb distal | 张开 / Open | 握紧 / Closed |
| `index_pos` | 食指 / Index | 张开 / Open | 握紧 / Closed |
| `middle_pos` | 中指 / Middle | 张开 / Open | 握紧 / Closed |
| `ring_pos` | 无名指 / Ring | 张开 / Open | 握紧 / Closed |
| `pinky_pos` | 小指 / Pinky | 张开 / Open | 握紧 / Closed |

**`toq` 的字段 (The `toq` fields)**：对应各手指的力矩限制，通常全部设 `0`（使用默认力矩）。

> *Torque limits per finger; usually all set to `0` (use default torque).*

**范围 (Range)**：0（张开 / open）~ 2000（完全握紧 / fully closed）。

常用姿势 (Common hand poses)：
```python
OPEN   = [0, 0, 0, 0, 0, 0]                          # 张开 / Open
FIST   = [2000, 2000, 2000, 2000, 2000, 2000]         # 握拳 / Fist
POINT  = [1500, 1500, 0, 2000, 2000, 2000]            # 指向（食指伸出）/ Point (index extended)
PEACE  = [1500, 1500, 0, 0, 2000, 2000]               # 剪刀手 / Peace sign
```

---

## 3. 知识点：ROS2 Topic 发布（行走）(Publishing ROS2 Topics — Walking)

### 3.1 为什么行走用 Topic 而不是 HTTP？ (Why Topic Instead of HTTP for Walking?)

行走需要**持续发送速度指令**（50Hz = 每秒 50 次）。HTTP 是同步的，每次请求都有握手开销，不适合高频场景。ROS2 Topic 是异步发布，开销更小，延迟更低。

> *Walking requires **continuously sending velocity commands** (50 Hz = 50 times per second). HTTP is synchronous with handshake overhead on every request, unsuitable for high-frequency use. ROS2 Topic is asynchronous, lower overhead, lower latency.*

### 3.2 ROS2 发布者的基本结构 (Basic Structure of a ROS2 Publisher)

```python
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSHistoryPolicy, QoSReliabilityPolicy
from ros2_plugin_proto.msg import RosMsgWrapper

class WalkNode(Node):
    def __init__(self):
        super().__init__("walk_node")   # 节点名称（在 ROS2 网络中唯一）/ Node name (unique in ROS2 network)

        qos = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,                   # 消息队列深度 / Message queue depth
            reliability=QoSReliabilityPolicy.BEST_EFFORT,  # 不保证送达（适合实时数据）/ No delivery guarantee (suitable for real-time data)
        )

        self.pub = self.create_publisher(
            RosMsgWrapper,              # 消息类型 / Message type
            "/motion/control/...",      # Topic 名称 / Topic name
            qos,
        )

    def publish_velocity(self, fwd, lat, ang):
        # 构造消息 / Construct message
        msg = RosMsgWrapper()
        msg.serialization_type = "json"   # 用 JSON 序列化 / Use JSON serialization
        cmd = {"data": {"mode": 0, "forward_velocity": fwd, ...}}
        msg.data = [bytes([b]) for b in json.dumps(cmd).encode()]
        self.pub.publish(msg)
```

**`RosMsgWrapper`** 是 SDK 的统一消息封装格式。它把不同格式的消息（JSON 或 Protobuf）都包在同一个 ROS2 消息类型里，这样 SDK 只需要定义一种 ROS2 消息类型就够了。

> *`RosMsgWrapper` is the SDK's unified message wrapper. It encapsulates messages in different formats (JSON or Protobuf) inside a single ROS2 message type, so the SDK only needs to define one ROS2 message type.*

### 3.3 QoS 参数理解 (Understanding QoS Parameters)

QoS（Quality of Service）定义消息传递策略 / QoS (Quality of Service) defines the message-delivery policy:

| 参数 / Parameter | 选项 / Options | 行走场景 / Walking scenario |
|------|------|---------|
| `reliability` | RELIABLE（保证送达 / guaranteed）/ BEST_EFFORT（尽力而为 / best effort）| BEST_EFFORT（实时性优先，丢包没关系 / Prioritize real-time; packet loss is fine）|
| `history` | KEEP_LAST / KEEP_ALL | KEEP_LAST（只保留最近 N 条 / Keep only the last N messages）|
| `depth` | 整数 / Integer | 10（队列深度 / Queue depth）|

**规律 (Rule)**：实时控制用 BEST_EFFORT，状态通知用 RELIABLE。

> *Real-time control uses BEST_EFFORT; state notifications use RELIABLE.*

### 3.4 行走指令格式 (Walking Command Format)

```python
{
    "data": {
        "mode": 0,                  # 0=速度控制模式 / 0 = velocity control mode
        "forward_velocity": 0.15,   # 前进速度 m/s（正=前，负=后，范围约 ±0.5）/ Forward speed m/s (positive=forward, negative=backward, ~±0.5)
        "lateral_velocity": 0.0,    # 侧移速度 m/s（正=左，负=右）/ Lateral speed m/s (positive=left, negative=right)
        "angular_velocity": 0.0,    # 转向角速度 rad/s（正=左转，负=右转）/ Angular speed rad/s (positive=left turn, negative=right turn)
    }
}
```

安全建议 (Safety tip)：初次测试用小速度，`forward_velocity: 0.1`（约 1/3 正常步速）。

> *Use a low speed for initial testing: `forward_velocity: 0.1` (approximately 1/3 of normal walking speed).*

---

## 4. 代码详解：`phase2_motion.py` (Code Walkthrough)

### 4.1 `nod_sequence()` 点头序列 (Nod Sequence)

```python
def nod_sequence():
    set_neck(nod_pos=0.4)    # 低头（正值）/ Nod down (positive value)
    time.sleep(0.5)          # 等待关节到位（没有反馈，用时间估算）/ Wait for joint to reach position (no feedback, estimated by time)
    set_neck(nod_pos=-0.1)   # 微抬头 / Slight head raise
    time.sleep(0.5)
    set_neck(nod_pos=0.4)    # 再低头 / Nod down again
    time.sleep(0.5)
    set_neck(nod_pos=0.0)    # 归位 / Return to neutral
```

**注意 (Note)**：`SetNeckCommand` 没有"完成回调"，机器人会以自身速度去到目标位置。`time.sleep()` 是估算关节运动时间，实际工程中可以查询关节状态来精确等待。

> *`SetNeckCommand` has no "completion callback" — the robot moves to the target at its own pace. `time.sleep()` estimates the motion time; in real engineering you can poll joint state for precise waiting.*

### 4.2 `walk_for_seconds()` 行走 (Walking)

```python
def walk_for_seconds(forward_vel, lateral_vel, angular_vel, duration):
    rclpy.init()
    node = WalkNode()
    deadline = time.time() + duration

    while time.time() < deadline:
        node.publish_velocity(forward_vel, lateral_vel, angular_vel)
        time.sleep(0.02)        # 1/50 秒 = 50Hz

    node.publish_velocity(0.0, 0.0, 0.0)  # ← 重要：停止指令 / Important: stop command
    time.sleep(0.1)
    node.destroy_node()
    rclpy.shutdown()
```

**重要细节 (Important detail)**：行走结束时必须发一条速度全为 0 的指令。如果程序崩溃没有发停止指令，机器人会继续按最后一条指令行走。

> *Always send an all-zero velocity command when walking ends. If the program crashes without sending a stop command, the robot continues executing the last command.*

---

## 5. 实战任务 (Hands-on Tasks)

### 任务 2-A：验证仿真 (Task 2-A: Verify in Simulation)

Phase 2 包含 ROS2 Topic（行走部分），需要在仿真容器内运行：

> *Phase 2 includes ROS2 Topics (for walking) and must run inside the simulation container:*

```bash
# 1. 启动容器（首次或重建时）/ Start container (first time or rebuild)
cd /home/sucre/Code/robot/sim
./start_sim.sh

# 2. 进入容器并启动仿真服务 / Enter container and start simulation services
./enter_and_start.sh
```

在 tmux dev 窗口（窗口 3）执行 (Run in the tmux dev window, window 3):
```bash
export ROBOT_TARGET=sim
python3 /home/sucre/Code/robot/exercises/phase2_motion.py
```

观察 Mujoco 窗口里机器人是否做出相应动作。

> *Observe whether the robot performs the corresponding actions in the Mujoco window.*

### 任务 2-B：自定义手势 (Task 2-B: Custom Hand Gestures)
在文件末尾实现一个 `rock_paper_scissors()` 函数，让机器人依次做出：

> *Implement a `rock_paper_scissors()` function at the end of the file to make the robot show:*

- 石头（握拳）→ 等 1 秒 → 剪刀（食中指伸出）→ 等 1 秒 → 布（张开）
- Rock (fist) → wait 1 s → Scissors (index+middle extended) → wait 1 s → Paper (open)

提示 (Hint)：修改 `OPEN / FIST / POINT` 这类预设数组。

> *Modify preset arrays like `OPEN / FIST / POINT`.*

### 任务 2-C：转圈 (Task 2-C: Walk in a Circle)
实现 `walk_in_circle(radius, speed, duration)`：

> *Implement `walk_in_circle(radius, speed, duration)`:*

- 机器人走一个近似的圆形路径 / The robot walks an approximate circular path
- 提示 (Hint)：圆周运动 = 同时有 forward_velocity 和 angular_velocity / Circular motion = simultaneous forward_velocity and angular_velocity

半径 `r`，线速度 `v`，则角速度 `ω = v / r`（rad/s）。

> *With radius `r` and linear speed `v`, angular velocity `ω = v / r` (rad/s).*

### 任务 2-D：安全包装（挑战）(Task 2-D: Safety Wrapper (Challenge))
给 `set_neck()` 加一个参数校验：如果 `shake` 超出 `[-0.6, 0.6]` 或 `nod` 超出 `[-0.3, 0.5]`，不发送指令并打印警告。

> *Add parameter validation to `set_neck()`: if `shake` is outside `[-0.6, 0.6]` or `nod` is outside `[-0.3, 0.5]`, do not send the command and print a warning.*

---

## 6. 安全注意事项 (Safety Notes)

> 以下注意事项在真机上**非常重要**，仿真里不会损坏硬件但养成好习惯很必要。
>
> *The following are **critical** on the real robot. You won't damage hardware in simulation, but forming good habits matters.*

1. **切换动作模式前确认状态 (Confirm state before switching modes)**：从 `ZERO_TORQUE` 跳到 `RL_LOCOMOTION_DEFAULT` 会让机器人突然弹起，容易摔倒。应该按顺序切换。/ Jumping from `ZERO_TORQUE` directly to `RL_LOCOMOTION_DEFAULT` causes the robot to spring up suddenly and may fall. Switch step by step.

2. **行走时确保周围有足够空间 (Ensure sufficient clearance)**：至少 1.5 米净空。/ At least 1.5 m of clear space.

3. **始终发送停止指令 (Always send a stop command)**：用 `try/finally` 保证即使程序异常也能停止 / Use `try/finally` to guarantee a stop even if the program crashes:
   ```python
   try:
       walk_for_seconds(0.1, 0, 0, 3.0)
   finally:
       node.publish_velocity(0, 0, 0)   # 无论如何都停止 / Stop no matter what
   ```

4. **速度值从小开始 (Start with low speeds)**：`0.1 m/s` 开始，稳定后再增大。/ Start at `0.1 m/s`, increase only after the robot is stable.

---

## 7. 本节要点总结 (Summary)

```
动作模式 = 全局状态机，只有当前模式下的指令才被执行
Action mode = global state machine; only commands for the current mode are executed

SetAction = 异步，要轮询 GetAction 等待切换完成
SetAction = async; poll GetAction to wait for the transition

颈部控制 = position 单位是弧度，velocity/effort 设 0 即可
Neck control = position in radians; set velocity/effort to 0

手部控制 = 0~2000 整数范围，0 张开，2000 握紧
Hand control = integer range 0–2000; 0 = open, 2000 = closed

行走指令 = ROS2 Topic，50Hz 持续发布，结束时发停止指令
Walking = ROS2 Topic, publish at 50 Hz, send a stop command when done
```

**下一节预告 (Next)**: 机器人能动了，现在让它去一个**预定的地点**——导航系统。

> *Now that the robot can move, let's send it to a **specific location** — navigation.*

---

## 8. 扩展：多台机器人的键盘控制 (Extension: Keyboard Control for Multiple Robots)

`keyboard_control()` 已经支持多机器人，方法有两种：

> *`keyboard_control()` already supports multiple robots via two approaches:*

**方案一：多终端（推荐）/ Option 1: Multiple terminals (recommended)**

每台机器人开一个终端，指定 `ROBOT_ID` 和 `ROS_DOMAIN_ID`：

> *Open one terminal per robot, specifying `ROBOT_ID` and `ROS_DOMAIN_ID`:*

```bash
# 终端 A / Terminal A — Robot 0
ROBOT_ID=0 ROS_DOMAIN_ID=0 python3 exercises/phase2_motion.py keyboard

# 终端 B / Terminal B — Robot 1
ROBOT_ID=1 ROS_DOMAIN_ID=1 python3 exercises/phase2_motion.py keyboard
```

两个终端完全独立，WASD 行走、模式切换、起立蹲下全部正常。适合双人对抗或分工合作场景。

> *The two terminals are fully independent — WASD walking, mode switching, stand/sit all work normally. Suitable for two-player or cooperative scenarios.*

**方案二：单键盘 Tab 切换 / Option 2: Single keyboard with Tab switching**

```bash
python3 exercises/multi_robot.py keyboard
```

按 **Tab** 循环切换目标机器人，其余键位与单机模式相同。行走键通过子进程实现 ROS2 域隔离。详见 `docs/06_multi_robot.md` 第 5 节。

> *Press **Tab** to cycle through target robots; all other keys work the same as single-robot mode. Walking keys use subprocesses for ROS2 domain isolation. See `docs/06_multi_robot.md` section 5 for details.*
