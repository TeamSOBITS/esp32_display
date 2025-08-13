import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse
from sobits_interfaces.action import ChatLlmRecognition
import time

class DisplayActionServer(Node):
    def __init__(self):
        super().__init__('display_server')
        self._action_server = ActionServer(
            self,                               # ノードインスタンス
            ChatLlmRecognition,                 # アクションインターフェース
            'esp32_display',                    # アクション名
            self.execute_callback,              # ゴールの実行時に呼ばれるコールバック関数
            cancel_callback=self.cancel_callback # キャンセルリクエスト時に呼ばれるコールバック関数
        )
        self.get_logger().info('Display action server is ready')

    def execute_callback(self, goal_handle):
        self.get_logger().info('Executing goal...')

        topic_name = goal_handle.request.room_name
        file_path = goal_handle.request.request
        seconds = goal_handle.request.model_name

        # secondsを整数に変換する
        try:
            seconds = int(float(seconds))
        except ValueError:
            # 変換に失敗した場合はエラーログを出力し、ゴールを中断
            self.get_logger().error(f"Invalid seconds: {seconds}")
            goal_handle.abort()
            result = ChatLlmRecognition.Result()
            result.result = "Invalid seconds: not a number"
            return result

        # secondsが0以下の場合はゴールを中断
        if seconds <= 0:
            self.get_logger().info('seconds <= 0, aborting goal')
            goal_handle.abort()
            result = ChatLlmRecognition.Result()
            result.result = "Invalid seconds: <= 0"
            return result
        #
        #
        #
        #            
        #kokode syori
        #
        #
        #
        #

        # フィードバックメッセージを作成
        feedback = ChatLlmRecognition.Feedback()

        # secondsの回数だけループ
        for i in range(seconds):
            # サーバーの処理を一度だけ実行し、キャンセルリクエストをチェック
            rclpy.spin_once(self, timeout_sec=1.0)
            
            # キャンセルリクエストがあるか確認
            if goal_handle.is_cancel_requested:
                self.get_logger().info('Goal canceled during execution')
                # ゴールをキャンセル済みに設定
                goal_handle.canceled()
                result = ChatLlmRecognition.Result()
                result.result = "Goal canceled by client request"
                return result

            # フィードバックメッセージを更新
            feedback.wip_result = f"{seconds - i}"
            goal_handle.publish_feedback(feedback)
            self.get_logger().info(f'Publishing feedback: {feedback.wip_result}')

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
    while True:
      rclpy.spin_once(server)
    rclpy.shutdown()
if __name__ == '__main__':
    main()