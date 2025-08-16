import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse
from sobits_interfaces.action import ChatLlmRecognition
from sobits_interfaces.action._text_to_speech import TextToSpeech_FeedbackMessage
from sensor_msgs.msg import Image
from cv_bridge import CvBridge, CvBridgeError
import time
import os
import serial
import cv2
from rclpy.qos import QoSProfile, qos_profile_sensor_data, HistoryPolicy, ReliabilityPolicy
from ament_index_python.packages import get_package_share_directory
import threading
import pulsectl

BAUDRATE = 3000000

class DisplayActionServer(Node):
    def __init__(self):
        super().__init__('display_server')

        # パラメータでのポート宣言を削除
        self.declare_parameter('quality', 30)
        self.declare_parameter('image_hight', 240)
        self.declare_parameter('image_width', 320)

        self.quality = self.get_parameter('quality').get_parameter_value().integer_value
        self.image_hight = self.get_parameter('image_hight').get_parameter_value().integer_value
        self.image_width = self.get_parameter('image_width').get_parameter_value().integer_value

        self.ser = self._connect_to_serial()
        if self.ser is None:
            self.get_logger().error("Could not connect to any serial port.")

        self._action_server = ActionServer(
            self,
            ChatLlmRecognition,
            'esp32_display',
            self.execute_callback,
            cancel_callback=self.cancel_callback
        )
        self.get_logger().info('Display action server is ready')

        self.bridge = CvBridge()
        self.latest_frame = None

        self.is_action_active = False
        self.is_mic_in_use = False
        self.pulse = None
        self.mic_image = None

        self.stop_threads = threading.Event()

        share_dir = get_package_share_directory('esp32_display')
        image_dir = os.path.join(os.path.abspath(os.path.join(share_dir, '..', '..', '..', '..')),
                                 'src', 'esp32_display', 'images')
        os.makedirs(image_dir, exist_ok=True)
        self.mic_image_path = os.path.join(image_dir, 'mic.jpeg')
        self.speaker_image_path = os.path.join(image_dir, 'speaker.jpeg')

        if os.path.exists(self.mic_image_path):
            self.mic_image = cv2.imread(self.mic_image_path)
        else:
            self.get_logger().warn(f"Mic image not found: {self.mic_image_path}")

        if os.path.exists(self.speaker_image_path):
            self.speaker_image = cv2.imread(self.speaker_image_path)
        else:
            self.get_logger().warn(f"Speaker image not found: {self.speaker_image_path}")

        self.is_tts_active = False
        self.last_tts_feedback_time = 0.0
        self.last_remaining_time = -1

        self._feedback_subscription = self.create_subscription(
            TextToSpeech_FeedbackMessage,
            '/speech_word/_action/feedback',
            self.tts_feedback_callback,
            10
        )

        self._setup_mic_monitor()

        self.tts_send_thread = threading.Thread(target=self._tts_send_loop, daemon=True)
        self.tts_send_thread.start()

    def _connect_to_serial(self):
        # 試行するポートのリストを内部的に定義
        ports_to_try = ['/dev/esp32_board_a', '/dev/esp32_board_b']
        for port in ports_to_try:
            try:
                self.get_logger().info(f"Trying to connect to serial port {port}...")
                ser = serial.Serial(port, BAUDRATE, timeout=1)
                self.get_logger().info(f"Connected to serial port {port}.")
                return ser
            except serial.SerialException as e:
                self.get_logger().warn(f"Could not connect to {port}: {e}")
        return None

    def __del__(self):
        self.stop_threads.set()
        try:
            if hasattr(self, 'pulse_thread') and self.pulse_thread.is_alive():
                self.pulse.event_listen_stop()
                self.pulse_thread.join()
            if hasattr(self, 'mic_send_thread') and self.mic_send_thread.is_alive():
                self.mic_send_thread.join()
            if hasattr(self, 'tts_send_thread') and self.tts_send_thread.is_alive():
                self.tts_send_thread.join()
        except Exception:
            pass

    def tts_feedback_callback(self, msg: TextToSpeech_FeedbackMessage):
        if not self.is_action_active:
            self.is_tts_active = True
            self.last_tts_feedback_time = time.time()
            fb = msg.feedback
            self.last_remaining_time = fb.remaining_time
            goal_id_bytes = bytes(msg.goal_id.uuid)
            goal_id_hex = goal_id_bytes.hex()
            self.get_logger().info(
                f"[TTS] Remaining time={fb.remaining_time:.2f}s"
            )

    def _tts_send_loop(self):
        while not self.stop_threads.is_set():
            if self.is_tts_active and not self.is_action_active:
                if (time.time() - self.last_tts_feedback_time > 0.6) or (self.last_remaining_time == 0):
                    self.is_tts_active = False
                elif self.speaker_image is not None and self.ser is not None:
                    self._send_image_data(self.speaker_image, self.quality)
                    time.sleep(0.5)
                    continue
            time.sleep(0.1)

    def _setup_mic_monitor(self):
        try:
            self.pulse = pulsectl.Pulse('mic-monitor')
            self.pulse_thread = threading.Thread(target=self._start_pulse_listener, daemon=True)
            self.pulse_thread.start()
        except Exception as e:
            self.get_logger().error(f"PulseAudio monitor start failed: {e}")
        self.mic_send_thread = threading.Thread(target=self._mic_send_loop, daemon=True)
        self.mic_send_thread.start()

    def _start_pulse_listener(self):
        self.pulse.event_mask_set('source_output')
        self.pulse.event_callback_set(self.on_source_output_event_with_send)
        try:
            self.pulse.event_listen(timeout=None)
        except Exception:
            pass

    def _mic_send_loop(self):
        while not self.stop_threads.is_set():
            if self.is_mic_in_use and not self.is_action_active:
                if self.mic_image is not None and self.ser is not None:
                    self._send_image_data(self.mic_image, self.quality)
            time.sleep(0.5)

    def on_source_output_event_with_send(self, event):
        if event.t == 'new':
            self.is_mic_in_use = True
            self.get_logger().info("➡️ Default microphone is now in use!")
        elif event.t == 'remove':
            self.is_mic_in_use = False
            self.get_logger().info(f"Input stream removed: ID={event.index}")

    def _send_image_data(self, frame, quality):
        try:
            resized_frame = cv2.resize(frame, (self.image_width, self.image_hight))
            rotated_frame = cv2.rotate(resized_frame, cv2.ROTATE_90_CLOCKWISE)
            result_flag, img_encoded = cv2.imencode('.jpg', rotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
            if not result_flag:
                return False
            img_buf = img_encoded.tobytes()
            img_size = len(img_buf)
            img_size1 = (img_size >> 16) & 0xFF
            img_size2 = (img_size >> 8) & 0xFF
            img_size3 = img_size & 0xFF
            data_packet = bytearray([0xFF, 0xD8, 0xEA, 0x01, img_size1, img_size2, img_size3, 0x00, 0x00, 0x00])
            full_data = data_packet + img_buf
            self.ser.write(full_data)
            return True
        except Exception:
            return False
            
    def _get_topic_qos_profile(self, topic_name):
        try:
            publishers_info = self.get_publishers_info_by_topic(topic_name)
            
            if not publishers_info:
                self.get_logger().warn(f"No publishers found for topic '{topic_name}'. Using default QoS profile.")
                return qos_profile_sensor_data

            qos_profile = publishers_info[0].qos_profile
            self.get_logger().info(f"Obtained QoS profile for topic '{topic_name}'.")

            history_policy = "KEEP_LAST" if qos_profile.history == HistoryPolicy.KEEP_LAST else "KEEP_ALL"
            reliability_policy = "RELIABLE" if qos_profile.reliability == ReliabilityPolicy.RELIABLE else "BEST_EFFORT"
            self.get_logger().info(f"  - History: {history_policy}")
            self.get_logger().info(f"  - Reliability: {reliability_policy}")

            return qos_profile
        
        except Exception as e:
            self.get_logger().error(f"Error while getting QoS profile: {e}")
            return qos_profile_sensor_data

    def execute_callback(self, goal_handle):
        self.get_logger().info('Executing goal...')
        self.is_action_active = True
        file_path = goal_handle.request.request
        seconds_str = goal_handle.request.model_name
        topic_name = goal_handle.request.room_name

        if self.ser is None:
            self.is_action_active = False
            result = ChatLlmRecognition.Result()
            result.result = "Serial port not available."
            goal_handle.abort()
            return result

        try:
            total_seconds = int(float(seconds_str))
            if total_seconds <= 0:
                raise ValueError
        except Exception:
            self.is_action_active = False
            result = ChatLlmRecognition.Result()
            result.result = f"Invalid seconds: {seconds_str}"
            goal_handle.abort()
            return result

        try:
            if not file_path and topic_name:
                self.get_logger().info(f"Subscribing to topic: {topic_name}")
                sub_qos_profile = self._get_topic_qos_profile(topic_name)
                sub = self.create_subscription(
                    Image, topic_name, self._image_callback, sub_qos_profile
                )
                frame_getter = lambda: self.latest_frame
                result = self._execute_common_loop(goal_handle, frame_getter, total_seconds)
                self.destroy_subscription(sub)
                return result
            elif file_path:
                if not os.path.exists(file_path):
                    raise FileNotFoundError
                frame = cv2.imread(file_path)
                if frame is None:
                    raise FileNotFoundError
                result = self._execute_common_loop(goal_handle, frame, total_seconds)
                return result
        finally:
            self.is_action_active = False
            self.is_tts_active = False

    def cancel_callback(self, goal_handle):
        self.get_logger().info('Received cancel request')
        return CancelResponse.ACCEPT

    def _execute_common_loop(self, goal_handle, frame_getter, total_seconds):
        start_time = time.time()
        last_feedback_time = start_time
        
        while time.time() - start_time < total_seconds:
            rclpy.spin_once(self, timeout_sec=0.01)
            
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                result = ChatLlmRecognition.Result()
                result.result = "Goal canceled"
                return result

            if callable(frame_getter):
                frame = self.latest_frame
                if frame is not None:
                    if not self._send_image_data(frame, self.quality):
                        goal_handle.abort()
                        result = ChatLlmRecognition.Result()
                        result.result = "Failed to send image"
                        return result
                    self.latest_frame = None
            else:
                frame = frame_getter
                if not self._send_image_data(frame, self.quality):
                    goal_handle.abort()
                    result = ChatLlmRecognition.Result()
                    result.result = "Failed to send image"
                    return result

            # 1秒ごとにフィードバックを送信
            current_time = time.time()
            if current_time - last_feedback_time >= 1.0:
                last_feedback_time = current_time
                
                # 残り時間を計算
                elapsed_time = current_time - start_time
                remaining_time = max(0, total_seconds - elapsed_time)
                
                feedback = ChatLlmRecognition.Feedback()
                # wip_result フィールドを使って残り秒数を文字列として送信
                feedback.wip_result = f"Remaining seconds: {int(remaining_time)}"
                self.get_logger().info(f"Publishing feedback: {feedback.wip_result}")
                goal_handle.publish_feedback(feedback)

        goal_handle.succeed()
        result = ChatLlmRecognition.Result()
        result.result = "Successed"
        return result

    def _image_callback(self, msg):
        try:
            self.latest_frame = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        except CvBridgeError as e:
            self.get_logger().error(f"CvBridgeError: {e}")

def main(args=None):
    rclpy.init(args=args)
    server = DisplayActionServer()
    try:
        while rclpy.ok():
            rclpy.spin_once(server)
    finally:
        server.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()