"""Odds API endpoints for retrieving market odds data."""

import logging
from typing import List, Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.session import get_db
from app.database.models import AverageMarketOdds, BookmakerOdds
from app.providers.odds_api_provider import the_odds_api_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/odds", tags=["odds"])


class MarketOddsResponse(BaseModel):
    """Response model for market odds."""
    
    provider_event_id: str
    match_id: Optional[str]
    market_key: str
    market_point: Optional[float]
    outcome_name: str
    average_odds: float
    bookmaker_count: int
    min_odds: Optional[float]
    max_odds: Optional[float]
    bookmakers: List[str]
    individual_odds: List[float]
    calculated_at: datetime
    
    class Config:
        from_attributes = True


class MatchOddsResponse(BaseModel):
    """Response model for complete match odds."""
    
    match_found: bool
    home_team: str
    away_team: str
    commence_time: Optional[datetime]
    home_win: Optional[MarketOddsResponse]
    draw: Optional[MarketOddsResponse]
    away_win: Optional[MarketOddsResponse]
    over_2_5: Optional[MarketOddsResponse]
    under_2_5: Optional[MarketOddsResponse]
    last_updated: Optional[datetime]


class OddsHealthResponse(BaseModel):
    """Response model for odds system health."""
    
    api_available: bool
    api_quota_remaining: Optional[int]
    last_update: Optional[datetime]
    total_events_cached: int
    total_bookmakers: int


@router.get("/match/{match_id}", response_model=MatchOddsResponse)
async def get_match_odds(
    match_id: str,
    db: Session = Depends(get_db)
):
    """
    Bir maç için ortalama piyasa oranlarını getir.
    
    Args:
        match_id: TUTAR X maç ID'si
        db: Veritabanı oturumu
        
    Returns:
        Maç oranları veya match_found: false
    """
    logger.info(f"Fetching odds for match {match_id}")
    
    # Veritabanından ortalama oranları getir
    odds_records = db.query(AverageMarketOdds).filter(
        AverageMarketOdds.match_id == match_id
    ).all()
    
    if not odds_records:
        logger.info(f"No odds found for match {match_id}")
        return MatchOddsResponse(
            match_found=False,
            home_team="",
            away_team="",
            commence_time=None,
            home_win=None,
            draw=None,
            away_win=None,
            over_2_5=None,
            under_2_5=None,
            last_updated=None
        )
    
    # Maç bilgilerini al (ilk kayıttan)
    sample_record = odds_records[0]
    
    # Oranları outcome_name'e göre grupla
    odds_by_outcome = {}
    last_updated = None
    
    for record in odds_records:
        if record.market_key == 'h2h':
            # Match result oranları
            outcome_lower = record.outcome_name.lower()
            if 'draw' in outcome_lower:
                odds_by_outcome['draw'] = record
            elif sample_record.provider_event_id:
                # Provider event'ten takım isimlerini çıkar (basitleştirilmiş)
                if record.outcome_name == sample_record.home_team_name:
                    odds_by_outcome['home_win'] = record
                elif record.outcome_name == sample_record.away_team_name:
                    odds_by_outcome['away_win'] = record
        
        elif record.market_key == 'totals' and record.market_point == 2.5:
            # Over/Under 2.5 oranları
            outcome_lower = record.outcome_name.lower()
            if 'over' in outcome_lower:
                odds_by_outcome['over_2_5'] = record
            elif 'under' in outcome_lower:
                odds_by_outcome['under_2_5'] = record
        
        # En son güncelleme zamanını takip et
        if last_updated is None or record.calculated_at > last_updated:
            last_updated = record.calculated_at
    
    # Response oluştur
    def convert_to_response(odds_record: Optional[AverageMarketOdds]) -> Optional[MarketOddsResponse]:
        if not odds_record:
            return None
        return MarketOddsResponse.from_orm(odds_record)
    
    return MatchOddsResponse(
        match_found=True,
        home_team=sample_record.home_team_name or "",
        away_team=sample_record.away_team_name or "",
        commence_time=sample_record.commence_time,
        home_win=convert_to_response(odds_by_outcome.get('home_win')),
        draw=convert_to_response(odds_by_outcome.get('draw')),
        away_win=convert_to_response(odds_by_outcome.get('away_win')),
        over_2_5=convert_to_response(odds_by_outcome.get('over_2_5')),
        under_2_5=convert_to_response(odds_by_outcome.get('under_2_5')),
        last_updated=last_updated
    )


@router.get("/events/{provider_event_id}", response_model=List[MarketOddsResponse])
async def get_event_odds(
    provider_event_id: str,
    db: Session = Depends(get_db)
):
    """
    Bir provider event ID'si için tüm ortalama oranları getir.
    
    Args:
        provider_event_id: The Odds API event ID'si
        db: Veritabanı oturumu
        
    Returns:
        Event'e ait ortalama oranlar listesi
    """
    odds_records = db.query(AverageMarketOdds).filter(
        AverageMarketOdds.provider_event_id == provider_event_id
    ).all()
    
    return [MarketOddsResponse.from_orm(record) for record in odds_records]


@router.get("/search")
async def search_match_odds(
    home_team: str = Query(..., description="Ev sahibi takım adı"),
    away_team: str = Query(..., description="Deplasman takım adı"),
    sport_key: str = Query("soccer_epl", description="Spor kategorisi"),
    db: Session = Depends(get_db)
):
    """
    Takım adlarına göre maç oranlarını ara.
    
    Bu endpoint, provider veritabanında takım adlarına göre arama yapar.
    TUTAR X maç ID'si yoksa da çalışır.
    """
    from app.utils.team_name_normalizer import normalize_team_name
    
    # Normalize edilmiş takım isimleri
    home_normalized = normalize_team_name(home_team)
    away_normalized = normalize_team_name(away_team)
    
    # Veritabanında benzer takım isimlerini ara
    odds_records = db.query(AverageMarketOdds).join(BookmakerOdds).filter(
        BookmakerOdds.sport_key == sport_key,
        BookmakerOdds.home_team_name.ilike(f"%{home_normalized}%"),
        BookmakerOdds.away_team_name.ilike(f"%{away_normalized}%")
    ).all()
    
    if not odds_records:
        return {
            "match_found": False,
            "search_terms": {"home_team": home_team, "away_team": away_team},
            "message": "Maç bulunamadı"
        }
    
    # İlk eşleşen event'i al ve formatla
    event_id = odds_records[0].provider_event_id
    
    return await get_event_odds(event_id, db)


@router.get("/health", response_model=OddsHealthResponse)
async def get_odds_health(db: Session = Depends(get_db)):
    """
    Odds sistemi sağlık durumunu kontrol et.
    
    Returns:
        API durumu, kota bilgisi, son güncelleme vs.
    """
    # API durumu kontrol et
    api_available = the_odds_api_provider.is_available()
    
    # Kota kontrolü (opsiyonel)
    api_quota_remaining = None
    if api_available:
        try:
            has_quota, remaining = the_odds_api_provider.check_quota()
            api_quota_remaining = remaining
        except Exception as e:
            logger.warning(f"Quota check failed: {e}")
    
    # Veritabanı istatistikleri
    
    # Son güncelleme zamanı
    latest_odds = db.query(AverageMarketOdds).order_by(
        AverageMarketOdds.calculated_at.desc()
    ).first()
    
    last_update = latest_odds.calculated_at if latest_odds else None
    
    # Toplam event sayısı
    total_events = db.query(AverageMarketOdds.provider_event_id).distinct().count()
    
    # Toplam bookmaker sayısı
    total_bookmakers = db.query(BookmakerOdds.bookmaker_key).distinct().count()
    
    return OddsHealthResponse(
        api_available=api_available,
        api_quota_remaining=api_quota_remaining,
        last_update=last_update,
        total_events_cached=total_events,
        total_bookmakers=total_bookmakers
    )


@router.post("/manual-update")
async def manual_odds_update(
    sport_key: Optional[str] = Query(None, description="Belirli bir spor için güncelleme"),
    db: Session = Depends(get_db)
):
    """
    Manuel odds güncellemesi tetikle.
    
    Bu endpoint admin/test amaçlı kullanılır.
    Production'da scheduler otomatik güncelleme yapar.
    """
    try:
        if sport_key:
            # Tek spor güncellemesi
            from app.services.odds_updater_service import OddsUpdaterService
            
            service = OddsUpdaterService(db)
            result = service.update_odds_for_sport(sport_key)
        else:
            # Tüm sporlar
            from app.services.odds_updater_service import update_all_odds
            result = update_all_odds()
        
        return {
            "success": True,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Manual update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bookmakers")
async def get_available_bookmakers(db: Session = Depends(get_db)):
    """
    Sistemde mevcut bookmaker'ları listele.
    
    Returns:
        Bookmaker listesi ve istatistikleri
    """
    # Bookmaker'ları ve event sayılarını getir
    bookmaker_stats = db.query(
        BookmakerOdds.bookmaker_key,
        BookmakerOdds.bookmaker_title,
        db.func.count(BookmakerOdds.provider_event_id.distinct()).label('event_count'),
        db.func.max(BookmakerOdds.fetched_at).label('last_seen')
    ).group_by(
        BookmakerOdds.bookmaker_key,
        BookmakerOdds.bookmaker_title
    ).all()
    
    return [
        {
            "key": stat.bookmaker_key,
            "title": stat.bookmaker_title,
            "event_count": stat.event_count,
            "last_seen": stat.last_seen
        }
        for stat in bookmaker_stats
    ]


@router.get("/sports")
async def get_available_sports():
    """
    The Odds API'den mevcut sporları getir.
    
    Bu endpoint, hangi sporların desteklendiğini öğrenmek için kullanılır.
    """
    if not the_odds_api_provider.is_available():
        raise HTTPException(status_code=503, detail="Odds API not available")
    
    sports = the_odds_api_provider.get_available_sports()
    
    if sports is None:
        raise HTTPException(status_code=502, detail="Failed to fetch sports from API")
    
    # Sadece futbol sporlarını filtrele
    soccer_sports = [
        sport for sport in sports 
        if sport.get('key', '').startswith('soccer_')
    ]
    
    return {
        "total_sports": len(sports),
        "soccer_sports": soccer_sports,
        "configured_sports": [
            s.strip() for s in (the_odds_api_provider.provider.sports or "").split(',')
            if s.strip()
        ]
    }