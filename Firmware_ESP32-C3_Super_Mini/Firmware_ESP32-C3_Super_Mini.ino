#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>
#include <BLE2902.h>

#define CONTROL_A 5
#define CONTROL_B 6
#define CONTROL_C 7
#define ADC_PIN 1

#define BATTERY_PIN 4 

const float VCC = 3.3;
const float R_DIV = 10000.0;

int caso = 0;
int contador = 0;
bool enviarPaquete = false;

// ===== UUIDs personalizados =====
#define SERVICE_UUID        "8f3a2c10-7b21-4c9e-b8aa-001122334455"
#define CHAR_DATA_UUID      "8f3a2c11-7b21-4c9e-b8aa-001122334455"

// ===== Variables BLE =====
BLECharacteristic *pDataCharacteristic;
bool deviceConnected = false;

// ===== Protocolo =====
uint8_t sequenceNumber = 0;
uint8_t nodeID = 0x01;

// ===== CRC-8 simple XOR =====
uint8_t calculateCRC(uint8_t *data, int length) {
  uint8_t crc = 0;

  for (int i = 0; i < length; i++) {
    crc ^= data[i];
  }

  return crc;
}

// ===== Callback conexión =====
class MyServerCallbacks: public BLEServerCallbacks {

  void onConnect(BLEServer* pServer) {
    deviceConnected = true;
    Serial.println("Cliente conectado");
  }

  void onDisconnect(BLEServer* pServer) {
    deviceConnected = false;
    Serial.println("Cliente desconectado");
  }
};

// ===== Selección de canal =====
void seleccionarCanal(uint8_t canal) {

  digitalWrite(CONTROL_A, canal & 0x01);
  digitalWrite(CONTROL_B, (canal >> 1) & 0x01);
  digitalWrite(CONTROL_C, (canal >> 2) & 0x01);
}

// ===== Lectura estabilizada =====
uint16_t leerCanal(uint8_t canal) {

  seleccionarCanal(canal);

  delayMicroseconds(500);

  return analogRead(ADC_PIN);
}

// ===== Conversión FSR =====
uint16_t calcularFuerza(uint16_t adcValue) {

  if (adcValue <= 0) {
    return 0;
  }

  float fsrV = adcValue * VCC / 4095.0;

  // Protección división por cero
  if (fsrV <= 0.001) {
    return 0;
  }

  float fsrR = R_DIV * (VCC / fsrV - 1.0);

  // Protección resistencia inválida
  if (fsrR <= 0) {
    return 0;
  }

  float fsrG = 1.0 / fsrR;

  float force = (fsrR <= 600) ?
                (fsrG - 0.00075) / 0.00000032639 :
                fsrG / 0.000000642857;

  
  if (force < 3) {
    force = 0;
  }

  return (uint16_t)force;
}

// Lectura de la batería
 
uint8_t leerBateria() {

  uint16_t adc = analogRead(BATTERY_PIN);

  float vBatCH = adc * VCC / 4095.0;

  // Divisor 2M / 3M
  float vBat = vBatCH * (5.0 / 3.0);

  // Conversión a porcentaje
  float porcentaje = ((vBat - 3.0) / (4.2 - 3.0)) * 100.0;

  if (porcentaje < 0)
    porcentaje = 0;

  if (porcentaje > 100)
    porcentaje = 100;

  return (uint8_t)porcentaje;
}

void setup() {

  Serial.begin(115200);

  pinMode(CONTROL_A, OUTPUT);
  pinMode(CONTROL_B, OUTPUT);
  pinMode(CONTROL_C, OUTPUT);
  pinMode(BATTERY_PIN, INPUT);

  BLEDevice::init("ESP32_SPP_SPM");

  BLEServer *pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());

  BLEService *pService = pServer->createService(SERVICE_UUID);

  pDataCharacteristic = pService->createCharacteristic(
                          CHAR_DATA_UUID,
                          BLECharacteristic::PROPERTY_NOTIFY
                        );

  pDataCharacteristic->addDescriptor(new BLE2902());

  pService->start();

  pServer->getAdvertising()->start();

  Serial.println("Esperando conexión BLE...");
}

void loop() {

  if (!deviceConnected) {
    delay(500);
    return;
  }

  static uint16_t f1 = 0;
  static uint16_t f2 = 0;
  static uint16_t f3 = 0;
  static uint16_t f4 = 0;
  static uint16_t f5 = 0;
  static uint16_t f6 = 0;

  uint16_t adcValue = 0;

  // ===== MULTIPLEXADO =====
  switch(caso) {

    case 0:

      enviarPaquete = false;

      adcValue = leerCanal(0);

      f1 = calcularFuerza(adcValue);

      caso += 1;

      break;


    case 1:

      adcValue = leerCanal(1);

      f2 = calcularFuerza(adcValue);

      caso += 1;

      break;


    case 2:

      adcValue = leerCanal(2);

      f3 = calcularFuerza(adcValue);

      caso += 1;

      break;


    case 3:

      adcValue = leerCanal(3);

      f4 = calcularFuerza(adcValue);

      caso+= 1;
     
      break;
    
    case 4:

      adcValue = leerCanal(4);

      f5 = calcularFuerza(adcValue);

      caso+= 1;
     
      break;

    case 5:
      adcValue = leerCanal(5);

      f6 = calcularFuerza(adcValue);

      enviarPaquete = true;

      caso = 0;
  }

  uint8_t batteryLevel = leerBateria();

  if(enviarPaquete){
      // ===== Timestamp =====
      uint16_t timestamp = millis() & 0xFFFF;

      // ===== Construcción paquete =====
      uint8_t packet[20];

      int idx = 0;

      uint8_t version = 0x01;
      uint8_t type = 0x01;

      packet[idx++] = (version << 4) | type;

      packet[idx++] = nodeID;

      packet[idx++] = sequenceNumber;

      // ===== F1 =====
      packet[idx++] = highByte(f1);
      packet[idx++] = lowByte(f1);

      // ===== F2 =====
      packet[idx++] = highByte(f2);
      packet[idx++] = lowByte(f2);

      // ===== F3 =====
      packet[idx++] = highByte(f3);
      packet[idx++] = lowByte(f3);

      // ===== F4 =====
      packet[idx++] = highByte(f4);
      packet[idx++] = lowByte(f4);

      // ===== F5 =====
      packet[idx++] = highByte(f5);
      packet[idx++] = lowByte(f5);

      // ===== F6 =====

      packet[idx++] = highByte(f6);
      packet[idx++] = lowByte(f6);

      // ===== Battery =====
      packet[idx++] = batteryLevel; 

      // ===== Timestamp =====
      packet[idx++] = highByte(timestamp);
      packet[idx++] = lowByte(timestamp);

      // ===== CRC =====
      uint8_t crc = calculateCRC(packet, idx);

      packet[idx++] = crc;

      // ===== Enviar BLE =====
      pDataCharacteristic->setValue(packet, idx);

      pDataCharacteristic->notify();

      // ===== Debug serial =====
      Serial.print("Seq: ");
      Serial.print(sequenceNumber);

      Serial.print(" | F1: ");
      Serial.print(f1);

      Serial.print(" | F2: ");
      Serial.print(f2);

      Serial.print(" | F3: ");
      Serial.print(f3);

      Serial.print(" | F4: ");
      Serial.print(f4);

      Serial.print(" | F5: ");
      Serial.print(f5);

      Serial.print(" | F6: ");
      Serial.print(f6);

      Serial.print(" | BAT: ");
      Serial.print(batteryLevel);
      Serial.print("%");

      Serial.print(" | T: ");
      Serial.println(timestamp);

      sequenceNumber++;

      delay(100);
  }
}