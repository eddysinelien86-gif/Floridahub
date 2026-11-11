// Insulation Lead Finders — ESP32-S3 lead-finder box firmware
// Shows live "HOT LEADS / DRAFTS" from the Raspberry Pi, matching the
// original box display. Uses the GFX Library for Arduino (ST7789).
//
// Libraries: "GFX Library for Arduino" (moononournation) + "ArduinoJson".
// Board: ESP32S3 Dev Module, USB CDC On Boot = Enabled, PSRAM = OPI.
//
// NOTE: set LCD_BL to the backlight GPIO once found with the BOOT-button
// finder sketch (the screen stays dark until this is correct).

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Arduino_GFX_Library.h>

#define LCD_SCK  40
#define LCD_MOSI 45
#define LCD_DC   41
#define LCD_CS   42
#define LCD_RST  39
#define LCD_BL    5     // <-- set to the real backlight pin once found

#ifndef BLACK
#define BLACK 0x0000
#endif
#ifndef WHITE
#define WHITE 0xFFFF
#endif
#ifndef CYAN
#define CYAN  0x07FF
#endif
#ifndef GREEN
#define GREEN 0x07E0
#endif

Arduino_DataBus *bus = new Arduino_ESP32SPI(LCD_DC, LCD_CS, LCD_SCK, LCD_MOSI, -1);
Arduino_GFX *gfx = new Arduino_ST7789(bus, LCD_RST, 0, true, 240, 320);

const char* WIFI_SSID     = "ATTmNniXi2";
const char* WIFI_PASSWORD = "PUT-YOUR-WIFI-PASSWORD-HERE";
const char* API_URL       = "http://192.168.1.207:8000/api/leadcount";

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) { delay(500); }
}

void draw(int hot, int drafts) {
  gfx->fillScreen(BLACK);
  gfx->setTextColor(CYAN);
  gfx->setTextSize(2);
  gfx->setCursor(10, 10);
  gfx->println("INSULATION");
  gfx->setCursor(10, 34);
  gfx->println("LEAD FINDERS");

  gfx->setTextColor(GREEN);
  gfx->setTextSize(7);
  gfx->setCursor(20, 90);
  gfx->println(hot);
  gfx->setTextColor(WHITE);
  gfx->setTextSize(2);
  gfx->setCursor(20, 160);
  gfx->println("HOT LEADS");

  gfx->setTextColor(WHITE);
  gfx->setTextSize(5);
  gfx->setCursor(20, 210);
  gfx->println(drafts);
  gfx->setTextSize(2);
  gfx->setCursor(20, 265);
  gfx->println("DRAFTS");
}

void setup() {
  Serial.begin(115200);
  pinMode(LCD_BL, OUTPUT);
  digitalWrite(LCD_BL, HIGH);
  gfx->begin();
  gfx->fillScreen(BLACK);
  gfx->setTextColor(WHITE); gfx->setTextSize(2);
  gfx->setCursor(10, 20); gfx->println("Connecting...");
  connectWifi();
}

void loop() {
  HTTPClient http;
  http.begin(API_URL);
  int code = http.GET();
  if (code == HTTP_CODE_OK) {
    JsonDocument doc;
    if (!deserializeJson(doc, http.getString())) {
      draw(doc["hot_leads"] | 0, doc["drafts"] | 0);
    }
  }
  http.end();
  delay(15000);
}
