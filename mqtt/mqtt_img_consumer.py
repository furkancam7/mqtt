#!/usr/bin/env python3
import os, time, logging, hashlib, zlib, cbor2
import paho.mqtt.client as mqtt
from zstandard import ZstdDecompressor

BROKER_HOST = "127.0.0.1"
BROKER_PORT = 1883
CLIENT_ID   = "img-consumer"
TOPIC_IMG   = "sat/image"
TOPIC_IMG_CHUNK = "sat/image/chunk"
OUTDIR = "/tmp/recv_images"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
os.makedirs(OUTDIR, exist_ok=True)

def crc32(b: bytes) -> int:
    return zlib.crc32(b) & 0xFFFFFFFF

# state: file_id -> {"meta": {...}, "chunks": {idx: bytes}, "received": 0}
files = {}

def try_finalize(file_id: str):
    st = files.get(file_id)
    if not st or "meta" not in st: return
    meta = st["meta"]
    total = meta["total"]
    if len(st["chunks"]) != total:
        return
    # sıralı birleştir
    comp = b"".join(st["chunks"][i] for i in range(total))
    data = ZstdDecompressor().decompress(comp) if meta.get("enc") == "zstd" else comp
    calc_sha = hashlib.sha256(data).hexdigest()
    ok = (calc_sha == meta.get("sha256"))

    ts  = meta.get("ts", int(time.time_ns()))
    seq = meta.get("seq", 0)
    name = meta.get("name") or "image.bin"
    root, ext = os.path.splitext(name)
    if not ext: ext = ".bin"
    out = os.path.join(OUTDIR, f"img_{ts}_{seq}{ext if ok else '.corrupt'+ext}")

    with open(out, "wb") as f:
        f.write(data)

    logging.info("saved %s (%d bytes) SHA256 %s -> %s",
                 name, len(data), "OK" if ok else "MISMATCH", out)
    # temizlik
    del files[file_id]

def on_message(c, u, m):
    try:
        obj = cbor2.loads(m.payload)
    except Exception as e:
        logging.warning("decode error on %s: %s", m.topic, e)
        return

    if m.topic == TOPIC_IMG:
        # header
        fid = obj["file_id"]
        files.setdefault(fid, {"chunks": {}})
        files[fid]["meta"] = obj
        logging.info("header for %s: total=%s name=%s", fid, obj.get("total"), obj.get("name"))
        try_finalize(fid)

    elif m.topic == TOPIC_IMG_CHUNK:
        fid = obj["file_id"]
        idx = int(obj["idx"])
        chunk = obj["payload"]
        if crc32(chunk) != int(obj["crc"]):
            logging.warning("CRC mismatch on %s idx=%d", fid, idx)
            return
        files.setdefault(fid, {"chunks": {}})
        files[fid]["chunks"][idx] = chunk
        if "meta" in files[fid]:
            logging.info("chunk %d/%d for %s", idx+1, files[fid]["meta"]["total"], fid)
        else:
            logging.info("chunk %d for %s (header not yet)", idx+1, fid)
        try_finalize(fid)

def main():
    c = mqtt.Client(client_id=CLIENT_ID, clean_session=True, protocol=mqtt.MQTTv311, transport="tcp")
    c.on_connect = lambda c,u,f,rc: logging.info("connected rc=%s", rc)
    c.on_message = on_message
    c.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    c.subscribe([(TOPIC_IMG, 1), (TOPIC_IMG_CHUNK, 1)])
    logging.info("listening %s and %s, writing to %s", TOPIC_IMG, TOPIC_IMG_CHUNK, OUTDIR)
    c.loop_forever()

if __name__ == "__main__":
    main()
