---
name: project-robot-sdk
description: 智元远征 A2 机器人 AimDK SDK 项目结构、通信模式和学习课程进度
metadata: 
  node_type: memory
  type: project
  originSessionId: 37964b7b-6a8f-452c-8b1c-91bd7305468d
---

## 项目背景
SDK 路径: `/home/sucre/Code/robot/agibot_a2_aimdk-dev2.0`
机器人型号: 智元远征 A2，SDK 版本: AimDK 2.0
官方文档: https://open.agibot.com/docs/aimdk

## 通信架构
两种通信方式并用:
1. **HTTP RPC**: `http://{ip}:{port}/rpc/{service}/{method}` + JSON payload
2. **ROS2 Topic**: 通过 `RosMsgWrapper` 包裹 Protobuf，topic 命名含编码后的 proto 类名

## 关键 IP 和端口
| 功能 | IP | 端口 | 服务 |
|---|---|---|---|
| 运动控制 (MC) | 192.168.100.100 | 56322 | McActionService, McMotionService, McDataService |
| 电池 (BMS) | 192.168.100.100 | 56421 | HalBmsService |
| 系统状态 | 192.168.100.110 | 51011 | SystemService |
| 地图管理 (MM) | 192.168.100.110 | 50807 | MappingService, LocalizationService |
| 导航规划 (PNC) | 192.168.100.110 | 53176 | PncService |
| 任务引擎 | 192.168.100.110 | 57881 | TaskEngineService |
| TTS 语音 | 192.168.100.110 | 59301 | TTSService |
| RGB 灯光 | 192.168.100.110 | 52893 | HalRgbLightService |

## 学习课程结构
课程文件在 `/home/sucre/Code/robot/exercises/`:
- `phase1_basics.py` — 系统状态/电量/动作模式/关节状态读取
- `phase2_motion.py` — 颈部/手部/行走控制
- `phase3_navigation.py` — 地图查询/PNC 导航/状态监控
- `phase4_voice.py` — TTS/唤醒词/RGB 灯光

## 仿真环境

Docker 镜像: `tongyong-public-cn-shanghai.cr.volces.com/aima-public/a2-simulator:v2.0`
启动脚本: `/home/sucre/Code/robot/sim/start_sim.sh [--gpu]`
服务启动: `/home/sucre/Code/robot/sim/enter_and_start.sh` (tmux 4窗口)

**IP 规则**: 仿真用 `127.0.0.1`（--net=host），真机用 `192.168.100.x`
控制方式: `export ROBOT_TARGET=sim`（默认）或 `export ROBOT_TARGET=real`

仿真可用服务: MC (port 56322) — SetAction/GetAction/关节/颈部/手部/walk
仿真不可用: 导航(PNC/MM)、TTS、ASR、唤醒词、RGB灯光、BMS、系统状态

仿真容器内工具: `/home/agi/a2_simulation/tools-ultra/mc/` (SetAction.py, walk.py等)
ROS2 source: `source /home/agi/a2_simulation/ros2_plugin_proto_x86_64/share/ros2_plugin_proto/local_setup.bash`

## 最终项目
路径: `/home/sucre/Code/robot/projects/reception_robot/`
项目名: 语音导引接待机器人
文件:
- `robot_client.py` — 统一 HTTP API 封装层
- `state_machine.py` — IDLE→GREETING→LISTENING→NAVIGATING→ARRIVED 状态机
- `main.py` — ROS2 节点 + 主循环；支持 `--simulate` 无机器人测试

**Why:** 综合练习所有 SDK 模块 (语音+导航+运动控制)
**How to apply:** 用户完成 4 个 phase 练习后再做这个项目
