#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cv2
import serial
import time
import numpy as np

class ImageSender:
    def __init__(self, port, baudrate, width=320, height=240, quality=30):
        """
        カメラ映像をシリアルポート経由で送信するクラス
        Args:
            port (str): シリアルポート名 (例: '/dev/ttyUSB0')
            baudrate (int): 通信速度 (例: 3000000)
            width (int): カメラ画像の幅
            height (int): カメラ画像の高さ
            quality (int): JPEG圧縮品質 (0-100)
        """
        # シリアルポートの設定
        try:
            self.ser = serial.Serial(port, baudrate)
            print(f"シリアルポート {port} に接続しました。")
        except serial.SerialException as e:
            print(f"シリアルポートに接続できませんでした: {e}")
            self.ser = None
            
        # カメラの設定
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("カメラを開けませんでした。")
        else:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            print("カメラを開きました。")
        
        self.quality = quality
    
    def send_image(self, img):
        """
        JPEG圧縮された画像をシリアルポートに送信します
        Args:
            img (np.ndarray): 送信する画像データ
        """
        if self.ser is None:
            return

        # Jpeg圧縮
        result, img_encoded = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), self.quality])
        if not result:
            print("JPEG圧縮に失敗しました。")
            return
            
        img_buf = img_encoded.tobytes()
        
        # 画像サイズの取得
        img_size = len(img_buf)
        
        # Packetヘッダの作成
        # 0xFF, 0xD8: JPEGの開始マーカー
        # 0xEA, 0x01: オリジナルのパケットマーカー
        img_size1 = (img_size & 0xFF0000) >> 16
        img_size2 = (img_size & 0x00FF00) >> 8
        img_size3 = (img_size & 0x0000FF)
        data_packet = bytearray([0xFF, 0xD8, 0xEA, 0x01, img_size1, img_size2, img_size3, 0x00, 0x00, 0x00])
        
        # Packetヘッダと画像データの送信
        try:
            self.ser.write(data_packet)
            self.ser.write(img_buf)
        except serial.SerialTimeoutException:
            print("シリアル送信がタイムアウトしました。")

    def run(self, delay=0.08):
        """
        カメラ映像の取得、回転、表示、送信をループで実行します
        Args:
            delay (float): フレーム間の遅延時間（秒）
        """
        if not self.cap.isOpened():
            print("カメラが利用できないため、実行できません。")
            return

        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("フレームを取得できませんでした。")
                break
            
            # --- 修正点: ここに画像の回転処理を追加します ---
            # cv2.rotate() を使用して、画像を時計回りに90度回転させます
            rotated_frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            
            # 画像を表示
            cv2.imshow('Camera Feed', rotated_frame)
            
            # 回転したフレームを送信
            self.send_image(rotated_frame)
            
            # --- 修正点ここまで ---
            
            # 'q'キーで終了
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            time.sleep(delay)

    def close(self):
        """
        リソースを解放します
        """
        if self.cap.isOpened():
            self.cap.release()
            print("カメラを解放しました。")
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("シリアルポートを閉じました。")
        cv2.destroyAllWindows()  # すべてのOpenCVウィンドウを閉じる

if __name__ == '__main__':
    sender = ImageSender('/dev/ttyACM0', 3000000)
    try:
        sender.run()
    except KeyboardInterrupt:
        print("ユーザーによって中断されました。")
    finally:
        sender.close()
