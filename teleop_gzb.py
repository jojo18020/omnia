import asyncio
import json
import os
import math
from datetime import datetime

from dotenv import load_dotenv
from videosdk import (
    VideoSDK,
    MeetingConfig,
    Meeting,
    MeetingEventHandler,
    PubSubSubscribeConfig,
)

# ---------- ROS2 ----------
import rclpy
from rclpy.node import Node
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration

# ---------- ENV ----------
load_dotenv()

TOKEN = os.getenv("VIDEOSDK_TOKEN")
MEETING_ID = os.getenv("MEETING_ID")
NAME = "RobotTeleopNode"

TELEOP_TOPIC = "TELEOP"

# ✅ Python 3.12-safe event loop (matches your original style)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# ---------- ROS2 JOINT JOG CONFIG ----------
TRAJ_TOPIC = "/joint_trajectory_controller/joint_trajectory"
JOINT_NAMES = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6", "joint7"]

STEP_RAD = math.radians(3.0)  # 3 degrees per key press
TFS = 0.4  # time_from_start seconds

KEYMAP = {
    "q": (0, +1), "a": (0, -1),
    "w": (1, +1), "s": (1, -1),
    "e": (2, +1), "d": (2, -1),
    "r": (3, +1), "f": (3, -1),
    "t": (4, +1), "g": (4, -1),
    "y": (5, +1), "h": (5, -1),
    "u": (6, +1), "j": (6, -1),
}

STOP_KEYS = {" ", "x"}

ros_node = None  # set in __main__


class JointJogNode(Node):
    def __init__(self):
        super().__init__("videosdk_joint_jog")
        self.pub = self.create_publisher(JointTrajectory, TRAJ_TOPIC, 10)
        self.q = [0.0] * len(JOINT_NAMES)
        self.get_logger().info(f"Publishing JointTrajectory to {TRAJ_TOPIC}")

    def publish_target(self):
        msg = JointTrajectory()
        msg.joint_names = JOINT_NAMES

        pt = JointTrajectoryPoint()
        pt.positions = self.q[:]
        sec = int(TFS)
        pt.time_from_start = Duration(sec=sec, nanosec=int((TFS - sec) * 1e9))
        msg.points = [pt]

        self.pub.publish(msg)

    def handle_key(self, key: str):
        if not key:
            return
        k = key.lower().strip()

        now = datetime.now().isoformat(timespec="seconds")

        if k in STOP_KEYS:
            print(f"[{now}] TELEOP stop/hold key='{k}' -> publishing current target")
            self.publish_target()
            return

        if k not in KEYMAP:
            return

        idx, sgn = KEYMAP[k]
        self.q[idx] += sgn * STEP_RAD
        print(f"[{now}] TELEOP key='{k}' -> joint{idx+1} target={self.q[idx]:+.4f} rad")
        self.publish_target()


async def ros_spin_task():
    """Keep rclpy alive without blocking VideoSDK callbacks."""
    global ros_node
    while rclpy.ok():
        if ros_node is not None:
            rclpy.spin_once(ros_node, timeout_sec=0.0)
        await asyncio.sleep(0.01)


def handle_teleop_message(pubsub_message):
    """
    PubSub callback. Expected payload from index.html:
      {"key":"q","ts":123...}
    """
    global ros_node
    try:
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
        key = data.get("key")
        ts = data.get("ts")

        now = datetime.now().isoformat(timespec="seconds")
        print(f"[{now}] TELEOP received: key={key} ts={ts} sender={sender}")

        if ros_node is None:
            print(f"[{now}] WARN: ROS node not ready yet; ignoring key='{key}'")
            return

        ros_node.handle_key(key)

    except Exception as e:
        print("Error handling teleop message:", e, "raw=", pubsub_message)


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

        # ✅ schedule on our explicit loop (same style as your original code)
        loop.create_task(self.subscribe_to_teleop(sub_cfg))

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
    # ROS2 init
    rclpy.init()
    ros_node = JointJogNode()

    # ✅ schedule ROS spinner on our explicit loop (fixes your runtime error)
    loop.create_task(ros_spin_task())

    # Join meeting + start PubSub listener
    main()

    print("Event loop running. Teleop listener active (Ctrl+C to stop).")
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("Shutting down Teleop loop...")
        loop.stop()
        if ros_node is not None:
            ros_node.destroy_node()
        rclpy.shutdown()
