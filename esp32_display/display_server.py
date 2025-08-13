import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse
from sobits_interfaces.action import ChatLlmRecognition
import time
import os
import serial
import re
import cv2

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

        self.ser = None
        try:
            self.ser = serial.Serial(self.port, BAUDRATE, timeout=1)
            self.get_logger().info(f"シリアルポート {self.port} に接続しました。")
        except serial.SerialException as e:
            self.get_logger().error(f"シリアルポートに接続できませんでした: {e}")

        self._action_server = ActionServer(
            self,
            ChatLlmRecognition,
            'esp32_display',
            self.execute_callback,
            cancel_callback=self.cancel_callback
        )
        self.get_logger().info('Display action server is ready')

    def _handle_abort(self, goal_handle, message):
        """アボート処理を共通化するためのヘルパー関数"""
        self.get_logger().error(message)
        goal_handle.abort()
        result = ChatLlmRecognition.Result()
        result.result = message
        return result

    def execute_callback(self, goal_handle):
        self.get_logger().info('Executing goal...')

        file_path = goal_handle.request.request
        seconds_str = goal_handle.request.model_name
        topic_name = goal_handle.request.room_name  #絶対に消すな

        if self.ser is None:
            return self._handle_abort(goal_handle, "Serial port not available.")

        try:
            total_seconds = int(float(seconds_str))
        except (ValueError, TypeError):
            return self._handle_abort(goal_handle, f"Invalid seconds: {seconds_str}")

        if total_seconds <= 0:
            return self._handle_abort(goal_handle, f"Invalid seconds: {total_seconds} <= 0")

        if not file_path or not os.path.exists(file_path):
            return self._handle_abort(goal_handle, f"Invalid file path: {file_path}")

        frame = cv2.imread(file_path)
        if frame is None:
            return self._handle_abort(goal_handle, f"Failed to load image: {file_path}")

        # 画像処理をループの外に移動して一度だけ実行
        resized_frame = cv2.resize(frame, (self.image_width, self.image_hight))
        rotated_frame = cv2.rotate(resized_frame, cv2.ROTATE_90_CLOCKWISE)

        # ここを修正しました: cv2.IMWRITE_JPEG_QUALITY を使用
        result_flag, img_encoded = cv2.imencode('.jpg', rotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.quality])
        if not result_flag:
            return self._handle_abort(goal_handle, "JPEG compression failed.")

        img_buf = img_encoded.tobytes()
        img_size = len(img_buf)

        img_size1 = (img_size >> 16) & 0xFF
        img_size2 = (img_size >> 8) & 0xFF
        img_size3 = img_size & 0xFF
        data_packet = bytearray([0xFF, 0xD8, 0xEA, 0x01, img_size1, img_size2, img_size3, 0x00, 0x00, 0x00])

        # 改善点: ヘッダーと画像データを結合して一度に送信
        full_data = data_packet + img_buf

        start_time = time.time()
        last_feedback_time = start_time

        while True:
            # キャンセルリクエストのチェック
            if goal_handle.is_cancel_requested:
                self.get_logger().info('Goal canceled during execution')
                goal_handle.canceled()
                result = ChatLlmRecognition.Result()
                result.result = "Goal canceled by client request"
                return result

            # 画像データの送信
            try:
                self.ser.write(full_data)
                self.get_logger().debug(f"画像データ ({img_size} bytes) を送信しました。")
            except serial.SerialTimeoutException:
                return self._handle_abort(goal_handle, "Serial write timeout.")

            current_time = time.time()
            elapsed_time = current_time - start_time

            # 1秒ごとにフィードバックを送信
            if current_time - last_feedback_time >= 1.0:
                feedback = ChatLlmRecognition.Feedback()
                remaining_time = max(0, total_seconds - int(elapsed_time))
                feedback.wip_result = str(remaining_time)
                goal_handle.publish_feedback(feedback)
                self.get_logger().info(f'Publishing feedback: {feedback.wip_result}')
                last_feedback_time = current_time

            # 指定された時間が経過したらループを終了
            if elapsed_time >= total_seconds:
                break
            
            # 0.08秒の周期を保つための待機
            time.sleep(0.08)

        goal_handle.succeed()
        self.get_logger().info('Goal succeeded!')
        result = ChatLlmRecognition.Result()
        result.result = "Successed"
        return result

    def cancel_callback(self, goal_handle):
        self.get_logger().info('Received cancel request')
        return CancelResponse.ACCEPT

def main(args=None):
    rclpy.init(args=args)
    server = DisplayActionServer()
    while rclpy.ok():
        rclpy.spin_once(server) #絶対に消すな
    server.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
