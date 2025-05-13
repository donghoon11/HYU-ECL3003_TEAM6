from .camera import Camera
import atexit
import cv2
import numpy as np
import threading
import traitlets
import os
import glob


class CSICamera(Camera):

    capture_device = traitlets.Integer(default_value=0)
    capture_fps = traitlets.Integer(default_value=30)
    capture_width = traitlets.Integer(default_value=640)
    capture_height = traitlets.Integer(default_value=480)
    downsample = traitlets.Integer(default_value=1)
    save_video = traitlets.Bool(default_value=True)
    video_base_name = traitlets.Unicode(
        default_value="output"
    )  # 기본 이름, 확장자는 자동

    def __init__(self, *args, **kwargs):
        super(CSICamera, self).__init__(*args, **kwargs)
        self.downsample = self.downsample or kwargs.get("downsample")
        self.capture_fps = self.capture_fps or kwargs.get("capture_fps")
        self.capture_width = self.capture_width or kwargs.get("capture_width")
        self.capture_height = self.capture_height or kwargs.get("capture_height")
        self.save_video = kwargs.get("save_video", self.save_video)
        self.video_base_name = kwargs.get("video_base_name", self.video_base_name)

        self.width = self.capture_width // self.downsample
        self.height = self.capture_height // self.downsample

        try:
            self.cap = cv2.VideoCapture(self._gst_str(), cv2.CAP_GSTREAMER)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if self.save_video:
                self.video_filename = self._get_next_video_filename()
                fourcc = cv2.VideoWriter_fourcc(*"XVID")
                self.video_writer = cv2.VideoWriter(
                    self.video_filename,
                    fourcc,
                    self.capture_fps,
                    (self.width, self.height),
                )
                atexit.register(self._release_video_writer)

            atexit.register(self.cap.release)
        except:
            raise RuntimeError("Could not initialize camera. Please see error trace.")

    def _gst_str(self):
        return (
            "nvarguscamerasrc sensor-id=%d ! "
            "video/x-raw(memory:NVMM), width=(int)%d, height=(int)%d, format=(string)NV12, framerate=(fraction)%d/1 ! "
            "nvvidconv ! "
            "video/x-raw, format=(string)BGRx ! "
            "videoconvert ! "
            "video/x-raw, format=(string)BGR ! "
            "appsink max-buffers=1 drop=True"
            % (
                self.capture_device,
                self.capture_width,
                self.capture_height,
                self.capture_fps,
            )
        )

    def _read(self):
        ret, image = self.cap.read()
        if not ret:
            raise RuntimeError("Could not read image from camera")

        if self.downsample > 1:
            image = cv2.resize(image, (self.width, self.height))

        if (
            self.save_video
            and hasattr(self, "video_writer")
            and self.video_writer.isOpened()
        ):
            self.video_writer.write(image)

        return image

    def _release_video_writer(self):
        if hasattr(self, "video_writer") and self.video_writer.isOpened():
            self.video_writer.release()

    def _get_next_video_filename(self):
        """output_0.avi, output_1.avi, ... 형식으로 다음 저장 파일명 반환"""
        base = self.video_base_name
        existing = glob.glob(f"{base}_*.avi")
        existing_nums = [
            int(os.path.splitext(f)[0].replace(f"{base}_", ""))
            for f in existing
            if f.replace(f"{base}_", "").split(".")[0].isdigit()
        ]
        next_num = max(existing_nums, default=-1) + 1
        return f"{base}_{next_num}.avi"
