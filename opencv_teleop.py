import os
import asyncio
import time
import fractions

import cv2
from av import VideoFrame
from dotenv import load_dotenv
from vsaiortc.mediastreams import MediaStreamError
from videosdk import (
    CustomVideoTrack,
    MeetingConfig,
    VideoSDK,
    MeetingEventHandler,
    ParticipantEventHandler,
)

# ------------ ENV SETUP ------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)

VIDEOSDK_TOKEN = os.getenv("VIDEOSDK_TOKEN")
MEETING_ID = os.getenv("MEETING_ID")
NAME = os.getenv("NAME", "RobotCamera-OpenCV")

print("DEBUG token_len:", len(VIDEOSDK_TOKEN or ""), "meeting:", MEETING_ID)

# Use a persistent asyncio loop, like in the VideoSDK docs
loop = asyncio.get_event_loop()

# ------------ PIPELINE CONFIG ------------

# Target FPS and resolution for the stream
TARGET_FPS = 30
TARGET_WIDTH = 1280
TARGET_HEIGHT = 720

VIDEO_CLOCK_RATE = 90000  # standard RTP clock rate
VIDEO_TIME_BASE = fractions.Fraction(1, VIDEO_CLOCK_RATE)


def process_frame(frame_bgr):
    """
    FRAME PROCESSING LAYER

    Input: raw BGR frame from OpenCV.
    Output: processed BGR frame (same shape).

    This is where you:
      - resize
      - crop
      - color-correct
      - overlay HUD / detections
      - compress or downscale resolution, etc.
    """
    # 1) Resize to 720p (or whatever your pipeline wants)
    frame_resized = cv2.resize(frame_bgr, (TARGET_WIDTH, TARGET_HEIGHT))

    # 2) (Optional) Add any debug overlays here
    # cv2.putText(frame_resized, "RobotCamera", (20, 40),
    #             cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

    return frame_resized


# ------------ CUSTOM VIDEO TRACK FROM OPENCV ------------

class OpenCVCameraTrack(CustomVideoTrack):
    """
    Custom VideoSDK video track that pulls frames from an OpenCV camera.
    """

    def __init__(self, device_index: int = 0):
        super().__init__()
        self.kind = "video"

        self.cap = cv2.VideoCapture(device_index)
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open camera device {device_index}")

        # Try to set resolution (best effort, not guaranteed)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, TARGET_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, TARGET_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)

        self._start = time.time()
        self._timestamp = None

        print(f"OpenCVCameraTrack initialized on device {device_index}")

    async def next_timestamp(self):
        """
        Copy of the timestamp logic from VideoSDK's custom track example.
        Ensures frames are paced at ~TARGET_FPS with a valid RTP timestamp.
        """
        VIDEO_PTIME = 1 / TARGET_FPS  # packet time

        if self.readyState != "live":
            raise MediaStreamError("Track is not live")

        if self._timestamp is not None:
            self._timestamp += int(VIDEO_PTIME * VIDEO_CLOCK_RATE)
            wait = self._start + (self._timestamp / VIDEO_CLOCK_RATE) - time.time()
            await asyncio.sleep(max(0, wait))
        else:
            self._start = time.time()
            self._timestamp = 0

        return self._timestamp, VIDEO_TIME_BASE

    async def recv(self) -> VideoFrame:
        """
        Called by VideoSDK when it wants the next frame.
        """
        pts, time_base = await self.next_timestamp()

        ret, frame = self.cap.read()
        if not ret:
            raise MediaStreamError("Failed to read frame from camera")

        # FRAME PROCESSING LAYER
        frame = process_frame(frame)

        # Convert to VideoFrame for VideoSDK
        vf = VideoFrame.from_ndarray(frame, format="bgr24")
        vf.pts = pts
        vf.time_base = time_base
        return vf


# ------------ EVENT HANDLERS (LOGGING ONLY) ------------

class MyMeetingEventHandler(MeetingEventHandler):
    def on_meeting_joined(self, data):
        print("Meeting joined (RobotCamera-OpenCV)")

    def on_meeting_left(self, data):
        print("Meeting left")


class MyParticipantEventHandler(ParticipantEventHandler):
    def __init__(self, participant_id: str):
        super().__init__()
        self.participant_id = participant_id

    def on_stream_enabled(self, stream):
        print(f"[{self.participant_id}] stream enabled: {stream.kind}")

    def on_stream_disabled(self, stream):
        print(f"[{self.participant_id}] stream disabled: {stream.kind}")


# ------------ MAIN ------------

def main():
    if not VIDEOSDK_TOKEN or not MEETING_ID:
        raise RuntimeError("Token or Meeting ID missing from .env")

    # CAMERA SENSOR + DRIVER + OPENCV LAYER
    camera_track = OpenCVCameraTrack(device_index=0)

    # VIDEO SDK CLIENT LAYER
    meeting_config = MeetingConfig(
        meeting_id=MEETING_ID,
        name=NAME,
        mic_enabled=False,
        webcam_enabled=False,             # we are using custom track instead
        token=VIDEOSDK_TOKEN,
        custom_camera_video_track=camera_track,
    )

    meeting = VideoSDK.init_meeting(**meeting_config)

    meeting.add_event_listener(MyMeetingEventHandler())
    meeting.local_participant.add_event_listener(
        MyParticipantEventHandler(participant_id=meeting.local_participant.id)
    )

    print("Joining the meeting with OpenCV camera...")
    meeting.join()
    print("Joined successfully as", NAME)

    print("Event loop running, streaming OpenCV frames. Ctrl+C to stop.")
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("Stopping...")
        try:
            meeting.leave()
        except Exception:
            pass
        loop.stop()
        print("Exited cleanly.")


if __name__ == "__main__":
    main()
