import serial
import time

PORT = "/dev/ttyUSB0"   # your port
BAUD = 115200

ser = serial.Serial(PORT, BAUD, timeout=1)
time.sleep(2)  # let Arduino reset

print("Sending 'forward' once...")
ser.write(b"forward\n")

time.sleep(0.5)

while ser.in_waiting:
    print("Arduino says:", ser.readline().decode(errors="ignore").strip())

ser.close()
print("Done.")
