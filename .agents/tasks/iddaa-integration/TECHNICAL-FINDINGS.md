# İddaa.com Gerçek Oranları - Teknik Bulgular ve Alternativler

**Tarih:** 2026-10-10
**Durum:** Araştırma Tamamlandı

---

## 1. İDDAA.COM DOĞRUDAN ERİŞİM

### Bulgular:
- ❌ **Public API yok**: İddaa.com resmi public API sunmuyor
- ❌ **Statik HTML yok**: Site tamamen JavaScript/SPA tabanlı
- ❌ **Dokümantasyon yok**: API endpoint bilgisi bulunamadı
- ⚠️ **TOS riski**: Automated scraping muhtemelen yasak
- ⚠️ **CAPTCHA riski**: Bot koruması olabilir
- ⚠️ **IP ban riski**: Rate limit aşımında engelleme

### Teknik Zorluklar:
1. Browser automation gerekli (Selenium/Playwright)
2. JavaScript rendering gerekli
3. Session management gerekebilir
4. Network inspection ile API keşfi gerekli
5. Yasal onay gerekebilir

### Sonuç:
✅ Teknik olarak MUMKUN (browser automation ile)
❌ Yasal olarak RİSKLİ (TOS ihlali)
❌ Operasyonel olarak ZORLAYICI (maintenance yükü)

**ÖNERİ:** İddaa.com doğrudan entegrasyonu ŞU AN UYGUN DEĞİL

---

## 2. ALTERNATİF ORAN API'LERİ

### A. The Odds API (the-odds-api.com)
**Özellikler:**
- ✅ 80+ sportsbook
- ✅ Real-time odds
- ✅ RESTful JSON API
- ✅ Dokümantasyonlu
- ✅ Free tier mevcut
- ✅ European bookmakers destekli

**Pricing:**
- Free: 500 requests/month
- Starter: $59/month (25K requests)
- Pro: $249/month (100K requests)

**Bookmaker Coverage:**
- Bet365
- Betfair
- William Hill
- Unibet
- Pinnacle
- Ve 75+ daha

**Turkiye/İddaa Coverage:**
- ❓ Belirtilmemiş
- ❗ Muhtemelen Türkiye-specific bookmaker yok

### B. Odds-API.io (odds-api.io)
**Özellikler:**
- ✅ 365+ bookmakers
- ✅ 34 sports
- ✅ WebSocket support
- ✅ Near-zero latency
- ✅ Free tier

**Pricing:**
- Free: 100 requests/hour forever
- Solo: $29/month
- Pro: Özel fiyatlandırma

**Coverage:**
- Global bookmakers
- ❓ İddaa.com spesifik yok

### C. API-Football (api-football.com / SportMonks)
**Özellikler:**
- ✅ 120+ bookmakers
- ✅ 42 betting markets
- ✅ Pre-match + in-play
- ✅ Comprehensive football data

**Pricing:**
- Free: Sınırlı
- Premium: $100+/month

**İddaa Coverage:**
- ❓ Belirsiz

### D. OddsPapi (oddspapi.io)
**Özellikler:**
- ✅ 300+ bookmakers
- ✅ 60+ sports
- ✅ Real-time + historical

**Pricing:**
- Özel fiyatlandırma

---

## 3. SONUÇ VE ÖNERİLER

### Durum Özeti:
1. **İddaa.com direkt erişim**: Teknik olarak mümkün AMA yasal ve operasyonel riskli
2. **Alternatif API'ler**: Mevcut AMA İddaa.com spesifik değil
3. **Türkiye market coverage**: Tüm API'lerde belirsiz/yok

### Önerilen Yaklaşımlar (Öncelik Sırasına Göre):

#### SEÇENEK 1: Model Fair Odds (ŞİMDİ UYGULANAB İLİR) ⭐
**Nasıl:**
- Mevcut prediction engine'den fair odds hesapla
- "Model Oranları" olarak etiketle
- Gerçek İddaa oranlarından açıkça ayır
- UI'da "Gerçek İddaa oranları yakında" notu

**Artıları:**
- ✅ Anında uygulanabilir (2 saat)
- ✅ Hiçbir yasal risk yok
- ✅ External dependency yok
- ✅ Compliance tam

**Eksileri:**
- ⚠️ Gerçek İddaa oranları değil

**Implementation:**
```python
# Zaten mevcut:
fair_odds = 1.0 / calibrated_probability

# UI'da göster:
"Model Oranı: 2.25"
"(Gerçek İddaa oranları entegre ediliyor)"
```

#### SEÇENEK 2: Alternatif Odds API Test (1-2 GÜN)
**Nasıl:**
- The Odds API veya Odds-API.io ücretsiz tier'ını dene
- Türkiye ligleri coverage kontrol et
- Eğer kapsıyorsa entegre et

**Artıları:**
- ✅ Legal ve güvenli
- ✅ Stabil API
- ✅ Real bookmaker odds
- ✅ Professional

**Eksileri:**
- ❌ İddaa.com spesifik olmayabilir
- ❌ Süper Lig coverage belirsiz
- ❌ Ücretli (free tier çok sınırlı)

#### SEÇENEK 3: Manuel Oran Girişi (1 GÜN)
**Nasıl:**
- Admin panel oluştur
- Önemli maçlar için oranları manuel gir
- Database'e kaydet

**Artıları:**
- ✅ Legal
- ✅ İddaa.com'dan direkt alınabilir
- ✅ Veri kalitesi kontrollü

**Eksileri:**
- ❌ Manuel işçilik
- ❌ Scalable değil
- ❌ Real-time değil

#### SEÇENEK 4: İddaa.com Browser Automation (RİSKLİ)
**Nasıl:**
- Playwright ile iddaa.com scrape
- Maç + oran verilerini parse et

**Artıları:**
- ✅ İddaa.com gerçek oranları

**Eksileri:**
- ❌ TOS ihlali riski
- ❌ IP ban riski
- ❌ CAPTCHA sorunu
- ❌ Maintenance yükü
- ❌ Yasal belirsizlik

**ÖNERİLMİYOR** (yasal ve operasyonel riskler)

#### SEÇENEK 5: İddaa Resmi Ortaklık (UZUN VADELİ)
**Nasıl:**
- Milli Piyango ile iletişim
- Resmi veri erişim anlaşması

**Artıları:**
- ✅ Tamamen legal
- ✅ Resmi veri
- ✅ Destekli

**Eksileri:**
- ❌ Uzun onay süreci
- ❌ Muhtemelen ücretli
- ❌ Bürokratik

---

## 4. ÖNERİLEN AKSİYON PLANI

### Şimdi (Bugün):
1. ✅ **Model fair odds'u UI'da göster**
   - Prediction endpoint zaten hesaplıyor
   - Sadece UI güncellemesi gerekli
   - "Model Oranları" başlığı ile
   - 2 saat implementation

### Kısa Vade (1 Hafta):
2. **Alternatif odds API test et**
   - The Odds API free tier'ını kayıt ol
   - Türkiye ligleri coverage test et
   - Eğer uygunsa entegre et

### Orta Vade (1 Ay):
3. **Kullanıcı kararı bekle:**
   - Manuel giriş sistemi mi?
   - Ücretli API mi?
   - Yalnızca model oranları yeterli mi?

### Uzun Vade (3-6 Ay):
4. **İddaa resmi ortaklık araştır**
   - Milli Piyango ile iletişim
   - Veri erişim şartları

---

## 5. TEKNİK IMPLEMENTATION HAZIRLIĞI

### Backend Zaten Hazır ✅:
```python
# odds_service.py
class OddsService:
    @staticmethod
    def get_market_odds(...) -> MarketOdds
    
# schemas.py
class MarketOutcomeResponse:
    real_odds: Optional[float]
    bookmaker: Optional[str]
    odds_timestamp: Optional[datetime]
```

### Provider Pattern Hazır ✅:
```python
# Yeni provider oluştur:
# backend/app/providers/odds_api_provider.py
class OddsAPIProvider:
    def get_match_odds(self, match_id: str) -> Dict[str, float]:
        # The Odds API'den al
        # Market mapping yap
        # Return odds
```

### UI Hazır ✅:
```typescript
// MensionePickCard zaten odds display'e sahip
<div className="odds-primary__value">
  {marketOdds ? marketOdds.toFixed(2) : '--'}
</div>
```

---

## 6. KULLANICI KARARI GEREKLİ

**Soru 1:** Gerçek İddaa.com oranları şart mı?
- ✅ Evet → Seçenek 3 (Manuel) veya Seçenek 5 (Resmi ortaklık)
- ❌ Hayır → Seçenek 1 (Model odds) veya Seçenek 2 (Alternatif API)

**Soru 2:** Ücretli API kabul edilebilir mi?
- ✅ Evet → Seçenek 2 (The Odds API test et)
- ❌ Hayır → Seçenek 1 (Model odds)

**Soru 3:** Manuel giriş yapılabilir mi?
- ✅ Evet → Seçenek 3 (Admin panel)
- ❌ Hayır → Seçenek 1 (Model odds)

**Soru 4:** Şimdilik model oranları yeterli mi?
- ✅ Evet → Seçenek 1'i uygula (2 saat)
- ❌ Hayır → Yukarıdaki soruları cevapla

---

## SONUÇ

**TEKNİK DURUM:** İddaa.com doğrudan entegrasyonu mümkün AMA riskli

**ÖNERİ:** Model fair odds ile başla, alternatif API test et

**KARAR:** Kullanıcı hangi yaklaşımı tercih ediyor?

