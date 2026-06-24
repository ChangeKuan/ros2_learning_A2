# Phase 4：语音与交互 — TTS、唤醒词、RGB 灯光 (Voice and Interaction — TTS, Wake Word, RGB Lights)

> 对应练习文件：`exercises/phase4_voice.py`
> **需要真机**（`export ROBOT_TARGET=real`）— 语音硬件不在仿真容器内
> 无真机可运行 `uv run exercises/phase4_voice.py test` 测试 HTTP 连通性
>
> *Exercise file: `exercises/phase4_voice.py`*
> ***Requires real robot** (`export ROBOT_TARGET=real`) — voice hardware is not in the simulation container.*
> *Without a real robot, run `uv run exercises/phase4_voice.py test` to test HTTP connectivity.*

---

## 学习目标 (Learning Objectives)

完成本节后，你能：

> *After completing this section, you will be able to:*

1. 理解语音交互的完整链路（唤醒词 → ASR → TTS）/ Understand the full voice-interaction pipeline (wake word → ASR → TTS)
2. 通过 HTTP API 让机器人播报文字（TTS）/ Make the robot speak text via the HTTP API (TTS)
3. 通过 ROS2 Topic 订阅唤醒词和语音识别结果 / Subscribe to wake word and ASR results via ROS2 Topics
4. 用 RGB 灯光配合状态做视觉反馈 / Use RGB lights for visual state feedback
5. 组合成"检测唤醒 → 改变灯光 → 语音回应"的完整交互流 / Combine into a complete "detect wake → change lights → voice response" interaction flow

---

## 1. 知识点：语音交互链路 (Voice Interaction Pipeline)

A2 的语音交互有三个环节：

> *A2's voice interaction has three stages:*

```
麦克风 (Microphone)
  │
  ▼
VAD（语音活动检测 / Voice Activity Detection）
  │  检测到有人说话 / Speech detected
  ▼
唤醒词检测 (Wake Word Detection)    ← 持续运行，监听特定关键词 / Runs continuously, listening for keywords
  │  检测到唤醒词 / Wake word detected
  ▼  Topic: /agent/wakeup/...
ASR（语音识别 / Automatic Speech Recognition）  ← 唤醒后才激活，把语音转成文字 / Activates after wake word, converts speech to text
  │  识别完成 / Recognition complete
  ▼  Topic: /agent/asr_result/...
你的应用逻辑 (Your application logic)  ← 你来处理这段文字，决定做什么 / You process the text and decide what to do
  │
  ▼
TTS（文字转语音 / Text-to-Speech）    ← HTTP API，让机器人说话 / HTTP API to make the robot speak
  │
扬声器播放 (Speaker output)
```

### 1.1 VAD（语音活动检测）/ VAD (Voice Activity Detection)

VAD 持续监听麦克风，判断当前是否有人在说话。它产生 4 种状态：

> *VAD continuously listens on the microphone to detect whether someone is speaking. It produces 4 states:*

| 状态 / State | 含义 / Meaning |
|------|------|
| `AUDIO_VAD_STATE_NONE` | 静默，无人说话 / Silence, nobody speaking |
| `AUDIO_VAD_STATE_BEGIN` | 检测到有人开始说话 / Speech started |
| `AUDIO_VAD_STATE_PROCESSING` | 说话进行中 / Speech in progress |
| `AUDIO_VAD_STATE_END` | 说话结束 / Speech ended |

这些状态通过 Topic `/agent/process_audio_output/...` 发布，可以用来做连续的音频缓冲（见 `examples/agent/get_voice.py`）。

> *These states are published via Topic `/agent/process_audio_output/...` and can be used for continuous audio buffering (see `examples/agent/get_voice.py`).*

### 1.2 唤醒词 (Wake Word)

机器人默认有一个唤醒词（出厂设置，通常是"你好，小爱"或类似词汇）。可以用 `SetCustomWakeUpWord` 自定义。

> *The robot has a default wake word (factory setting, typically "你好，小爱" or similar). Use `SetCustomWakeUpWord` to customize it.*

唤醒词检测结果通过 Topic `/agent/wakeup/...` 发布，消息类型为 `WakeUpResult`（Protobuf）：

> *Wake word detection results are published via Topic `/agent/wakeup/...`, message type `WakeUpResult` (Protobuf):*

**`WakeUpResult` 的字段 (Fields)**：

| 字段 / Field | 含义 / Meaning |
|------|------|
| `wake_word` | 触发的唤醒词文本（可用于区分多个唤醒词）/ The triggered wake word text (useful for distinguishing multiple wake words) |
| `timestamp` | 检测到唤醒词的时间戳 / Timestamp when the wake word was detected |

### 1.3 ASR（自动语音识别）/ ASR (Automatic Speech Recognition)

唤醒后，机器人的 ASR 引擎激活，把接下来说的话转成文字，通过 Topic `/agent/asr_result/...` 发布，消息类型为 `AsrResult`（Protobuf）：

> *After wake-up, the ASR engine activates and converts subsequent speech to text, publishing via Topic `/agent/asr_result/...`, message type `AsrResult` (Protobuf):*

**`AsrResult` 的字段 (Fields)**：

| 字段 / Field | 含义 / Meaning |
|------|------|
| `text` | 识别出的文字内容 / The recognized text |
| `is_final` | `True` 表示这是最终结果；`False` 表示中间结果 / `True` = final result; `False` = intermediate result (ASR streams partial results, then a final result) |

实际使用时通常只处理 `is_final=True` 的消息，避免对中间结果做出响应。

> *In practice, only handle messages where `is_final=True` to avoid reacting to partial results.*

---

## 2. 知识点：TTS API (TTS API)

### 2.1 接口说明 (Interface Description)

```
POST http://192.168.100.110:59301/rpc/aimdk.protocol.TTSService/PlayTTS
```

请求体（`PlayTTSRequest`）/ Request body:
```json
{
    "text": "你好，我是 A2 机器人",
    "priority_level": "INTERACTION_L6",
    "domain": "my_app",
    "trace_id": "req_001",
    "is_interrupted": true
}
```

**字段说明 (Field descriptions)**：

| 字段 / Field | 含义 / Meaning |
|------|------|
| `text` | 要播报的文字内容 / Text to be spoken |
| `priority_level` | 优先级，格式 `INTERACTION_L{1~9}`，数字越大优先级越高 / Priority; format `INTERACTION_L{1–9}`, higher number = higher priority |
| `domain` | 应用标识，自定义字符串，用于日志追踪 / Application identifier, custom string for log tracing |
| `trace_id` | 本次请求的唯一 ID，用于在 TTS Status Topic 里匹配播放完成事件 / Unique request ID for matching TTS_STATE_FINISHED events in the TTS Status Topic |
| `is_interrupted` | `true`=允许被更高优先级的 TTS 打断；`false`=不可被打断 / `true` = can be interrupted by higher-priority TTS; `false` = not interruptible |

**优先级说明 (Priority levels)**：

| 级别 / Level | 典型用途 / Typical use |
|------|---------|
| L1~L3 | 背景提示，可被任何交互打断 / Background hints, interruptible by any interaction |
| L4~L6 | 普通交互回复（**推荐使用**）/ Normal interaction replies (**recommended**) |
| L7~L9 | 紧急警告，不可被打断 / Emergency alerts, non-interruptible |

**TTS 是异步的 (TTS is asynchronous)**：发完请求后立刻返回，语音在后台播放。如果你想等播放完成再继续，需要订阅 Topic `/interaction/tts_status/...` 监听播放状态。

> *The request returns immediately; speech plays in the background. To wait for completion, subscribe to Topic `/interaction/tts_status/...` and listen for the playback status.*

### 2.2 监控 TTS 播放状态 (Monitoring TTS Playback Status)

`TTSStatus`（Protobuf）的字段 (Fields):

| 字段 / Field | 含义 / Meaning |
|------|------|
| `state` | `"TTS_STATE_PLAYING"` 播放中 / `"TTS_STATE_FINISHED"` 播放完成 / `"TTS_STATE_ERROR"` 错误 / playing / finished / error |
| `trace_id` | 与发送请求时的 `trace_id` 对应，用来确认是哪条 TTS 播完了 / Matches the `trace_id` from the request; confirms which TTS finished |

在项目里可以用这个功能实现"等机器人说完话再做下一个动作"。

> *Use this in your project to implement "wait for the robot to finish speaking before performing the next action."*

---

## 3. 知识点：ROS2 订阅者 (ROS2 Subscriber)

订阅者和上一节的发布者相反：你不再发消息，而是被动接收消息。

> *A subscriber is the opposite of the publisher from the previous section: instead of sending messages, you passively receive them.*

```python
class WakeupNode(Node):
    def __init__(self):
        super().__init__("wakeup_listener")

        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,     # 唤醒词要保证送达 / Wake words must be delivered
            durability=QoSDurabilityPolicy.VOLATILE,       # 不保留历史消息 / Don't retain historical messages
            ...
        )

        self.create_subscription(
            RosMsgWrapper,           # 消息类型 / Message type
            WAKEUP_TOPIC,            # Topic 名称 / Topic name
            self._callback,          # 收到消息时调用的函数 / Function called when message arrives
            qos,
        )

    def _callback(self, msg):
        # 解析 Protobuf / Parse Protobuf
        raw = b"".join(msg.data)
        result = WakeUpResult()
        result.ParseFromString(raw)
        # 处理结果... / Process result...
```

### 3.1 QoS 对比（订阅 vs 发布）/ QoS Comparison (Subscribe vs Publish)

| 场景 / Scenario | reliability | durability | 原因 / Reason |
|------|-------------|------------|------|
| 唤醒词 / Wake word | RELIABLE | VOLATILE | 不能丢，但不需要历史 / Must not lose, but no history needed |
| 行走指令发布 / Walk command publish | BEST_EFFORT | — | 实时性优先，丢包无所谓 / Real-time priority; packet loss is fine |
| 音频数据订阅 / Audio data subscribe | BEST_EFFORT | — | 数据量大，实时处理 / High data volume, real-time processing |

### 3.2 `rclpy.spin()` vs `executor`

```python
# 方式 1: 阻塞式（简单，但会占用主线程）/ Method 1: blocking (simple, but occupies main thread)
rclpy.spin(node)           # 一直处理消息，直到 Ctrl+C / Process messages until Ctrl+C

# 方式 2: 非阻塞（在循环里手动触发）/ Method 2: non-blocking (manually trigger in a loop)
executor = rclpy.executors.SingleThreadedExecutor()
executor.add_node(node)
executor.spin_once(timeout_sec=0.1)   # 处理一次消息，然后返回 / Process one message batch, then return
```

`spin_once` 在 Phase 4 的 `listen_for_wakeup()` 里很重要：它让你在等待唤醒词的同时，还能做超时判断：

> *`spin_once` is crucial in Phase 4's `listen_for_wakeup()`: it lets you check for a timeout while waiting for a wake word:*

```python
deadline = time.time() + timeout
while time.time() < deadline and not triggered:
    executor.spin_once(timeout_sec=0.1)   # 每 0.1 秒检查一次是否有消息 / Check for messages every 0.1 s
```

---

## 4. 知识点：RGB 灯光控制 (RGB Light Control)

### 4.1 接口说明 (Interface Description)

```
POST http://192.168.100.110:52893/rpc/aimdk.protocol.HalRgbLightService/SetRgbLightCommand
```

```json
{
    "cmd": {
        "red": 0,
        "green": 255,
        "blue": 80,
        "effect": 1,
        "control": 1
    }
}
```

**`cmd` 的字段 (Fields in `cmd`)**：

| 字段 / Field | 范围 / Range | 含义 / Meaning |
|------|------|------|
| `red` | 0~255 | 红色分量 / Red component |
| `green` | 0~255 | 绿色分量 / Green component |
| `blue` | 0~255 | 蓝色分量 / Blue component |
| `effect` | 1/2/3 | 灯效：`1`=常亮，`2`=呼吸（渐亮渐暗），`3`=闪烁 / Light effect: `1`=steady, `2`=breathing (fade in/out), `3`=blinking |
| `control` | 0/1 | `1`=开灯，`0`=关灯 / `1`=on, `0`=off |

### 4.2 灯光与状态的对应关系 (Light-State Mapping)

灯光是机器人状态的直观反馈，用户不需要看屏幕就能判断机器人在做什么：

> *Lights provide intuitive state feedback — users can tell what the robot is doing without looking at a screen:*

```python
def light_standby():    set_light(0, 80, 255, effect=2)   # 蓝色呼吸 — 我在等待 / Blue breathing — waiting
def light_greeting():   set_light(0, 255, 80, effect=1)   # 绿色常亮 — 我在注意你 / Green steady — paying attention
def light_navigating(): set_light(255, 200, 0, effect=2)  # 黄色呼吸 — 我在走路 / Yellow breathing — walking
def light_arrived():    set_light(0, 200, 255, effect=3)  # 青色闪烁 — 我到了 / Cyan blinking — arrived
def light_error():      set_light(255, 0, 0, effect=3)    # 红色闪烁 — 我遇到问题了 / Red blinking — problem
```

这不只是好看，这是机器人 UX 设计的一部分。

> *This isn't just aesthetics — it's part of robot UX design.*

---

## 5. 代码详解：`phase4_voice.py` (Code Walkthrough)

### 5.1 `listen_for_wakeup()` 结构 (Structure)

```python
def listen_for_wakeup(on_wakeup_callback, timeout: float = 60.0):
    triggered = {"fired": False}   # ← 用 dict 传递可变状态（避免闭包问题）/ Use dict for mutable state (avoids closure issues)

    class WakeupNode(Node):
        def _cb(self, msg):
            result = WakeUpResult()
            result.ParseFromString(b"".join(msg.data))
            triggered["fired"] = True
            on_wakeup_callback(result)   # ← 调用你传入的函数 / Call your callback

    rclpy.init()
    node = WakeupNode()
    executor = rclpy.executors.SingleThreadedExecutor()
    executor.add_node(node)

    deadline = time.time() + timeout
    while time.time() < deadline and not triggered["fired"]:
        executor.spin_once(timeout_sec=0.1)

    node.destroy_node()
    rclpy.shutdown()
    return triggered["fired"]
```

**为什么用 `{"fired": False}` 而不是 `fired = False`？**

> *Why use `{"fired": False}` instead of `fired = False`?*

Python 的闭包（内部类访问外部变量）对基本类型有限制：内部类不能修改外部的 `bool`、`int` 等不可变类型。用 `dict` 或 `list` 这类可变对象可以绕过这个限制。

> *Python closures (inner classes accessing outer variables) can't rebind immutable types like `bool` or `int` in the outer scope. Using a mutable object like `dict` or `list` works around this limitation.*

### 5.2 `wakeup_response_demo()` 流程 (Flow)

```python
def wakeup_response_demo():
    # 设置初始状态 / Set initial state
    set_light(0, 80, 255, effect=2)        # 蓝色待机 / Blue standby

    def on_wakeup(result):
        set_light(0, 255, 80, effect=1)    # 绿色激活 / Green active
        say("你好，请问有什么需要帮助的？")
        time.sleep(5.0)                    # 等待说完（TTS 是异步的！）/ Wait for speech (TTS is async!)
        set_light(0, 80, 255, effect=2)    # 回到蓝色待机 / Back to blue standby

    listen_for_wakeup(on_wakeup, timeout=60.0)
```

**问题思考 (Think about this)**：`time.sleep(5.0)` 是怎么估算的？中文语速约 5 字/秒，"你好，请问有什么需要帮助的？" 约 13 个字，所以 2~3 秒说完，加 2 秒余量。

> *How is `time.sleep(5.0)` estimated? Chinese speech rate is ~5 characters/second. "你好，请问有什么需要帮助的？" is ~13 characters, so ~2–3 seconds to say, plus 2 seconds of buffer.*

更精确的做法是监听 `TTS_STATE_FINISHED`，这是 Phase 5 项目里会用到的改进点。

> *A more precise approach is to listen for `TTS_STATE_FINISHED` — this is an improvement covered in the Phase 5 project.*

---

## 6. 实战任务 (Hands-on Tasks)

### 任务 4-A：纯 HTTP 测试 (Task 4-A: HTTP-Only Test)

不需要 ROS2，先测试 TTS 和灯光：

> *No ROS2 needed — test TTS and lights first:*

```bash
export ROBOT_TARGET=real
uv run exercises/phase4_voice.py test
```

验证机器人能说话、灯光能变色。

> *Verify that the robot can speak and that lights change color.*

### 任务 4-B：唤醒词触发序列 (Task 4-B: Wake Word Trigger Sequence)

实现一个响应：

> *Implement a response:*

1. 检测到唤醒词 / Wake word detected
2. 红灯闪两下（表示"我听到你了"）/ Red light blinks twice ("I heard you")
3. TTS 播报当前时间（用 Python 的 `datetime` 获取）/ TTS announces the current time (use Python's `datetime`)
4. 恢复蓝色待机灯 / Return to blue standby light

### 任务 4-C：多种响应 (Task 4-C: Multiple Responses)

在 `on_wakeup` 里，根据唤醒词的**时间**做不同响应：

> *In `on_wakeup`, respond differently based on the **time** of the wake word:*

- 上午（6~12点）："早上好！" / Morning (6–12): "Good morning!"
- 下午（12~18点）："下午好！" / Afternoon (12–18): "Good afternoon!"
- 晚上（18~24点）："晚上好！" / Evening (18–24): "Good evening!"

```python
import datetime
hour = datetime.datetime.now().hour
```

### 任务 4-D（挑战）：TTS 完成等待 (Task 4-D (Challenge): Wait for TTS Completion)

实现一个 `say_and_wait(text, timeout=10.0)` 函数：

> *Implement a `say_and_wait(text, timeout=10.0)` function:*

- 发送 TTS 请求 / Send a TTS request
- 订阅 `/interaction/tts_status/...` Topic / Subscribe to `/interaction/tts_status/...` Topic
- 等待收到 `TTS_STATE_FINISHED` 状态后才返回 / Wait until `TTS_STATE_FINISHED` is received before returning
- 超时则强制返回 / Return on timeout regardless

参考 `examples/agent/tts_status_topic.py`。

> *See `examples/agent/tts_status_topic.py` for reference.*

---

## 7. 深入理解：消息解析流程 (Deep Dive: Message Parsing)

每次收到 ROS2 消息时的解析步骤：

> *Steps to parse each incoming ROS2 message:*

```python
def _callback(self, msg: RosMsgWrapper):
    # 步骤 1：检查序列化类型 / Step 1: Check serialization type
    if msg.serialization_type != "pb":
        return   # 只处理 Protobuf 格式 / Only handle Protobuf format

    # 步骤 2：把 list[bytes] 合并成一个 bytes 对象 / Step 2: Merge list[bytes] into one bytes object
    # msg.data 是 List[bytes]，每个元素是单字节 / msg.data is List[bytes], each element is one byte
    raw_bytes = b"".join(msg.data)

    # 步骤 3：用对应的 Protobuf 类解析 / Step 3: Parse with the corresponding Protobuf class
    result = WakeUpResult()
    result.ParseFromString(raw_bytes)

    # 步骤 4：访问字段 / Step 4: Access fields
    print(result.wake_word)
```

**为什么 `msg.data` 是 `List[bytes]` 而不是直接 `bytes`？**

> *Why is `msg.data` a `List[bytes]` rather than plain `bytes`?*

这是 ROS2 消息定义的历史遗留问题，SDK 选择用单字节 `bytes` 的列表来存储字节数组，需要手动 `join`。

> *This is a historical artifact of the ROS2 message definition. The SDK chose to store byte arrays as a list of single-byte `bytes` objects, requiring a manual `join`.*

---

## 8. 本节要点总结 (Summary)

```
语音链路: 麦克风 → VAD → 唤醒词 → ASR → 你的代码 → TTS → 扬声器
Voice pipeline: Mic → VAD → Wake word → ASR → Your code → TTS → Speaker

TTS = HTTP POST 异步请求，用 TTS Status Topic 等待完成
TTS = async HTTP POST; use TTS Status Topic to wait for completion

唤醒词/ASR = ROS2 Topic 订阅，用 RELIABLE QoS
Wake word/ASR = ROS2 Topic subscription, use RELIABLE QoS

灯光 = HTTP POST 同步请求，effect: 1=常亮, 2=呼吸, 3=闪烁
Lights = sync HTTP POST, effect: 1=steady, 2=breathing, 3=blinking

消息解析 = b"".join(msg.data) → ParseFromString
Message parsing = b"".join(msg.data) → ParseFromString
```

**下一节 (Next)**: 把这四个 Phase 学到的技能全部组合起来——接待机器人项目。

> *Combine everything from the four phases into a complete reception robot project.*
