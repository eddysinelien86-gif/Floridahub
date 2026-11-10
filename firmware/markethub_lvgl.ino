#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <lvgl.h>
#include <TFT_eSPI.h>

#define LV_TICK_PERIOD 5

const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* apiUrl = "http://192.168.1.207:8000/api/dashboard";

static TFT_eSPI tft = TFT_eSPI();
static lv_disp_draw_buf_t draw_buf;
static lv_color_t buf[LV_HOR_RES_MAX * 20];

static lv_obj_t* titleLabel = nullptr;
static lv_obj_t* subtitleLabel = nullptr;
static lv_obj_t* statusLabel = nullptr;
static lv_obj_t* timeLabel = nullptr;
static lv_obj_t* metricValue1 = nullptr;
static lv_obj_t* metricValue2 = nullptr;
static lv_obj_t* metricValue3 = nullptr;
static lv_obj_t* metricValue4 = nullptr;

static void my_disp_flush(lv_disp_drv_t* disp, const lv_area_t* area, lv_color_t* color_p) {
  uint32_t w = (area->x2 - area->x1 + 1);
  uint32_t h = (area->y2 - area->y1 + 1);

  tft.startWrite();
  tft.setAddrWindow(area->x1, area->y1, w, h);

  for (uint32_t i = 0; i < w * h; ++i) {
    tft.writeColor(color_p[i].full, 1);
  }

  tft.endWrite();
  lv_disp_flush_ready(disp);
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  Serial.println("Connecting to Wi-Fi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("Wi-Fi connected");
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

void updateClock() {
  unsigned long seconds = millis() / 1000;
  unsigned long hours = (seconds / 3600) % 24;
  unsigned long minutes = (seconds / 60) % 60;

  char buffer[16];
  snprintf(buffer, sizeof(buffer), "%02lu:%02lu", hours, minutes);
  lv_label_set_text(timeLabel, buffer);
}

void updateDashboardUI(const String& payload) {
  DynamicJsonDocument doc(2048);
  DeserializationError error = deserializeJson(doc, payload);
  if (error) {
    lv_label_set_text(statusLabel, "Offline");
    return;
  }

  const char* companyName = doc["profile"]["name"] | "MarketHub";
  const char* tagline = doc["profile"]["tagline"] | "Growth dashboard";
  lv_label_set_text(titleLabel, companyName);
  lv_label_set_text(subtitleLabel, tagline);
  lv_label_set_text(statusLabel, "Pi connected");

  JsonArray metrics = doc["metrics"].as<JsonArray>();
  if (metrics.size() >= 4) {
    lv_label_set_text_fmt(metricValue1, "%s", metrics[0]["value"].as<const char*>());
    lv_label_set_text_fmt(metricValue2, "%s", metrics[1]["value"].as<const char*>());
    lv_label_set_text_fmt(metricValue3, "%s", metrics[2]["value"].as<const char*>());
    lv_label_set_text_fmt(metricValue4, "%s", metrics[3]["value"].as<const char*>());
  }
}

void createDashboardUI() {
  lv_obj_t* scr = lv_scr_act();
  lv_obj_set_style_bg_color(scr, lv_color_hex(0x07111F), 0);
  lv_obj_set_style_bg_opa(scr, LV_OPA_COVER, 0);

  lv_obj_t* header = lv_obj_create(scr);
  lv_obj_set_size(header, LV_PCT(100), 52);
  lv_obj_align(header, LV_ALIGN_TOP_MID, 0, 0);
  lv_obj_set_style_bg_color(header, lv_color_hex(0x0E1D33), 0);
  lv_obj_set_style_radius(header, 16, 0);
  lv_obj_set_style_pad_all(header, 12, 0);

  lv_obj_t* logo = lv_obj_create(header);
  lv_obj_set_size(logo, 28, 28);
  lv_obj_align(logo, LV_ALIGN_LEFT_MID, 0, 0);
  lv_obj_set_style_bg_color(logo, lv_color_hex(0x3B82F6), 0);
  lv_obj_set_style_radius(logo, 8, 0);

  titleLabel = lv_label_create(header);
  lv_obj_align_to(titleLabel, header, LV_ALIGN_TOP_LEFT, 42, 6);
  lv_label_set_text(titleLabel, "MarketHub");
  lv_obj_set_style_text_font(titleLabel, &lv_font_montserrat_18, 0);
  lv_obj_set_style_text_color(titleLabel, lv_color_hex(0xE5F2FF), 0);

  subtitleLabel = lv_label_create(header);
  lv_obj_align_to(subtitleLabel, titleLabel, LV_ALIGN_OUT_BOTTOM_LEFT, 0, 2);
  lv_label_set_text(subtitleLabel, "Touch-ready growth dashboard");
  lv_obj_set_style_text_color(subtitleLabel, lv_color_hex(0x8DA5C8), 0);
  lv_obj_set_style_text_font(subtitleLabel, &lv_font_montserrat_12, 0);

  timeLabel = lv_label_create(header);
  lv_obj_align(timeLabel, LV_ALIGN_RIGHT_MID, -6, 0);
  lv_label_set_text(timeLabel, "00:00");
  lv_obj_set_style_text_color(timeLabel, lv_color_hex(0x8DA5C8), 0);

  lv_obj_t* content = lv_obj_create(scr);
  lv_obj_set_size(content, LV_PCT(100), LV_PCT(100));
  lv_obj_align(content, LV_ALIGN_TOP_MID, 0, 64);
  lv_obj_set_style_bg_opa(content, LV_OPA_TRANSP, 0);
  lv_obj_set_style_pad_all(content, 12, 0);
  lv_obj_set_flex_flow(content, LV_FLEX_FLOW_ROW_WRAP);
  lv_obj_set_flex_align(content, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);
  lv_obj_set_style_pad_gap(content, 10, 0);

  auto addCard = [&](lv_obj_t* parent, const char* title, const char* value, const char* note, lv_obj_t** valueLabelOut) {
    lv_obj_t* card = lv_obj_create(parent);
    lv_obj_set_size(card, 140, 82);
    lv_obj_set_style_bg_color(card, lv_color_hex(0x11253E), 0);
    lv_obj_set_style_radius(card, 16, 0);
    lv_obj_set_style_pad_all(card, 10, 0);

    lv_obj_t* t = lv_label_create(card);
    lv_label_set_text(t, title);
    lv_obj_set_style_text_color(t, lv_color_hex(0xE5F2FF), 0);
    lv_obj_align(t, LV_ALIGN_TOP_LEFT, 0, 0);

    lv_obj_t* v = lv_label_create(card);
    lv_label_set_text(v, value);
    lv_obj_set_style_text_font(v, &lv_font_montserrat_18, 0);
    lv_obj_set_style_text_color(v, lv_color_hex(0x60A5FA), 0);
    lv_obj_align(v, LV_ALIGN_LEFT_MID, 0, 4);

    lv_obj_t* n = lv_label_create(card);
    lv_label_set_text(n, note);
    lv_obj_set_style_text_color(n, lv_color_hex(0x8DA5C8), 0);
    lv_obj_set_style_text_font(n, &lv_font_montserrat_12, 0);
    lv_obj_align(n, LV_ALIGN_BOTTOM_LEFT, 0, -2);

    if (valueLabelOut != nullptr) {
      *valueLabelOut = v;
    }

    return card;
  };

  lv_obj_t* card1 = addCard(content, "Engagement", "+24%", "Instagram + TikTok", &metricValue1);
  lv_obj_t* card2 = addCard(content, "Reviews", "4.9/5", "New alerts live", &metricValue2);
  lv_obj_t* card3 = addCard(content, "Leads", "321", "Qualified this month", &metricValue3);
  lv_obj_t* card4 = addCard(content, "Sales", "$18.2K", "Strong growth", &metricValue4);

  (void)card1;
  (void)card2;
  (void)card3;
  (void)card4;

  statusLabel = lv_label_create(scr);
  lv_obj_align(statusLabel, LV_ALIGN_BOTTOM_LEFT, 12, -10);
  lv_label_set_text(statusLabel, "Connecting...");
  lv_obj_set_style_text_color(statusLabel, lv_color_hex(0x8DA5C8), 0);
}

void setup() {
  Serial.begin(115200);
  tft.begin();
  tft.setRotation(1);
  tft.fillScreen(TFT_BLACK);

  lv_init();

  lv_disp_draw_buf_init(&draw_buf, buf, NULL, LV_HOR_RES_MAX * 20);

  static lv_disp_drv_t disp_drv;
  lv_disp_drv_init(&disp_drv);
  disp_drv.hor_res = 320;
  disp_drv.ver_res = 240;
  disp_drv.flush_cb = my_disp_flush;
  disp_drv.draw_buf = &draw_buf;
  lv_disp_drv_register(&disp_drv);

  connectWiFi();
  createDashboardUI();
  updateClock();
}

void loop() {
  static unsigned long lastTick = 0;
  unsigned long now = millis();

  if (now - lastTick >= LV_TICK_PERIOD) {
    lastTick = now;
    lv_tick_inc(LV_TICK_PERIOD);
  }

  lv_timer_handler();
  delay(1);

  if (millis() - lastTick > 1000) {
    updateClock();
  }

  static unsigned long lastApi = 0;
  if (millis() - lastApi > 10000) {
    lastApi = millis();
    String payload = fetchDashboard();
    updateDashboardUI(payload);
  }
}
