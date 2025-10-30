import streamlit as st
import asyncio
import hashlib
import json
import time
from pathlib import Path
from bleak import BleakScanner

# === CONFIG ===
SAVE_FILE = Path("devices.json")
SCAN_INTERVAL = 5
SCAN_DURATION = 4
EXIT_TIMEOUT = 30
TAG_PREFIX = "TAG"


# === HELPER FUNCTIONS ===
def load_devices():
    if SAVE_FILE.exists():
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_devices(devices):
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(devices, f, indent=2, ensure_ascii=False)


def make_tag(addr: str) -> str:
    h = hashlib.sha1(addr.encode()).hexdigest()[:8].upper()
    return f"{TAG_PREFIX}-{h}"


def mark_seen(devices, addr, name, rssi):
    now = int(time.time())
    if addr in devices:
        d = devices[addr]
        d["last_seen"] = now
        d["rssi"] = rssi
        d["status"] = "IN"
        d["seen_count"] = d.get("seen_count", 0) + 1
        if name:
            d["ble_name"] = name
    else:
        tag = make_tag(addr)
        devices[addr] = {
            "tag": tag,
            "address": addr,
            "ble_name": name or "-",
            "custom_name": "",
            "rssi": rssi,
            "first_seen": now,
            "last_seen": now,
            "status": "IN",
            "seen_count": 1
        }


def cleanup_exits(devices):
    now = int(time.time())
    for addr, d in list(devices.items()):
        if d.get("status") == "IN" and now - d.get("last_seen", 0) > EXIT_TIMEOUT:
            d["status"] = "OUT"
            d["out_time"] = now


async def scan_once(devices):
    scanner = BleakScanner()
    try:
        await scanner.start()
        await asyncio.sleep(SCAN_DURATION)
        await scanner.stop()
    except Exception as e:
        st.error(f"Error scanning: {e}")
        return

    found = await scanner.get_discovered_devices()
    for dev in found:
        mark_seen(devices, dev.address, dev.name, getattr(dev, "rssi", None))

    cleanup_exits(devices)
    save_devices(devices)


# === STREAMLIT APP ===
st.set_page_config(page_title="BLE RFID-like Scanner", layout="wide")
st.title("📡 Bluetooth (BLE) RFID-like Scanner + Penamaan Tag")

devices = load_devices()

col1, col2, col3 = st.columns(3)
with col1:
    scan_btn = st.button("🔍 Scan Sekali")
with col2:
    auto_scan = st.toggle("Auto Scan (Tiap 5 detik)", value=False)
with col3:
    if st.button("🧹 Hapus Semua Data"):
        devices = {}
        save_devices(devices)
        st.success("Data perangkat dihapus.")

# === MANUAL TAGGING ===
st.subheader("✏️ Beri Nama untuk Tag Bluetooth")
if devices:
    selected_addr = st.selectbox("Pilih Tag yang Ingin Diberi Nama:", list(devices.keys()), format_func=lambda x: f"{devices[x]['tag']} ({devices[x]['custom_name'] or 'Belum dinamai'})")
    new_name = st.text_input("Masukkan Nama Baru:", devices[selected_addr].get("custom_name", ""))
    if st.button("💾 Simpan Nama"):
        devices[selected_addr]["custom_name"] = new_name
        save_devices(devices)
        st.success(f"Nama disimpan untuk {devices[selected_addr]['tag']}")
else:
    st.info("Belum ada perangkat terdeteksi.")

# === PEMINDAIAN ===
if scan_btn:
    with st.spinner("Memindai perangkat BLE..."):
        asyncio.run(scan_once(devices))
        st.success("Selesai scan!")

# Auto scan loop (simulasi RFID gate aktif)
if auto_scan:
    st.info("Auto scanning aktif... (perbarui daftar tiap 5 detik)")
    scan_placeholder = st.empty()
    while True:
        asyncio.run(scan_once(devices))
        df = [
            {
                "Tag": d["tag"],
                "Nama BLE": d["ble_name"],
                "Nama Kustom": d["custom_name"] or "-",
                "Alamat": d["address"],
                "RSSI": d.get("rssi"),
                "Status": d.get("status"),
                "Terakhir Terlihat (detik lalu)": int(time.time()) - d.get("last_seen", 0),
            }
            for d in devices.values()
        ]
        scan_placeholder.dataframe(df, use_container_width=True)
        time.sleep(SCAN_INTERVAL)
else:
    df = [
        {
            "Tag": d["tag"],
            "Nama BLE": d["ble_name"],
            "Nama Kustom": d["custom_name"] or "-",
            "Alamat": d["address"],
            "RSSI": d.get("rssi"),
            "Status": d.get("status"),
            "Terakhir Terlihat (detik lalu)": int(time.time()) - d.get("last_seen", 0),
        }
        for d in devices.values()
    ]
    st.dataframe(df, use_container_width=True)
