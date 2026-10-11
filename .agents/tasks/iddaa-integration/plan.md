# İddaa.com Gerçek Oranları Entegrasyonu - Teknik Plan

**Tarih:** 2026-10-10
**Durum:** Araştırma ve Planlama

---

## 1. İDDAA.COM VERİ YAPISI ARAŞTIRMASI

### Bulgular:

#### Web Sitesi Yapısı:
- ✅ Ana site: https://www.iddaa.com/
- ✅ Program sayfası: https://www.iddaa.com/program (statik bilgi sayfası)
- ❌ /futbol, /mac-programi endpoint'leri 404 veriyor
- ⚠️ Site tamamen JavaScript/SPA tabanlı görünüyor

#### Tespit Edilen Sorunlar:
1. **Public API yok**: İddaa.com resmî bir public API sunmuyor
2. **JavaScript render gerekli**: İçerik dinamik olarak yükleniyor
3. **Session/auth gerekebilir**: Bazı içerikler giriş gerektirebilir
4. **CAPTCHA olasılığı**: Otomatik erişim engellenebilir
5. **TOS kısıtlaması**: Kullanım koşulları otomatik scraping'i yasaklıyor olabilir

### GitHub Araştırması:
- `utkukaynar/iddaa-api`: Eski Ruby projesi, dokümantasyon yok, aktif değil
- Başka açık kaynak iddaa scraper/parser bulunmadı

---

## 2. UYGULANAB İLİR ÇÖZÜMLER

### Seçenek A: Browser Automation (Selenium/Playwright)
**Nasıl çalışır:**
```python
# Playwright ile iddaa.com'u gerçek tarayıcıda aç
# JavaScript'in yüklenmesini bekle
# Maç listesi ve oranları DOM'dan çek
# Veriyi parse et ve normalize et
```

**Artıları:**
- ✅ Gerçek tarayıcı gibi davranır
- ✅ JavaScript içeriği render olur
- ✅ İnsan davranışı simüle edilebilir

**Eksileri:**
- ❌ Yavaş (her istek 5-10 saniye)
- ❌ Resource intensive (Chrome/Firefox çalıştırma)
- ❌ CAPTCHA çıkarsa engellenir
- ❌ Kullanım koşullarını ihlal edebilir
- ❌ IP ban riski
- ❌ Deployment karmaşık (headless browser gerekli)

**Risk:** YÜKSEK - İddaa.com bu tür erişimi engelleyebilir

### Seçenek B: Network Traffic Analysis
**Nasıl çalışır:**
```
# Tarayıcıda iddaa.com'u aç
# Network tab'dan XHR/Fetch isteklerini incele
# API endpoint'lerini tespit et
# Direkt olarak o endpoint'leri çağır
```

**Artıları:**
- ✅ Hızlı (direkt API çağrısı)
- ✅ Lightweight (tarayıcı gerekmez)
- ✅ Efficient

**Eksileri:**
- ❌ API endpoint'leri public olmayabilir
- ❌ Authentication/token gerekebilir
- ❌ Rate limit olabilir
- ❌ API yapısı değişebilir
- ❌ CORS sorunları

**Risk:** ORTA - API keşfi gerekli

### Seçenek C: İddaa Resmi Veri Ortaklığı
**Nasıl çalışır:**
```
# Milli Piyango / İddaa ile iletişime geç
# Veri erişim anlaşması yap
# Resmi API veya feed al
```

**Artıları:**
- ✅ Legal ve güvenli
- ✅ Kararlı veri akışı
- ✅ Resmi destek
- ✅ Rate limit yok
- ✅ Dokümantasyon var

**Eksileri:**
- ❌ Onay süreci uzun olabilir
- ❌ Ücretli olabilir
- ❌ Bürokratik süreç

**Risk:** DÜŞÜK - En güvenli yöntem

### Seçenek D: Manuel Veri Girişi
**Nasıl çalışır:**
```
# Admin panel oluştur
# Önemli maçlar için oranları manuel gir
# Veritabanına kaydet
# UI'da göster
```

**Artıları:**
- ✅ Legal sorun yok
- ✅ Veri kalitesi kontrol edilebilir
- ✅ Hızlı başlangıç

**Eksileri:**
- ❌ Manuel işçilik gerekli
- ❌ Scalable değil
- ❌ Tüm maçları kapsamaz

**Risk:** YOK - Tamamen manuel

### Seçenek E: Alternatif Oran Sağlayıcı API
**Nasıl çalışır:**
```
# Odds API, The Odds API, API-Football gibi servisleri kullan
# Türkiye marketleri destekleyen birini bul
# API entegrasyonu yap
```

**Artıları:**
- ✅ Legal
- ✅ Stabil API
- ✅ Dokümantasyonlu
- ✅ Birden fazla bookmaker desteği

**Eksileri:**
- ❌ Genelde ücretli
- ❌ İddaa.com özelinde olmayabilir
- ❌ Türkiye maçları kapsam dışı olabilir

**Risk:** DÜŞÜK - Yasal ve stabil

---

## 3. ÖNERİLEN YAKLAŞIM

### Aşama 1: Manuel Network Analysis (ŞİMDİ)
1. Tarayıcıda iddaa.com/program aç
2. DevTools Network tab'ı izle
3. Maç listesi ve oranların nasıl geldiğini tespit et
4. API endpoint'lerini belirle
5. Request/response yapısını dokümante et

### Aşama 2: API Test (SONRA)
1. Tespit edilen endpoint'leri test et
2. Authentication gerekip gerekmediğini kontrol et
3. Rate limit'leri test et
4. Veri yapısını map et

### Aşama 3: Karar Noktası (KULLANICI)
**Eğer API erişilebilir ve yasal:**
→ Provider implementasyonu yap

**Eğer API korumalı veya yasak:**
→ Kullanıcıya rapor et:
- Resmi veri ortaklığı gerekli
- VEYA alternatif oran API'si kullan
- VEYA manuel giriş sistemi kur
- VEYA yalnızca model oranları göster

---

## 4. MEVCUT MİMARİ HAZIRLIĞI

### Backend Altyapısı ✅:
```python
# backend/app/services/odds_service.py
class OddsService:
    - get_market_odds()
    - calculate_value_contribution()
    - apply_high_base_rate_protection()
    ✅ TAM HAZIR

# backend/app/domain/ schemas
MarketOutcomeResponse:
    - real_odds ✅
    - bookmaker ✅
    - odds_timestamp ✅
    - implied_probability ✅
```

### Provider Pattern ✅:
```python
# backend/app/providers/iddaa_provider.py (OLUŞTURULACAK)
class IddaaOddsProvider:
    def get_match_odds(match_id: str) -> Dict[str, float]:
        # İddaa.com'dan oranları al
        # Market mapping yap
        # Timestamp ile dön
```

### API Endpoint ✅:
```python
# backend/app/api/v1/endpoints/matches.py
# get_prediction endpoint zaten odds desteğine sahip
# has_bookmaker_odds flag mevcut
# Sadece provider'ı bağla
```

---

## 5. UYUMLULUK KONTROL LİSTESİ

- [ ] İddaa.com Terms of Service okuması
- [ ] Robots.txt kontrolü
- [ ] Rate limit testi
- [ ] CAPTCHA varlığı
- [ ] Authentication gereksinimleri
- [ ] Legal danışmanlık (gerekirse)

---

## 6. SONRAKİ ADIMLAR

### Şimdi Yapılacak:
1. **Manuel browser inspection** ile API endpoint'lerini tespit et
2. Network traffic'i analiz et
3. Veri yapısını dokümante et
4. Erişim kısıtlamalarını belirle

### Kullanıcı Onayı Sonrası:
- **Eğer API erişilebilir:** Provider implementasyonu
- **Eğer kısıtlı:** Alternatif çözüm raporu

---

## 7. TEKNİK ENGEL RAPORU

⚠️ **DİKKAT:** İddaa.com public API sunmuyor ve site tamamen JavaScript tabanlı.

**Durum:**
- Statik HTML scraping mümkün değil
- Dinamik içerik render gerekli
- API endpoint'leri hidden/protected olabilir
- Terms of Service automated access'i yasaklıyor olabilir

**Risk Değerlendirmesi:**
- Unauthorized scraping → IP ban
- CAPTCHA → Erişim engeli
- Legal issue → TOS ihlali

**Önerilen Yaklaşım:**
1. Önce manuel inspection ile teknik fizibilite belirle
2. Yasal durumu netleştir
3. Eğer engel varsa kullanıcıya rapor et
4. Alternatif çözümler sun

---

## SONUÇ

İddaa.com entegrasyonu **teknik ve yasal zorluklar** içeriyor.

**Sonraki adım:** Manuel network inspection ile API keşfi

**Karar gereken:** Teknik engel tespit edilirse alternatif yöntem seçimi

