<a name="readme-top"></a>

[JA](README.md) | [EN](README.en.md)

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![License][license-shield]][license-url]

# ESP32 Display

<!-- 目次 -->
<details>
  <summary>目次</summary>
  <ol>
    <li>
      <a href="#概要">概要</a>
    </li>
    <li>
      <a href="#環境構築">環境構築</a>
      <ul>
        <li><a href="#環境条件">環境条件</a></li>
        <li><a href="#インストール方法">インストール方法</a></li>
      </ul>
    </li>
    <li><a href="#実行操作方法">実行・操作方法</a></li>
    <li><a href="#パラメータ">パラメータ</a></li>
    <li><a href="#マイルストーン">マイルストーン</a></li>
    <li><a href="#参考文献">参考文献</a></li>
  </ol>
</details>


<!-- レポジトリの概要 -->
## 概要

本リポジトリは[SOBIT MINI
](https://github.com/TeamSOBITS/sobit_mini)と
[SOBIT LIGHT
](https://github.com/TeamSOBITS/sobit_light)の頭部に搭載されているディスプレイの制御を行うものです．

非通信時は目のまばたきが表示され，通信時は任意の画像を任意のときに任意の時間だけ表示可能になります．

また，TTSとSTTの使用を自動で検知し，使用している間スピーカーやマイクの画像を表示します．


<p align="right">(<a href="#readme-top">上に戻る</a>)</p>


<!-- 環境構築 -->
## 環境構築

ここで，本レポジトリのセットアップ方法について説明します．

### 環境条件

まず，以下の環境を整えてから，次のインストール段階に進んでください．

| System  | Version |
| ------------- | ------------- |
| Ubuntu | 22.04 (Jammy Jellyfish) |
| ROS | Humble Hawksbill |
| Python | 3.10 |

<p align="right">(<a href="#readme-top">上に戻る</a>)</p>

### インストール方法

1. ROSの`src`フォルダに移動します．
   ```sh
   cd ~/colcon_ws/src/
   ```
2. 本レポジトリをcloneします．
   ```sh
   git clone -b humble-devel https://github.com/TeamSOBITS/esp32_display.git
   ```
3. レポジトリの中へ移動します．
   ```sh
   cd esp32_display/
   ```
4. 依存パッケージをインストールします．
   ```sh
   bash install.sh
   ```
5. パッケージをコンパイルします．
   ```sh
   cd ~/colcon_ws/
   ```
   ```sh
   colcon build --symlink-install
   ```
   ```sh
   source ~/colcon_ws/install/setup.sh
   ```


<p align="right">(<a href="#readme-top">上に戻る</a>)</p>

<!-- 実行・操作方法 -->
## 実行・操作方法
以下の状態において以下の機能を使用できます．

- ESP32へ電源供給のみしている場合 (PCと通信していない場合)
    - 目のまばたきが表示される
- [esp32_display.launch.py](launch/esp32_display.launch.py)を起動した場合
    - [Speech Recognition Whisper](https://github.com/TeamSOBITS/speech_recognition_whisper), [Speech Recognition Nemo](https://github.com/TeamSOBITS/speech_recognition_nemo), [Speech Recognition Vosk](https://github.com/TeamSOBITS/speech_recognition_vosk)を使用している場合
        - マイクの使用を自動で検知して[マイク画像](images/mic.png)が表示される
    - [Sobits TTS](https://github.com/TeamSOBITS/sobits_tts)を使用している場合
        - 発話を自動で検知して[スピーカー画像](images/speaker.png)が表示される
    - [display_client.py](esp32_display/display_client.py)を起動した場合
        - Image型のTopic名 or 画像の絶対パスと，表示させたい秒数を送信することで，画像を指定秒数だけ表示させる．(任意のタイミングでキャンセル可能)

1. [esp32_display.launch.py](launch/esp32_display.launch.py)を起動
   ```sh
   ros2 launch esp32_display esp32_display.launch.py
   ```
2. [display_client.py](esp32_display/display_client.py)を起動
   ```sh
   ros2 run esp32_display display_client.py
   ```
    - トピックを送信する場合
    ```sh
        topic_name = "/image_raw"
        file_path = ""
    ```
    - 静止画を送信する場合
    ```sh
        topic_name = ""
        file_path = "画像ファイルの絶対パス"
    ```
- 画像ファイル対応形式
    - Windowsビットマップ: .bmp, .dib
    - JPEG: .jpeg, .jpg, .jpe
    - JPEG 2000: .jp2
    - PNG: .png
    - WebP: .webp
    - ポータブル画像フォーマット: .pbm,pgm, 	.ppm, .pxm, .pnm
    - PFM: .pfm
    - Sun rasters: .sr, .ras
    - TIFF: .tiff, .tif
    - OpenEXR: .exr
    - Radiance HDR: .hdr, .pic   

<p align="right">(<a href="#readme-top">上に戻る</a>)</p>

## パラメータ
[esp32_display.launch.py](launch/esp32_display.launch.py)では以下のパラメータを指定できます．

| パラメータ | 説明 | デフォルト値 |
| --- | --- | --- |
| port | マイコンとのシリアルポート名 | /dev/ttyACM0 |
| quality | ディスプレイに描画する画像の品質．最小値1，最大値100．高いほど高画質．マイコンの性能上，320×240のサイズでは50が限界． | 30 |
| image_hight | ディスプレイに描画する画像の高さ | 240 |
| image_width | ディスプレイに描画する画像の幅 | 320 |


 <p align="right">(<a href="#readme-top">上に戻る</a>)</p>
 

<!-- マイルストーン -->
## マイルストーン
- シリアルポート自動識別機能追加
- 人検出し瞳孔を追従させる機能追加
- 独自interface型作成

現時点のバッグや新規機能の依頼を確認するために[Issueページ](issues-url) をご覧ください．

<p align="right">(<a href="#readme-top">上に戻る</a>)</p>

<!-- 参考文献 -->
## 参考文献

* [ESP32-S3-DevKitC-1](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/index.html)
* [ILI9341](https://cdn-shop.adafruit.com/datasheets/ILI9341.pdf)

<p align="right">(<a href="#readme-top">上に戻る</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/TeamSOBITS/esp32_display.svg?style=for-the-badge
[contributors-url]: https://github.com/TeamSOBITS/esp32_display/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/TeamSOBITS/esp32_display.svg?style=for-the-badge
[forks-url]: https://github.com/TeamSOBITS/esp32_display/network/members
[stars-shield]: https://img.shields.io/github/stars/TeamSOBITS/esp32_display.svg?style=for-the-badge
[stars-url]: https://github.com/TeamSOBITS/esp32_display/stargazers
[issues-shield]: https://img.shields.io/github/issues/TeamSOBITS/esp32_display.svg?style=for-the-badge
[issues-url]: https://github.com/TeamSOBITS/esp32_display/issues
[license-shield]: https://img.shields.io/github/license/TeamSOBITS/esp32_display.svg?style=for-the-badge
[license-url]: LICENSE
