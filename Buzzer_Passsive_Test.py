from machine import Pin, PWM
from time import sleep

# Passive Buzzer on GPIO23
buzzer = PWM(Pin(23), freq=2000)

def buzzer_on():
    buzzer.freq(2000)
    buzzer.duty_u16(32768)
    print("BUZZER ON")

def buzzer_off():
    buzzer.duty_u16(0)
    print("BUZZER OFF")

while True:
    buzzer_on()
    sleep(1)

    buzzer_off()
    sleep(1)
