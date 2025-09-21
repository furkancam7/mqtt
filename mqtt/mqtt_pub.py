#!/usr/bin/env python3
import os, sys, time, zlib, hashlib, logging, argparse, uuid
import cbor2
import paho.mqtt.client as mqtt
from zstandard import ZstdCompressor

BROKER_HOST = "127.0.0.1"
BROKER_PORT = 1883
CLIENT_ID   = "jetson-pub"

TOPIC_TLM       = "sat/telemetry"
TOPIC_IMG       = "sat/image"          # header/meta
TOPIC_IMG_CHUNK = "sat/image/chunk"    # chunks

QOS = 1
CHUNK_SIZE = 60 * 1024          # ~60KB (broker/MTU için güvenli)
RETRY_MAX  = 5

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")


def crc32(b: bytes) -> int:
    return zlib.crc32(b) & 0xFFFFFFFF


def connect_client(host, port, client_id):
    c = mqtt.Client(client_id=client_id, clean_session=False,
                    protocol=mqtt.MQTTv311, transport="tcp")
    # c.username_pw_set("user", "pass")  # gerekiyorsa
    c.will_set("sat/status", payload=f"{client_id}:offline", qos=1, retain=False)
    c.on_connect = lambda c,u,f,rc: logging.info("connected rc=%s", rc)
    c.on_disconnect = lambda c,u,rc: logging.warning("disconnected rc=%s", rc)
    c.max_queued_messages_set(0)  # istersen sınır koyabilirsin
    c.connect(host, port, keepalive=60)
    c.loop_start()
    return c


def publish_with_retry(c, topic, payload: bytes, qos=QOS, retain=False, max_retries=RETRY_MAX):
    for attempt in range(1, max_retries + 1):
        result, mid = c.publish(topic, payload=payload, qos=qos, retain=retain)
        if result == mqtt.MQTT_ERR_SUCCESS:
            return True
        logging.warning("publish attempt %d failed (result=%s) topic=%s", attempt, result, topic)
        time.sleep(min(2 ** attempt, 8))
    logging.error("publish failed after %d attempts topic=%s", max_retries, topic)
    return False


def send_telemetry(c, seq: int):
    obj = {"ts": time.time_ns(), "temp": 23.4, "press": 1012.2, "batt": 3.91, "seq": seq}
    raw = cbor2.dumps(obj)
    comp = ZstdCompressor(level=6).compress(raw)
    msg = {
        "ts": obj["ts"], "seq": seq, "type": 0,
        "enc": "zstd", "crc": crc32(comp), "payload": comp
    }
    return publish_with_retry(c, TOPIC_TLM, cbor2.dumps(msg))


def chunk_bytes(data: bytes, chunk_size: int):
    for i in range(0, len(data), chunk_size):
        yield i // chunk_size, data[i:i + chunk_size]


def send_image(client, path: str) -> bool:
    """Sıkıştırılmış görseli meta+chunk olarak gönder."""
    with open(path, "rb") as f:
        img = f.read()

    file_id = uuid.uuid4().hex
    ts = time.time_ns()

    # Sıkıştır
    comp = ZstdCompressor(level=10).compress(img)
    total_size_raw  = len(img)
    total_size_comp = len(comp)
    total_chunks = (total_size_comp + CHUNK_SIZE - 1) // CHUNK_SIZE
    sha256_comp = hashlib.sha256(comp).hexdigest()

    # META / header
    header = {
    "file_id": file_id,
    "name": os.path.basename(path),
    "ts": ts,
    "enc": "zstd",

    # Boyutlar
    "size_raw": total_size_raw,      # bilgilendirme
    "size_comp": total_size_comp,    # asıl gönderilenin boyutu
    "size": total_size_comp,         # 🔴 geri uyumluluk: viewer 'size' bekliyor

    # Parça sayısı
    "chunks": total_chunks,          # bizim alanımız
    "total": total_chunks,           # 🔴 geri uyumluluk: consumer 'total' bekliyor

    "sha256": sha256_comp,
    "type": 1
}
    logging.info("image header: %s", {k: header[k] for k in ("file_id","name","size_comp","chunks")})

    if not publish_with_retry(client, TOPIC_IMG, cbor2.dumps(header)):
        return False

    # CHUNKS
    for idx, chunk in chunk_bytes(comp, CHUNK_SIZE):
        part = {
            "file_id": file_id,
            "idx": idx,
            "total": total_chunks,
            "crc": crc32(chunk),
            "payload": chunk,
        }
        ok = publish_with_retry(client, TOPIC_IMG_CHUNK, cbor2.dumps(part))
        if not ok:
            return False
        logging.info("sent chunk %d/%d (%d bytes)", idx + 1, total_chunks, len(chunk))

    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=BROKER_HOST)
    ap.add_argument("--port", type=int, default=BROKER_PORT)
    ap.add_argument("--image", help="image path to send (optional)")
    args = ap.parse_args()

    c = connect_client(args.host, args.port, CLIENT_ID)

    # küçük telemetri serisi
    for i in range(3):
        send_telemetry(c, i)
        time.sleep(0.5)

    if args.image:
        logging.info("sending image: %s", args.image)
        ok = send_image(c, args.image)
        logging.info("image sent: %s", ok)

    time.sleep(1.5)
    c.loop_stop()
    c.disconnect()


if __name__ == "__main__":
    main()
