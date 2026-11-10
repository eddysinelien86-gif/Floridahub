// MarketHub display firmware for the Waveshare ESP32-S3-Touch-LCD-2.8
// Uses the "GFX Library for Arduino" (Arduino_GFX by moononournation) so all
// the display pins live right here in the sketch -- no User_Setup.h / lv_conf.h.
//
// Libraries to install (Tools -> Manage Libraries):
//   * "GFX Library for Arduino"  (by moononournation)
//   * "ArduinoJson"              (by Benoit Blanchon)
//
// Board settings: ESP32S3 Dev Module, USB CDC On Boot = Enabled, PSRAM = OPI.

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Arduino_GFX_Library.h>

// ---- Waveshare ESP32-S3-Touch-LCD-2.8 (ST7789) display pins ----
#define LCD_SCK   40
#define LCD_MOSI  45
#define LCD_DC    41
#define LCD_CS    42
#define LCD_RST   39
#define LCD_BL     5

Arduino_DataBus *bus = new Arduino_ESP32SPI(LCD_DC, LCD_CS, LCD_SCK, LCD_MOSI, -1 /* MISO unused */);
Arduino_GFX *gfx = new Arduino_ST7789(bus, LCD_RST, 0 /* rotation */, true /* IPS */, 240, 320);

const char* WIFI_SSID     = "ATTmNniXi2";
const char* WIFI_PASSWORD = "PUT-YOUR-WIFI-PASSWORD-HERE";
const char* API_URL       = "http://192.168.1.207:8000/api/dashboard";

void showMessage(const char* msg) {
  gfx->fillScreen(BLACK);
  gfx->setTextColor(WHITE);
  gfx->setTextSize(2);
  gfx->setCursor(10, 20);
  gfx->println(msg);
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) { delay(500); }
}

String fetchDashboard() {
  HTTPClient http;
  http.begin(API_URL);
  int code = http.GET();
  String payload = (code == HTTP_CODE_OK) ? http.getString() : String("");
  http.end();
  return payload;
}

void drawDashboard(const String& payload) {
  JsonDocument doc;
  if (deserializeJson(doc, payload)) { showMessage("Parse error"); return; }

  gfx->fillScreen(BLACK);

  // Title
  gfx->setTextColor(CYAN);
  gfx->setTextSize(3);
  gfx->setCursor(10, 8);
  gfx->println(doc["profile"]["name"] | "MarketHub");

  // Metrics list: label on the left, value on the right
  gfx->setTextSize(2);
  int y = 56;
  for (JsonObject m : doc["metrics"].as<JsonArray>()) {
    gfx->setTextColor(WHITE);
    gfx->setCursor(10, y);
    gfx->print((const char*)(m["label"] | ""));
    gfx->setTextColor(GREEN);
    gfx->setCursor(165, y);
    gfx->print((const char*)(m["value"] | ""));
    y += 30;
    if (y > 300) break;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LCD_BL, OUTPUT);
  digitalWrite(LCD_BL, HIGH);   // backlight on
  gfx->begin();
  showMessage("Connecting Wi-Fi...");
  connectWifi();
  showMessage("Connected! Loading...");
}

void loop() {
  String payload = fetchDashboard();
  if (payload.length() > 0) drawDashboard(payload);
  else showMessage("No data from Pi");
  delay(10000);
}
