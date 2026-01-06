import asyncio
import json
import os
from datetime import datetime

from dotenv import load_dotenv
from videosdk import (
    VideoSDK,
    MeetingConfig,
    Meeting,
    MeetingEventHandler,
    PubSubSubscribeConfig,
)

# ---------- ENV ----------
load_dotenv()

TOKEN = os.getenv("VIDEOSDK_TOKEN")
MEETING_ID = os.getenv("MEETING_ID")
NAME = "RobotTeleopNode"

TELEOP_TOPIC = "TELEOP"

# Global event loop (same as in docs)
loop = asyncio.get_event_loop()


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

        # TODO: actually send this to your robot here

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

        # Schedule subscribe() as async task (exactly like docs)
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
    main()
    print("Event loop running. Teleop listener active (Ctrl+C to stop).")
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("Shutting down Teleop loop...")
        loop.stop()
