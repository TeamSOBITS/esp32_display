import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse
from sobits_interfaces.action import ChatLlmRecognition
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

        self.declare_parameter('port', '/dev/ttyACM0')
        self.declare_parameter('quality', 30)
        self.declare_parameter('image_hight', 240)
        self.declare_parameter('image_width', 320)        

        self.port = self.get_parameter('port').get_parameter_value().string_value
        self.quality = self.get_parameter('quality').get_parameter_value().integer_value
        self.image_hight = self.get_parameter('image_hight').get_parameter_value().integer_value
        self.image_width = self.get_parameter('image_width').get_parameter_value().integer_value

        share_dir = get_package_share_directory('esp32_display')
        mic_image_dir = os.path.join(os.path.abspath(os.path.join(share_dir, '..', '..', '..', '..')),
                                        'src', 'esp32_display', 'images')
        os.makedirs(mic_image_dir, exist_ok=True)
        self.mic_image_path = os.path.join(mic_image_dir, 'mic.jpeg')

        self.ser = None
        try:
            self.ser = serial.Serial(self.port, BAUDRATE, timeout=1)
            self.get_logger().info(f"Connected to serial port {self.port}.")
        except serial.SerialException as e:
            self.get_logger().error(f"Could not connect to serial port: {e}")

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
        
        # スレッドの停止フラグ
        self.stop_threads = threading.Event()
        
        self._setup_mic_monitor()

    def __del__(self):
        # オブジェクトが破棄されるときにスレッドを安全に停止
        self.stop_threads.set()
        if self.pulse_thread.is_alive():
            self.pulse.event_listen_stop()
            self.pulse_thread.join()
        if self.mic_send_thread.is_alive():
            self.mic_send_thread.join()

    def _setup_mic_monitor(self):
        # マイク画像の事前読み込み
        if not os.path.exists(self.mic_image_path):
            self.get_logger().error(f"Mic image not found at: {self.mic_image_path}")
        else:
            self.mic_image = cv2.imread(self.mic_image_path)
            if self.mic_image is None:
                self.get_logger().error(f"Failed to load mic image: {self.mic_image_path}")
        
        # PulseAudioのイベントリスナーを別スレッドで開始
        try:
            self.pulse = pulsectl.Pulse('mic-monitor')
            self.pulse_thread = threading.Thread(target=self._start_pulse_listener, daemon=True)
            self.pulse_thread.start()
            self.get_logger().info("Started PulseAudio monitor thread.")
        except Exception as e:
            self.get_logger().error(f"Could not start PulseAudio monitor: {e}")
            
        # マイクの使用状況に応じた画像送信ループを別スレッドで開始
        self.mic_send_thread = threading.Thread(target=self._mic_send_loop, daemon=True)
        self.mic_send_thread.start()
        self.get_logger().info("Started mic image sending thread.")

    def _start_pulse_listener(self):
        self.pulse.event_mask_set('source_output')
        self.pulse.event_callback_set(self.on_source_output_event_with_send)
        try:
            # stop_threadsが設定されるまでイベントリスナーをブロックする
            self.pulse.event_listen(timeout=None)
        except pulsectl.PulseError:
            pass
        except Exception as e:
            self.get_logger().error(f"Error in PulseAudio event listener: {e}")

    def _mic_send_loop(self):
        while not self.stop_threads.is_set():
            if self.is_mic_in_use and not self.is_action_active:
                if self.mic_image is not None and self.ser is not None:
                    # 画像の送信
                    if not self._send_image_data(self.mic_image, self.quality):
                        self.get_logger().error("Failed to send mic image during loop.")
            
            # 1秒ごとにループ
            time.sleep(1.0)
            
    def on_source_output_event_with_send(self, event):
        """
        マイクイベントが発生したときに呼び出される。
        フラグを更新するのみで、画像送信は_mic_send_loopで行う。
        """
        if event.t == 'new':
            self.is_mic_in_use = True
            self.get_logger().info("➡️ デフォルトマイクが使用され始めました！")
        
        elif event.t == 'remove':
            self.is_mic_in_use = False
            self.get_logger().info("入力ストリームが削除されました: ID=%d" % event.index)
            # 必要であれば、マイク使用終了時の処理を追加

    def _handle_abort(self, goal_handle, message):
        self.get_logger().error(message)
        goal_handle.abort()
        result = ChatLlmRecognition.Result()
        result.result = message
        return result

    def _image_callback(self, msg):
        try:
            self.latest_frame = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        except CvBridgeError as e:
            self.get_logger().error(f"CvBridgeError: {e}")

    def _handle_goal_state(self, goal_handle):
        if goal_handle.is_cancel_requested:
            self.get_logger().info('Goal canceled by client request')
            goal_handle.canceled()
            result = ChatLlmRecognition.Result()
            result.result = "Goal canceled by client request"
            return True, result
        return False, None

    def _send_feedback(self, goal_handle, start_time, total_seconds):
        current_time = time.time()
        elapsed_time = current_time - start_time
        remaining_time = max(0, total_seconds - int(elapsed_time))
        
        feedback = ChatLlmRecognition.Feedback()
        feedback.wip_result = str(remaining_time)
        goal_handle.publish_feedback(feedback)
        self.get_logger().info(f'Publishing feedback: {feedback.wip_result}')
        
        return current_time

    def _send_image_data(self, frame, quality):
        try:
            resized_frame = cv2.resize(frame, (self.image_width, self.image_hight))
            rotated_frame = cv2.rotate(resized_frame, cv2.ROTATE_90_CLOCKWISE)

            result_flag, img_encoded = cv2.imencode('.jpg', rotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
            if not result_flag:
                self.get_logger().error("Failed to compress image to JPEG.")
                return False
            
            img_buf = img_encoded.tobytes()
            img_size = len(img_buf)

            img_size1 = (img_size >> 16) & 0xFF
            img_size2 = (img_size >> 8) & 0xFF
            img_size3 = img_size & 0xFF
            data_packet = bytearray([0xFF, 0xD8, 0xEA, 0x01, img_size1, img_size2, img_size3, 0x00, 0x00, 0x00])
            
            full_data = data_packet + img_buf
            
            self.ser.write(full_data)
            self.get_logger().debug(f"Sent image data ({img_size} bytes).")
            return True
            
        except serial.SerialTimeoutException:
            self.get_logger().error("Serial write timeout.")
            return False
        except CvBridgeError as e:
            self.get_logger().error(f"CvBridgeError: {e}")
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

    def _execute_common_loop(self, goal_handle, frame_getter, total_seconds):
        start_time = time.time()
        last_feedback_time = start_time

        while time.time() - start_time < total_seconds:
            is_cancelled, result = self._handle_goal_state(goal_handle)
            if is_cancelled:
                return result
            rclpy.spin_once(self, timeout_sec=0.01)

            if callable(frame_getter):
                frame = self.latest_frame
                if frame is not None:
                    if not self._send_image_data(frame, self.quality):
                        return self._handle_abort(goal_handle, "Failed to send image data.")
                    self.latest_frame = None
            else:
                frame = frame_getter
                if not self._send_image_data(frame, self.quality):
                    return self._handle_abort(goal_handle, "Failed to send image data.")

            if time.time() - last_feedback_time >= 1.0:
                last_feedback_time = self._send_feedback(goal_handle, start_time, total_seconds)
        
        goal_handle.succeed()
        self.get_logger().info('Goal succeeded!')
        result = ChatLlmRecognition.Result()
        result.result = "Successed"
        return result
    
    def execute_callback(self, goal_handle):
        self.get_logger().info('Executing goal...')
        self.is_action_active = True

        file_path = goal_handle.request.request
        seconds_str = goal_handle.request.model_name
        topic_name = goal_handle.request.room_name

        if self.ser is None:
            self.is_action_active = False
            return self._handle_abort(goal_handle, "Serial port not available.")

        try:
            total_seconds = int(float(seconds_str))
            if total_seconds <= 0:
                self.is_action_active = False
                return self._handle_abort(goal_handle, f"Invalid seconds: {total_seconds} <= 0")
        except (ValueError, TypeError):
            self.is_action_active = False
            return self._handle_abort(goal_handle, f"Invalid seconds: {seconds_str}")

        if not file_path and topic_name:
            self.get_logger().info(f"Subscribing to topic: {topic_name}")
            
            sub_qos_profile = self._get_topic_qos_profile(topic_name)
            sub = self.create_subscription(
                Image,
                topic_name,
                self._image_callback,
                sub_qos_profile
            )
            
            frame_getter = lambda: self.latest_frame
            result = self._execute_common_loop(goal_handle, frame_getter, total_seconds)
            
            self.destroy_subscription(sub)
            self.is_action_active = False
            return result

        elif file_path:
            if not os.path.exists(file_path):
                self.is_action_active = False
                return self._handle_abort(goal_handle, f"Invalid file path: {file_path}")

            frame = cv2.imread(file_path)
            if frame is None:
                self.is_action_active = False
                return self._handle_abort(goal_handle, f"Failed to load image: {file_path}")

            result = self._execute_common_loop(goal_handle, frame, total_seconds)
            self.is_action_active = False
            return result
        
        else:
            self.is_action_active = False
            return self._handle_abort(goal_handle, "Either file_path or topic_name must be provided.")

    def cancel_callback(self, goal_handle):
        self.get_logger().info('Received cancel request')
        return CancelResponse.ACCEPT

def main(args=None):
    rclpy.init(args=args)
    server = DisplayActionServer()
    while rclpy.ok():
        rclpy.spin_once(server)
    server.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()