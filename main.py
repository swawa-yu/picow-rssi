import network
import urequests
import utime
import time
from machine import Pin
import ubinascii
from ubluetooth import BLE, UUID
from env import env


# 環境変数がロードされているか確認
if not env:
    raise ValueError(".env file not loaded or empty. Ensure the file exists and contains valid key-value pairs.")

# Wi-Fi接続情報
SSID = env.get("SSID")
PASSWORD = env.get("PASSWORD")

# IFTTT情報
IFTTT_EVENT = env.get("IFTTT_EVENT")
IFTTT_KEY = env.get("IFTTT_KEY")


# Wi-Fi接続
def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    print(f"Connecting to Wi-Fi({SSID})...")
    wlan.connect(ssid, password)

    while not wlan.isconnected():
        pass

    print("Wi-Fi connected:", wlan.ifconfig())


# グローバル変数でデバイスの最後の送信時刻を追跡
last_send_time = {}


def send_to_ifttt(rssi, mac, name):
    current_time = utime.time()
    if mac not in last_send_time or current_time - last_send_time[mac] >= 1:
        url = f"https://maker.ifttt.com/trigger/{IFTTT_EVENT}/with/key/{IFTTT_KEY}"
        payload = {"value1": mac, "value2": rssi, "value3": name}
        headers = {"Content-Type": "application/json"}
        response = urequests.post(url, json=payload, headers=headers)
        print(f"Sent data for {mac}: RSSI={rssi}, Name={name}")
        print(response.text)
        last_send_time[mac] = current_time
    else:
        print(f"Skipped sending for {mac}: too soon since last send")


def parse_adv_data(adv_data):
    name = ""
    i = 0
    while i < len(adv_data):
        if i + 1 >= len(adv_data):
            break
        length = adv_data[i]
        type = adv_data[i + 1]
        if length == 0:
            break
        data = adv_data[i + 2 : i + 1 + length]
        if type == 0x09 or type == 0x08:  # Complete Local Name or Shortened Local Name
            try:
                name = bytes(data).decode("utf-8")
                break
            except UnicodeDecodeError:
                name = "Decode Error"
        i += length + 1
    return name if name else "Unknown"


def bt_irq(event, data):
    if event == 5:  # Event 5 is for scan results
        addr_type, addr, adv_type, rssi, adv_data = data
        mac = ubinascii.hexlify(addr).decode()
        name = parse_adv_data(adv_data)
        send_to_ifttt(rssi, mac, name)


last_data = None


def main():
    global last_data

    # 環境変数のチェック
    if not SSID or not PASSWORD or not IFTTT_EVENT or not IFTTT_KEY:
        raise ValueError("Missing Wi-Fi or IFTTT configuration. Check your .env file.")

    # Wi-Fi接続
    connect_wifi(SSID, PASSWORD)

    # BLE設定
    print("BLE setting start.")
    ble = BLE()
    ble.active(True)
    ble.irq(bt_irq)
    # ble.gap_scan(0)  # Start scanning (0 means scan indefinitely)
    ble.gap_scan(10000, 30000, 30000)  # Scan for 10 seconds, with 30ms interval and window
    print("BLE setting finished.")

    # 1秒毎にデータを送信するループ
    while True:
        utime.sleep(1)


if __name__ == "__main__":
    main()
