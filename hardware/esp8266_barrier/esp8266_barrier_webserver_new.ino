#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <Servo.h>

/**
 * SMARTPARK V2 - ALL-IN-ONE HARDWARE CONTROL
 * =========================================
 * Board: ESP8266 (NodeMCU/WeMos D1)
 * Features: 
 *   - 2 Servos (Entrance & Exit)
 *   - 2 IR Sensors for Gate Triggers
 *   - 3 IR Sensors for Parking Slots
 */

// ================= CẤU HÌNH WIFI =================
const char* ssid = "Ho Sy Can";
const char* password = "phongtro284";

// ================= CẤU HÌNH SERVER =================
// IP của máy tính chạy api_server.py
const char* serverIp = "192.168.2.34"; 
const int serverPort = 8000;

// URL các endpoint
String triggerUrl = "/api/trigger";
String statusUrl = "/api/hardware/status";

// ================= CẤU HÌNH CHÂN (PINS) =================
// Servos
const int SERVO_IN_PIN  = D3; // GPIO 0
const int SERVO_OUT_PIN = D4; // GPIO 2

// Gate Sensors (IR)
const int SENSOR_IN_PIN  = D1; // GPIO 5
const int SENSOR_OUT_PIN = D2; // GPIO 4

// Parking Slot Sensors (IR)
const int SLOT1_PIN = D5; // GPIO 14
const int SLOT2_PIN = D6; // GPIO 12
const int SLOT3_PIN = D7; // GPIO 13

// ================= KHỞI TẠO ĐỐI TƯỢNG =================
Servo servoIn;
Servo servoOut;
ESP8266WebServer server(80);

// Trạng thái xe tại cổng (Tránh gửi request liên tục)
bool carAtIn = false;
bool carAtOut = false;

// Thời gian cập nhật sensor định kỳ
unsigned long lastStatusUpdate = 0;
const unsigned long UPDATE_INTERVAL = 5000; // 5 giây/lần

void setup() {
  Serial.begin(115200);
  
  // Cấu hình chân Sensor (INPUT_PULLUP tùy loại cảm biến, thường là INPUT)
  pinMode(SENSOR_IN_PIN, INPUT);
  pinMode(SENSOR_OUT_PIN, INPUT);
  pinMode(SLOT1_PIN, INPUT);
  pinMode(SLOT2_PIN, INPUT);
  pinMode(SLOT3_PIN, INPUT);
  
  // Cấu hình Servo
  servoIn.attach(SERVO_IN_PIN);
  servoOut.attach(SERVO_OUT_PIN);
  closeGate(1);
  closeGate(2);
  
  // Kết nối WiFi
  WiFi.begin(ssid, password);
  Serial.print("Dang ket noi WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi da ket noi!");
  Serial.print("IP ESP8266: ");
  Serial.println(WiFi.localIP());

  // Định nghĩa các endpoint WebServer (Server gọi xuống)
  server.on("/open", HTTP_GET, handleOpenManual);
  server.on("/", HTTP_GET, []() {
    server.send(200, "text/plain", "SmartPark ESP8266 System Online");
  });
  
  server.begin();
  Serial.println("WebServer san sang!");
}

// Hàm mở cổng
void openGate(int gateId) {
  if (gateId == 1) {
    Serial.println(">>> DANG MO CONG VAO...");
    servoIn.write(90);
    delay(5000);
    servoIn.write(0);
    Serial.println(">>> DA DONG CONG VAO.");
  } else {
    Serial.println(">>> DANG MO CONG RA...");
    servoOut.write(90);
    delay(5000);
    servoOut.write(0);
    Serial.println(">>> DA DONG CONG RA.");
  }
}

// Hàm đóng cổng ngay lập tức (Reset)
void closeGate(int gateId) {
  if (gateId == 1) servoIn.write(0);
  else servoOut.write(0);
}

// Xử lý lệnh mở thủ công từ Dashboard (GET /open?gate=1)
void handleOpenManual() {
  int gateId = server.arg("gate").toInt();
  server.send(200, "application/json", "{\"success\":true}");
  openGate(gateId);
}

// Gửi yêu cầu nhận diện lên Server
void sendTrigger(String gateName) {
  if (WiFi.status() != WL_CONNECTED) return;
  
  WiFiClient client;
  HTTPClient http;
  String url = "http://" + String(serverIp) + ":" + String(serverPort) + triggerUrl + "?gate=" + gateName;
  
  Serial.print("[TRIGGER] Goi AI cho lan: ");
  Serial.println(gateName);
  
  http.begin(client, url);
  int httpCode = http.POST(""); // Gửi POST trống
  
  if (httpCode > 0) {
    String payload = http.getString();
    Serial.println("[SERVER] Response: " + payload);
    
    // Nếu Server quyết định mở cổng
    if (payload.indexOf("\"action\":\"open\"") != -1) {
      openGate(gateName == "in" ? 1 : 2);
    }
  } else {
    Serial.print("[ERROR] Ket noi that bai: ");
    Serial.println(http.errorToString(httpCode));
  }
  http.end();
}

// Gửi trạng thái cảm biến lên Server
void sendStatus() {
  if (WiFi.status() != WL_CONNECTED) return;
  
  WiFiClient client;
  HTTPClient http;
  String url = "http://" + String(serverIp) + ":" + String(serverPort) + statusUrl;
  
  // Đọc trạng thái (LOW là có vật cản với hầu hết cảm biến IR)
  int sIn = digitalRead(SENSOR_IN_PIN) == LOW ? 1 : 0;
  int sOut = digitalRead(SENSOR_OUT_PIN) == LOW ? 1 : 0;
  int p1 = digitalRead(SLOT1_PIN) == LOW ? 1 : 0;
  int p2 = digitalRead(SLOT2_PIN) == LOW ? 1 : 0;
  int p3 = digitalRead(SLOT3_PIN) == LOW ? 1 : 0;
  
  String json = "{\"sensors\":[" + String(sIn) + "," + String(sOut) + "," + String(p1) + "," + String(p2) + "," + String(p3) + "], \"gate_trigger\": 0}";
  
  http.begin(client, url);
  http.addHeader("Content-Type", "application/json");
  int httpCode = http.POST(json);
  http.end();
}

void loop() {
  server.handleClient();
  
  // 1. Kiểm tra Sensor Làn Vào
  int valIn = digitalRead(SENSOR_IN_PIN);
  if (valIn == LOW && !carAtIn) {
    carAtIn = true;
    sendTrigger("in");
  } else if (valIn == HIGH) {
    carAtIn = false;
  }
  
  // 2. Kiểm tra Sensor Làn Ra
  int valOut = digitalRead(SENSOR_OUT_PIN);
  if (valOut == LOW && !carAtOut) {
    carAtOut = true;
    sendTrigger("out");
  } else if (valOut == HIGH) {
    carAtOut = false;
  }
  
  // 3. Cập nhật trạng thái ô đỗ định kỳ
  if (millis() - lastStatusUpdate > UPDATE_INTERVAL) {
    sendStatus();
    lastStatusUpdate = millis();
  }
  
  delay(50); // Nhịp lặp 50ms
}
