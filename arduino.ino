#include <SoftwareSerial.h>
#include <Wire.h>
#include "RTClib.h"

RTC_DS3231 rtc;
SoftwareSerial BTSerial(2, 3); // 2為RX(接TXD)，3為TX(接RXD)

const long baudRate = 9600; // 傳輸速率
String cmd; // app 傳送之指令
const int buzzerPin = 9;
int i = 0;
String sleepDuration = "", startTime = "", asleepTime = "", buzzTime = "";

void setup() {
  Serial.begin(baudRate); // 啟動序列通訊
  BTSerial.begin(baudRate); // 啟動藍牙序列通訊
  rtc.begin();

  if (rtc.lostPower()) {
    rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
  }
  pinMode(buzzerPin, OUTPUT);
}

void loop() {
  if (BTSerial.available()) { // 藍芽
    char receivedChar = BTSerial.read(); // 讀取app(藍芽)傳來的命令
    if (receivedChar == '\n' && cmd[0] == 'a') {

      int firstCommaIndex = cmd.indexOf(',');
      int secondCommaIndex = cmd.indexOf(',', firstCommaIndex + 1);

      sleepDuration = cmd.substring(firstCommaIndex + 1, secondCommaIndex);
      startTime = cmd.substring(secondCommaIndex + 1);
      Serial.println("start");

      tone(buzzerPin, 1000);
      delay(500);           
      noTone(buzzerPin);
      cmd = "";
    } else {
      cmd += receivedChar;
    }
  }
  if (Serial.available()) {
    String receivedData = Serial.readStringUntil('\n');
    int commaIndex = receivedData.indexOf(',');
    
    if (receivedData[0] == 'd') {
      asleepTime = receivedData.substring(commaIndex + 1);
      String actualAT = calculateBuzzTime(asleepTime, startTime);
      buzzTime = calculateBuzzTime(actualAT, sleepDuration);
      String TBSend = "e,"+actualAT+","+buzzTime+"\n";
      BTSerial.write(TBSend.c_str());
    }
    else if (receivedData[0] == 'b') {
      String TBSend = "c,"+receivedData.substring(commaIndex + 1)+"\n";
      BTSerial.write(TBSend.c_str());
    }
  }

  DateTime now = rtc.now();
  char currentTime[6];
  sprintf(currentTime, "%02d:%02d", now.hour(), now.minute());
  if (String(currentTime) >= buzzTime && buzzTime != "") {
    tone(buzzerPin, 1000);
    delay(500);
    noTone(buzzerPin); 
  } else {
    noTone(buzzerPin); 
  }
}

String calculateBuzzTime(String asleepTime, String sleepDuration) {
  int asleepHour = asleepTime.substring(0, 2).toInt();
  int asleepMinute = asleepTime.substring(3, 5).toInt();
  int durationHour = sleepDuration.substring(0, 2).toInt();
  int durationMinute = sleepDuration.substring(3, 5).toInt();

  int buzzHour = asleepHour + durationHour;
  int buzzMinute = asleepMinute + durationMinute;

  if (buzzMinute >= 60) {
    buzzMinute -= 60;
    buzzHour += 1;
  }

  if (buzzHour >= 24) {
    buzzHour -= 24;
  }

  String buzzTime = (buzzHour < 10 ? "0" : "") + String(buzzHour) + ":" + (buzzMinute < 10 ? "0" : "") + String(buzzMinute);
  return buzzTime;
}