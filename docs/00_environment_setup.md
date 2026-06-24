# 环境配置指南 (Environment Setup Guide)

> 目标：搞清楚整个开发环境由哪些部分组成，把仿真跑起来。
>
> *Goal: Understand what the development environment consists of and get the simulator running.*

---

## 0. 在新机器上恢复项目 (Restore Project on a New Machine)

如果你在新机器上继续 AI coding，按以下步骤恢复完整环境（包括 Claude 的记忆上下文）。

> *If you're continuing AI coding on a new machine, follow these steps to restore the full environment (including Claude's memory context).*

### 0.1 克隆代码 (Clone the Repository)

```bash
git clone git@github.com:ChangeKuan/ros2_learning_A2.git
cd ros2_learning_A2
```

> 需要先把本机 SSH 公钥添加到 GitHub：[github.com/settings/keys](https://github.com/settings/keys)
>
> *You need to add your machine's SSH public key to GitHub first: [github.com/settings/keys](https://github.com/settings/keys)*

### 0.2 恢复 Claude AI 记忆 (Restore Claude AI Memory)

Memory 文件已经存放在仓库的 `.claude/memory/` 目录里。把它们复制到 Claude Code 读取的位置：

> *Memory files are stored in `.claude/memory/` inside the repo. Copy them to where Claude Code reads them:*

```bash
# 确认当前目录是项目根目录 / Make sure you're in the project root
# 根据你的用户名调整路径 / Adjust the path to match your username
PROJECT_PATH=$(pwd | sed 's|/|-|g' | sed 's|^-||')
MEMORY_DIR=~/.claude/projects/${PROJECT_PATH}/memory

mkdir -p "$MEMORY_DIR"
cp .claude/memory/* "$MEMORY_DIR/"
echo "Memory restored to $MEMORY_DIR"
```

完成后用 Claude Code 打开项目，AI 会自动加载项目背景（SDK 架构、端口表、双语要求等）。

> *After this, open the project with Claude Code and the AI will automatically load the project context (SDK architecture, port table, bilingual requirement, etc.).*

### 0.3 验证 (Verify)

```bash
ls ~/.claude/projects/$(pwd | sed 's|/|-|g' | sed 's|^-||')/memory/
# 应该看到：MEMORY.md  project_robot_sdk.md  feedback_bilingual_requirement.md
# Should show: MEMORY.md  project_robot_sdk.md  feedback_bilingual_requirement.md
```

---

## 1. 整体架构 (System Architecture)

在开始写第一行代码之前，先理解你在和什么打交道。

> *Before writing the first line of code, understand what you're working with.*

```
┌─────────────────────────────────────────────────────────┐
│                    你的开发代码                           │
│               (Your development code)                    │
│  (exercises/*.py  /  projects/reception_robot/*.py)      │
└────────────────────┬────────────────────────────────────┘
                     │  两种通信方式 (Two communication methods)
          ┌──────────┴──────────┐
          ▼                     ▼
   HTTP RPC (requests)    ROS2 Topic (rclpy)
   同步，一问一答           异步，持续订阅/发布
   (Sync, request-reply)  (Async, pub/sub)
          │                     │
          └──────────┬──────────┘
                     ▼
         ┌───────────────────────┐
         │    机器人服务进程      │
         │  (Robot service proc) │
         │  (仿真: Docker 容器)  │
         │  (Sim: Docker)        │
         │  (真机: ORIN 板子)    │
         │  (Real: ORIN board)   │
         └───────────────────────┘
```

**核心要点**：你的代码不直接操作硬件。你通过网络请求发指令给机器人的服务进程，服务进程再控制硬件。这意味着**仿真和真机的代码完全相同**，只是 IP 地址不同。

> *Your code does not directly control the hardware. You send commands via network requests to the robot's service process, which then controls the hardware. This means **simulation and real-robot code are identical** — only the IP address differs.*

---

## 2. 两种通信方式详解 (Communication Methods in Detail)

### 2.1 HTTP RPC

**是什么**：用 HTTP POST 请求调用机器人的服务函数。

> *What it is: Call robot service functions via HTTP POST requests.*

```
你的代码                             机器人服务进程
(Your code)                         (Robot service)
  │                                        │
  │  POST /rpc/aimdk.protocol.McActionService/GetAction
  │  Body: {}                              │
  │ ──────────────────────────────────────>│
  │                                        │ 处理请求 (Processing)
  │  Response: {"info": {"current_action": "McAction_RL_LOCOMOTION_DEFAULT"}}
  │ <──────────────────────────────────────│
```

**格式规律 (URL format)**：
```
http://{IP}:{PORT}/rpc/{包名}.{服务名}/{方法名}
http://{IP}:{PORT}/rpc/{package}.{service}/{method}
```

例如 (Example)：
```
http://127.0.0.1:56322/rpc/aimdk.protocol.McActionService/GetAction
```
- IP: `127.0.0.1`（仿真 / sim）或 `192.168.100.100`（真机 MC / real MC）
- Port: `56322`（运动控制器端口 / motion controller port）
- 服务 / Service: `aimdk.protocol.McActionService`（对应 protobuf 里的 service 定义 / matches service definition in protobuf）
- 方法 / Method: `GetAction`

**适用场景 (Use cases)**：查询状态、发送一次性指令（调用完就结束）。

> *Best for: querying state or sending one-shot commands (fire and forget).*

### 2.2 ROS2 Topic

**是什么**：机器人使用 ROS2（Robot Operating System 2）作为内部消息总线。你通过订阅或发布 Topic 来和机器人持续交互。

> *What it is: The robot uses ROS2 (Robot Operating System 2) as its internal message bus. You interact with the robot continuously by subscribing to or publishing Topics.*

```
                  ROS2 消息总线 (ROS2 message bus)
                       │
      发布方            │            订阅方
  (Publisher)          │          (Subscriber)
  ─────────────        │         ─────────────
  你的代码              │         机器人运动控制
  (Your code)  ───────>│──────>  (Robot motion ctrl)
                        │
  机器人传感器           │         你的代码
  (Robot sensor) ──────>│──────>  (Your code)
```

**适用场景 (Use cases)**：
- **发布 (Publish)**：需要持续发送的指令（如 50Hz 行走速度指令）/ Commands that must be sent continuously (e.g. 50 Hz walking velocity)
- **订阅 (Subscribe)**：持续监听机器人状态（如唤醒词、音频数据、传感器数据）/ Continuously listening to robot state (e.g. wake word, audio, sensor data)

**Topic 命名 (Topic naming)**：SDK 用了一个编码格式来在 ROS2 Topic 名字里嵌入 Protobuf 类型信息：

> *The SDK embeds Protobuf type information into ROS2 Topic names using a URL-encoding scheme:*

```
/motion/control/locomotion_velocity/pb_3Aaimdk_2Eprotocol_2EMcLocomotionVelocityChannel
                                    ↑ 这段是 "aimdk.protocol.McLocomotionVelocityChannel" URL编码后的结果
                                    ↑ This is "aimdk.protocol.McLocomotionVelocityChannel" URL-encoded
```

---

## 3. Protobuf 基础 (Protobuf Basics)

SDK 的消息格式用的是 **Protocol Buffers (protobuf)**，Google 的二进制序列化格式。

> *The SDK uses **Protocol Buffers (protobuf)**, Google's binary serialization format, for all message types.*

你不需要深入学，只需要知道：

> *You don't need to study it in depth — just know the following:*

```python
# 1. 先引入生成好的 Python 类 / Import the pre-generated Python class
from aimdk.protocol_pb2 import WakeUpResult

# 2. 从字节流解析消息 / Parse a message from raw bytes
result = WakeUpResult()
result.ParseFromString(raw_bytes)   # raw_bytes 来自 ROS2 消息的 data 字段 / raw_bytes from ROS2 msg.data

# 3. 访问字段 / Access fields
print(result.wake_word)
```

SDK 已经帮你把 `.proto` 文件编译成了 Python 类，打包在 `a2_aimdk-2.0.0-py3-none-any.whl` 里。

> *The SDK pre-compiles `.proto` files into Python classes, bundled in `a2_aimdk-2.0.0-py3-none-any.whl`.*

---

## 4. 仿真环境搭建 (Setting Up the Simulation)

### 4.1 前置检查 (Prerequisites)

```bash
# 检查 Docker / Check Docker
docker --version          # 需要 Docker 20+ / Requires Docker 20+

# 检查显示环境 / Check display environment
echo $DISPLAY             # 应该输出 :0 或 :1 / Should output :0 or :1
echo $XDG_SESSION_TYPE    # x11 或 wayland / x11 or wayland
```

**Wayland 用户（Fedora/GNOME 默认）**：Mujoco 需要 X11 图形窗口，但不必切换桌面——Wayland 合成器会自动启动 XWayland（`$DISPLAY=:0`）。`start_sim.sh` 已内置处理，直接运行即可。

> *Wayland users (Fedora/GNOME default): Mujoco requires an X11 display window, but you don't need to switch desktops — the Wayland compositor automatically starts XWayland (`$DISPLAY=:0`). `start_sim.sh` handles this internally; just run it directly.*

若 `echo $DISPLAY` 输出为空（罕见），手动补充：

> *If `echo $DISPLAY` outputs nothing (rare), set it manually:*
```bash
export DISPLAY=:0
```

> Fedora 的 SELinux 会拦截 Docker 访问 X11 socket。脚本已在卷挂载上加了 `:z` 标签让 SELinux 自动重标签，无需手动操作。
>
> *Fedora's SELinux will block Docker from accessing the X11 socket. The script adds a `:z` label to volume mounts so SELinux automatically relabels them — no manual action needed.*

### 4.2 拉取仿真镜像 (Pull the Simulation Image)

```bash
cd /home/sucre/Code/robot/sim
./start_sim.sh            # 约 5~10 GB，首次需要等待 / ~5–10 GB, first run takes time
```

**脚本做了什么 (What the script does)**：
1. 登录公开镜像仓库（凭证在脚本里，仓库是公开读取的）/ Logs in to a public registry (credentials in script, public read access)
2. `docker pull` 镜像 / Pulls the image
3. `xhost +local:docker` 允许容器访问你的显示器 / Allows the container to access your display
4. `docker run --net=host` 启动容器，**共享宿主机网络** / Starts the container **sharing the host network**

`--net=host` 是关键：容器里的服务进程直接监听在你的机器上，端口和服务 IP 直接是 `127.0.0.1`。

> *`--net=host` is the key: service processes inside the container listen directly on your machine, making the port and service IP simply `127.0.0.1`.*

### 4.3 启动仿真服务 (Start Simulation Services)

```bash
./enter_and_start.sh      # 进入容器，用 tmux 启动 3 个服务 / Enter container and start 3 services with tmux
```

会自动打开 4 个 tmux 窗口 (Opens 4 tmux windows automatically)：

| 窗口 / Window | 服务 / Service | 作用 / Role |
|------|------|------|
| 0: mujoco | Mujoco 物理引擎 / Physics engine | 3D 仿真可视化，处理物理碰撞 / 3D visualization and physics |
| 1: motion_ctrl | 运动控制服务 / Motion control service | 提供 MC HTTP API（Port 56322）/ Provides MC HTTP API |
| 2: motion_player | 动作播放服务 / Action player service | 播放预录制动作序列 / Plays pre-recorded action sequences |
| 3: dev | 交互终端 / Dev terminal | 在这里运行你的代码 / Run your code here |

**等待约 10 秒**，等服务完全启动后再执行指令。

> *Wait about 10 seconds for services to fully start before issuing commands.*

### 4.4 首次验证 (First Verification)

在开发终端（窗口 3）测试 (Test in the dev terminal, window 3)：

```bash
# 方法 1：用容器内置工具 / Method 1: use built-in container tool
python3 SetAction.py      # 选择 RL_JOINT_DEFAULT / Select RL_JOINT_DEFAULT

# 方法 2：用 curl 直接测试 / Method 2: test directly with curl
curl -s -X POST http://127.0.0.1:56322/rpc/aimdk.protocol.McActionService/GetAction \
     -H 'Content-Type: application/json' \
     -d '{}' | python3 -m json.tool
```

能看到 JSON 响应说明仿真服务正常。

> *A JSON response confirms that the simulation service is running correctly.*

---

## 5. 开发环境（宿主机）(Development Environment on the Host)

使用 [uv](https://docs.astral.sh/uv/) 管理项目虚拟环境，隔离干净且无需手动激活。

> *Use [uv](https://docs.astral.sh/uv/) to manage the project virtual environment — clean isolation with no manual activation needed.*

```bash
# 安装 uv（只需一次）/ Install uv (once only)
pip install --user uv

# 在项目根目录创建虚拟环境并安装依赖 / Create venv and install deps in project root
cd /home/sucre/Code/robot
uv venv
uv pip install agibot_a2_aimdk-dev2.0/prebuilt/a2_aimdk-2.0.0-py3-none-any.whl requests
```

运行练习时用 `uv run`，无需手动激活虚拟环境：

> *Use `uv run` to run exercises — no manual venv activation needed:*

```bash
uv run exercises/phase1_basics.py
```

清理环境只需删除 `.venv/` 目录：

> *To clean up, simply delete the `.venv/` directory:*

```bash
rm -rf .venv
```

**注意 (Note)**：Phase 1 和 Phase 2 的 HTTP 部分（颈部、手部控制）可以在宿主机用 `uv run` 跑。但涉及 ROS2 Topic 的部分（walk、音频订阅等）必须在容器内运行——`start_sim.sh` 已将 `/home/sucre/Code/robot` 挂载进容器，在容器里直接 `python3 /home/sucre/Code/robot/exercises/phase2_motion.py` 即可，代码改动实时生效。

> *Phase 1 and the HTTP parts of Phase 2 (neck and hand control) can run on the host with `uv run`. However, anything involving ROS2 Topics (walking, audio subscriptions, etc.) must run inside the container — `start_sim.sh` already mounts `/home/sucre/Code/robot` into the container, so running `python3 /home/sucre/Code/robot/exercises/phase2_motion.py` inside the container works directly, with live code changes.*

---

## 6. 运行第一个练习 (Running the First Exercise)

确认仿真服务已启动，然后：

> *Confirm the simulation services are running, then:*

```bash
cd /home/sucre/Code/robot

# 仿真模式（默认）/ Simulation mode (default)
export ROBOT_TARGET=sim
uv run exercises/phase1_basics.py
```

预期输出 (Expected output)：
```
[config] 模式=仿真  MC=127.0.0.1  NAV=127.0.0.1
[1] 系统状态:
  [仿真] SystemService 不可用，跳过
[2] 电池状态:
  [仿真] BMS 不可用，返回模拟数据
  ...
[3] 当前动作模式:
  McAction_ZERO_TORQUE
[4] 关节状态摘要:
  idx01_left_hip_yaw         :  +0.0000 rad
  ...
```

---

## 7. 常见问题 (Common Issues)

**Q: `docker: Error response from daemon: could not select device driver`**
A: 不用 GPU 版本，去掉 `--gpu` 参数。
> *Don't use the GPU version; remove the `--gpu` flag.*

**Q: Mujoco 窗口没出来 / `cannot connect to X server`**
A: 先在宿主机运行 `xhost +`，确认 `echo $DISPLAY` 不为空。
> *Run `xhost +` on the host first, and confirm `echo $DISPLAY` is non-empty.*

**Q: `curl` 报 `Connection refused`**
A: 等服务启动完，约需 10~20 秒。用 `tmux` 看 `motion_ctrl` 窗口是否有报错。
> *Wait for services to start (~10–20 seconds). Check the `motion_ctrl` tmux window for errors.*

**Q: `ModuleNotFoundError: No module named 'aimdk'`**
A: 用 `uv run` 代替 `python3` 运行脚本，或先执行 `uv pip install agibot_a2_aimdk-dev2.0/prebuilt/a2_aimdk-2.0.0-py3-none-any.whl`
> *Use `uv run` instead of `python3`, or install the wheel first.*

**Q: ROS2 相关的 import 报错**
A: `source /opt/ros/humble/setup.bash`，或者用容器内的终端运行。
> *Run `source /opt/ros/humble/setup.bash`, or run the script from inside the container.*

---

## 8. 目录结构速查 (Directory Structure Reference)

```
robot/
├── agibot_a2_aimdk-dev2.0/     ← SDK 原始文件（不要修改）/ SDK source (do not modify)
│   ├── examples/               ← 官方示例（参考用）/ Official examples (reference only)
│   ├── protocol/               ← .proto 协议定义 / .proto protocol definitions
│   └── prebuilt/               ← 预编译 whl 包 / Pre-compiled wheel package
├── sim/                        ← 仿真启动脚本 / Simulation launch scripts
│   ├── start_sim.sh            ← 启动 Docker / Start Docker
│   ├── enter_and_start.sh      ← 进入容器启动服务 / Enter container and start services
│   └── sim_services.sh         ← tmux 服务管理 / tmux service management
├── robot_descriptions_public/  ← 机器人 URDF 模型（RViz 可视化）/ Robot URDF model (RViz visualization)
├── exercises/                  ← 练习文件（你的主战场）/ Exercise files (your main workspace)
│   ├── phase1_basics.py
│   ├── phase2_motion.py
│   ├── phase3_navigation.py
│   └── phase4_voice.py
├── projects/
│   └── reception_robot/        ← 最终项目 / Final project
└── docs/                       ← 本教案 / This curriculum
```
