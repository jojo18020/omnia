import os
import asyncio
from dotenv import load_dotenv
from videosdk import MeetingConfig, VideoSDK

# ----------------------------------------------------
# LOAD .env FROM THIS DIRECTORY
# ----------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)

VIDEOSDK_TOKEN = os.getenv("VIDEOSDK_TOKEN")
MEETING_ID = os.getenv("MEETING_ID")
NAME = os.getenv("NAME", "RobotCamera")

print("DEBUG token_len:", len(VIDEOSDK_TOKEN or ""), "meeting:", MEETING_ID)

# Create a global event loop like in the official docs
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def main():
    if not VIDEOSDK_TOKEN or not MEETING_ID:
        raise RuntimeError("Token or Meeting ID missing from .env")

    meeting_config = MeetingConfig(
        meeting_id=MEETING_ID,
        name=NAME,
        mic_enabled=False,
        webcam_enabled=True,
        token=VIDEOSDK_TOKEN,
    )

    # Initialize meeting
    meeting = VideoSDK.init_meeting(**meeting_config)

    print("Joining the meeting...")
    meeting.join()
    print("Joined successfully as", NAME)

    # At this point VideoSDK will hook into the event loop and keep the
    # WebRTC connection alive as long as the loop is running.

if __name__ == "__main__":
    main()
    print("Event loop running, RobotCamera should now appear in the room.")
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("Shutting down event loop.")
        loop.stop()
