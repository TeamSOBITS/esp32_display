import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from builtin_interfaces.msg import Duration
from sobits_interfaces.action import DisplayControl

class DisplayActionClient(Node):
    def __init__(self):
        super().__init__('display_client')
        self._action_client = ActionClient(
            self,
            DisplayControl,
            'esp32_display'
        )
        self._goal_handle = None

    def send_goal(self, topic_name, file_path, display_time):
        goal_msg = DisplayControl.Goal()
        goal_msg.topic_name = topic_name
        goal_msg.file_path = file_path
        goal_msg.display_time = Duration(sec=int(display_time), nanosec=0)

        self.get_logger().info('Waiting for display action server...')
        self._action_client.wait_for_server()

        self._send_goal_future = self._action_client.send_goal_async(
            goal_msg,
            feedback_callback=self.feedback_callback
        )
        self._send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().info('Goal rejected by server')
            return
        
        self.get_logger().info('Goal accepted')
        self._goal_handle = goal_handle
        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        result = future.result().result
        status = future.result().status

        STATUS_SUCCEEDED = 4
        STATUS_CANCELED = 5

        if status == STATUS_SUCCEEDED:
            self.get_logger().info(f'Goal succeeded: {result.result}')
        elif status == STATUS_CANCELED:
            self.get_logger().info(f'Goal canceled or failed: {result.result}')
        else:
            self.get_logger().info(f'Goal finished with status {status}: {result.result}')
        rclpy.shutdown()

    def feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback
        self.get_logger().info(f'Feedback: {feedback.remaining_time.sec} seconds remaining')
        # try:
        #     remaining = int(feedback.remaining_time.sec)
        #     if remaining == 5 and self._goal_handle is not None:
        #         self.get_logger().info("Remaining is 5 → cancel goal")
        #         self._goal_handle.cancel_goal_async()
        # except ValueError:
        #     pass

def main(args=None):
    rclpy.init(args=args)
    client = DisplayActionClient()

    # topic_name = "/image_raw"
    # file_path = ""

    topic_name = ""
    file_path = "/home/sobits/colcon_ws/src/esp32_display/images/speaker.jpeg"
    
    display_time = int(input("Please enter the number of seconds to draw (integer): "))

    client.send_goal(topic_name, file_path, display_time)
    rclpy.spin(client)

if __name__ == '__main__':
    main()