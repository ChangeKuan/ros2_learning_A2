# Phase 6：多机器人仿真与协同控制 (Multi-Robot Simulation and Coordinated Control)

> 对应代码：`exercises/multi_robot.py`、`sim/start_multi_sim.sh`
> 前提：完成 Phase 2（运动控制）
>
> *Code: `exercises/multi_robot.py`, `sim/start_multi_sim.sh`*
> *Prerequisite: Complete Phase 2 (Motion Control)*

---

## 学习目标 (Learning Objectives)

完成本节后，你能：

> *After completing this section, you will be able to:*

1. 理解为什么一台仿真容器只能跑一台机器人 / Explain why one simulation container can only run one robot
2. 用多容器方案同时运行 N 台机器人 / Use a multi-container approach to run N robots simultaneously
3. 用 Python 并行、顺序、波浪式控制多台机器人 / Control multiple robots in parallel, sequential, and wave patterns with Python
4. 用单键盘（Tab 切换）或多终端控制多台机器人行走 / Control multiple robots walking with a single keyboard (Tab switching) or multiple terminals

---

## 1. 为什么「一个场景」里跑不了多台机器人？ (Why Can't Multiple Robots Run in One Scene?)

当前 SDK 架构的三个硬约束：

> *Three hard constraints in the current SDK architecture:*

| 层 / Layer | 问题 / Problem |
|---|---|
| **Iceoryx 共享内存 / Iceoryx shared memory** | Topic 名没有机器人命名空间，两台机器人的 MC 会互相干扰 / Topic names have no robot namespace; two robots' MCs interfere with each other |
| **MC 二进制 / MC binary** | 内部只认一套关节名（`idx01_left_hip_roll`…），无法区分机体 / Internally recognizes only one set of joint names; can't distinguish multiple bodies |
| **Mujoco 插件 / Mujoco plugin** | 一个 `aimrt_main` 进程对应一套关节绑定，无法绑定两套 / One `aimrt_main` process maps to one set of joint bindings; can't bind two |

**结论 (Conclusion)**：在不修改闭源 SDK 的前提下，无法在同一物理场景里运行多台机器人。

> *Without modifying the closed-source SDK, it's impossible to run multiple robots in the same physical scene.*

---

## 2. 可行方案：多容器隔离 (Workable Solution: Multi-Container Isolation)

每台机器人运行在**独立 Docker 容器**里：

> *Each robot runs in its own **independent Docker container**:*

```
宿主机 (Host)
 ├── a2-sim-0  [Robot 0]  MC端口 56322  ROS_DOMAIN 0
 │     ├── Mujoco仿真引擎  ──(Iceoryx)──  MC服务  ──(HTTP)──> 宿主机代码
 │     │   Mujoco physics  ──(Iceoryx)──  MC svc  ──(HTTP)──> Host code
 │     └── iox-roudi（独立 / isolated）
 └── a2-sim-1  [Robot 1]  MC端口 56323  ROS_DOMAIN 1
       ├── Mujoco仿真引擎  ──(Iceoryx)──  MC服务  ──(HTTP)──> 宿主机代码
       │   Mujoco physics  ──(Iceoryx)──  MC svc  ──(HTTP)──> Host code
       └── iox-roudi（独立 / isolated）
```

**隔离机制对比 (Isolation mechanism comparison)**：

| 机制 / Mechanism | 单机器人 `start_sim.sh` | 多机器人 `start_multi_sim.sh` |
|---|---|---|
| IPC（Iceoryx）| `--ipc=host`（共享主机 IPC / shares host IPC）| 不加 → 每容器独立 iox-roudi / Not set → each container has its own iox-roudi |
| PID | `--pid=host` | 不加 → 每容器独立进程树 / Not set → each container has its own process tree |
| 网络 / Network | `--net=host` | 保留 → HTTP/ROS2 可从宿主机直接访问 / Kept → HTTP/ROS2 accessible from host |
| MC HTTP 端口 / Port | 固定 56322 / Fixed 56322 | sed 补丁配置，56322 + N / Patched with sed, 56322 + N |
| ROS2 DDS 域 / Domain | 共享 / Shared | `ROS_DOMAIN_ID=N` 隔离 / Isolated |

---

## 3. 快速开始 (Quick Start)

### 3.1 启动多台机器人 (Start Multiple Robots)

```bash
cd /home/sucre/Code/robot/sim

# 启动 2 台（默认）/ Start 2 robots (default)
./start_multi_sim.sh

# 启动 3 台 / Start 3 robots
./start_multi_sim.sh 3

# GPU 加速 / GPU acceleration
./start_multi_sim.sh 2 --gpu
```

启动后会打印 (Output after starting)：

```
  Robot 0  MC=127.0.0.1:56322  ROS_DOMAIN=0
  Robot 1  MC=127.0.0.1:56323  ROS_DOMAIN=1
```

每台机器人各有一个 Mujoco 窗口，等待约 15 秒自动站立。

> *Each robot has its own Mujoco window; wait ~15 seconds for them to stand automatically.*

### 3.2 停止所有机器人 (Stop All Robots)

```bash
docker rm -f $(docker ps -aq --filter 'name=a2-sim-')
```

### 3.3 进入某台机器人的终端 (Access a Robot's Terminal)

```bash
docker exec -it a2-sim-0 bash
tmux attach -t a2sim-r0          # 查看各服务日志 / View service logs
```

---

## 4. Python API：`multi_robot.py` (Python API)

### 4.1 Robot 类 (The Robot Class)

```python
from multi_robot import Robot

r0 = Robot(robot_id=0)   # 连接到 127.0.0.1:56322 / Connects to 127.0.0.1:56322
r1 = Robot(robot_id=1)   # 连接到 127.0.0.1:56323 / Connects to 127.0.0.1:56323

r0.set_action("McAction_RL_LOCOMOTION_DEFAULT")
r1.set_neck(nod=0.4)
```

所有方法均通过 HTTP RPC，无需 ROS2 域配置：

> *All methods use HTTP RPC; no ROS2 domain configuration needed:*

| 方法 / Method | 说明 / Description |
|---|---|
| `robot.ping()` | 检查是否在线 / Check if online |
| `robot.set_action(name)` | 切换动作模式 / Switch action mode |
| `robot.get_action()` | 查询当前模式 / Query current mode |
| `robot.set_neck(shake, nod)` | 控制颈部 / Control neck |

### 4.2 多机编排工具 (Multi-Robot Orchestration Tools)

```python
from multi_robot import wait_ready, parallel

robots = [Robot(i) for i in range(3)]

# 等待所有机器人就绪 / Wait for all robots to be ready
online = wait_ready(robots, timeout=30.0)

# 并行执行：所有机器人同时点头 / Parallel: all robots nod at the same time
parallel(online, lambda r: r.set_neck(nod=0.4))

# 顺序执行：依次点头（普通 for 循环即可）/ Sequential: nod one by one (plain for loop)
for robot in online:
    robot.set_neck(nod=0.4)
    time.sleep(0.5)
    robot.set_neck(nod=0.0)
```

### 4.3 运行演示 (Run Demo)

```bash
# 动作演示（同步点头、接力点头、波浪摇头）/ Action demo (sync nod, relay nod, wave shake)
python3 exercises/multi_robot.py

# 3 台 / 3 robots
NUM_ROBOTS=3 python3 exercises/multi_robot.py
```

---

## 5. 键盘控制多台机器人 (Keyboard Control of Multiple Robots)

### 5.1 方案一：多终端，每台机器人独立键盘 (Option 1: Multiple Terminals, Independent Keyboards)

最简单的方式。为每台机器人开一个终端窗口，各自用 `ROBOT_ID` 和 `ROS_DOMAIN_ID` 指定目标：

> *The simplest approach. Open one terminal per robot, specifying `ROBOT_ID` and `ROS_DOMAIN_ID`:*

```bash
# 终端 A — 控制 Robot 0 / Terminal A — Control Robot 0
ROBOT_ID=0 ROS_DOMAIN_ID=0 python3 exercises/phase2_motion.py keyboard

# 终端 B — 控制 Robot 1 / Terminal B — Control Robot 1
ROBOT_ID=1 ROS_DOMAIN_ID=1 python3 exercises/phase2_motion.py keyboard
```

两个终端互相独立，操作互不干扰。适合双人对抗或分工合作场景。

> *The two terminals are fully independent. Suitable for two-player competition or cooperative scenarios.*

### 5.2 方案二：单键盘，Tab 键切换目标机器人 (Option 2: Single Keyboard, Tab to Switch Robots)

```bash
python3 exercises/multi_robot.py keyboard
# 或指定台数 / Or specify number of robots
NUM_ROBOTS=3 python3 exercises/multi_robot.py keyboard
```

**键位布局 (Key layout)**：

```
Tab      → 循环切换目标机器人（屏幕底部高亮显示当前目标）
           Cycle through target robots (current target highlighted at screen bottom)
W/S/A/D  → 前/后/左移/右移 / Forward/backward/left/right
←/→      → 左转/右转 / Turn left/turn right
空格/Space → 停止行走 / Stop walking
↑/↓      → 起立/蹲下 / Stand up/sit down
1~6      → 切换动作模式 / Switch action modes
0        → 默认模式 / Default mode
q/ESC    → 退出 / Quit
b        → 切换「单选」/「广播全体」模式 / Toggle "single robot" / "broadcast all" mode
```

**状态栏示例（2 台机器人，当前选中 Robot 1）/ Status bar example (2 robots, Robot 1 selected)**：

```
 R0:56322   【R1:56323】  | Tab切换 · q退出
```

---

## 6. 知识点：行走指令与 ROS2 域隔离 (Walking Commands and ROS2 Domain Isolation)

### 6.1 为什么行走（WASD）比较特殊？ (Why is Walking (WASD) Special?)

行走速度指令通过 **ROS2 Topic** 以 50Hz 持续发布（详见 Phase 2 第 3 节）。ROS2 的 DDS 协议通过 **Domain ID** 隔离网络：

> *Walking velocity commands are published continuously at 50 Hz via **ROS2 Topic** (see Phase 2 section 3). ROS2's DDS protocol isolates networks via **Domain ID**:*

```
ROS_DOMAIN_ID=0  →  Robot 0 的 MC 能收到 / Robot 0's MC receives
ROS_DOMAIN_ID=1  →  Robot 1 的 MC 能收到 / Robot 1's MC receives
```

一个 Python 进程里 `rclpy.init()` 只能调用一次，固定住一个 Domain。所以**单进程只能 walk 一台机器人**。

> *`rclpy.init()` can only be called once per Python process, locking in one Domain. So a **single process can only walk one robot**.*

### 6.2 `multi_keyboard_control()` 如何解决？ (How Does `multi_keyboard_control()` Solve This?)

每次按下行走键，`multi_keyboard_control()` 在后台启动一个**子进程**：

> *Every time a walking key is pressed, `multi_keyboard_control()` spawns a **subprocess**:*

```python
env['ROS_DOMAIN_ID'] = str(robot.robot_id)   # 设置正确的域 / Set the correct domain
subprocess.Popen(
    ['bash', '-c', script],
    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
```

子进程持续发布 `KEY_TIMEOUT` 秒的速度指令，然后自动发送停止指令退出。主进程无需阻塞，可以继续响应下一个按键。

> *The subprocess continuously publishes velocity commands for `KEY_TIMEOUT` seconds, then sends a stop command and exits. The main process doesn't block and can respond to the next key immediately.*

**时序示意 (Timing diagram)**：

```
主进程 (Main process)      子进程（Robot 1 行走 0.4s）/ Subprocess (Robot 1 walk 0.4s)
  │                    │
  ├─ 按 W / Press W ── spawn_walk()
  │                    ├─ 发布 forward 0.2 m/s / Publish forward 0.2 m/s
  │                    ├─ 发布 forward 0.2 m/s  (50Hz)
  ├─ 按 Tab           ├─ ...
  │  (切换 Robot 0 / Switch to Robot 0)    ├─ 0.4s 后发布 0,0,0（停止）/ Publish 0,0,0 after 0.4s
  ├─ 按 W / Press W ── spawn_walk() 对 Robot 0 / for Robot 0
  │                    └─ 退出 / Exit
```

**注意 (Note)**：行走子进程需要 `rclpy` 和 `ros2_plugin_proto` 在当前 Python 环境中可导入。如果这些包未安装，行走键会静默失效（其他键位仍正常）。在仿真容器内运行时需先 source：

> *The walk subprocess requires `rclpy` and `ros2_plugin_proto` to be importable in the current Python environment. If these packages are not installed, walking keys silently fail (other keys still work). When running inside the simulation container, source first:*

```bash
source /home/agi/a2_simulation/ros2_plugin_proto_x86_64/share/ros2_plugin_proto/local_setup.bash
```

---

## 7. 实战任务 (Hands-on Tasks)

### 任务 6-A：两台机器人握手 (Task 6-A: Two Robots Shake Hands)

实现 `handshake(robot_a, robot_b)` 函数：

> *Implement a `handshake(robot_a, robot_b)` function:*

- Robot A 伸出右手（右手食指/中指伸出）/ Robot A extends its right hand (index + middle fingers out)
- Robot B 同步伸出左手（左手同样姿态）/ Robot B simultaneously extends its left hand (same gesture)
- 保持 2 秒 / Hold for 2 seconds
- 两台同时收回 / Both retract simultaneously

提示 (Hint)：用 `parallel()` + `robot.set_hand()` 实现（参考 `phase2_motion.py` 的 `set_hand`）。

> *Use `parallel()` + `robot.set_hand()` (see `set_hand` in `phase2_motion.py`).*

### 任务 6-B：多机问候序列 (Task 6-B: Multi-Robot Greeting Sequence)

实现 `relay_greeting(robots)` 函数，让 N 台机器人按顺序依次：

> *Implement `relay_greeting(robots)` to have N robots, one after another:*

1. 点头 / Nod
2. 挥手（右手）/ Wave (right hand)
3. 前行 1 步 / Step forward

要求：每台机器人的问候开始时，上一台机器人刚好完成挥手（时间衔接紧凑）。

> *Requirement: each robot's greeting starts just as the previous robot finishes waving (tight timing).*

### 任务 6-C：跟随控制（挑战）/ Task 6-C: Follow Control (Challenge)

Robot 0 是"领头"，Robot 1 是"跟随"。用键盘控制 Robot 0 运动，同时：

> *Robot 0 is the "leader," Robot 1 is the "follower." Control Robot 0 with the keyboard, while:*

- 延迟 1 秒后，Robot 1 执行完全相同的动作序列 / After a 1-second delay, Robot 1 performs the identical action sequence

提示 (Hint)：录制 Robot 0 的速度指令队列，延迟回放给 Robot 1。

> *Record Robot 0's velocity command queue and replay it to Robot 1 with a delay.*

---

## 8. 本节要点总结 (Summary)

```
多机器人仿真 = 多个独立容器，每容器一套 Mujoco + MC
Multi-robot sim = multiple independent containers, each with its own Mujoco + MC

IPC 隔离     = 不加 --ipc=host，各容器 iox-roudi 互不干扰
IPC isolation = omit --ipc=host; each container's iox-roudi is independent

ROS2 隔离    = ROS_DOMAIN_ID=N，避免话题串扰
ROS2 isolation = ROS_DOMAIN_ID=N, avoids topic cross-talk

HTTP 控制    = 端口 56322+N，直接从宿主机访问，无需进入容器
HTTP control = port 56322+N, accessible from host without entering container

键盘控制     = 多终端（推荐）或 单终端 Tab 切换（行走用子进程）
Keyboard control = multiple terminals (recommended) or single terminal Tab switching (walking via subprocesses)
```
