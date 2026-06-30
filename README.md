# ROS2 Learning A2 Project

This repository collects the learning materials, simulator scripts, and a reception-robot demo for the AgiBot A2 SDK.

## Overview

The project is organized around three main parts:

- Learning exercises and notes in [docs](docs)
- SDK and protocol assets in [agibot_a2_aimdk-dev2.0](agibot_a2_aimdk-dev2.0)
- A reception robot application in [projects/reception_robot](projects/reception_robot)

## Key Features

- Basic SDK communication examples and robotics tutorials
- Simulation startup scripts for the A2 robot environment
- An LLM-driven reception robot demo using function calling
- Waypoint-based navigation workflow for visitor guidance

## Quick Start

### 1. Prerequisites

- Docker 20+
- Python 3.14 (recommended for the LLM demo)
- ROS 2 Humble environment available at `/opt/ros/humble/setup.bash`
- A valid Xiaomi MIMO API key for the LLM backend

### 2. Install the SDK wheel

```bash
pip install agibot_a2_aimdk-dev2.0/prebuilt/a2_aimdk-2.0.0-py3-none-any.whl
```

### 3. Set environment variables

```bash
export ROBOT_TARGET=sim
export MIMO_API_KEY=your-api-key
export MIMO_MODEL=mimo-v2.5
source /opt/ros/humble/setup.bash
```

## Start the Simulation

```bash
cd sim
./start_sim.sh
./enter_and_start.sh
```

The simulator starts the core services in tmux windows for motion control, action playback, and development use.

## Run the Reception Robot Demo

### Option A: LLM-controlled receptionist

```bash
python3.14 projects/reception_robot/llm_agent.py "送我去会议室"
```

### Option B: Direct simulation check

```bash
python3.14 -m py_compile projects/reception_robot/llm_agent.py
```

## Project Structure

```text
.
├── docs/                          # Tutorial and setup documents
├── exercises/                     # Practice code for SDK basics
├── projects/
│   └── reception_robot/           # Reception robot application
│       ├── config.py              # Robot target and IP settings
│       ├── llm_agent.py           # ReAct + function-calling controller
│       ├── main.py                # ROS2 state-machine entrypoint
│       ├── robot_client.py        # Robot API wrappers
│       ├── state_machine.py       # Reception flow state machine
│       └── tools.py               # LLM tool definitions and executors
├── sim/                           # Simulation launch scripts
└── agibot_a2_aimdk-dev2.0/        # SDK and protocol package
```

## Recommended Reading Order

1. [docs/00_environment_setup.md](docs/00_environment_setup.md)
2. [docs/01_basics.md](docs/01_basics.md)
3. [projects/reception_robot/main.py](projects/reception_robot/main.py)
4. [projects/reception_robot/llm_agent.py](projects/reception_robot/llm_agent.py)

## Notes

- The simulation environment is useful for offline development and verification.
- For a real robot, change `ROBOT_TARGET=real` and update the network settings in [projects/reception_robot/config.py](projects/reception_robot/config.py).
- If navigation is unavailable in the current simulation, the system should report the service issue clearly instead of pretending the robot moved.
