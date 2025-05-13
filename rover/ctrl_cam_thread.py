import time
import threading
from pynput import keyboard
from base_ctrl import BaseController

from IPython.display import display, Image
import ipywidgets as widgets
import threading

from jetcam.utils import bgr8_to_jpeg

from jetcam.csi_camera import CSICamera


class UGVKeyboardController:
    MAX_STEER = 0.8
    MAX_SPEED = 0.5
    STEP_STEER = 0.2
    STEP_SPEED = 0.05

    def __init__(self, port='/dev/ttyUSB0', baudrate=115200, update_interval=0.1):
        self.base = BaseController(port, baudrate)
        self.steering = 0.0
        self.speed = 0.0
        self.pressed_keys = set()
        self.last_update_time = 0
        self.update_interval = update_interval
        self.running = False
        self.listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)

    def _clip(self, val, max_val):
        return max(min(val, max_val), -max_val)

    def _send_control_async(self, L, R):
        def worker():
            self.base.base_json_ctrl({"T": 1, "L": L, "R": R})
        threading.Thread(target=worker).start()

    def _update_vehicle_motion(self):
        steer_val = self._clip(self.steering, self.MAX_STEER)
        speed_val = self._clip(self.speed, self.MAX_STEER)

        base_speed = abs(speed_val)
        left_ratio = max(0.0, 1.0 - steer_val)
        right_ratio = max(0.0, 1.0 + steer_val)

        L = base_speed * left_ratio
        R = base_speed * right_ratio

        L = self._clip(L, self.MAX_SPEED)
        R = self._clip(R, self.MAX_SPEED)

        if self.speed < 0:
            L, R = -L, -R

        self._send_control_async(-L, -R)
        print(f"[UGV] Speed: {speed_val:.2f}, Steering: {steer_val:.2f} → L: {L:.2f}, R: {R:.2f}")

    def _on_press(self, key):
        try:
            self.pressed_keys.add(key.char)
        except AttributeError:
            pass

    def _on_release(self, key):
        try:
            self.pressed_keys.discard(key.char)
            if key.char == 'q':
                self.running = False  # Stop main loop
                return False
        except AttributeError:
            pass

    def start(self):
        print("[UGV] Starting keyboard control. Press 'q' to quit.")
        self.listener.start()
        self.running = True

        try:
            while self.running and self.listener.running:
                now = time.time()
                if (now - self.last_update_time) >= self.update_interval:
                    if 'w' in self.pressed_keys:
                        self.speed += self.STEP_SPEED
                    elif 's' in self.pressed_keys:
                        self.speed -= self.STEP_SPEED
                    else:
                        self.speed *= 0.9

                    if 'a' in self.pressed_keys:
                        self.steering -= self.STEP_STEER
                    elif 'd' in self.pressed_keys:
                        self.steering += self.STEP_STEER
                    else:
                        self.steering *= 0.5

                    self._update_vehicle_motion()
                    self.last_update_time = now

                time.sleep(0.01)

        except KeyboardInterrupt:
            print("\n[UGV] Interrupted by user.")

        finally:
            self.base.base_json_ctrl({"T": 1, "L": 0.0, "R": 0.0})
            print("[UGV] Stopped and motors released.")

class CameraStreamer:
    def __init__(self,
                 capture_width=1280,
                 capture_height=720,
                 downsample=2,
                 capture_fps=30,
                 save_video=False,
                 video_base_name='output'):
        
        self.camera = CSICamera(
            capture_width=capture_width,
            capture_height=capture_height,
            downsample=downsample,
            capture_fps=capture_fps,
            save_video=save_video,
            video_base_name=video_base_name
        )

        self.stop_button = widgets.Checkbox(
            value=False,
            description='Streaming',
            disabled=False,
            indent=False,
        )

        self.thread = None
        self.running = False

    def _stream_loop(self):
        frame = self.camera.read()
        display_handle = display(Image(data=bgr8_to_jpeg(frame)), display_id=True)

        while self.running:
            if self.stop_button.value:
                frame = self.camera.read()
                display_handle.update(Image(data=bgr8_to_jpeg(frame)))

    def start(self):
        display(self.stop_button)
        self.running = True
        self.thread = threading.Thread(target=self._stream_loop)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        self.camera.release()

streamer = CameraStreamer(
    capture_width=1280,
    capture_height=720,
    downsample=2,
    capture_fps=30,
    save_video=True,
    video_base_name='my_recording'
)

streamer.start()


def run_ugv_controller():
    ugv_controller = UGVKeyboardController('/dev/ttyUSB0', 115200)
    ugv_controller.start()


def run_camera_streamer():
    camera_streamer = CameraStreamer(
        capture_width=1280,
        capture_height=720,
        downsample=2,
        capture_fps=30,
        save_video=True,
        video_base_name='my_recording'
    )
    camera_streamer.start()


if __name__ == "__main__":
    # 스레드 생성
    ugv_thread = threading.Thread(target=run_ugv_controller)
    cam_thread = threading.Thread(target=run_camera_streamer)

    # 스레드 시작
    ugv_thread.start()
    cam_thread.start()

    # 메인 스레드는 UGV 쓰레드가 종료될 때까지 대기
    ugv_thread.join()
    print("[Main] UGV 조작 종료됨. 카메라 녹화도 중지합니다.")
