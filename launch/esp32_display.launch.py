from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='esp32_display',
            executable='display_server',
            name='display_server_node',
            output='screen',
            emulate_tty=True,
            parameters=[{
                'quality': 30,
                'image_hight': 240,
                'image_width': 320
            }]
        ),
    ])