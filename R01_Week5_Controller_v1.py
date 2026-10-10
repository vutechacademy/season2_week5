# VU TECH Academy - R-01 Controller
# Week 6: BUILD A DEVICE | MicroPython / ESP32
# Wi-Fi: R-01-AP | Password: 12345678 | Browser: http://192.168.4.1
#
# Pin map:
# L298N ENA=GPIO14, IN1=GPIO27, IN2=GPIO26
# L298N ENB=GPIO32, IN3=GPIO25, IN4=GPIO33
# HC-SR04 TRIG=GPIO18, ECHO=GPIO19 (use a voltage divider on ECHO)
# Servo signal=GPIO5 | LED1=GPIO2 | LED2=GPIO4 | Buzzer=GPIO23
# OLED SDA=GPIO21, SCL=GPIO22 (optional; requires ssd1306.py)

from machine import Pin, PWM, ADC, time_pulse_us
import network, socket, time, gc

AP_SSID = "R-01-VU"
AP_PASSWORD = "12345678"
DEFAULT_SPEED = 65
MOVE_TIMEOUT_MS = 800

# -------------------- MOTOR --------------------
left_pwm = PWM(Pin(14), freq=1000)
left_in1, left_in2 = Pin(27, Pin.OUT), Pin(26, Pin.OUT)
right_pwm = PWM(Pin(32), freq=1000)
right_in3, right_in4 = Pin(25, Pin.OUT), Pin(33, Pin.OUT)

def set_pwm(pwm, percent):
    pwm.duty_u16(int(max(0, min(100, int(percent))) * 65535 / 100))

def motors_stop():
    left_in1.off(); left_in2.off()
    right_in3.off(); right_in4.off()
    set_pwm(left_pwm, 0); set_pwm(right_pwm, 0)

def motor_forward(speed):
    left_in1.on(); left_in2.off()
    right_in3.on(); right_in4.off()
    set_pwm(left_pwm, speed); set_pwm(right_pwm, speed)

def motor_backward(speed):
    left_in1.off(); left_in2.on()
    right_in3.off(); right_in4.on()
    set_pwm(left_pwm, speed); set_pwm(right_pwm, speed)

def motor_left(speed):
    left_in1.off(); left_in2.on()
    right_in3.on(); right_in4.off()
    set_pwm(left_pwm, speed); set_pwm(right_pwm, speed)

def motor_right(speed):
    left_in1.on(); left_in2.off()
    right_in3.off(); right_in4.on()
    set_pwm(left_pwm, speed); set_pwm(right_pwm, speed)

# -------------------- SERVO --------------------
servo_pwm = PWM(Pin(5), freq=50)
def servo_angle(angle):
    angle = max(0, min(180, int(angle)))
    pulse_us = 500 + (2000 * angle // 180)
    servo_pwm.duty_u16(int(pulse_us * 65535 // 20000))
    return angle

# -------------------- LED / BUZZER --------------------
led1, led2 = Pin(2, Pin.OUT), Pin(4, Pin.OUT)
# BUZZER - GPIO23
buzzer_pwm = PWM(Pin(23), freq=2000)
buzzer_pwm.duty_u16(0)

def set_led(on):
    led1.value(1 if on else 0); led2.value(1 if on else 0)

def set_buzzer(on):
    buzzer_pwm.freq(2000)
    buzzer_pwm.duty_u16(50000 if on else 0)




# -------------------- SENSORS --------------------
trig, echo = Pin(18, Pin.OUT), Pin(19, Pin.IN)
ldr = ADC(Pin(34))
ldr.atten(ADC.ATTN_11DB)

def read_distance():
    try:
        trig.off(); time.sleep_us(2); trig.on(); time.sleep_us(10); trig.off()
        duration = time_pulse_us(echo, 1, 30000)
        if duration < 0: return None
        return round(duration * 0.0343 / 2, 1)
    except Exception:
        return None

def read_light():
    try: return ldr.read()
    except Exception: return None

# -------------------- OPTIONAL OLED --------------------
oled = None
try:
    from machine import I2C
    import ssd1306
    i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
    found = i2c.scan()
    print("I2C scan:", [hex(x) for x in found])
    oled_addr = 0x3C if 0x3C in found else (0x3D if 0x3D in found else None)
    if oled_addr is not None:
        oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=oled_addr)
except Exception as e:
    print("OLED unavailable (web control still runs):", e)

mode, status, last_command = "READY", "ONLINE", "READY"
last_move_ms = time.ticks_ms()
speed_percent, servo_position = DEFAULT_SPEED, 90
led_state, buzzer_state = False, False

def update_oled(distance, light):
    if oled is None: return
    try:
        oled.fill(0)
        oled.text("R-01 CONTROLLER", 0, 0)
        oled.text("MODE:" + mode[:10], 0, 13)
        oled.text("DIST:" + (str(distance) if distance is not None else "--") + " cm", 0, 26)
        oled.text("LIGHT:" + (str(light) if light is not None else "--"), 0, 39)
        oled.text("LED:{} BUZ:{}".format("ON" if led_state else "OFF", "ON" if buzzer_state else "OFF"), 0, 52)
        oled.show()
    except Exception as e:
        print("OLED update error:", e)

def state_json(distance, light):
    d = "null" if distance is None else str(distance)
    l = "null" if light is None else str(light)
    return ('{"network":"ONLINE","mode":"%s","status":"%s","last_command":"%s",'
            '"distance":%s,"light":%s,"speed":%d,"servo":%d,"led":%s,"buzzer":%s}') % (
                mode, status, last_command, d, l, speed_percent, servo_position,
                "true" if led_state else "false", "true" if buzzer_state else "false")

HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>R-01 Controller | VU TECH Academy</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#eef5ff;color:#10264c;font-family:Arial,sans-serif}
header{background:linear-gradient(120deg,#0649b8,#168cff);color:white;padding:18px;text-align:center}
header h1{margin:0;font-size:26px}header p{margin:6px 0 0}main{max-width:760px;margin:auto;padding:14px}
.card{background:white;border-radius:18px;padding:16px;margin:12px 0;box-shadow:0 4px 16px #16345b18}
h2{font-size:18px;margin:0 0 12px}.status{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.tile{background:#f1f6ff;border-radius:12px;padding:10px}.tile small{display:block;color:#526887}.tile b{font-size:18px;overflow-wrap:anywhere}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
button{border:0;border-radius:12px;padding:14px 8px;color:white;font-size:15px;font-weight:bold;min-height:48px;touch-action:none;cursor:pointer}
.move{background:#0759ce}.go{background:#159447}.stop{background:#d82035}.aux{background:#693bd1}.off{background:#53627a}
.row{display:flex;gap:8px;flex-wrap:wrap}.row button{flex:1;min-width:90px}input[type=range]{width:100%}
.note{font-size:13px;color:#536887;line-height:1.5}#feedback{font-weight:bold;color:#087a43;min-height:22px}
@media(max-width:440px){header h1{font-size:22px}.grid{gap:6px}button{font-size:13px;padding:12px 4px}.card{padding:12px}}
</style></head><body>
<header><h1>R-01 CONTROLLER</h1><p>VU TECH ACADEMY · CONTROL • STATUS • FEEDBACK</p></header>
<main>
<section class="card"><h2>DEVICE STATUS</h2><div class="status">
<div class="tile"><small>NETWORK</small><b id="network">ONLINE</b></div>
<div class="tile"><small>MODE / STATUS</small><b id="mode">READY / ONLINE</b></div>
<div class="tile"><small>DISTANCE</small><b id="distance">-- cm</b></div>
<div class="tile"><small>LIGHT (ADC)</small><b id="light">--</b></div>
<div class="tile"><small>SERVO</small><b id="servoStatus">90°</b></div>
<div class="tile"><small>OUTPUTS</small><b id="outputs">LED OFF · BUZZER OFF</b></div>
</div><p id="feedback">Connected to R-01. Ready.</p></section>
<section class="card"><h2>MOTOR CONTROL · press and hold to move</h2>
<div class="grid"><div></div><button class="go" data-move="forward">▲<br>FORWARD</button><div></div>
<button class="move" data-move="left">◀ LEFT</button><button class="stop" id="stop">STOP</button><button class="move" data-move="right">RIGHT ▶</button>
<div></div><button class="move" data-move="backward">▼<br>BACKWARD</button><div></div></div>
<p class="note">ปล่อยปุ่มเพื่อหยุดรถ ระบบจะหยุดอัตโนมัติหากไม่มีสัญญาณควบคุมต่อเนื่อง</p>
<label for="speed">Motor speed: <b id="speedLabel">65%</b></label><input id="speed" type="range" min="30" max="100" value="65">
</section>
<section class="card"><h2>SERVO POSITION</h2><div class="row">
<button class="aux" data-servo="45">SERVO 45°</button><button class="aux" data-servo="90">SERVO 90°</button><button class="aux" data-servo="135">SERVO 135°</button>
</div></section>
<section class="card"><h2>STATUS LIGHT · LED</h2><div class="row"><button class="go" data-led="on">LED ON</button><button class="off" data-led="off">LED OFF</button></div></section>
<section class="card"><h2>SOUND FEEDBACK · BUZZER</h2><div class="row"><button class="go" data-buzzer="on">BUZZER ON</button><button class="off" data-buzzer="off">BUZZER OFF</button></div></section>
<p class="note">Week 6: Control + Status + Feedback. ยกรถให้ล้อลอยก่อนทดสอบ Motor ครั้งแรก</p>
</main>
<script>
const feedback=document.getElementById('feedback');let keepAlive=null;
async function command(path){try{const r=await fetch(path,{cache:'no-store'});const d=await r.json();feedback.textContent=d.message||'Command sent';refresh();}
catch(e){feedback.textContent='No response from R-01. Check Wi-Fi and IP.';}}
function startMove(move){command('/cmd?move='+move+'&speed='+document.getElementById('speed').value);
clearInterval(keepAlive);keepAlive=setInterval(()=>command('/cmd?move='+move+'&speed='+document.getElementById('speed').value),250);}
function endMove(){clearInterval(keepAlive);keepAlive=null;command('/cmd?move=stop');}
document.querySelectorAll('[data-move]').forEach(b=>{
 b.addEventListener('pointerdown',e=>{e.preventDefault();startMove(b.dataset.move);});
 ['pointerup','pointercancel','pointerleave'].forEach(ev=>b.addEventListener(ev,endMove));
});
document.getElementById('stop').addEventListener('click',endMove);
document.querySelectorAll('[data-servo]').forEach(b=>b.addEventListener('click',()=>command('/cmd?servo='+b.dataset.servo)));
document.querySelectorAll('[data-led]').forEach(b=>b.addEventListener('click',()=>command('/cmd?led='+b.dataset.led)));
document.querySelectorAll('[data-buzzer]').forEach(b=>b.addEventListener('click',()=>command('/cmd?buzzer='+b.dataset.buzzer)));
document.getElementById('speed').addEventListener('input',e=>document.getElementById('speedLabel').textContent=e.target.value+'%');
async function refresh(){try{const r=await fetch('/api',{cache:'no-store'});const d=await r.json();
document.getElementById('network').textContent=d.network;document.getElementById('mode').textContent=d.mode+' / '+d.status;
document.getElementById('distance').textContent=(d.distance===null?'--':d.distance)+' cm';
document.getElementById('light').textContent=d.light===null?'--':d.light;
document.getElementById('servoStatus').textContent=d.servo+'°';
document.getElementById('outputs').textContent='LED '+(d.led?'ON':'OFF')+' · BUZZER '+(d.buzzer?'ON':'OFF');
}catch(e){}}
setInterval(refresh,1000);refresh();
</script></body></html>'''

# -------------------- WIFI ACCESS POINT --------------------
ap = network.WLAN(network.AP_IF)
ap.active(False); time.sleep_ms(300); ap.active(True)
try:
    ap.config(essid=AP_SSID, password=AP_PASSWORD, authmode=network.AUTH_WPA_WPA2_PSK)
except Exception:
    ap.config(essid=AP_SSID, password=AP_PASSWORD)
while not ap.active(): time.sleep_ms(100)
ip = ap.ifconfig()[0]
print("Wi-Fi:", AP_SSID, "| Password:", AP_PASSWORD)
print("Open browser: http://" + ip)

# -------------------- WEB SERVER --------------------
addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(addr); server.listen(3); server.settimeout(0.2)
print("R-01 Controller ready")

def send_response(client, body, content_type="text/html; charset=utf-8"):
    header = ("HTTP/1.1 200 OK\r\nContent-Type: " + content_type +
              "\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n")
    client.send(header.encode())
    if isinstance(body, str): body = body.encode()
    client.send(body)

def handle_command(path):
    global mode, status, last_command, last_move_ms, speed_percent
    global servo_position, led_state, buzzer_state
    message = "Command received"
    try:
        args = {}
        if "?" in path:
            query = path.split("?",1)[1].split(" ",1)[0]
            for part in query.split("&"):
                if "=" in part:
                    k,v=part.split("=",1); args[k]=v
        if "speed" in args: speed_percent=max(30,min(100,int(args["speed"])))
        move=args.get("move")
        if move:
            last_command=move.upper()
            if move=="forward": motor_forward(speed_percent); mode="MOVE"; last_move_ms=time.ticks_ms()
            elif move=="backward": motor_backward(speed_percent); mode="MOVE"; last_move_ms=time.ticks_ms()
            elif move=="left": motor_left(speed_percent); mode="MOVE"; last_move_ms=time.ticks_ms()
            elif move=="right": motor_right(speed_percent); mode="MOVE"; last_move_ms=time.ticks_ms()
            elif move=="stop": motors_stop(); mode="STOP"; last_move_ms=time.ticks_ms()
            message="Motor: "+last_command
        if "servo" in args:
            servo_position=servo_angle(int(args["servo"]))
            last_command="SERVO "+str(servo_position); message=last_command+" applied"
        if "led" in args:
            led_state=args["led"]=="on"; set_led(led_state)
            last_command="LED "+("ON" if led_state else "OFF"); message=last_command+" applied"
        if "buzzer" in args:
            buzzer_state=args["buzzer"]=="on"; set_buzzer(buzzer_state)
            last_command="BUZZER "+("ON" if buzzer_state else "OFF"); message=last_command+" applied"
        status="ONLINE"
    except Exception as e:
        message="Command error: "+str(e); print(message)
    safe=message.replace("\\","\\\\").replace('"','\\"')
    return '{"message":"'+safe+'"}'

motors_stop(); set_led(False); set_buzzer(False); servo_angle(90)

while True:
    if mode=="MOVE" and time.ticks_diff(time.ticks_ms(),last_move_ms)>MOVE_TIMEOUT_MS:
        motors_stop(); mode="STOP"; last_command="AUTO STOP"
    distance=read_distance(); light=read_light(); update_oled(distance,light)
    client=None
    try:
        client,remote=server.accept()
        client.settimeout(1)
        request=client.recv(1024)
        if not request: client.close(); continue
        first_line=request.split(b"\r\n",1)[0].decode("utf-8","ignore")
        parts=first_line.split(" ")
        path=parts[1] if len(parts)>1 else "/"
        if path.startswith("/api"):
            send_response(client,state_json(distance,light),"application/json; charset=utf-8")
        elif path.startswith("/cmd"):
            send_response(client,handle_command(path),"application/json; charset=utf-8")
        else:
            send_response(client,HTML)
    except OSError:
        pass
    except Exception as e:
        print("Server error:",e)
    finally:
        if client:
            try: client.close()
            except Exception: pass
    gc.collect()
