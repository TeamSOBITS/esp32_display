#pragma once

//#include "LovyanGFX.hpp"

#include <LovyanGFX.hpp>

#define TFT_MISO 13
#define TFT_MOSI 11
#define TFT_SCLK 12
// #define TFT_CS 10   // Chip select control pin //2台つなぐときは消す
#define TFT_DC 17  // Data Command control pin
#define TFT_RST 16 // Reset pin (could connect to RST pin)
#define TFT_WIDTH 240
#define TFT_HEIGHT 320


class LGFX : public lgfx::LGFX_Device
{
  lgfx::Panel_ILI9341 _panel_instance;
  lgfx::Bus_SPI _bus_instance; // SPIバスのインスタンス
public:
  LGFX(void)
  {
    {                                    // バス制御の設定を行います。
      auto cfg = _bus_instance.config(); // バス設定用の構造体を取得します。

      // SPIバスの設定
      cfg.spi_host = SPI2_HOST;
      cfg.spi_mode = 0;          // SPI通信モードを設定 (0 ~ 3)
      cfg.freq_write = 40000000; // 送信時のSPIクロック (最大80MHz, 80MHzを整数で割った値に丸められます)
      cfg.freq_read = 20000000;  // 受信時のSPIクロック

      //      cfg.spi_3wire  = true;        // 受信をMOSIピンで行う場合はtrueを設定
      //      cfg.use_lock   = true;        // トランザクションロックを使用する場合はtrueを設定
      cfg.dma_channel = SPI_DMA_CH_AUTO; // 使用するDMAチャンネルを設定 (0=DMA不使用 / 1=1ch / 2=ch / SPI_DMA_CH_AUTO=自動設定)

      cfg.pin_sclk = TFT_SCLK; // SPIのSCLKピン番号を設定
      cfg.pin_mosi = TFT_MOSI; // SPIのMOSIピン番号を設定
      cfg.pin_miso = TFT_MISO; // SPIのMISOピン番号を設定 (-1 = disable)
      cfg.pin_dc = TFT_DC;     // SPIのD/Cピン番号を設定  (-1 = disable)

      _bus_instance.config(cfg);              // 設定値をバスに反映します。
      _panel_instance.setBus(&_bus_instance); // バスをパネルにセットします。
    }
    {
      auto cfg = _panel_instance.config(); // 表示パネル設定用の構造体を取得します。
      // cfg.pin_cs = TFT_CS;   // CSが接続されているピン番号   (-1 = disable)
      cfg.pin_rst = TFT_RST; // RSTが接続されているピン番号  (-1 = disable)
      cfg.pin_busy = -1;     // BUSYが接続されているピン番号 (-1 = disable)

      // cfg.panel_width = 240;  // 実際に表示可能な幅
      // cfg.panel_height = 320; // 実際に表示可能な高さ
      // cfg.offset_x = 0;       // パネルのX方向オフセット量
      cfg.offset_y = 5; // パネルのY方向オフセット量

      _panel_instance.config(cfg);
    }
    setPanel(&_panel_instance); // 使用するパネルをセットします。
  }
};