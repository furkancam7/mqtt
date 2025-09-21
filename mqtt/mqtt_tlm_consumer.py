#!/usr/bin/env python3
import os, time, hashlib, logging
import cbor2
import paho.mqtt.client as mqtt
from zstandard import ZstdDecompressor

BROKER = "127.0.0.1"
PORT   = 1883
TOPIC_META  = "sat/image"
TOPIC_CHUNK = "sat/image/chunk"
SAVE_DIR = "/tmp/recv_images"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
os.makedirs(SAVE_DIR, exist_ok=True)

# file_id -> state
STATE = {}

def get_u64(meta, *names):
    for n in names:
        if n in meta:
            return int(meta[n])
    return None

def on_connect(c,u,f,rc):
    logging.info("listening %s and %s, writing to %s", TOPIC_META, TOPIC_CHUNK, SAVE_DIR)
    c.subscribe([(TOPIC_META, 1), (TOPIC_CHUNK, 1)])

def try_finalize(fid):
    st = STATE.get(fid)
    if not st: return
    total = st["total"]
    # tüm parçalar geldi mi?
    if len(st["parts"]) != total:
        return
    # sırayla birleştir
    comp = b"".join(st["parts"][i] for i in range(total))
    if st["size_comp"] is not None and len(comp) != st["size_comp"]:
        logging.warning("size mismatch for %s: expected %d got %d",
                        fid, st["size_comp"], len(comp))
    # sha256 doğrula (varsa)
    if st["sha256"]:
        sha = hashlib.sha256(comp).hexdigest()
        ok = (sha == st["sha256"])
    else:
        ok = True

    # decompress & kaydet
    name = st["name"]
    ts   = st["ts"]
    if st["enc"] == "zstd":
        try:
            img = ZstdDecompressor().decompress(comp)
        except Exception as e:
            logging.error("decompress error for %s: %s", fid, e)
            img = comp  # son çare ham yaz
        out = os.path.join(SAVE_DIR, f"img_{ts}_{fid}.jpg")
        with open(out, "wb") as f:
            f.write(img)
    else:
        out = os.path.join(SAVE_DIR, f"img_{ts}_{fid}.bin")
        with open(out, "wb") as f:
            f.write(comp)

    if ok:
        logging.info("saved %s (%d bytes) -> %s", name, len(comp), out)
    else:
        bad = out.replace(".jpg", ".corrupt.jpg").replace(".bin", ".corrupt.bin")
        os.rename(out, bad)
        logging.warning("SHA256 MISMATCH -> %s", bad)

    # temizlik
    STATE.pop(fid, None)

def on_message(c, userdata, msg):
    topic = msg.topic
    obj = cbor2.loads(msg.payload)

    if topic == TOPIC_META:
        fid = obj.get("file_id")
        if not fid:
            logging.warning("meta with no file_id, ignoring")
            return
        # geriye uyumlu alan okumaları
        total      = get_u64(obj, "total", "chunks")
        size_comp  = get_u64(obj, "size", "size_comp")
        name       = obj.get("name", f"{fid}.dat")
        enc        = obj.get("enc", "raw")
        ts         = obj.get("ts", int(time.time_ns()))
        sha256     = obj.get("sha256", "")

        STATE[fid] = {
            "name": name, "enc": enc, "ts": ts,
            "total": total, "size_comp": size_comp,
            "sha256": sha256,
            "parts": {}
        }
        logging.info("header for %s: total=%s name=%s", fid, total, name)

    elif topic == TOPIC_CHUNK:
        # chunk alan adı: 'payload' ya da 'data'
        fid   = obj.get("file_id")
        idx   = int(obj.get("idx", -1))
        total = int(obj.get("total", obj.get("chunks", -1)))
        data  = obj.get("payload", obj.get("data", None))
        if fid is None or idx < 0 or data is None:
            logging.warning("malformed chunk, skipping")
            return

        st = STATE.setdefault(fid, {"name":"unknown","enc":"raw","ts":int(time.time_ns()),
                                    "total": total, "size_comp": None, "sha256": "",
                                    "parts": {}})
        st["total"] = total if total != -1 else st["total"]
        st["parts"][idx] = data
        logging.info("chunk %d/%d for %s", idx+1, st["total"], fid)
        try_finalize(fid)

def main():
    c = mqtt.Client(client_id="img-dumper", protocol=mqtt.MQTTv311)
    c.on_connect = on_connect
    c.on_message = on_message
    c.connect(BROKER, PORT, 60)
    c.loop_forever()

if __name__ == "__main__":
    main()
