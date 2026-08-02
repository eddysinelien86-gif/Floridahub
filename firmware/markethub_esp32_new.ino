#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>

const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* apiUrl = "http://pi.local:8000/api/dashboard";

void connectWiFi() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  Serial.println("Connecting to Wi-Fi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("Wi-Fi connected");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
}

String fetchDashboard() {
  HTTPClient http;
  http.begin(apiUrl);

  int httpCode = http.GET();
  if (httpCode != HTTP_CODE_OK) {
    http.end();
    return "{}";
  }

  String payload = http.getString();
  http.end();
  return payload;
}

void setup() {
  connectWiFi();
}

void loop() {
  String payload = fetchDashboard();
  Serial.println(payload);
  delay(10000);
}
