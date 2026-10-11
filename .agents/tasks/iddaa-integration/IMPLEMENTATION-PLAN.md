# Ücretsiz Odds API Entegrasyonu - Implementation Plan

**Tarih:** 2026-10-10
**Durum:** Planlama

---

## 1. API SEÇİMİ VE DURUM

### The Odds API
**Durum:** ✅ KULLANILABIL İR
- **Free Tier:** 500 requests/month
- **Coverage:** 100+ bookmakers, 100+ sports
- **API Key:** Email ile kayıt gerekli
- **Docs:** https://the-odds-api.com/liveapi/guides/v4/

**Bookmakers:**
- US: DraftKings, FanDuel, BetMGM, Caesars
- UK: William Hill, Ladbrokes, Betfair
- EU: 1xBet, Pinnacle, Unibet
- ❓ İddaa: Belirtilmemiş (test edilmeli)

**Football Coverage:**
- EPL, Bundesliga, La Liga, Serie A
- Champions League, Europa League
- ❓ Türkiye Süper Ligi: Belirtilmemiş (test edilmeli)

### Odds-API.io
**Durum:** ❌ YENİ KAYITLARA KAPALI
- "New free API keys are paused"
- Mevcut ücretsiz anahtarlar çalışıyor ama yenisi verilmiyor
- ❌ KULLANILAMA Z

---

## 2. IMPLEMENTATION YAKLAŞIMI

### Aşama 1: API Anahtarı ve Test (KULLANICI AKSİYONU)
```
1. Kullanıcı the-odds-api.com'a kayıt olur
2. Email ile API key alır
3. backend/.env'e ekler:
   THE_ODDS_API_KEY=your_key_here
4. Git'e commit ETMEZ (zaten .gitignore'da)
```

### Aşama 2: Test Script (GERÇEKleştirme)
```python
# backend/scripts/test_odds_api.py
import requests
import os

API_KEY = os.getenv('THE_ODDS_API_KEY')
BASE_URL = 'https://api.the-odds-api.com/v4'

def test_sports_list():
    """List all available sports"""
    url = f'{BASE_URL}/sports'
    params = {'apiKey': API_KEY}
    response = requests.get(url, params=params)
    return response.json()

def test_turkey_super_lig():
    """Check if Turkey Super Lig is available"""
    sports = test_sports_list()
    turkey_sports = [s for s in sports if 'turkey' in s.get('title', '').lower() 
                     or 'super' in s.get('title', '').lower()]
    return turkey_sports

def test_football_odds(sport_key='soccer_epl'):
    """Get odds for a specific football league"""
    url = f'{BASE_URL}/sports/{sport_key}/odds'
    params = {
        'apiKey': API_KEY,
        'regions': 'eu,uk',
        'markets': 'h2h',
        'oddsFormat': 'decimal'
    }
    response = requests.get(url, params=params)
    return response.json()
```

### Aşama 3: Bookmaker Kontrolü
```python
def check_bookmakers(odds_data):
    """Check which bookmakers are available"""
    bookmakers = set()
    for event in odds_data:
        for bookmaker in event.get('bookmakers', []):
            bookmakers.add(bookmaker['key'])
    return bookmakers

def has_iddaa(bookmakers_set):
    """Check if İddaa is in the bookmaker list"""
    iddaa_variations = ['iddaa', 'nesine', 'bilyoner']
    return any(b.lower() in iddaa_variations for b in bookmakers_set)
```

### Aşama 4: Provider Implementation
```python
# backend/app/providers/odds_api_provider.py
import requests
from typing import Dict, Optional, List
from datetime import datetime
from app.config import settings

class TheOddsAPIProvider:
    """Provider for The Odds API"""
    
    def __init__(self):
        self.api_key = settings.the_odds_api_key
        self.base_url = 'https://api.the-odds-api.com/v4'
        self.cache = {}  # Simple cache to save requests
    
    def get_match_odds(
        self, 
        home_team: str, 
        away_team: str, 
        commence_time: datetime,
        sport_key: str = 'soccer_turkey_super_league'
    ) -> Optional[Dict[str, float]]:
        """Get odds for a specific match"""
        # Implementation
        pass
    
    def _map_to_internal_markets(self, bookmaker_data: dict) -> Dict[str, float]:
        """Map The Odds API markets to internal format"""
        # h2h -> HOME_WIN, DRAW, AWAY_WIN
        # spreads -> ...
        # totals -> OVER_X, UNDER_X
        pass
```

### Aşama 5: Config Integration
```python
# backend/app/config.py
class Settings(BaseSettings):
    # ... existing fields ...
    
    the_odds_api_key: Optional[str] = Field(None, env="THE_ODDS_API_KEY")
    the_odds_api_enabled: bool = Field(False, env="THE_ODDS_API_ENABLED")
    the_odds_api_cache_minutes: int = Field(60, env="THE_ODDS_API_CACHE_MINUTES")
```

### Aşama 6: Service Integration
```python
# backend/app/services/odds_service.py
from app.providers.odds_api_provider import TheOddsAPIProvider

class OddsService:
    def __init__(self):
        self.odds_provider = TheOddsAPIProvider() if settings.the_odds_api_enabled else None
    
    def get_real_odds(self, match) -> Optional[Dict[str, MarketOdds]]:
        """Get real odds from external provider"""
        if not self.odds_provider:
            return None
        
        return self.odds_provider.get_match_odds(
            home_team=match.home_team.name,
            away_team=match.away_team.name,
            commence_time=match.scheduled_at
        )
```

---

## 3. TEST PLANI

### Test 1: API Erişim
```bash
# Test: API key geçerli mi?
python backend/scripts/test_odds_api.py --test connection

# Beklenen: 200 OK, sports list
```

### Test 2: Türkiye Süper Ligi Kapsamı
```bash
# Test: Türkiye ligleri var mı?
python backend/scripts/test_odds_api.py --test turkey

# Beklenen: Sport key listesi (örn: soccer_turkey_super_league)
# Alternatif: Yoksa EPL gibi başka lig kullan
```

### Test 3: Bookmaker Listesi
```bash
# Test: İddaa bookmaker var mı?
python backend/scripts/test_odds_api.py --test bookmakers --sport soccer_epl

# Beklenen: Bookmaker listesi
# İddaa kontrolü: ['bet365', 'unibet', ...] içinde 'iddaa' var mı?
```

### Test 4: Gerçek Oran Çekme
```bash
# Test: Gerçek bir maç için oran al
python backend/scripts/test_odds_api.py --test odds --sport soccer_epl --limit 1

# Beklenen: Event with bookmakers and odds
```

### Test 5: Oran Doğrulama
```
# Manuel: The-odds-api.com sitesindeki oranla karşılaştır
# Eşleşme: API'den gelen oran == sitede gösterilen oran
```

---

## 4. ENTEGRASYON KONTROL LİSTESİ

### Hazırlık:
- [ ] Kullanıcı The Odds API'ye kayıt oldu
- [ ] API key email ile alındı
- [ ] `.env` dosyasına `THE_ODDS_API_KEY` eklendi
- [ ] Git'e commit edilmedi (`.gitignore` kontrolü)

### Test:
- [ ] Test script çalışıyor
- [ ] API erişimi başarılı
- [ ] Sports list alınıyor
- [ ] Türkiye Süper Ligi var mı kontrol edildi
- [ ] Bookmaker listesi alındı
- [ ] İddaa bookmaker'ı var mı kontrol edildi
- [ ] Gerçek oranlar çekildi
- [ ] Oranlar doğrulandı (site ile karşılaştırma)

### Implementation:
- [ ] Provider class oluşturuldu
- [ ] Config'e fields eklendi
- [ ] Service entegrasyonu yapıldı
- [ ] Market mapping tamamlandı
- [ ] Cache mechanism eklendi
- [ ] Error handling eklendi

### UI:
- [ ] Gerçek oranlar Pick Card'da gösteriliyor
- [ ] Bookmaker adı gösteriliyor (İddaa veya alternatif)
- [ ] Timestamp gösteriliyor
- [ ] "Oran mevcut değil" durumu handle ediliyor

### Doğrulama:
- [ ] Build başarılı
- [ ] Testler geçiyor
- [ ] Gerçek maç oranları doğrulandı
- [ ] Rate limit kontrol edildi (500 req/month)

---

## 5. BEKLENEN SONUÇLAR

### Senaryo A: Türkiye Süper Ligi + İddaa Var ✅
```json
{
  "sport_key": "soccer_turkey_super_league",
  "home_team": "Galatasaray",
  "away_team": "Fenerbahçe",
  "bookmakers": [
    {
      "key": "iddaa",
      "title": "İddaa",
      "markets": [
        {
          "key": "h2h",
          "outcomes": [
            {"name": "Galatasaray", "price": 2.10},
            {"name": "Draw", "price": 3.40},
            {"name": "Fenerbahçe", "price": 3.20}
          ]
        }
      ]
    }
  ]
}
```

### Senaryo B: Türkiye Ligleri Yok, İddaa Var (başka ligde)
```
- Süper Lig kapsamı yok
- Ama İddaa bookmaker olarak mevcut
- Champions League veya Europa'da Türk takımları için İddaa oranı kullan
```

### Senaryo C: Türkiye Ligleri Var, İddaa Yok
```
- Süper Lig var
- Ama İddaa bookmaker değil
- Alternatif bookmaker kullan (Bet365, Unibet vs.)
- UI'da "Bet365 Oranı" olarak göster
```

### Senaryo D: Hiçbiri Yok ❌
```
- Türkiye ligleri yok
- İddaa yok
- RAPOR: The Odds API Türkiye kapsamı sağlamıyor
- ÖNERİ: Yalnızca model oranları kullan
```

---

## 6. RATE LIMIT YÖNETİMİ

**Free Tier: 500 requests/month**

### Hesaplama:
- 500 req/month ÷ 30 days = ~16 req/day
- Her odds çekme = 1 request
- Dikkatli kullanım gerekli

### Strateji:
1. **Cache aggressive:** 60 dakika cache
2. **Selective updates:** Sadece yaklaşan maçlar
3. **Batch requests:** Mümkünse toplu al
4. **Development mode:** Test sırasında mock data kullan

### Implementation:
```python
import time
from functools import lru_cache

class TheOddsAPIProvider:
    def __init__(self):
        self.last_request_time = {}
        self.cache_duration = 3600  # 1 hour
    
    def get_match_odds(self, ...):
        cache_key = f"{home_team}_{away_team}_{commence_time}"
        
        # Check cache
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if time.time() - cached_time < self.cache_duration:
                return cached_data
        
        # Make request
        data = self._fetch_from_api(...)
        self.cache[cache_key] = (data, time.time())
        return data
```

---

## 7. KULLANICI AKSİYONU GEREKLİ

### Adım 1: API Key Al
```
1. https://the-odds-api.com/ adresine git
2. "Get API Key" butonuna tıkla
3. Email adresini gir
4. Email'den API key'i al
```

### Adım 2: .env Güncelle
```bash
# backend/.env dosyasına ekle:
THE_ODDS_API_KEY=your_actual_api_key_here
THE_ODDS_API_ENABLED=true
```

### Adım 3: Test Et
```bash
cd backend
python scripts/test_odds_api.py
```

---

## SONUÇ

**Durum:** The Odds API kullanılabilir, API key gerekli

**Sonraki adım:** Kullanıcı API key aldıktan sonra test ve entegrasyon

**Alternatif:** API key alınamazsa model oranları kullan

