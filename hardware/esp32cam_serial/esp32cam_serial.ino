/**
 * ============================================================
 *  ESP32-CAM — USB Serial Camera Server
 * ============================================================
 *  Chức năng:
 *    Lắng nghe lệnh "CAPTURE\n" qua USB Serial.
 *    Khi nhận được lệnh → chụp ảnh → gửi JPEG base64 về PC.
 *
 *  Protocol Serial (921600 baud):
 *    PC gửi  : "CAPTURE\n"
 *    ESP trả : "IMG_START\n" + [base64 JPEG] + "\nIMG_END\n"
 *    Hoặc    : "ERROR:no_camera\n" nếu thất bại
 *
 *  Board: AI Thinker ESP32-CAM
 *  Cài đặt:
 *    - Board: "AI Thinker ESP32-CAM" (hoặc ESP32 Wrover Module)
 *    - Partition Scheme: "Huge APP (3MB No OTA)"
 *    - Flash Mode: QIO
 *    - Flash Frequency: 80MHz
 *    - Upload Speed: 115200
 *
 *  Kết nối upload:
 *    GPIO0 nối GND khi nạp firmware, bỏ ra khi chạy bình thường
 * ============================================================
 */

#include "esp_camera.h"
#include "Arduino.h"
#include "base64.h"

// ─── CAMERA MODEL (AI Thinker ESP32-CAM) ────────────────────────────────────
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// ─── CÀI ĐẶT CAMERA ─────────────────────────────────────────────────────────
#define SERIAL_BAUD   921600   // Tốc độ Serial cao để truyền ảnh nhanh
#define JPEG_QUALITY  12       // Chất lượng JPEG: 10=tốt, 63=thấp (12 là cân bằng)
#define FRAME_SIZE    FRAMESIZE_VGA  // 640x480 — đủ cho ALPR

bool camera_ok = false;

// ─── KHỞI TẠO CAMERA ────────────────────────────────────────────────────────
bool init_camera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = FRAME_SIZE;
  config.jpeg_quality = JPEG_QUALITY;
  config.fb_count     = 1;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("ERROR:camera_init_failed_%d\n", err);
    return false;
  }

  // Warm-up: chụp và bỏ 3 frame đầu để camera ổn định độ sáng
  for (int i = 0; i < 3; i++) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (fb) esp_camera_fb_return(fb);
    delay(100);
  }

  Serial.println("READY");
  return true;
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(500);
  Serial.println("ESP32-CAM USB Serial Camera v1.0");
  camera_ok = init_camera();
}

void loop() {
  // Đọc lệnh từ PC qua Serial
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "CAPTURE") {
      capture_and_send();
    } else if (cmd == "PING") {
      // Lệnh kiểm tra kết nối
      Serial.println("PONG");
    } else if (cmd == "STATUS") {
      Serial.printf("STATUS:camera=%s\n", camera_ok ? "ok" : "error");
    }
  }
}

// ─── CHỤP ẢNH VÀ GỬI QUA SERIAL ────────────────────────────────────────────
void capture_and_send() {
  if (!camera_ok) {
    Serial.println("ERROR:camera_not_initialized");
    return;
  }

  // Chụp frame
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("ERROR:capture_failed");
    return;
  }

  // Encode sang base64
  String encoded = base64::encode(fb->buf, fb->len);
  esp_camera_fb_return(fb);

  // Gửi về PC theo protocol:
  // IMG_START → [base64 data] → IMG_END
  Serial.println("IMG_START");
  Serial.println(encoded);
  Serial.println("IMG_END");
}
