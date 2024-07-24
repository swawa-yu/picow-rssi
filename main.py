import network
import utime
import ubinascii
from ubluetooth import BLE
from env import env

# 環境変数がロードされているか確認
if not env:
    raise ValueError(".env file not loaded or empty. Ensure the file exists and contains valid key-value pairs.")

# Wi-Fi接続情報
SSID = env.get("SSID")
PASSWORD = env.get("PASSWORD")

# デバイス情報を保存する辞書
devices = {}


# Wi-Fi接続
def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    print(f"Connecting to Wi-Fi({ssid})...")
    wlan.connect(ssid, password)

    while not wlan.isconnected():
        pass

    print("Wi-Fi connected:", wlan.ifconfig())


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
        current_time = utime.time()

        if mac not in devices:
            devices[mac] = {"name": name, "max_rssi": rssi, "min_rssi": rssi, "last_seen": current_time}
        else:
            devices[mac]["last_seen"] = current_time
            devices[mac]["max_rssi"] = max(devices[mac]["max_rssi"], rssi)
            devices[mac]["min_rssi"] = min(devices[mac]["min_rssi"], rssi)


def print_device_list():
    current_time = utime.time()
    print("\nDevices seen in the last minute:")
    print("MAC Address         | Device Name        | Max RSSI | Min RSSI")
    print("-" * 65)
    for mac, info in devices.items():
        if current_time - info["last_seen"] <= 60:  # 直近1分以内に見たデバイスのみ
            print(f"{mac:18} | {info['name'][:18]:18} | {info['max_rssi']:8} | {info['min_rssi']:8}")


def main():
    # 環境変数のチェック
    if not SSID or not PASSWORD:
        raise ValueError("Missing Wi-Fi configuration. Check your .env file.")

    # Wi-Fi接続
    connect_wifi(SSID, PASSWORD)

    # BLE設定
    print("BLE setting start.")
    ble = BLE()
    ble.active(True)
    ble.irq(bt_irq)
    ble.gap_scan(0)  # 継続的にスキャン
    print("BLE setting finished.")

    # 5秒おきにデバイスリストを表示
    while True:
        print_device_list()
        utime.sleep(5)


if __name__ == "__main__":
    main()
