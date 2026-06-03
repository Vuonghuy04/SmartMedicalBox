//import libraries

#include <Keypad.h>
#include <Servo.h>
#include <DHT.h>


//set up pins
const int servoPin = 3;

const int ldrPin = A0;

const int button = A2;

const int buzzer = A1;

const int redPin = A3;
const int greenPin = A4;
const int bluePin = A5;

Servo myServo;  //servo object

unsigned long lastSend = 0;

//dht11 sensor setup
#define DHTPIN 2
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);


//set up password system
String password = "7866";
String input = "";
bool Unlocked = false;  //state

//set alarm states from the Edge Server
bool ldrAlarm = false;   //light intrusion
bool tempAlarm = false;  //temperature alarm
bool humAlarm = false;   //humidity alarm
bool alarmMute = false;  //mute buzzer


//delay locking to prevent triggering ldr instantly
unsigned long armDelayStart = 0;
bool armDelayActive = false;

//control red and green flashes
unsigned long greenStartTime = 0;
unsigned long redStartTime = 0;
bool showGreen = false;
bool showRed = false;

//configure keypad
const byte ROWS = 4, COLS = 4;
char keys[ROWS][COLS] = {
  { '1', '2', '3', 'A' },
  { '4', '5', '6', 'B' },
  { '7', '8', '9', 'C' },
  { '*', '0', '#', 'D' }
};
byte rowPins[ROWS] = { 13, 12, 11, 10 };
byte colPins[COLS] = { 9, 8, 7, 6 };

Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);  //keypad object


//setRGB function - controls rgb
void setRGB(bool r, bool g, bool b) {
  digitalWrite(redPin, r);
  digitalWrite(greenPin, g);
  digitalWrite(bluePin, b);
}


void setup() {
  Serial.begin(9600);

  pinMode(buzzer, OUTPUT);
  pinMode(redPin, OUTPUT);
  pinMode(greenPin, OUTPUT);
  pinMode(bluePin, OUTPUT);
  pinMode(button, INPUT_PULLUP);  //pressed = low

  dht.begin();  //Start dht11 sensor

  myServo.attach(servoPin);
  myServo.write(0);  //sets servo to start position(locked)

  setRGB(0, 0, 0);
}

void loop() {
  //read commands from the Edge Server
  while (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    //turn on LDR alarm
    if (cmd == "ALARM_LDR") {
      ldrAlarm = true;
      alarmMute = false;
    }

    //turn on temperature alarm
    if (cmd == "ALARM_TEMP") {
      tempAlarm = true;
      alarmMute = false;
    }


    //turn on humidity alarm
    if (cmd == "ALARM_HUM") {
      humAlarm = true;
      alarmMute = false;
    }

    //turn off LDR alarm
    if (cmd == "CLEAR_LDR") {
      ldrAlarm = false;
    }

    //turn off temp alarm
    if (cmd == "CLEAR_TEMP") {
      tempAlarm = false;
    }

    //turn off humidity alarm
    if (cmd == "CLEAR_HUM") {
      humAlarm = false;
    }

    //rest all alarms
    if (cmd == "CLEAR_ALL") {
      ldrAlarm = tempAlarm = humAlarm = false;
      noTone(buzzer);
    }

    //mute buzzer
    if (cmd == "MUTE") {
      alarmMute = true;
      noTone(buzzer);
    }

    if (cmd == "UNMUTE") {
      alarmMute = false;
    }

    //lock/unlock from web server
    if (cmd == "LOCK") {
      Unlocked = false;
      myServo.write(0);
    } else if (cmd == "UNLOCK") {
      Unlocked = true;
      myServo.write(90);  // unlocked position
    }
  }
  //read sensor inputs
  int light = analogRead(ldrPin);
  float temp = dht.readTemperature();
  float hum = dht.readHumidity();

  //mute button
  if (digitalRead(button) == LOW) {
    alarmMute = true;
    noTone(buzzer);
  }

  //green flash when password correct
  if (showGreen) {
    setRGB(0, 1, 0);
    if (millis() - greenStartTime > 2000) showGreen = false;
    return;
  }

  //red flash for wrong password
  if (showRed) {
    setRGB(1, 0, 0);
    if (millis() - redStartTime > 1000) showRed = false;
    return;
  }

  //delay alarm reset
  if (armDelayActive && millis() - armDelayStart > 2000)
    armDelayActive = false;



  //keypad logic
  char key = keypad.getKey();
  if (key) {
    if (key == '*') {
      input = "";
    } else if (key == '#') {    //checks password when key '#'
      if (input == password) {  //correct password
        Unlocked = !Unlocked;

        if (Unlocked) {
          myServo.write(90);  //move servo to unlocked position
          showGreen = true;   //flash green led
          greenStartTime = millis();

        } else {                  //locking
          myServo.write(0);       //lock position
          armDelayActive = true;  //delay
          armDelayStart = millis();
        }

        ldrAlarm = false;  // reset ldr alarm only
        alarmMute = false;
        noTone(buzzer);

      } else {           //wrong password
        showRed = true;  //flash red
        redStartTime = millis();
      }

      input = "";
    } else {

      input += key;
    }
  }



  //buzzer logic
  if (!alarmMute) {
    //set frequencies for different alarms
    if (ldrAlarm)
      tone(buzzer, 1000);

    else if (tempAlarm)
      tone(buzzer, 800);

    else if (humAlarm)
      tone(buzzer, 600);

    else
      noTone(buzzer);

  } else {
    noTone(buzzer);
  }

  //RGB
  if (ldrAlarm)
    setRGB(1, 0, 0);  //red = ldr intrusion alarm

  else if (tempAlarm)
    setRGB(0, 0, 1);  //blue = temperature alarm

  else if (humAlarm)
    setRGB(0, 1, 0);  //green = humidity alar

  else
    setRGB(0, 0, 0);

  // send sensor data to the Edge Server
  if (millis() - lastSend >= 500) {
    if (!isnan(temp) && !isnan(hum)) {
      Serial.print(light);
      Serial.print(",");
      Serial.print(temp);
      Serial.print(",");
      Serial.print(hum);
      Serial.print(",");
      Serial.println(Unlocked ? 1 : 0);
    }
    lastSend = millis();
  }
}