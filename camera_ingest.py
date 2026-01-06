import os
import asyncio
from dotenv import load_dotenv
from videosdk import MeetingConfig, VideoSDK
from vsaiortc.contrib.media import MediaPlayer

# ---------- ENV ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)

VIDEOSDK_TOKEN = os.getenv("VIDEOSDK_TOKEN")
MEETING_ID = os.getenv("MEETING_ID")
NAME = os.getenv("NAME", "RobotCamera-MediaPlayer")

print("DEBUG token_len:", len(VIDEOSDK_TOKEN or ""), "meeting:", MEETING_ID)

# Same pattern as official docs
loop = asyncio.get_event_loop()

def main():
    if not VIDEOSDK_TOKEN or not MEETING_ID:
        raise RuntimeError("Token or Meeting ID missing from .env")

    # ---------- CAMERA / MEDIA SOURCE LAYER ----------
    # For Linux webcam:
    #   - '/dev/video0' is the camera device
    #   - format='v4l2' tells ffmpeg/av it's a V4L2 device
    #   - video_size sets resolution (best-effort)
    player = MediaPlayer(
        "/dev/video0",
        format="v4l2",
    )

    # ---------- VIDEO SDK CLIENT LAYER ----------
    meeting_config = MeetingConfig(
        meeting_id=MEETING_ID,
        name=NAME,
        mic_enabled=False,
        webcam_enabled=True,   # we are sending a custom track as the "webcam"
        token=VIDEOSDK_TOKEN,
        custom_camera_video_track=player.video,
        # you could also use: custom_microphone_audio_track=player.audio
    )

    meeting = VideoSDK.init_meeting(**meeting_config)

    print("Joining the meeting with MediaPlayer webcam...")
    meeting.join()
    print("Joined successfully as", NAME)

if __name__ == "__main__":
    main()
    print("Event loop running, RobotCamera-MediaPlayer should be streaming.")
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("Shutting down event loop.")
        loop.stop()
