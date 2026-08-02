#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>

// MarketHub ESP32-S3 firmware sketch
// This version is plain ASCII and is safe to paste into Arduino IDE.

const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* API_URL = "http://pi.local:8000/api/dashboard";

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.println("Connecting to Wi-Fi...");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("Wi-Fi connected");
}

String fetchDashboard() {
  HTTPClient http;
  http.begin(API_URL);

  int code = http.GET();
  if (code != HTTP_CODE_OK) {
    http.end();
    return "{}";
  }

  String payload = http.getString();
  http.end();
  return payload;
}

void setup() {
  Serial.begin(115200);
  connectWifi();
}

void loop() {
  String payload = fetchDashboard();
  Serial.println(payload);
  delay(10000);
}
