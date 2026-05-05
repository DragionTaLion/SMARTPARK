#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <Servo.h>

/**
 * SMARTPARK V2 - SMART GATE CONTROL
 * =========================================
 * Board: ESP8266 (NodeMCU/WeMos D1)
 * Features: 
 *   - Smart Auto-Close: Đóng sau khi xe đã qua hẳn cảm biến 2 giây.
 *   - Manual Control: Hỗ trợ lệnh mở thủ công từ Server.
 */

// ================= CẤU HÌNH WIFI =================
const char* ssid = "Ho Sy Can";
const char* password = "phongtro284";

// ================= CẤU HÌNH SERVER =================
const char* serverIp = "192.168.2.34"; 
const int serverPort = 8000;
String triggerUrl = "/api/trigger";
String statusUrl = "/api/hardware/status";

// ================= CẤU HÌNH CHÂN (PINS) =================
const int SERVO_IN_PIN  = D3; // GPIO 0
const int SERVO_OUT_PIN = D4; // GPIO 2
const int SENSOR_IN_PIN  = D1; // GPIO 5
const int SENSOR_OUT_PIN = D2; // GPIO 4
const int SLOT1_PIN = D5; // GPIO 14
const int SLOT2_PIN = D6; // GPIO 12
const int SLOT3_PIN = D7; // GPIO 13

// ================= KHỞI TẠO ĐỐI TƯỢNG =================
Servo servoIn;
Servo servoOut;
ESP8266WebServer server(80);

// Trạng thái xe tại cổng
bool carAtIn = false;
bool carAtOut = false;

// Trạng thái điều khiển cổng thông minh
bool isGateInOpening = false;
bool isGateOutOpening = false;
unsigned long gateInClearTime = 0;
unsigned long gateOutClearTime = 0;
const unsigned long CLOSE_DELAY = 2000; // 2 giây sau khi xe qua thì đóng

unsigned long lastStatusUpdate = 0;
const unsigned long UPDATE_INTERVAL = 5000; 

void setup() {
  Serial.begin(115200);
  pinMode(SENSOR_IN_PIN, INPUT);
  pinMode(SENSOR_OUT_PIN, INPUT);
  pinMode(SLOT1_PIN, INPUT);
  pinMode(SLOT2_PIN, INPUT);
  pinMode(SLOT3_PIN, INPUT);
  
  servoIn.attach(SERVO_IN_PIN);
  servoOut.attach(SERVO_OUT_PIN);
  servoIn.write(0);
  servoOut.write(0);
  
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\nWiFi connected! IP: " + WiFi.localIP().toString());

  server.on("/open", HTTP_GET, handleOpenManual);
  server.on("/", HTTP_GET, []() { server.send(200, "text/plain", "SmartPark ESP8266 System Online"); });
  server.begin();
}

void openGate(int gateId) {
  if (gateId == 1) {
    Serial.println(">>> OPENING GATE IN...");
    servoIn.write(90);
    isGateInOpening = true;
    gateInClearTime = 0; // Reset timer
  } else {
    Serial.println(">>> OPENING GATE OUT...");
    servoOut.write(90);
    isGateOutOpening = true;
    gateOutClearTime = 0; // Reset timer
  }
}

void handleOpenManual() {
  int gateId = server.arg("gate").toInt();
  server.send(200, "application/json", "{\"success\":true}");
  openGate(gateId);
}

void sendTrigger(String gateName) {
  if (WiFi.status() != WL_CONNECTED) return;
  WiFiClient client;
  HTTPClient http;
  String url = "http://" + String(serverIp) + ":" + String(serverPort) + triggerUrl + "?gate=" + gateName;
  http.begin(client, url);
  int httpCode = http.POST("");
  if (httpCode > 0) {
    String payload = http.getString();
    if (payload.indexOf("\"action\":\"open\"") != -1) openGate(gateName == "in" ? 1 : 2);
  }
  http.end();
}

void sendStatus() {
  if (WiFi.status() != WL_CONNECTED) return;
  WiFiClient client;
  HTTPClient http;
  String url = "http://" + String(serverIp) + ":" + String(serverPort) + statusUrl;
  int sIn = digitalRead(SENSOR_IN_PIN) == LOW ? 1 : 0;
  int sOut = digitalRead(SENSOR_OUT_PIN) == LOW ? 1 : 0;
  int p1 = digitalRead(SLOT1_PIN) == LOW ? 1 : 0;
  int p2 = digitalRead(SLOT2_PIN) == LOW ? 1 : 0;
  int p3 = digitalRead(SLOT3_PIN) == LOW ? 1 : 0;
  String json = "{\"sensors\":[" + String(sIn) + "," + String(sOut) + "," + String(p1) + "," + String(p2) + "," + String(p3) + "], \"gate_trigger\": 0}";
  http.begin(client, url);
  http.addHeader("Content-Type", "application/json");
  http.POST(json);
  http.end();
}

void loop() {
  server.handleClient();
  
  // 1. Cảm biến phát hiện xe mới đến
  int valIn = digitalRead(SENSOR_IN_PIN);
  if (valIn == LOW && !carAtIn) {
    carAtIn = true;
    sendTrigger("in");
  } else if (valIn == HIGH) {
    carAtIn = false;
  }
  
  int valOut = digitalRead(SENSOR_OUT_PIN);
  if (valOut == LOW && !carAtOut) {
    carAtOut = true;
    sendTrigger("out");
  } else if (valOut == HIGH) {
    carAtOut = false;
  }

  // 2. Logic ĐÓNG CỔNG THÔNG MINH (Gate In)
  if (isGateInOpening) {
    if (valIn == LOW) { // Xe vẫn đang chắn ngang
      gateInClearTime = 0; 
    } else { // Đường đã trống
      if (gateInClearTime == 0) gateInClearTime = millis();
      if (millis() - gateInClearTime > CLOSE_DELAY) {
        servoIn.write(0);
        isGateInOpening = false;
        Serial.println(">>> CLOSED GATE IN (Auto)");
      }
    }
  }

  // 3. Logic ĐÓNG CỔNG THÔNG MINH (Gate Out)
  if (isGateOutOpening) {
    if (valOut == LOW) {
      gateOutClearTime = 0;
    } else {
      if (gateOutClearTime == 0) gateOutClearTime = millis();
      if (millis() - gateOutClearTime > CLOSE_DELAY) {
        servoOut.write(0);
        isGateOutOpening = false;
        Serial.println(">>> CLOSED GATE OUT (Auto)");
      }
    }
  }
  
  if (millis() - lastStatusUpdate > UPDATE_INTERVAL) {
    sendStatus();
    lastStatusUpdate = millis();
  }
  delay(20);
}
