#!/usr/bin/env bash
# 从源码树启动（bash）：自动 source ROS 与工作空间 install，再运行 lift 键盘控制台。
# 指定串口示例:
#   LIFT_SERIAL_PORT=/dev/ttyACM1 ./scripts/keyboard_control.bash
#   ./scripts/keyboard_control.bash -- --port /dev/ttyACM1
set -eo pipefail

_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_PKG="$(cd "${_DIR}/.." && pwd)"
_SRC="$(cd "${_PKG}/.." && pwd)"
_WS="$(cd "${_SRC}/.." && pwd)"

if [[ ! -f "${_WS}/install/setup.bash" ]]; then
  echo "[ERROR] 未找到 ${_WS}/install/setup.bash — 请先在 ${_WS} 执行: colcon build --packages-select lift" >&2
  exit 1
fi

if [[ -z "${ROS_DISTRO:-}" ]]; then
  for _d in humble jazzy iron; do
    if [[ -f "/opt/ros/${_d}/setup.bash" ]]; then
      # shellcheck source=/dev/null
      source "/opt/ros/${_d}/setup.bash"
      break
    fi
  done
fi

# shellcheck source=/dev/null
source "${_WS}/install/setup.bash"
exec ros2 run lift keyboard_control "$@"
