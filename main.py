import network
import utime
import urequests
import ubinascii
from ubluetooth import BLE
from env import env2 as env
from machine import Timer

# 環境変数がロードされているか確認
if not env:
    raise ValueError(".env file not loaded or empty. Ensure the file exists and contains valid key-value pairs.")

# Wi-Fi接続情報
SSID = env.get("SSID")
PASSWORD = env.get("PASSWORD")

IFTTT_EVENT = env.get("IFTTT_EVENT")
IFTTT_KEY = env.get("IFTTT_KEY")

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


def send_to_ifttt(rssi, mac):
    url = f"https://maker.ifttt.com/trigger/{IFTTT_EVENT}/with/key/{IFTTT_KEY}"
    payload = {"value1": mac, "value2": rssi}
    headers = {"Content-Type": "application/json"}
    response = urequests.post(url, json=payload, headers=headers)
    print(response.text)


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


def estimate_distance(rssi):
    txPower = -59
    if rssi == 0:
        return float("inf")  # 無限大を返す
    ratio = rssi * 1.0 / txPower
    if ratio < 1.0:
        return pow(ratio, 10)
    else:
        return (0.89976) * pow(ratio, 7.7095) + 0.111


def bt_irq(event, data):
    if event == 5:  # Event 5 is for scan results
        addr_type, addr, adv_type, rssi, adv_data = data
        mac = ubinascii.hexlify(addr).decode()
        name = parse_adv_data(adv_data)
        current_time = utime.time()

        if mac not in devices:
            devices[mac] = {"name": name, "max_rssi": rssi, "min_rssi": rssi, "last_seen": current_time, "current_rssi": rssi}
        else:
            devices[mac].update({"last_seen": current_time, "max_rssi": max(devices[mac]["max_rssi"], rssi), "min_rssi": min(devices[mac]["min_rssi"], rssi), "current_rssi": rssi})


def format_time(timestamp):
    t = utime.localtime(timestamp)
    return "{:02d}:{:02d}:{:02d}".format(t[3], t[4], t[5])


def print_device_list():
    current_time = utime.time()

    # 画面をクリア
    print("\033[2J\033[H", end="")

    print(f"Devices seen in the last minute (sorted by estimated distance) - Current time: {format_time(current_time)}")
    print("MAC Address         | Device Name        | Current | Max RSSI | Min RSSI | Est. Dist (m) | Last Seen                ")
    print("-" * 115)

    # デバイスリストを作成し、推定距離でソート
    sorted_devices = []
    for mac, info in devices.items():
        if current_time - info["last_seen"] <= 120:  # 直近1分以内に見たデバイスのみ
            current_rssi = info.get("current_rssi", info["max_rssi"])  # current_rssiがない場合はmax_rssiを使用
            est_distance = estimate_distance(current_rssi)
            sorted_devices.append((mac, info, est_distance))

    sorted_devices.sort(key=lambda x: x[2])  # 推定距離でソート

    for mac, info, est_distance in sorted_devices:
        last_seen_str = format_time(info["last_seen"])
        current_rssi = info.get("current_rssi", info["max_rssi"])  # current_rssiがない場合はmax_rssiを使用
        time_since_last_detection = current_time - info["last_seen"]
        print(f"{mac:18} | {info['name'][:18]:18} | {current_rssi:7} | {info['max_rssi']:8} | {info['min_rssi']:8} | {est_distance:12.2f} | {last_seen_str} ({time_since_last_detection} seconds ago)")

    print("-" * 115)
    # デバイスリストを作成し、推定距離でソート
    sorted_devices = []
    for mac, info in devices.items():
        if current_time - info["last_seen"] > 120:  # 直近1分以内に見たデバイスのみ
            current_rssi = info.get("current_rssi", info["max_rssi"])  # current_rssiがない場合はmax_rssiを使用
            est_distance = estimate_distance(current_rssi)
            sorted_devices.append((mac, info, est_distance))

    sorted_devices.sort(key=lambda x: x[2])  # 推定距離でソート

    for mac, info, est_distance in sorted_devices:
        last_seen_str = format_time(info["last_seen"])
        current_rssi = info.get("current_rssi", info["max_rssi"])  # current_rssiがない場合はmax_rssiを使用
        time_since_last_detection = current_time - info["last_seen"]
        print(f"{mac:18} | {info['name'][:18]:18} | {current_rssi:7} | {info['max_rssi']:8} | {info['min_rssi']:8} | {est_distance:12.2f} | {last_seen_str} ({time_since_last_detection} seconds ago)")


def periodic_send(timer):
    for k, v in devices.items():
        rssi, mac = devices[k]["current_rssi"], k
        send_to_ifttt(rssi, mac)


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

    # 1秒毎にデータを送信するタイマー設定
    timer = Timer(-1)
    timer.init(period=1000, mode=Timer.PERIODIC, callback=periodic_send)

    # 1秒おきにデバイスリストを表示
    while True:
        print_device_list()
        utime.sleep(0.1)


if __name__ == "__main__":
    main()
