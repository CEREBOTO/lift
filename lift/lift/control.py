#!/usr/bin/env python3
# control.py — PC 端通过串口与 Pico 通信（键盘升降控制）。Linux 用 termios；Windows 用 msvcrt。
import argparse
import os
import platform
import select
import serial
import serial.tools.list_ports
import sys
import time

if platform.system() == "Windows":
    import msvcrt

    def kbhit() -> bool:
        return msvcrt.kbhit()

    def getch() -> str:
        ch = msvcrt.getch()
        if isinstance(ch, int):
            ch = bytes([ch])
        if isinstance(ch, bytes):
            return ch.decode("latin-1").lower()
        return str(ch).lower()

else:
    import termios
    import tty

    _stdin_fd = sys.stdin.fileno()
    _old_termios: list | None = None

    def _term_enable_cbreak() -> None:
        global _old_termios
        _old_termios = termios.tcgetattr(_stdin_fd)
        tty.setcbreak(_stdin_fd)

    def _term_restore() -> None:
        global _old_termios
        if _old_termios is not None:
            termios.tcsetattr(_stdin_fd, termios.TCSADRAIN, _old_termios)
            _old_termios = None

    def kbhit() -> bool:
        return bool(select.select([sys.stdin], [], [], 0)[0])

    def getch() -> str:
        return sys.stdin.read(1).lower()


# Linux 下自动检测不到设备时使用的默认串口
DEFAULT_SERIAL_PORT = "/dev/ttyACM0"


def find_serial_port() -> str | None:
    for p in serial.tools.list_ports.comports():
        desc = (p.description or "").lower()
        dev = (p.device or "").lower()
        if "pico" in desc or "rp2040" in desc or "circuitpython" in desc:
            return p.device
        # Windows: COMx；Linux 上 device 多为 /dev/ttyACM*，避免用过于宽泛的 "usb" 匹配所有 USB 串口
        if platform.system() == "Windows" and "com" in dev:
            if "pico" in desc or "usb" in dev:
                return p.device
    return None


def send(ser: serial.Serial, cmd: str) -> None:
    ser.write((cmd + "\n").encode())
    ser.flush()
    print("[TX]", cmd)


def read_line(ser: serial.Serial) -> str | None:
    if ser.in_waiting:
        line = ser.readline().decode(errors="replace").strip()
        if line:
            print("[RX]", line)
            return line
    return None


def wait_for_goto_complete(ser: serial.Serial) -> bool:
    """等待 Pico 发送 GOTO_DONE 或 GOTO_CANCELLED，期间检测空格取消。"""
    print("Moving... press Space to cancel")
    while True:
        if kbhit():
            key = getch()
            if key == " ":
                send(ser, "stop")
                print("Cancelling...")
                continue
        line = read_line(ser)
        if line:
            if "GOTO_DONE" in line:
                print("Movement completed")
                return True
            if "GOTO_CANCELLED" in line:
                print("Movement cancelled")
                return False
        time.sleep(0.02)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pico lift keyboard serial console (text protocol @ 115200)."
    )
    parser.add_argument(
        "--port",
        "-p",
        default=(os.environ.get("LIFT_SERIAL_PORT") or "").strip() or None,
        help="串口设备；也可用环境变量 LIFT_SERIAL_PORT（默认：自动找 Pico，否则 Linux 用 "
        + DEFAULT_SERIAL_PORT
        + "）",
    )
    args, _unknown = parser.parse_known_args()

    port = args.port
    if not port:
        port = find_serial_port()
    if not port:
        if platform.system() != "Windows":
            port = DEFAULT_SERIAL_PORT
            print(f"[INFO] Using default serial port {port}")
        else:
            port = input("Enter port (e.g., COM3): ").strip()
    if not port:
        print("No port given.", file=sys.stderr)
        sys.exit(1)

    if platform.system() != "Windows":
        _term_enable_cbreak()
    try:
        ser = serial.Serial(port, 115200, timeout=0.2)
        # 避免部分板子在打开串口时 DTR/RTS 抖动导致反复复位、main.py 来不及跑
        try:
            ser.setDTR(False)
            ser.setRTS(False)
        except (AttributeError, serial.SerialException):
            pass
        time.sleep(0.15)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
    except serial.SerialException as e:
        print(f"Serial open failed: {e}", file=sys.stderr)
        if platform.system() != "Windows":
            _term_restore()
        sys.exit(1)

    print("Connected.")
    print(
        f"Serial: {port} @ 115200 — 文本行协议（如 up / down / stop / goto 100 / get），以换行结尾。"
    )
    print(
        "若无反应：1) Pico 上需运行会读 USB 串口的 main.py（不能只占着 REPL）；"
        "2) 确认波特与固件一致；3) 多设备时用 -p/--port 或 LIFT_SERIAL_PORT 指定。"
    )
    print("Commands:")
    print("  w/s/l : up/down/stop")
    print("  g     : get status")
    print("  c     : set compensation")
    print("  Number (0-600) + Enter : go to height (mm)")
    print("  Space : cancel current movement")
    print("  Ctrl+C: exit")

    input_buffer = ""
    try:
        while True:
            if kbhit():
                key = getch()
                if key.isdigit() or key == ".":
                    input_buffer += key
                    sys.stdout.write(key)
                    sys.stdout.flush()
                elif key in ("\r", "\n"):
                    if input_buffer:
                        try:
                            height = float(input_buffer)
                            if 0 <= height <= 600:
                                print()
                                send(ser, f"goto {height}")
                                wait_for_goto_complete(ser)
                            else:
                                print(f"\nHeight {height} out of range (0-600)")
                        except ValueError:
                            print(f"\nInvalid number: {input_buffer}")
                        input_buffer = ""
                elif key in ("\b", "\x08", "\x7f"):
                    if input_buffer:
                        input_buffer = input_buffer[:-1]
                        sys.stdout.write("\b \b")
                        sys.stdout.flush()
                elif key == " ":
                    send(ser, "stop")
                    print("Stop requested")
                else:
                    if key == "w":
                        send(ser, "up")
                    elif key == "s":
                        send(ser, "down")
                    elif key == "l":
                        send(ser, "stop")
                    elif key == "g":
                        send(ser, "get")
                    elif key == "c":
                        print()
                        if platform.system() != "Windows":
                            _term_restore()
                        try:
                            comp = input("Enter down_comp (e.g., 1.05): ")
                        finally:
                            if platform.system() != "Windows":
                                _term_enable_cbreak()
                        send(ser, f"set_comp {comp}")
                        time.sleep(0.1)
                    elif key == "\x03":
                        break
                if key not in ("\r", "\n", "\b", "\x08", "\x7f", " "):
                    time.sleep(0.1)
            read_line(ser)
            time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()
        if platform.system() != "Windows":
            _term_restore()
        print("Exit")


if __name__ == "__main__":
    main()
