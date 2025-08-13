#include <LovyanGFX.hpp>
#include <config.h>
#include <esp_psram.h> // PSRAMを使用するためのヘッダー

// 定数の定義
const int BLINK_INTERVAL = 1000;  // まばたきの間隔（ミリ秒）
const int UPPER_LID_STEP = 30;    // 上まぶたの移動ステップ
const int LOWER_LID_STEP = 15;    // 下まぶたの移動ステップ
const int led_pin = 18;

// グローバル定数とバッファを定義
const int RX_BUFFER_SIZE = 200000;
uint8_t* jpeg_buf; // PSRAMから動的に確保

class TFTImageDrawer {
public:
  TFTImageDrawer(LGFX* gfx)
    : _gfx(gfx), _sprite(gfx), first_display_pin(47), second_display_pin(10), blinkEnabled(false), isLidClosing(false), lastBlinkTime(0),
      x(0), x2(TFT_WIDTH), lastSerialDataTime(0) {}

  void init() {
    pinMode(led_pin, OUTPUT);
    pinMode(second_display_pin, OUTPUT);
    pinMode(first_display_pin, OUTPUT);
    digitalWrite(led_pin, HIGH);
    digitalWrite(first_display_pin, LOW);
    digitalWrite(second_display_pin, LOW);

    // シリアル受信バッファを4096バイトに設定
    Serial.setRxBufferSize(4096);
    // シリアル通信のタイムアウトを50msに設定
    Serial.setTimeout(50);

    _gfx->init();
    _gfx->fillScreen(TFT_BLACK);  // 背景を黒で塗りつぶし

    // スプライトをPSRAMに作成
    _sprite.setPsram(true);
    _sprite.createSprite(TFT_WIDTH, TFT_HEIGHT);
    if (!_sprite.getBuffer()) {
      Serial.println("Error: Failed to create sprite in PSRAM.");
      while(1);
    }
    _sprite.fillScreen(TFT_BLACK);
    _sprite.pushSprite(0, 0);

    // JPEGバッファをPSRAMから動的に確保
    jpeg_buf = (uint8_t*)ps_malloc(RX_BUFFER_SIZE);
    if (jpeg_buf == NULL) {
      Serial.printf("Error: Failed to allocate %d bytes from PSRAM for JPEG buffer.\n", RX_BUFFER_SIZE);
      while(1);
    }
    Serial.printf("JPEG buffer allocated from PSRAM: %d bytes.\n", RX_BUFFER_SIZE);
  }

  void main() {
    // 最後にデータを受信してから2秒以上経過しているかチェック
    if (millis() - lastSerialDataTime > 2000) {
      if (Serial.available() == 0) {
        handleBlink();
      } else {
        handleSerialData();
      }
    } else {
      if (Serial.available() >= PACKET_HEADER_SIZE) {
        handleSerialData();
      }
    }
  }

  // lastSerialDataTimeを外部から設定するためのpublicメソッド
  void setLastSerialDataTime(unsigned long time) {
    lastSerialDataTime = time;
  }

  // デストラクタで確保したメモリを解放
  ~TFTImageDrawer() {
    if (jpeg_buf) {
      free(jpeg_buf);
    }
  }

private:
  void handleSerialData() {
    lastSerialDataTime = millis();  // データを読み出した時刻を更新
    Serial.printf("Serial available!\n");

    uint8_t rx_buffer[PACKET_HEADER_SIZE];
    int rx_size = Serial.readBytes(rx_buffer, PACKET_HEADER_SIZE);

    // ヘッダーが有効な場合のみ処理を継続
    if (rx_size == PACKET_HEADER_SIZE && isPacketHeaderValid(rx_buffer)) {
      jpeg_length = getJpegLength(rx_buffer);
      if (jpeg_length > 0 && jpeg_length <= RX_BUFFER_SIZE) {
        readJpegData();
      } else {
        Serial.printf("Error: Invalid JPEG length %u or exceeds buffer size %d\n", jpeg_length, RX_BUFFER_SIZE);
        while (Serial.available()) {
          Serial.read();
        }
      }
    } else {
      while (Serial.available()) {
        Serial.read();
      }
    }
  }

  bool isPacketHeaderValid(const uint8_t* header) {
    return memcmp(header, packet_begin, 3) == 0;
  }

  uint32_t getJpegLength(const uint8_t* header) {
    return ((uint32_t)header[4] << 16) | ((uint32_t)header[5] << 8) | header[6];
  }

  void readJpegData() {
    int received = 0;
    while (received < jpeg_length) {
      int current_read = Serial.readBytes(jpeg_buf + received, jpeg_length - received);
      if (current_read == 0) {
        Serial.printf("Error: Read timeout. Received only %d of %u bytes.\n", received, jpeg_length);
        break;
      }
      received += current_read;
    }
    
    // バッファに読み込んだJPEGを描画
    drawJpeg(jpeg_buf, received);
  }

  void drawJpeg(const uint8_t* jpeg_data, int size) {
    _sprite.drawJpg(jpeg_data, size, 0, 0, _sprite.width(), _sprite.height());
    _sprite.pushSprite(0, 0);
  }

  void handleBlink() {
    unsigned long currentMillis = millis();
    if (!blinkEnabled && currentMillis - lastBlinkTime >= BLINK_INTERVAL) {
      blinkEnabled = true;
    }
    if (blinkEnabled) {
      updateisLidClosing();
      drawEye(x, x2);
      _sprite.pushSprite(0, 0);
    }
  }

  void updateisLidClosing() {
    if (isLidClosing == false) {
      x -= UPPER_LID_STEP;
      x2 += LOWER_LID_STEP;
      if (x <= -(TFT_WIDTH * 8 / 10)) {
        isLidClosing = true;
      }
    } else {
      x += UPPER_LID_STEP;
      x2 -= LOWER_LID_STEP;
      if (x >= 0) {
        isLidClosing = false;
        blinkEnabled = false;
        lastBlinkTime = millis();
        x = 0;
        x2 = TFT_WIDTH;
      }
    }
  }

  void drawEye(int x, int x2) {
    _sprite.clear(TFT_BLACK);
    _sprite.fillCircle(TFT_WIDTH / 2, TFT_HEIGHT / 2, 119, 0x3b57);
    _sprite.fillCircle(TFT_WIDTH / 2, TFT_HEIGHT / 2 + 30, 119, 0x3b57);
    _sprite.fillEllipse(TFT_WIDTH / 2, TFT_WIDTH / 2 + 25, 95, 95, 0x4c5e);
    _sprite.fillEllipse(TFT_WIDTH / 2, TFT_HEIGHT / 2 + 85, 65, 32, 0x7d9e);
    _sprite.fillCircle(TFT_WIDTH / 2, TFT_HEIGHT / 2, 80, 0x010c);
    _sprite.fillCircle(TFT_WIDTH / 2 + 40, TFT_HEIGHT / 2 - 40, 45, TFT_WHITE);
    _sprite.fillCircle(TFT_WIDTH / 2 + 85, TFT_HEIGHT / 2 - 5, 15, TFT_WHITE);
    _sprite.fillCircle(TFT_WIDTH / 2 - 50, TFT_HEIGHT / 2 + 60, 20, TFT_WHITE);
    _sprite.fillArc(x2, TFT_HEIGHT / 2, TFT_WIDTH + 10, TFT_WIDTH, 0, 360, 0x3b57);
    _sprite.fillArc(x, TFT_HEIGHT / 2, TFT_WIDTH + 10, TFT_WIDTH, 300, 60, 0x3b57);
    _sprite.fillArc(x2, TFT_HEIGHT / 2, TFT_WIDTH + (TFT_HEIGHT * 2), TFT_WIDTH + 10, 0, 360, TFT_BLACK);
    _sprite.fillArc(x, TFT_HEIGHT / 2, TFT_WIDTH + (TFT_HEIGHT * 2), TFT_WIDTH + 10, 300, 60, TFT_BLACK);
  }

  LGFX* _gfx;
  LGFX_Sprite _sprite;
  int first_display_pin, second_display_pin;
  int x, x2;
  bool isLidClosing, blinkEnabled;
  unsigned long lastBlinkTime;

  static const uint8_t packet_begin[3];
  uint32_t jpeg_length;
  static const int PACKET_HEADER_SIZE = 10;
  unsigned long lastSerialDataTime;
};

const uint8_t TFTImageDrawer::packet_begin[3] = { 0xFF, 0xD8, 0xEA };

LGFX gfx;
TFTImageDrawer tftImageDrawer(&gfx);

void setup() {
  Serial.begin(3000000);
  tftImageDrawer.init();
  tftImageDrawer.setLastSerialDataTime(millis());
}

void loop() {
  tftImageDrawer.main();
}