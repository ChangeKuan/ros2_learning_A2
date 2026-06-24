"""
机器人连接配置
Robot Connection Configuration

使用方式 / Usage:
  export ROBOT_TARGET=sim   # 仿真容器 (默认) / Simulation container (default)
  export ROBOT_TARGET=real  # 真机 / Real robot

仿真可用的服务 / Services available in simulation:
  ✓ MC: SetAction/GetAction, SetNeckCommand, SetHandCommand, walk (port 56322)
  ✓ MotionPlayer: motion playback
  ✗ 导航 (PNC/MM), TTS, ASR, 灯光, BMS, 系统状态
    Navigation (PNC/MM), TTS, ASR, lights, BMS, system state
"""
import os

_mode = os.environ.get("ROBOT_TARGET", "sim")
SIM = _mode == "sim"

if SIM:
    MC_IP = "127.0.0.1"
    NAV_IP = "127.0.0.1"   # nav services not available in sim
else:
    MC_IP = "192.168.100.100"
    NAV_IP = "192.168.100.110"
