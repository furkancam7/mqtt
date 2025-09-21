#!/usr/bin/env python3
import os, time, logging, tempfile, cbor2
import paho.mqtt.client as mqtt
from zstandard import ZstdDecompressor
import cv2

BROKER = "127.0.0.1"
PORT   = 1883
TOPIC_META  = "sat/image"
TOPIC_CHUNK = "sat/image/chunk"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

STATE = {}

def on_connect(c,u,f,rc):
    logging.info("connected rc=%s", rc)
    c.subscribe([(TOPIC_META, 1), (TOPIC_CHUNK, 1)])

def finish(fid):
    st = STATE.get(fid)
    if not st or len(st["parts"]) != st["total"]:
        return
    comp = b"".join(st["parts"][i] for i in range(st["total"]))
    if st["enc"] == "zstd":
        img = ZstdDecompressor().decompress(comp)
    else:
        img = comp
    # geçici dosyaya yaz ve göster
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tf:
        tf.write(img)
        path = tf.name
    logging.info("Image received ok -> %s", path)
    im = cv2.imread(path)
    if im is None:
        logging.warning("OpenCV failed to read image")
        return
    cv2.imshow("Received", im)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    STATE.pop(fid, None)

def on_message(client, userdata, msg):
    obj = cbor2.loads(msg.payload)
    if msg.topic == TOPIC_META:
        fid = obj.get("file_id")
        total = int(obj.get("total", obj.get("chunks", 0)))
        enc   = obj.get("enc", "raw")
        STATE[fid] = {"total": total, "enc": enc, "parts": {}}
        logging.info("[META] expecting %d chunks", total)
    else:
        fid  = obj.get("file_id")
        idx  = int(obj.get("idx", -1))
        data = obj.get("payload", obj.get("data", None))
        if fid and data is not None and idx >= 0:
            st = STATE.setdefault(fid, {"total": obj.get("total", obj.get("chunks", 0)),
                                        "enc":"raw","parts":{}})
            st["parts"][idx] = data
            finish(fid)

def main():
    client = mqtt.Client(client_id="img-viewer", protocol=mqtt.MQTTv311)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT, 60)
    client.loop_forever()

if __name__ == "__main__":
    main()
