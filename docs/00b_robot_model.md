# Phase 0b：机器人模型 — URDF 与 RViz 可视化 (Robot Model — URDF and RViz Visualization)

> 对应资源：`robot_descriptions_public/`
> 前置要求：完成 `00_environment_setup.md`，ROS2 环境已配置
>
> *Resource: `robot_descriptions_public/`*
> *Prerequisites: Complete `00_environment_setup.md` with ROS2 environment configured.*

---

## 学习目标 (Learning Objectives)

完成本节后，你能：

> *After completing this section, you will be able to:*

1. 说清楚 URDF 是什么，以及它和运行时 API 的关系 / Explain what URDF is and how it relates to the runtime API
2. 在 RViz 中可视化机器人模型并拖动关节滑条 / Visualize the robot model in RViz and drag joint sliders
3. 从 URDF 读出关节名称、运动轴方向和角度限制 / Read joint names, motion axis directions, and angle limits from URDF
4. 把 `GetJointState` 返回的 `idx01_left_hip_roll` 对应到机器人真实的物理关节 / Map joint names returned by `GetJointState` to real physical joints on the robot

---

## 1. 知识点：URDF 是什么 (What is URDF?)

URDF（Unified Robot Description Format）是机器人的"身份证"：

> *URDF (Unified Robot Description Format) is the robot's "identity card":*

```
URDF = 链路（Link）+ 关节（Joint）的树状结构
URDF = tree structure of Links + Joints
```

**Link**：物理刚体，有质量、惯量和外形（视觉网格 + 碰撞网格）。

> ***Link**: A rigid physical body with mass, inertia, and geometry (visual mesh + collision mesh).*

**Joint**：两个 Link 之间的连接关系，定义运动轴、运动范围和阻尼。

> ***Joint**: The connection between two Links, defining the axis of motion, range of motion, and damping.*

URDF 有两个独立用途：

> *URDF has two independent uses:*

1. **可视化 (Visualization)**：RViz 用 mesh 文件渲染 3D 模型 / RViz uses mesh files to render the 3D model
2. **碰撞检测 (Collision detection)**：仿真器/运动规划器用 convex 凸包做快速碰撞计算 / The simulator/motion planner uses convex hulls for fast collision checks

```
robot_descriptions_public/
├── urdf/
│   ├── model.urdf               ← 基础模型（无手指）/ Base model (no fingers)
│   └── model_with_finger.urdf   ← 带手指模型 / Model with fingers
├── mesh/                        ← 高精度视觉网格（.stl）/ High-resolution visual meshes (.stl)
├── convex/                      ← 简化碰撞凸包（.stl）/ Simplified collision convex hulls (.stl)
├── rviz/display.rviz            ← RViz 预配置布局 / Pre-configured RViz layout
└── launch/display.launch.py     ← 启动文件 / Launch file (ros2 launch entry point)
```

---

## 2. 构建与启动可视化 (Build and Launch Visualization)

### 2.1 构建 (Build)

在 ROS2 工作空间根目录运行：

> *Run from the ROS2 workspace root:*

```bash
cd ~/Code/robot/robot_descriptions_public
./build.sh
# 等价于 / Equivalent to:
# colcon build --packages-up-to robot_descriptions_public --symlink-install
```

### 2.2 启动 RViz (Launch RViz)

```bash
# 基础模型（无手指）/ Base model (no fingers)
./display_model.sh

# 带手指模型 / Model with fingers
./display_model_with_finger.sh
```

启动后会打开三个组件：

> *Launching opens three components:*

- **robot_state_publisher**：读取 URDF，广播 TF 坐标变换 / Reads URDF and broadcasts TF transforms
- **joint_state_publisher_gui**：弹出滑条窗口，可手动拖动每个关节 / Opens a slider GUI for manually moving each joint
- **rviz2**：3D 可视化界面，显示机器人模型 / 3D visualization showing the robot model

> **操作提示 (Tip)**：拖动 joint_state_publisher_gui 的滑条，RViz 里的对应关节会实时运动。这是理解关节物理位置最直观的方式。
>
> *Drag the sliders in joint_state_publisher_gui and the corresponding joint in RViz moves in real time. This is the most intuitive way to understand each joint's physical location.*

---

## 3. 关节树结构 (Joint Tree Structure)

机器人共有 **28 个可控关节**（revolute 类型），按身体部位分组：

> *The robot has **28 controllable joints** (revolute type), grouped by body part:*

### 腿部（12 个关节）/ Legs (12 joints)

| 关节名 / Joint name | 轴 / Axis | 说明 / Description |
|--------|-----|------|
| `idx01_left_hip_roll` | X | 左髋：左右侧展 / Left hip: lateral abduction |
| `idx02_left_hip_yaw` | Z | 左髋：内外旋 / Left hip: internal/external rotation |
| `idx03_left_hip_pitch` | Y | 左髋：前后摆动 / Left hip: flexion/extension |
| `idx04_left_tarsus` | Y | 左跗骨（踝上段）/ Left tarsus (upper ankle) |
| `idx05_left_toe_pitch` | Y | 左趾俯仰 / Left toe pitch |
| `idx06_left_toe_roll` | X | 左趾横滚 / Left toe roll |
| `idx07_right_hip_roll` | X | 右髋：左右侧展 / Right hip: lateral abduction |
| `idx08_right_hip_yaw` | Z | 右髋：内外旋 / Right hip: internal/external rotation |
| `idx09_right_hip_pitch` | Y | 右髋：前后摆动 / Right hip: flexion/extension |
| `idx10_right_tarsus` | Y | 右跗骨 / Right tarsus |
| `idx11_right_toe_pitch` | Y | 右趾俯仰 / Right toe pitch |
| `idx12_right_toe_roll` | X | 右趾横滚 / Right toe roll |

### 手臂（14 个关节，每侧 7-DOF）/ Arms (14 joints, 7-DOF per side)

| 关节名 / Joint name | 说明 / Description |
|--------|------|
| `idx13_left_arm_joint1` ~ `idx19_left_arm_joint7` | 左臂 7 自由度，joint1=肩部，joint7=腕部 / Left arm 7-DOF: joint1=shoulder, joint7=wrist |
| `idx20_right_arm_joint1` ~ `idx26_right_arm_joint7` | 右臂 7 自由度 / Right arm 7-DOF |

### 头部（2 个关节）/ Head (2 joints)

| 关节名 / Joint name | 说明 / Description |
|--------|------|
| `idx27_head_joint1` | 偏航（左右摇头）/ Yaw (shaking left/right) |
| `idx28_head_joint2` | 俯仰（上下点头）/ Pitch (nodding up/down) |

> **固定关节（fixed）** 如 `left_arm_base_joint`、`left_wrist_motor_A_ball` 等是机械连接，不可控制，API 中不会出现。
>
> ***Fixed joints** such as `left_arm_base_joint` and `left_wrist_motor_A_ball` are mechanical connections, not controllable, and do not appear in the API.*

---

## 4. URDF 与 API 的对应关系 (URDF–API Correspondence)

Phase 1 的 `GetJointState` 返回的 `name` 字段直接来自 URDF 关节名：

> *The `name` field returned by Phase 1's `GetJointState` comes directly from URDF joint names:*

```json
// GetJointState 响应 / GetJointState response
{
    "states": [
        { "name": "idx01_left_hip_roll", "position": 0.001, ... },
        { "name": "idx27_head_joint1",   "position": -0.05, ... }
    ]
}
```

**对照方法 (Mapping method)**：
1. 在 joint_state_publisher_gui 里拖动 `idx27_head_joint1` 滑条 / Drag the `idx27_head_joint1` slider in the GUI
2. 观察 RViz 里头部向哪个方向转 / Observe which direction the head turns in RViz
3. 在真机/仿真的 `GetJointState` 响应里找 `idx27_head_joint1` / Find `idx27_head_joint1` in the `GetJointState` response
4. `position` 为正值时对应刚才 RViz 里的转动方向 / A positive `position` corresponds to the direction you saw in RViz

这样每个关节名的物理含义就不再是字面猜测，而是有直观印象。

> *This way, every joint name has a concrete physical meaning you've seen rather than just an abstract label.*

---

## 5. URDF 与 Docker 仿真的关系 (URDF vs. Docker Simulation)

URDF 和 Docker 仿真是**独立的两套模型**，但共享同一套关节命名：

> *The URDF and Docker simulation are **two independent models** but share the same joint naming convention:*

```
robot_descriptions_public/urdf/model.urdf   ← 本地 URDF（RViz 可视化用）/ Local URDF (for RViz visualization)
        ↕ 关节名完全相同（idx01_* ~ idx28_*）/ Identical joint names (idx01_* ~ idx28_*)
Docker 容器内 MuJoCo XML                    ← 物理仿真引擎用的模型 / Model used by the physics engine
        ↕ 关节名完全相同 / Identical joint names
HTTP API（GetJointState / SetJointPositions）← 程序调用的接口 / Interface called by your code
```

**URDF 对开发的实际作用 (Practical use of URDF in development)**：

1. **查角度限制 (Check angle limits)**：写运动控制前先查 URDF，发送 SetJointPositions 超出范围会被拒绝。/ Check URDF before writing motion control code; commands outside the range will be rejected.
2. **确认关节方向 (Confirm joint direction)**：在 RViz 里拖滑条，正值对应哪个方向一目了然，避免方向搞反。/ Drag sliders in RViz to immediately see which direction is positive, avoiding sign errors.
3. **区分固定关节 (Distinguish fixed joints)**：URDF 里 `type="fixed"` 的关节不受控、不出现在 API 响应中，提前知道可以避免困惑。/ Joints with `type="fixed"` in URDF are not controllable and don't appear in API responses.

> URDF 是**离线的参考手册**——不联网、不需要 Docker，随时可查。写 API 调用前先在 RViz 确认关节，能省去大量调试时间。
>
> *URDF is an **offline reference manual** — no network or Docker required, always available. Confirm joints in RViz before writing API calls to save significant debugging time.*

---

## 6. 从 URDF 读取关节限制 (Reading Joint Limits from URDF)

运动规划时需要知道每个关节的角度范围。直接用 `grep`：

> *Motion planning requires knowing each joint's angle range. Use `grep` directly:*

```bash
# 查看某个关节的完整定义（含 limit）/ View a joint's full definition (including limit)
grep -A 20 '"idx27_head_joint1"' robot_descriptions_public/urdf/model.urdf
```

输出示例 (Example output)：
```xml
<joint name="idx27_head_joint1" type="revolute">
  <limit lower="-0.785398" upper="0.785398" effort="30" velocity="10"/>
  ...
</joint>
```

- `lower` / `upper`：角度范围（弧度），约 ±45° / Angle range (radians), approximately ±45°
- `effort`：最大力矩（N·m）/ Maximum torque (N·m)
- `velocity`：最大角速度（rad/s）/ Maximum angular velocity (rad/s)

批量提取所有可控关节的限制 (Batch extract all controllable joint limits)：

```bash
grep -E 'joint name="idx|<limit' robot_descriptions_public/urdf/model.urdf | paste - -
```

---

## 7. convex 目录的作用 (The convex/ Directory)

`convex/` 里的 `*_hull.stl` 是对应 mesh 的**凸包简化版**：

> *The `*_hull.stl` files in `convex/` are **convex-hull-simplified** versions of the corresponding meshes:*

```
mesh/left_hip_roll.stl         (高精度，~数千三角面 / High-res, ~thousands of triangles)
convex/left_hip_roll_hull.stl  (凸包，~几十三角面 / Convex hull, ~dozens of triangles)
```

用途 (Uses)：
- **碰撞检测 (Collision detection)**：仿真器（MuJoCo/Gazebo）用凸包做实时碰撞计算，高精度 mesh 太慢 / Simulators use convex hulls for real-time collision checks; high-res meshes are too slow
- **运动规划 (Motion planning)**（Phase 2 高级内容 / Phase 2 advanced topic）：MoveIt2 的碰撞检查也使用凸包 / MoveIt2's collision checking also uses convex hulls
- 对 Phase 0-2 的日常开发无需关心，理解存在即可 / Not needed for day-to-day Phase 0–2 development; just know they exist

---

## 8. 实战任务 (Hands-on Tasks)

### 任务 0b-A：可视化基础模型 (Task 0b-A: Visualize the Base Model)
1. 构建并启动 `./display_model.sh` / Build and launch `./display_model.sh`
2. 在 joint_state_publisher_gui 里分别拖动 / Drag sliders in joint_state_publisher_gui for:
   - `idx03_left_hip_pitch`（左腿前后摆 / Left leg flexion/extension）
   - `idx27_head_joint1`（头部左右 / Head yaw）
   - `idx13_left_arm_joint1`（左臂肩部 / Left arm shoulder）
3. 记住每个关节正值对应的运动方向。/ Note the movement direction for positive values of each joint.

### 任务 0b-B：关节限制速查 (Task 0b-B: Look Up Joint Limits)
用 grep 命令找出 `idx27_head_joint1` 和 `idx28_head_joint2` 的角度范围，换算成角度（°），填入：

> *Use grep to find the angle range for `idx27_head_joint1` and `idx28_head_joint2`, convert to degrees (°), and fill in:*

```
head_joint1: lower=___° upper=___°
head_joint2: lower=___° upper=___°
```

### 任务 0b-C：与 Phase 1 对接 (Task 0b-C: Connect to Phase 1)
在 `phase1_basics.py` 里运行 `get_joint_state()`，从返回的关节列表中找出头部两个关节的当前 position，与你在 RViz 观察到的初始位置对照。

> *Run `get_joint_state()` in `phase1_basics.py`, find the current `position` for both head joints in the returned list, and compare with the initial position you observed in RViz.*

---

## 9. 本节要点总结 (Summary)

```
URDF      = 机器人物理结构的完整描述（链路 + 关节）
           = Complete physical description of the robot (links + joints)
mesh/     = 视觉渲染用的高精度 STL / High-resolution STL for visual rendering
convex/   = 碰撞检测用的凸包 STL / Convex-hull STL for collision detection
idx{N}_*  = 关节命名规则，API 和 URDF 共用同一套名称
           = Joint naming convention, shared between API and URDF
```

**下一节 (Next)**: Phase 1 — 用 HTTP RPC 读取机器人状态，此时你已经知道每个关节名的物理含义。

> *Phase 1 — Read robot state via HTTP RPC. At this point you already know the physical meaning of every joint name.*
