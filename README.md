# MQTT Uydu Görüntüleme ve Telemetri Sistemi

Bu proje, MQTT protokolü kullanarak uydu verilerinin (telemetri ve görüntüler) gönderilmesi, alınması ve görüntülenmesi için geliştirilmiş bir sistemdir. Sistem, gerçek zamanlı veri iletimi, sıkıştırma, parçalama ve güvenilir mesaj teslimi özelliklerini içerir.

## 📁 Proje Yapısı

```
mqtt/
├── mqtt_pub.py          # Veri yayınlayıcı (Publisher)
├── mqtt_img_consumer.py # Görüntü tüketicisi (Image Consumer)
├── mqtt_tlm_consumer.py # Telemetri tüketicisi (Telemetry Consumer)
└── mqtt_viewer.py       # Görüntü görüntüleyici (Image Viewer)
```

## 🚀 Özellikler

### 🔧 Temel Özellikler
- **MQTT Protokolü**: Güvenilir mesaj iletimi için QoS 1 kullanımı
- **Veri Sıkıştırma**: Zstandard (zstd) ile yüksek performanslı sıkıştırma
- **Parçalama**: Büyük dosyaları küçük parçalara bölerek güvenli iletim
- **Hata Kontrolü**: CRC32 ve SHA256 ile veri bütünlüğü kontrolü
- **Yeniden Deneme**: Mesaj iletim hatalarında otomatik yeniden deneme
- **Geriye Uyumluluk**: Farklı versiyonlarla uyumlu alan okuma

### 📊 Veri Türleri
1. **Telemetri Verileri**: Sıcaklık, basınç, batarya durumu, zaman damgası
2. **Görüntü Verileri**: JPEG formatında sıkıştırılmış görüntüler

## 📋 Gereksinimler

### Python Kütüphaneleri
```bash
pip install paho-mqtt cbor2 zstandard opencv-python
```

### Sistem Gereksinimleri
- Python 3.7+
- MQTT Broker (örn: Mosquitto, Eclipse Mosquitto)
- OpenCV (görüntü görüntüleme için)

## 🛠️ Kurulum

### 1. Docker ile Çalıştırma (Önerilen)

#### Docker Compose ile Tam Sistem
```bash
# Proje dizininde
docker-compose up -d

# Logları takip et
docker-compose logs -f

# Sistemi durdur
docker-compose down
```

#### Docker ile Tek Servis
```bash
# MQTT Broker
docker run -d --name mosquitto -p 1883:1883 -p 9001:9001 eclipse-mosquitto

# Publisher
docker build -t mqtt-publisher .
docker run --rm --network host mqtt-publisher python mqtt/mqtt_pub.py --image test.jpg

# Consumer
docker build -t mqtt-consumer .
docker run --rm --network host -v $(pwd)/images:/tmp/recv_images mqtt-consumer python mqtt/mqtt_img_consumer.py
```

### 2. Manuel Kurulum

#### MQTT Broker Kurulumu

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install mosquitto mosquitto-clients
sudo systemctl start mosquitto
sudo systemctl enable mosquitto
```

**Windows:**
```bash
# Chocolatey ile
choco install mosquitto

# Veya manuel indirme
# https://mosquitto.org/download/
```

**macOS:**
```bash
brew install mosquitto
brew services start mosquitto
```

#### Python Bağımlılıkları
```bash
# Virtual environment oluştur
python -m venv venv
source venv/bin/activate  # Linux/macOS
# veya
venv\Scripts\activate     # Windows

# Bağımlılıkları yükle
pip install -r requirements.txt
```

*Not: requirements.txt dosyası yoksa, yukarıda belirtilen kütüphaneleri manuel olarak yükleyin.*

## 🎯 Kullanım

### 1. Veri Yayınlayıcı (Publisher) - `mqtt_pub.py`

Telemetri verilerini ve görüntüleri MQTT broker'a gönderir.

```bash
# Sadece telemetri gönder
python mqtt/mqtt_pub.py

# Telemetri + görüntü gönder
python mqtt/mqtt_pub.py --image /path/to/image.jpg

# Farklı broker kullan
python mqtt/mqtt_pub.py --host 192.168.1.100 --port 1883 --image test.jpg
```

**Parametreler:**
- `--host`: MQTT broker adresi (varsayılan: 127.0.0.1)
- `--port`: MQTT broker portu (varsayılan: 1883)
- `--image`: Gönderilecek görüntü dosyası yolu

### 2. Görüntü Tüketicisi (Image Consumer) - `mqtt_img_consumer.py`

Gelen görüntüleri `/tmp/recv_images` dizinine kaydeder.

```bash
python mqtt/mqtt_img_consumer.py
```

**Özellikler:**
- Gelen görüntüleri otomatik olarak kaydetme
- SHA256 doğrulama ile veri bütünlüğü kontrolü
- Bozuk dosyaları `.corrupt` uzantısıyla kaydetme
- Zstandard sıkıştırma desteği

### 3. Telemetri Tüketicisi (Telemetry Consumer) - `mqtt_tlm_consumer.py`

Gelen telemetri verilerini işler ve görüntüleri `/tmp/recv_images` dizinine kaydeder.

```bash
python mqtt/mqtt_tlm_consumer.py
```

### 4. Görüntü Görüntüleyici (Image Viewer) - `mqtt_viewer.py`

Gelen görüntüleri gerçek zamanlı olarak OpenCV ile gösterir.

```bash
python mqtt/mqtt_viewer.py
```

**Özellikler:**
- Gerçek zamanlı görüntü görüntüleme
- OpenCV tabanlı görüntü penceresi
- Otomatik pencere kapatma

## 📡 MQTT Konuları (Topics)

### Telemetri
- **Konu**: `sat/telemetry`
- **Format**: CBOR + Zstd sıkıştırma
- **İçerik**: Sıcaklık, basınç, batarya, zaman damgası

### Görüntü Meta Verisi
- **Konu**: `sat/image`
- **Format**: CBOR
- **İçerik**: Dosya bilgileri, boyut, parça sayısı, SHA256

### Görüntü Parçaları
- **Konu**: `sat/image/chunk`
- **Format**: CBOR
- **İçerik**: Dosya parçaları, indeks, CRC32

### Durum Bilgisi
- **Konu**: `sat/status`
- **Format**: Plain text
- **İçerik**: Bağlantı durumu (online/offline)

## 🔧 Yapılandırma

### Varsayılan Ayarlar
```python
BROKER_HOST = "127.0.0.1"
BROKER_PORT = 1883
CHUNK_SIZE = 60 * 1024  # ~60KB parça boyutu
RETRY_MAX = 5           # Maksimum yeniden deneme
QOS = 1                 # MQTT QoS seviyesi
```

### Güvenlik
- Kimlik doğrulama için `username_pw_set()` fonksiyonu kullanılabilir
- SSL/TLS desteği eklenebilir
- Varsayılan olarak kimlik doğrulama kapalı

## 📊 Veri Formatları

### Telemetri Verisi
```json
{
  "ts": 1640995200000000000,
  "temp": 23.4,
  "press": 1012.2,
  "batt": 3.91,
  "seq": 0
}
```

### Görüntü Meta Verisi
```json
{
  "file_id": "abc123def456",
  "name": "satellite_image.jpg",
  "ts": 1640995200000000000,
  "enc": "zstd",
  "size_raw": 2048576,
  "size_comp": 512144,
  "chunks": 9,
  "sha256": "abc123...",
  "type": 1
}
```

### Görüntü Parçası
```json
{
  "file_id": "abc123def456",
  "idx": 0,
  "total": 9,
  "crc": 1234567890,
  "payload": "base64_encoded_data..."
}
```

## 🐛 Hata Ayıklama

### Yaygın Sorunlar

1. **Bağlantı Hatası**
   ```
   Error: Connection refused
   ```
   - MQTT broker'ın çalıştığından emin olun
   - Host ve port ayarlarını kontrol edin

2. **Görüntü Görüntüleme Hatası**
   ```
   OpenCV failed to read image
   ```
   - OpenCV kurulumunu kontrol edin
   - Görüntü formatının desteklendiğinden emin olun

3. **Sıkıştırma Hatası**
   ```
   decompress error
   ```
   - Zstandard kütüphanesinin kurulu olduğundan emin olun
   - Veri bütünlüğünü kontrol edin

### Log Seviyeleri
```python
import logging
logging.basicConfig(level=logging.DEBUG)  # Detaylı log
logging.basicConfig(level=logging.INFO)   # Bilgi logları
logging.basicConfig(level=logging.WARNING) # Uyarı logları
```

## 🧪 Test Etme

### 1. Broker Bağlantısı Testi
```bash
# Broker durumunu kontrol et
mosquitto_pub -h 127.0.0.1 -t "test" -m "hello"
mosquitto_sub -h 127.0.0.1 -t "test"
```

### 2. Sistem Testi
```bash
# Terminal 1: Tüketiciyi başlat
python mqtt/mqtt_img_consumer.py

# Terminal 2: Yayınlayıcıyı başlat
python mqtt/mqtt_pub.py --image test_image.jpg
```

### 3. Görüntü Görüntüleme Testi
```bash
# Terminal 1: Görüntüleyiciyi başlat
python mqtt/mqtt_viewer.py

# Terminal 2: Görüntü gönder
python mqtt/mqtt_pub.py --image sample.jpg
```

## 📈 Performans Optimizasyonu

### Parça Boyutu Ayarlama
```python
CHUNK_SIZE = 60 * 1024  # 60KB - güvenli boyut
CHUNK_SIZE = 128 * 1024 # 128KB - daha hızlı, daha riskli
```

### Sıkıştırma Seviyesi
```python
ZstdCompressor(level=6)   # Hızlı sıkıştırma
ZstdCompressor(level=10)  # Yüksek sıkıştırma oranı
```

### Yeniden Deneme Stratejisi
```python
RETRY_MAX = 5  # Maksimum deneme sayısı
time.sleep(min(2 ** attempt, 8))  # Üstel geri çekilme
```

## 🔮 Gelecek Geliştirmeler

- [ ] SSL/TLS güvenlik desteği
- [ ] Web tabanlı arayüz
- [ ] Veritabanı entegrasyonu
- [ ] Çoklu broker desteği
- [ ] Otomatik yeniden bağlanma
- [ ] Metrikler ve izleme
- [ ] Docker containerization
- [ ] REST API arayüzü

## 📝 Lisans

Bu proje açık kaynak kodludur ve eğitim/araştırma amaçlı kullanılabilir.

## 🤝 Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Commit yapın (`git commit -m 'Add amazing feature'`)
4. Push yapın (`git push origin feature/amazing-feature`)
5. Pull Request oluşturun

## 📞 İletişim

Sorularınız için issue açabilir veya proje sahibi ile iletişime geçebilirsiniz.

---

**Not**: Bu sistem eğitim ve araştırma amaçlı geliştirilmiştir. Üretim ortamında kullanmadan önce güvenlik ve performans testlerini yapın.
