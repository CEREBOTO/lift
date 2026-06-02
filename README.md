# lift

PC 端键盘串口控制台：通过 USB 串口与 **Raspberry Pi Pico** 上的升降固件通信（文本行协议，115200）。

## 环境要求

- **ROS 2**（Humble / Jazzy / Iron 等；本包为 `ament_python`，仅用于 `colcon build` 与 `ros2 run`）
- **Python 3** 与 **pyserial**：`pip install pyserial` 或 `sudo apt install python3-serial`
- Pico 已烧录并运行会读 USB 串口的 **`main.py`**（不能只占着 REPL）
- Linux 串口权限（用户加入 `dialout` 组后重新登录）：

  ```bash
  sudo usermod -aG dialout $USER
  ```

## 安装

在工作空间根目录编译：

```bash
cd ~/ros2_ws
source /opt/ros/<你的发行版>/setup.bash   # 例: humble
colcon build --packages-select lift
source install/setup.bash
```

zsh 用户可将最后一行改为 `source install/setup.zsh`。

## 快速使用

### 方式一：一键脚本（推荐）

在包目录下直接运行，脚本会自动 source ROS 与工作空间 `install`：

```bash
cd ~/ros2_ws/src/lift
./scripts/keyboard_control        # zsh
./scripts/keyboard_control.bash   # bash
```

指定串口：

```bash
LIFT_SERIAL_PORT=/dev/ttyACM1 ./scripts/keyboard_control.bash
# 或
./scripts/keyboard_control.bash -- --port /dev/ttyACM1
```

### 方式二：`ros2 run`

已 `source install/setup.bash` 后：

```bash
ros2 run lift keyboard_control
ros2 run lift keyboard_control -- --port /dev/ttyACM0
```

### 方式三：不依赖 ROS（仅 Python）

```bash
python3 ~/ros2_ws/src/lift/lift/control.py --port /dev/ttyACM0
```

## 键盘操作

连接成功后会显示当前串口与按键说明：

| 按键 | 串口命令 | 说明 |
|------|----------|------|
| `w` | `up` | 上升 |
| `s` | `down` | 下降 |
| `l` | `stop` | 停止 |
| `g` | `get` | 查询状态 |
| `c` | `set_comp …` | 设置下行补偿系数（会提示输入数值） |
| `0`–`600` + Enter | `goto <高度>` | 走到目标高度（mm），等待 `GOTO_DONE` |
| 空格 | `stop` | 运动中取消当前 `goto` |
| Ctrl+C | — | 退出 |

终端会打印 `[TX]` / `[RX]` 便于对照固件回显。

## 串口选择

默认行为（未指定 `--port` 且未设置 `LIFT_SERIAL_PORT` 时）：

1. 自动查找描述中含 **Pico / RP2040 / CircuitPython** 的设备
2. Linux 上若未找到，使用 **`/dev/ttyACM0`**
3. Windows 上会提示手动输入（如 `COM3`）

环境变量与参数等价：

```bash
export LIFT_SERIAL_PORT=/dev/ttyACM1
ros2 run lift keyboard_control
```

## 常见问题

| 现象 | 处理 |
|------|------|
| 打开串口后无反应 | 确认 Pico 上 **`main.py` 在跑**；波特率 **115200**；多板子时用 `-p` 指定正确设备 |
| 一连接就反复复位 | 程序已尝试关闭 DTR/RTS；可换 USB 线/口，或拔插后再连 |
| `Permission denied` on `/dev/ttyACM*` | 加入 `dialout` 组并重新登录，或临时 `sudo chmod a+rw /dev/ttyACM0` |
| 未找到 `install/setup.bash` | 在工作空间根目录执行 `colcon build --packages-select lift` |

## 包结构

```text
lift/
├── lift/control.py      # 键盘控制台主程序
├── scripts/keyboard_control       # zsh 启动脚本（source + ros2 run）
├── scripts/keyboard_control.bash  # bash 启动脚本（同上）
├── setup.py
└── package.xml
```
