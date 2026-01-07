import asyncio
import json
import os
import time
from datetime import datetime
import glob

from dotenv import load_dotenv
from videosdk import (
    VideoSDK,
    MeetingConfig,
    Meeting,
    MeetingEventHandler,
    PubSubSubscribeConfig,
)

import serial  # for Arduino serial

# ---------- ENV ----------
load_dotenv()

TOKEN = os.getenv("VIDEOSDK_TOKEN")
MEETING_ID = os.getenv("MEETING_ID")
NAME = "RobotTeleopNode"

TELEOP_TOPIC = "TELEOP"

# Global event loop
loop = asyncio.get_event_loop()

# ---------- ARDUINO SERIAL ----------
arduino_ser = None  # will be set by init_arduino()


def find_arduino_port():
    """
    Try to auto-detect an Arduino-like serial port.
    We scan /dev/ttyUSB* and /dev/ttyACM* and return the first that works.
    """
    candidates = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")

    print(f"[ARDUINO] Scanning ports, candidates: {candidates}")

    for port in candidates:
        try:
            print(f"[ARDUINO] Probing {port} ...")
            s = serial.Serial(port, 115200, timeout=0.05)
            time.sleep(2)  # let it reset
            # ping it once
            s.write(b"ping\n")
            time.sleep(0.1)

            # don't block forever; just see if it behaves
            _ = s.read(10)
            s.close()
            print(f"[ARDUINO] {port} looks valid.")
            return port
        except Exception as e:
            print(f"[ARDUINO] {port} failed: {e}")

    print("[ARDUINO] No valid Arduino port found.")
    return None


def init_arduino():
    """
    Open serial connection to Arduino using auto-detected port.
    """
    global arduino_ser

    port = find_arduino_port()
    if port is None:
        print("[ARDUINO] Could not find any port. Arduino will NOT be connected.")
        arduino_ser = None
        return

    BAUD_RATE = 115200

    try:
        print(f"[ARDUINO] Connecting on {port} @ {BAUD_RATE}...")
        arduino_ser = serial.Serial(port, BAUD_RATE, timeout=0.05)
        time.sleep(2)  # allow Arduino to reset
        print("[ARDUINO] Connected.")
    except Exception as e:
        print(f"[ARDUINO] Failed to connect on {port}: {e}")
        arduino_ser = None


def send_cmd_to_arduino(cmd: str):
    """
    Send a single teleop command string to Arduino over serial.
    Arduino expects lines like 'forward\\n'.
    """
    global arduino_ser
    now = datetime.now().isoformat(timespec="seconds")

    if arduino_ser is None:
        print(f"[{now}] [ARDUINO] Not connected; cannot send cmd='{cmd}'")
        return

    try:
        msg = (cmd + "\n").encode("utf-8")
        arduino_ser.write(msg)
        print(f"[{now}] [ARDUINO] Sent: {cmd}")

        # Light, non-blocking-ish read if anything is waiting
        if arduino_ser.in_waiting:
            resp = arduino_ser.readline().decode(errors="ignore").strip()
            if resp:
                print(f"[{now}] [ARDUINO] Reply: {resp}")

    except Exception as e:
        print(f"[{now}] [ARDUINO] Error sending cmd='{cmd}': {e}")


# ---------- TELEOP HANDLER ----------

def handle_teleop_message(pubsub_message):
    """
    Callback for PubSub messages on TELEOP topic.
    pubsub_message is a dict from the VideoSDK Python SDK.
    Expected keys: "message", "senderId"
    """
    try:
        # Handle both dict and object styles just in case
        if isinstance(pubsub_message, dict):
            payload_str = pubsub_message.get("message")
            sender = pubsub_message.get("senderId")
        else:
            payload_str = getattr(pubsub_message, "message", None)
            sender = getattr(pubsub_message, "senderId", None)

        if not payload_str:
            print("Got PubSub message with no 'message' field:", pubsub_message)
            return

        data = json.loads(payload_str)

        cmd = data.get("cmd")
        ts = data.get("ts")

        now = datetime.now().isoformat(timespec="seconds")
        print(
            f"[{now}] TELEOP received: cmd={cmd} ts={ts} sender={sender}"
        )

        # Only forward known commands to Arduino
        if cmd in ("forward", "backward", "left", "right"):
            send_cmd_to_arduino(cmd)
        else:
            print(f"[{now}] TELEOP ignoring unknown cmd='{cmd}' (raw data={data})")

    except Exception as e:
        print(
            "Error handling teleop message:",
            e,
            "raw=",
            pubsub_message,
        )


class TeleopMeetingHandler(MeetingEventHandler):
    def __init__(self, meeting: Meeting):
        super().__init__()
        self.meeting = meeting

    def on_meeting_joined(self, data):
        print("RobotTeleopNode joined meeting, subscribing to TELEOP...")

        sub_cfg = PubSubSubscribeConfig(
            topic=TELEOP_TOPIC,
            cb=handle_teleop_message,
        )

        asyncio.create_task(self.subscribe_to_teleop(sub_cfg))

    async def subscribe_to_teleop(self, sub_cfg: PubSubSubscribeConfig):
        try:
            old_messages = await self.meeting.pubsub.subscribe(sub_cfg)
            print("Old TELEOP messages:", old_messages)
        except Exception as e:
            print("Error in subscribe_to_teleop:", e)


def main():
    if not TOKEN or not MEETING_ID:
        raise RuntimeError("VIDEOSDK_TOKEN or MEETING_ID missing from environment")

    print(f"Using MEETING_ID={MEETING_ID}, joining as {NAME}")

    meeting_config = MeetingConfig(
        meeting_id=MEETING_ID,
        name=NAME,
        mic_enabled=False,
        webcam_enabled=False,
        token=TOKEN,
    )

    meeting = VideoSDK.init_meeting(**meeting_config)
    meeting.add_event_listener(TeleopMeetingHandler(meeting=meeting))

    print("Joining meeting from RobotTeleopNode...")
    meeting.join()
    print("meeting.join() returned; waiting for PubSub events...")


if __name__ == "__main__":
    # 1) Connect to Arduino
    init_arduino()

    # 2) Join meeting + start Teleop listener
    main()
    print("Event loop running. Teleop listener active (Ctrl+C to stop).")
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("Shutting down Teleop loop...")
        loop.stop()
        if arduino_ser is not None:
            print("[ARDUINO] Closing serial...")
            arduino_ser.close()
