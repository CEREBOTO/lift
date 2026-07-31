#hall_lift_async.py - 异步绝对定位，支持中断
import machine, utime, ujson, select, sys

#===== 电机驱动 =====
RPWM = machine.PWM(machine.Pin(2))
LPWM = machine.PWM(machine.Pin(3))
R_EN = machine.Pin(4, machine.Pin.OUT)
L_EN = machine.Pin(5, machine.Pin.OUT)
R_EN.value(1); L_EN.value(1)
RPWM.freq(20000); LPWM.freq(20000)

#===== 霍尔传感器 =====
hall = machine.Pin(27, machine.Pin.IN, machine.Pin.PULL_UP)

#===== 固定参数 =====
MM_PER_PULSE = 600.0 / 850.0   
MIN_LIMIT = 0
MAX_LIMIT = 850

#===== 全局变量 =====
count = 0.0
offset = 0.0
current_dir = 0      # 0:停, 1:上, 2:下
down_comp = 1.0
last_irq_time = 0
MIN_PULSE_INTERVAL_MS = 15  #软滤波 
min_limit = MIN_LIMIT
max_limit = MAX_LIMIT

#异步 goto 相关
target_height = None   # 目标高度（mm），若不为 None 表示正在进行 goto
last_save_count = 0
last_save_ms = 0
SAVE_EVERY_PULSES = 10          # 运动中按脉冲保存（原先 100 太大，易丢位置）
SAVE_EVERY_MS = 1000            

#===== 中断 =====
def on_pulse(pin):
    global count, last_irq_time
    now = utime.ticks_ms()
    if utime.ticks_diff(now, last_irq_time) < MIN_PULSE_INTERVAL_MS:
        return
    last_irq_time = now
    if current_dir == 1:
        count += 1.0
    elif current_dir == 2:
        count -= down_comp
hall.irq(trigger=machine.Pin.IRQ_RISING, handler=on_pulse)

#===== 电机控制 =====
def motor(d):
    global current_dir
    if d == 2 and min_limit is not None and count <= min_limit:
        print("BOTTOM LIMIT REACHED")
        return
    if d == 1 and max_limit is not None and count >= max_limit:
        print("TOP LIMIT REACHED")
        return
    if d == 1:
        RPWM.duty_u16(65535)
        LPWM.duty_u16(0)
    elif d == 2:
        LPWM.duty_u16(65535)
        RPWM.duty_u16(0)
    else:
        RPWM.duty_u16(0)
        LPWM.duty_u16(0)
    prev_dir = current_dir
    current_dir = d
    if d == 0 and prev_dir != 0:
        # 停机立刻保存；
        save_config()
    if d == 1:
        print("MOTOR UP")
    elif d == 2:
        print("MOTOR DOWN")
    else:
        print("MOTOR STOP")

def cancel_goto(reason=None):
    """取消异步定位并停机。reason 有值则打印；否则在有 goto 时打印 GOTO_CANCELLED。"""
    global target_height
    had = target_height is not None
    target_height = None
    motor(0)
    if reason is not None:
        print(reason)
    elif had:
        print("GOTO_CANCELLED")

def get_height():
    return (count - offset) * MM_PER_PULSE

def set_height(mm):
    global offset
    offset = count - (mm / MM_PER_PULSE)
    save_config()
    print("HEIGHT_SET to {:.2f} mm".format(mm))

def set_zero():
    set_height(0.0)

#===== 异步 goto 启动 =====
def start_goto(mm):
    global target_height
    target_height = mm
    print("GOTO_START {:.2f}".format(mm))

#===== 在主循环中调用的 goto 状态机 =====
def goto_update():
    global target_height, current_dir
    if target_height is None:
        return
    cur_h = get_height()
    if abs(cur_h - target_height) < 0.5:
        target_height = None
        motor(0)
        print("GOTO_DONE {:.2f}".format(cur_h))
        return
    if current_dir == 0:
        if cur_h < target_height:
            motor(1)
        else:
            motor(2)
    elif (cur_h < target_height and current_dir == 2) or (cur_h > target_height and current_dir == 1):
        # 方向反了：先停，下一拍再按正确方向启动（保留 target）
        motor(0)

#===== Flash 存储 =====
def save_config():
    global last_save_count, last_save_ms
    data = {
        'count': count,
        'offset': offset,
        'height_mm': get_height(),  # 冗余记录，便于排查
        'down_comp': down_comp,
        'min_limit': min_limit,
        'max_limit': max_limit,
    }
    try:
        with open('lift.json', 'w') as f:
            ujson.dump(data, f)
        last_save_count = count
        last_save_ms = utime.ticks_ms()
    except Exception as e:
        print("SAVE_ERR", e)

def load_config():
    global count, offset, down_comp, min_limit, max_limit
    global last_save_count, last_save_ms
    try:
        with open('lift.json', 'r') as f:
            d = ujson.load(f)
            count = float(d.get('count', 0.0))
            offset = float(d.get('offset', 0.0))
            down_comp = float(d.get('down_comp', 1.0))
            min_limit = d.get('min_limit', MIN_LIMIT)
            max_limit = d.get('max_limit', MAX_LIMIT)
            last_save_count = count
            last_save_ms = utime.ticks_ms()
            print("LOADED count={:.1f} offset={:.1f} height={:.2f} mm".format(
                count, offset, get_height()))
    except Exception as e:
        print("LOAD_ERR (start from 0):", e)

load_config()

def auto_save():
    if current_dir == 0:
        return
    now = utime.ticks_ms()
    if abs(count - last_save_count) >= SAVE_EVERY_PULSES:
        save_config()
    elif utime.ticks_diff(now, last_save_ms) >= SAVE_EVERY_MS:
        save_config()

#===== 串口命令处理 =====
spoll = select.poll()
spoll.register(sys.stdin, select.POLLIN)
cmd_buf = ""

print("Lift Async Ready. Commands: up, down, stop, get, zero, set_height <mm>, goto <mm>")
print("           set_comp <val>, set_min, set_max, clear_limits, save")

try:
    while True:
        if spoll.poll(0):
            ch = sys.stdin.read(1)
            if ch == '\n':
                line = cmd_buf.strip().lower()
                cmd_buf = ""
                if line == "up":
                    target_height = None  # 手动覆盖异步 goto
                    motor(1)
                elif line == "down":
                    target_height = None
                    motor(2)
                elif line == "stop":
                    cancel_goto()
                elif line == "get":
                    print("COUNTS {:.0f} HEIGHT {:.2f} DIR {}".format(count, get_height(), current_dir))
                elif line == "zero":
                    set_zero()
                elif line.startswith("set_height"):
                    try:
                        mm = float(line.split()[1])
                        set_height(mm)
                    except:
                        print("ERR: set_height <mm>")
                elif line.startswith("goto"):
                    try:
                        mm = float(line.split()[1])
                        start_goto(mm)
                    except:
                        print("ERR: goto <mm>")
                elif line.startswith("set_comp"):
                    try:
                        val = float(line.split()[1])
                        down_comp = val
                        save_config()
                        print("DOWN_COMP = {:.3f}".format(down_comp))
                    except:
                        print("ERR: set_comp <float>")
                elif line == "set_min":
                    min_limit = count
                    save_config()
                    print("MIN limit = {:.0f}".format(min_limit))
                elif line == "set_max":
                    max_limit = count
                    save_config()
                    print("MAX limit = {:.0f}".format(max_limit))
                elif line == "clear_limits":
                    min_limit = None
                    max_limit = None
                    save_config()
                    print("Limits cleared")
                elif line == "save":
                    save_config()
                    print("SAVED")
                else:
                    print("Unknown command")
            elif ch != '\r':
                cmd_buf += ch

        goto_update()
        if current_dir == 2 and min_limit is not None and count <= min_limit:
            cancel_goto("Safety stop at bottom")
        elif current_dir == 1 and max_limit is not None and count >= max_limit:
            cancel_goto("Safety stop at top")
        auto_save()
        utime.sleep_ms(5)
finally:
    # Ctrl-C / 异常退出时尽量保住当前位置
    target_height = None
    motor(0)
    save_config()
    print("EXIT_SAVED height={:.2f} mm".format(get_height()))

