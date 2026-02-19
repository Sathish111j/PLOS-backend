"""Report endpoints for journal insights."""

from calendar import monthrange
from datetime import date, timedelta
from typing import Optional

from application.reporting.service import ReportService
from dependencies.providers import get_db_session
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth.dependencies import get_current_user
from shared.auth.models import TokenData

from .schemas import (
    ActivityDaily,
    HealthDaily,
    HealthSummary,
    MetricSeriesPoint,
    MetricSummary,
    NutritionDaily,
    NutritionSummary,
    SocialDaily,
    SocialSummary,
    TimeSeriesOverviewResponse,
    WeeklyActivityResponse,
    WeeklyHealthResponse,
    WeeklyMetricResponse,
    WeeklyNutritionResponse,
    WeeklyOverviewResponse,
    WeeklySocialResponse,
    WeeklyWorkResponse,
    WorkDaily,
    WorkSummary,
)

router = APIRouter(prefix="/journal/reports", tags=["journal-reports"])


def _validate_range(start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be on or after start_date",
        )


def _month_range(year: int, month: int) -> tuple[date, date]:
    if month < 1 or month > 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="month must be between 1 and 12",
        )
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _build_metric_response(
    *,
    service: ReportService,
    user_id: str,
    metric: str,
    unit: str,
    start_date: date,
    end_date: date,
    values_by_day: dict,
) -> WeeklyMetricResponse:
    series = [
        MetricSeriesPoint(date=day, value=values_by_day.get(day))
        for day in service._build_date_series(start_date, end_date)
    ]
    summary = MetricSummary(
        total=service._sum([point.value for point in series]),
        average=service._average([point.value for point in series]),
        unit=unit,
    )

    return WeeklyMetricResponse(
        user_id=user_id,
        metric=metric,
        unit=unit,
        start_date=start_date,
        end_date=end_date,
        series=series,
        summary=summary,
    )


def _build_activity_response(
    *,
    service: ReportService,
    user_id: str,
    start_date: date,
    end_date: date,
    activity_by_day: dict,
) -> WeeklyActivityResponse:
    daily = [
        ActivityDaily(
            date=day,
            minutes=activity_by_day.get(day, {}).get("minutes"),
            calories=activity_by_day.get(day, {}).get("calories"),
        )
        for day in service._build_date_series(start_date, end_date)
    ]

    total_minutes = service._sum([item.minutes for item in daily])
    total_calories = service._sum([item.calories for item in daily])

    return WeeklyActivityResponse(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        daily=daily,
        total_minutes=int(total_minutes) if total_minutes is not None else None,
        total_calories=int(total_calories) if total_calories is not None else None,
    )


def _build_nutrition_response(
    *,
    service: ReportService,
    user_id: str,
    start_date: date,
    end_date: date,
    nutrition_by_day: dict,
) -> WeeklyNutritionResponse:
    daily = [
        NutritionDaily(
            date=day,
            calories=nutrition_by_day.get(day, {}).get("calories"),
            protein_g=nutrition_by_day.get(day, {}).get("protein_g"),
            carbs_g=nutrition_by_day.get(day, {}).get("carbs_g"),
            fat_g=nutrition_by_day.get(day, {}).get("fat_g"),
        )
        for day in service._build_date_series(start_date, end_date)
    ]

    summary = NutritionSummary(
        total_calories=service._sum([item.calories for item in daily]),
        total_protein_g=service._sum([item.protein_g for item in daily]),
        total_carbs_g=service._sum([item.carbs_g for item in daily]),
        total_fat_g=service._sum([item.fat_g for item in daily]),
        avg_calories=service._average([item.calories for item in daily]),
        avg_protein_g=service._average([item.protein_g for item in daily]),
        avg_carbs_g=service._average([item.carbs_g for item in daily]),
        avg_fat_g=service._average([item.fat_g for item in daily]),
    )

    return WeeklyNutritionResponse(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        daily=daily,
        summary=summary,
    )


def _build_social_response(
    *,
    service: ReportService,
    user_id: str,
    start_date: date,
    end_date: date,
    result: dict,
) -> WeeklySocialResponse:
    daily = [
        SocialDaily(date=day, interactions=result["daily"].get(day))
        for day in service._build_date_series(start_date, end_date)
    ]
    summary = SocialSummary(
        total_interactions=result["summary"]["total_interactions"],
        by_relationship_category=result["summary"]["by_relationship_category"],
        top_people=result["summary"]["top_people"],
    )

    return WeeklySocialResponse(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        daily=daily,
        summary=summary,
    )


def _build_health_response(
    *,
    service: ReportService,
    user_id: str,
    start_date: date,
    end_date: date,
    result: dict,
) -> WeeklyHealthResponse:
    daily = [
        HealthDaily(date=day, symptoms=result["daily"].get(day))
        for day in service._build_date_series(start_date, end_date)
    ]
    summary = HealthSummary(
        total_symptoms=result["summary"]["total_symptoms"],
        top_symptoms=result["summary"]["top_symptoms"],
    )

    return WeeklyHealthResponse(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        daily=daily,
        summary=summary,
    )


def _build_work_response(
    *,
    service: ReportService,
    user_id: str,
    start_date: date,
    end_date: date,
    result: dict,
) -> WeeklyWorkResponse:
    daily = [
        WorkDaily(
            date=day,
            minutes=result["daily"].get(day, {}).get("minutes"),
            productivity_avg=result["daily"].get(day, {}).get("productivity_avg"),
        )
        for day in service._build_date_series(start_date, end_date)
    ]
    summary = WorkSummary(
        total_minutes=result["summary"]["total_minutes"],
        avg_productivity=result["summary"]["avg_productivity"],
    )

    return WeeklyWorkResponse(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        daily=daily,
        summary=summary,
    )


@router.get(
    "/weekly-overview",
    response_model=WeeklyOverviewResponse,
    summary="Weekly overview report",
    description="Aggregated weekly overview for calories, sleep, mood, water, and activity.",
)
async def get_weekly_overview(
    days: int = Query(7, ge=1, le=90),
    end_date: Optional[date] = Query(None),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyOverviewResponse:
    service = ReportService(db)
    start_date, resolved_end_date = service._resolve_date_range(days, end_date)

    result = await service.get_weekly_overview(
        user_id=current_user.user_id,
        start_date=start_date,
        end_date=resolved_end_date,
    )

    return WeeklyOverviewResponse(
        user_id=str(current_user.user_id),
        start_date=start_date,
        end_date=resolved_end_date,
        daily=result["daily"],
        summary=result["summary"],
        context_snapshot=result["context_snapshot"],
    )


@router.get(
    "/daily-overview",
    response_model=WeeklyOverviewResponse,
    summary="Daily overview report",
    description="Overview for a single date.",
)
async def get_daily_overview(
    target_date: date = Query(...),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyOverviewResponse:
    service = ReportService(db)
    result = await service.get_weekly_overview(
        user_id=current_user.user_id,
        start_date=target_date,
        end_date=target_date,
    )

    return WeeklyOverviewResponse(
        user_id=str(current_user.user_id),
        start_date=target_date,
        end_date=target_date,
        daily=result["daily"],
        summary=result["summary"],
        context_snapshot=result["context_snapshot"],
    )


@router.get(
    "/monthly-overview",
    response_model=WeeklyOverviewResponse,
    summary="Monthly overview report",
    description="Overview for a specific month.",
)
async def get_monthly_overview(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyOverviewResponse:
    service = ReportService(db)
    start_date, end_date = _month_range(year, month)
    result = await service.get_weekly_overview(
        user_id=current_user.user_id,
        start_date=start_date,
        end_date=end_date,
    )

    return WeeklyOverviewResponse(
        user_id=str(current_user.user_id),
        start_date=start_date,
        end_date=end_date,
        daily=result["daily"],
        summary=result["summary"],
        context_snapshot=result["context_snapshot"],
    )


@router.get(
    "/range-overview",
    response_model=WeeklyOverviewResponse,
    summary="Range overview report",
    description="Overview for a custom date range.",
)
async def get_range_overview(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyOverviewResponse:
    _validate_range(start_date, end_date)
    service = ReportService(db)
    result = await service.get_weekly_overview(
        user_id=current_user.user_id,
        start_date=start_date,
        end_date=end_date,
    )

    return WeeklyOverviewResponse(
        user_id=str(current_user.user_id),
        start_date=start_date,
        end_date=end_date,
        daily=result["daily"],
        summary=result["summary"],
        context_snapshot=result["context_snapshot"],
    )


@router.get(
    "/timeseries-overview",
    response_model=TimeSeriesOverviewResponse,
    summary="Bucketed time-series overview",
    description="Time-series analytics from Timescale hypertable with day/week/month buckets.",
)
async def get_timeseries_overview(
    start_date: date = Query(...),
    end_date: date = Query(...),
    bucket: str = Query("day", pattern="^(day|week|month)$"),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> TimeSeriesOverviewResponse:
    _validate_range(start_date, end_date)

    interval_map = {
        "day": timedelta(days=1),
        "week": timedelta(weeks=1),
        "month": timedelta(days=30),
    }

    service = ReportService(db)
    points = await service.get_timeseries_overview(
        user_id=current_user.user_id,
        start_date=start_date,
        end_date=end_date,
        bucket_interval=interval_map[bucket],
    )

    return TimeSeriesOverviewResponse(
        user_id=str(current_user.user_id),
        start_date=start_date,
        end_date=end_date,
        bucket=bucket,
        points=points,
    )


@router.get(
    "/calories/weekly",
    response_model=WeeklyMetricResponse,
    summary="Weekly calories intake",
    description="Daily calories intake totals over a date range.",
)
async def get_weekly_calories(
    days: int = Query(7, ge=1, le=90),
    end_date: Optional[date] = Query(None),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyMetricResponse:
    service = ReportService(db)
    start_date, resolved_end_date = service._resolve_date_range(days, end_date)
    calories_by_day = await service.get_daily_calories(
        current_user.user_id, start_date, resolved_end_date
    )
    return _build_metric_response(
        service=service,
        user_id=str(current_user.user_id),
        metric="calories_in",
        unit="kcal",
        start_date=start_date,
        end_date=resolved_end_date,
        values_by_day=calories_by_day,
    )


@router.get(
    "/calories/monthly",
    response_model=WeeklyMetricResponse,
    summary="Monthly calories intake",
    description="Daily calories intake totals for a specific month.",
)
async def get_monthly_calories(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyMetricResponse:
    service = ReportService(db)
    start_date, end_date = _month_range(year, month)
    calories_by_day = await service.get_daily_calories(
        current_user.user_id, start_date, end_date
    )
    return _build_metric_response(
        service=service,
        user_id=str(current_user.user_id),
        metric="calories_in",
        unit="kcal",
        start_date=start_date,
        end_date=end_date,
        values_by_day=calories_by_day,
    )


@router.get(
    "/calories/range",
    response_model=WeeklyMetricResponse,
    summary="Range calories intake",
    description="Daily calories intake totals for a custom range.",
)
async def get_range_calories(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyMetricResponse:
    _validate_range(start_date, end_date)
    service = ReportService(db)
    calories_by_day = await service.get_daily_calories(
        current_user.user_id, start_date, end_date
    )
    return _build_metric_response(
        service=service,
        user_id=str(current_user.user_id),
        metric="calories_in",
        unit="kcal",
        start_date=start_date,
        end_date=end_date,
        values_by_day=calories_by_day,
    )


@router.get(
    "/sleep/weekly",
    response_model=WeeklyMetricResponse,
    summary="Weekly sleep duration",
    description="Daily sleep duration in hours over a date range.",
)
async def get_weekly_sleep(
    days: int = Query(7, ge=1, le=90),
    end_date: Optional[date] = Query(None),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyMetricResponse:
    service = ReportService(db)
    start_date, resolved_end_date = service._resolve_date_range(days, end_date)
    sleep_by_day = await service.get_daily_sleep(
        current_user.user_id, start_date, resolved_end_date
    )
    values_by_day = {
        day: value.get("sleep_hours") for day, value in sleep_by_day.items()
    }
    return _build_metric_response(
        service=service,
        user_id=str(current_user.user_id),
        metric="sleep_hours",
        unit="hours",
        start_date=start_date,
        end_date=resolved_end_date,
        values_by_day=values_by_day,
    )


@router.get(
    "/sleep/monthly",
    response_model=WeeklyMetricResponse,
    summary="Monthly sleep duration",
    description="Daily sleep duration in hours for a specific month.",
)
async def get_monthly_sleep(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyMetricResponse:
    service = ReportService(db)
    start_date, end_date = _month_range(year, month)
    sleep_by_day = await service.get_daily_sleep(
        current_user.user_id, start_date, end_date
    )
    values_by_day = {
        day: value.get("sleep_hours") for day, value in sleep_by_day.items()
    }
    return _build_metric_response(
        service=service,
        user_id=str(current_user.user_id),
        metric="sleep_hours",
        unit="hours",
        start_date=start_date,
        end_date=end_date,
        values_by_day=values_by_day,
    )


@router.get(
    "/sleep/range",
    response_model=WeeklyMetricResponse,
    summary="Range sleep duration",
    description="Daily sleep duration in hours for a custom range.",
)
async def get_range_sleep(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyMetricResponse:
    _validate_range(start_date, end_date)
    service = ReportService(db)
    sleep_by_day = await service.get_daily_sleep(
        current_user.user_id, start_date, end_date
    )
    values_by_day = {
        day: value.get("sleep_hours") for day, value in sleep_by_day.items()
    }
    return _build_metric_response(
        service=service,
        user_id=str(current_user.user_id),
        metric="sleep_hours",
        unit="hours",
        start_date=start_date,
        end_date=end_date,
        values_by_day=values_by_day,
    )


@router.get(
    "/mood/weekly",
    response_model=WeeklyMetricResponse,
    summary="Weekly mood score",
    description="Daily mood score (1-10) over a date range.",
)
async def get_weekly_mood(
    days: int = Query(7, ge=1, le=90),
    end_date: Optional[date] = Query(None),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyMetricResponse:
    service = ReportService(db)
    start_date, resolved_end_date = service._resolve_date_range(days, end_date)
    mood_by_day = await service.get_daily_mood(
        current_user.user_id, start_date, resolved_end_date
    )
    return _build_metric_response(
        service=service,
        user_id=str(current_user.user_id),
        metric="mood_score",
        unit="score",
        start_date=start_date,
        end_date=resolved_end_date,
        values_by_day=mood_by_day,
    )


@router.get(
    "/mood/monthly",
    response_model=WeeklyMetricResponse,
    summary="Monthly mood score",
    description="Daily mood score (1-10) for a specific month.",
)
async def get_monthly_mood(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyMetricResponse:
    service = ReportService(db)
    start_date, end_date = _month_range(year, month)
    mood_by_day = await service.get_daily_mood(
        current_user.user_id, start_date, end_date
    )
    return _build_metric_response(
        service=service,
        user_id=str(current_user.user_id),
        metric="mood_score",
        unit="score",
        start_date=start_date,
        end_date=end_date,
        values_by_day=mood_by_day,
    )


@router.get(
    "/mood/range",
    response_model=WeeklyMetricResponse,
    summary="Range mood score",
    description="Daily mood score (1-10) for a custom range.",
)
async def get_range_mood(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyMetricResponse:
    _validate_range(start_date, end_date)
    service = ReportService(db)
    mood_by_day = await service.get_daily_mood(
        current_user.user_id, start_date, end_date
    )
    return _build_metric_response(
        service=service,
        user_id=str(current_user.user_id),
        metric="mood_score",
        unit="score",
        start_date=start_date,
        end_date=end_date,
        values_by_day=mood_by_day,
    )


@router.get(
    "/water/weekly",
    response_model=WeeklyMetricResponse,
    summary="Weekly water intake",
    description="Daily water intake in ml over a date range.",
)
async def get_weekly_water(
    days: int = Query(7, ge=1, le=90),
    end_date: Optional[date] = Query(None),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyMetricResponse:
    service = ReportService(db)
    start_date, resolved_end_date = service._resolve_date_range(days, end_date)
    water_by_day = await service.get_daily_water(
        current_user.user_id, start_date, resolved_end_date
    )
    return _build_metric_response(
        service=service,
        user_id=str(current_user.user_id),
        metric="water_ml",
        unit="ml",
        start_date=start_date,
        end_date=resolved_end_date,
        values_by_day=water_by_day,
    )


@router.get(
    "/water/monthly",
    response_model=WeeklyMetricResponse,
    summary="Monthly water intake",
    description="Daily water intake in ml for a specific month.",
)
async def get_monthly_water(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyMetricResponse:
    service = ReportService(db)
    start_date, end_date = _month_range(year, month)
    water_by_day = await service.get_daily_water(
        current_user.user_id, start_date, end_date
    )
    return _build_metric_response(
        service=service,
        user_id=str(current_user.user_id),
        metric="water_ml",
        unit="ml",
        start_date=start_date,
        end_date=end_date,
        values_by_day=water_by_day,
    )


@router.get(
    "/water/range",
    response_model=WeeklyMetricResponse,
    summary="Range water intake",
    description="Daily water intake in ml for a custom range.",
)
async def get_range_water(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyMetricResponse:
    _validate_range(start_date, end_date)
    service = ReportService(db)
    water_by_day = await service.get_daily_water(
        current_user.user_id, start_date, end_date
    )
    return _build_metric_response(
        service=service,
        user_id=str(current_user.user_id),
        metric="water_ml",
        unit="ml",
        start_date=start_date,
        end_date=end_date,
        values_by_day=water_by_day,
    )


@router.get(
    "/steps/weekly",
    response_model=WeeklyMetricResponse,
    summary="Weekly steps",
    description="Daily step counts over a date range.",
)
async def get_weekly_steps(
    days: int = Query(7, ge=1, le=90),
    end_date: Optional[date] = Query(None),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyMetricResponse:
    service = ReportService(db)
    start_date, resolved_end_date = service._resolve_date_range(days, end_date)
    steps_by_day = await service.get_daily_steps(
        current_user.user_id, start_date, resolved_end_date
    )
    return _build_metric_response(
        service=service,
        user_id=str(current_user.user_id),
        metric="steps",
        unit="steps",
        start_date=start_date,
        end_date=resolved_end_date,
        values_by_day=steps_by_day,
    )


@router.get(
    "/steps/monthly",
    response_model=WeeklyMetricResponse,
    summary="Monthly steps",
    description="Daily step counts for a specific month.",
)
async def get_monthly_steps(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyMetricResponse:
    service = ReportService(db)
    start_date, end_date = _month_range(year, month)
    steps_by_day = await service.get_daily_steps(
        current_user.user_id, start_date, end_date
    )
    return _build_metric_response(
        service=service,
        user_id=str(current_user.user_id),
        metric="steps",
        unit="steps",
        start_date=start_date,
        end_date=end_date,
        values_by_day=steps_by_day,
    )


@router.get(
    "/steps/range",
    response_model=WeeklyMetricResponse,
    summary="Range steps",
    description="Daily step counts for a custom range.",
)
async def get_range_steps(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyMetricResponse:
    _validate_range(start_date, end_date)
    service = ReportService(db)
    steps_by_day = await service.get_daily_steps(
        current_user.user_id, start_date, end_date
    )
    return _build_metric_response(
        service=service,
        user_id=str(current_user.user_id),
        metric="steps",
        unit="steps",
        start_date=start_date,
        end_date=end_date,
        values_by_day=steps_by_day,
    )


@router.get(
    "/activity/weekly",
    response_model=WeeklyActivityResponse,
    summary="Weekly activity totals",
    description="Daily activity minutes and calories over a date range.",
)
async def get_weekly_activity(
    days: int = Query(7, ge=1, le=90),
    end_date: Optional[date] = Query(None),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyActivityResponse:
    service = ReportService(db)
    start_date, resolved_end_date = service._resolve_date_range(days, end_date)
    activity_by_day = await service.get_daily_activity(
        current_user.user_id, start_date, resolved_end_date
    )
    return _build_activity_response(
        service=service,
        user_id=str(current_user.user_id),
        start_date=start_date,
        end_date=resolved_end_date,
        activity_by_day=activity_by_day,
    )


@router.get(
    "/activity/monthly",
    response_model=WeeklyActivityResponse,
    summary="Monthly activity totals",
    description="Daily activity minutes and calories for a specific month.",
)
async def get_monthly_activity(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyActivityResponse:
    service = ReportService(db)
    start_date, end_date = _month_range(year, month)
    activity_by_day = await service.get_daily_activity(
        current_user.user_id, start_date, end_date
    )
    return _build_activity_response(
        service=service,
        user_id=str(current_user.user_id),
        start_date=start_date,
        end_date=end_date,
        activity_by_day=activity_by_day,
    )


@router.get(
    "/activity/range",
    response_model=WeeklyActivityResponse,
    summary="Range activity totals",
    description="Daily activity minutes and calories for a custom range.",
)
async def get_range_activity(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyActivityResponse:
    _validate_range(start_date, end_date)
    service = ReportService(db)
    activity_by_day = await service.get_daily_activity(
        current_user.user_id, start_date, end_date
    )
    return _build_activity_response(
        service=service,
        user_id=str(current_user.user_id),
        start_date=start_date,
        end_date=end_date,
        activity_by_day=activity_by_day,
    )


@router.get(
    "/nutrition/weekly",
    response_model=WeeklyNutritionResponse,
    summary="Weekly nutrition summary",
    description="Daily nutrition totals and macro breakdown over a date range.",
)
async def get_weekly_nutrition(
    days: int = Query(7, ge=1, le=90),
    end_date: Optional[date] = Query(None),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyNutritionResponse:
    service = ReportService(db)
    start_date, resolved_end_date = service._resolve_date_range(days, end_date)
    nutrition_by_day = await service.get_daily_nutrition(
        current_user.user_id, start_date, resolved_end_date
    )
    return _build_nutrition_response(
        service=service,
        user_id=str(current_user.user_id),
        start_date=start_date,
        end_date=resolved_end_date,
        nutrition_by_day=nutrition_by_day,
    )


@router.get(
    "/nutrition/monthly",
    response_model=WeeklyNutritionResponse,
    summary="Monthly nutrition summary",
    description="Daily nutrition totals for a specific month.",
)
async def get_monthly_nutrition(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyNutritionResponse:
    service = ReportService(db)
    start_date, end_date = _month_range(year, month)
    nutrition_by_day = await service.get_daily_nutrition(
        current_user.user_id, start_date, end_date
    )
    return _build_nutrition_response(
        service=service,
        user_id=str(current_user.user_id),
        start_date=start_date,
        end_date=end_date,
        nutrition_by_day=nutrition_by_day,
    )


@router.get(
    "/nutrition/range",
    response_model=WeeklyNutritionResponse,
    summary="Range nutrition summary",
    description="Daily nutrition totals for a custom range.",
)
async def get_range_nutrition(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyNutritionResponse:
    _validate_range(start_date, end_date)
    service = ReportService(db)
    nutrition_by_day = await service.get_daily_nutrition(
        current_user.user_id, start_date, end_date
    )
    return _build_nutrition_response(
        service=service,
        user_id=str(current_user.user_id),
        start_date=start_date,
        end_date=end_date,
        nutrition_by_day=nutrition_by_day,
    )


@router.get(
    "/social/weekly",
    response_model=WeeklySocialResponse,
    summary="Weekly social summary",
    description="Daily social interactions and relationship breakdown.",
)
async def get_weekly_social(
    days: int = Query(7, ge=1, le=90),
    end_date: Optional[date] = Query(None),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklySocialResponse:
    service = ReportService(db)
    start_date, resolved_end_date = service._resolve_date_range(days, end_date)
    result = await service.get_social_summary(
        current_user.user_id, start_date, resolved_end_date
    )
    return _build_social_response(
        service=service,
        user_id=str(current_user.user_id),
        start_date=start_date,
        end_date=resolved_end_date,
        result=result,
    )


@router.get(
    "/social/monthly",
    response_model=WeeklySocialResponse,
    summary="Monthly social summary",
    description="Daily social interactions for a specific month.",
)
async def get_monthly_social(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklySocialResponse:
    service = ReportService(db)
    start_date, end_date = _month_range(year, month)
    result = await service.get_social_summary(
        current_user.user_id, start_date, end_date
    )
    return _build_social_response(
        service=service,
        user_id=str(current_user.user_id),
        start_date=start_date,
        end_date=end_date,
        result=result,
    )


@router.get(
    "/social/range",
    response_model=WeeklySocialResponse,
    summary="Range social summary",
    description="Daily social interactions for a custom range.",
)
async def get_range_social(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklySocialResponse:
    _validate_range(start_date, end_date)
    service = ReportService(db)
    result = await service.get_social_summary(
        current_user.user_id, start_date, end_date
    )
    return _build_social_response(
        service=service,
        user_id=str(current_user.user_id),
        start_date=start_date,
        end_date=end_date,
        result=result,
    )


@router.get(
    "/health/weekly",
    response_model=WeeklyHealthResponse,
    summary="Weekly health summary",
    description="Daily symptom counts and top symptoms over a date range.",
)
async def get_weekly_health(
    days: int = Query(7, ge=1, le=90),
    end_date: Optional[date] = Query(None),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyHealthResponse:
    service = ReportService(db)
    start_date, resolved_end_date = service._resolve_date_range(days, end_date)
    result = await service.get_health_summary(
        current_user.user_id, start_date, resolved_end_date
    )
    return _build_health_response(
        service=service,
        user_id=str(current_user.user_id),
        start_date=start_date,
        end_date=resolved_end_date,
        result=result,
    )


@router.get(
    "/health/monthly",
    response_model=WeeklyHealthResponse,
    summary="Monthly health summary",
    description="Daily symptom counts for a specific month.",
)
async def get_monthly_health(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyHealthResponse:
    service = ReportService(db)
    start_date, end_date = _month_range(year, month)
    result = await service.get_health_summary(
        current_user.user_id, start_date, end_date
    )
    return _build_health_response(
        service=service,
        user_id=str(current_user.user_id),
        start_date=start_date,
        end_date=end_date,
        result=result,
    )


@router.get(
    "/health/range",
    response_model=WeeklyHealthResponse,
    summary="Range health summary",
    description="Daily symptom counts for a custom range.",
)
async def get_range_health(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyHealthResponse:
    _validate_range(start_date, end_date)
    service = ReportService(db)
    result = await service.get_health_summary(
        current_user.user_id, start_date, end_date
    )
    return _build_health_response(
        service=service,
        user_id=str(current_user.user_id),
        start_date=start_date,
        end_date=end_date,
        result=result,
    )


@router.get(
    "/work/weekly",
    response_model=WeeklyWorkResponse,
    summary="Weekly work summary",
    description="Daily work minutes and productivity averages over a date range.",
)
async def get_weekly_work(
    days: int = Query(7, ge=1, le=90),
    end_date: Optional[date] = Query(None),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyWorkResponse:
    service = ReportService(db)
    start_date, resolved_end_date = service._resolve_date_range(days, end_date)
    result = await service.get_work_summary(
        current_user.user_id, start_date, resolved_end_date
    )
    return _build_work_response(
        service=service,
        user_id=str(current_user.user_id),
        start_date=start_date,
        end_date=resolved_end_date,
        result=result,
    )


@router.get(
    "/work/monthly",
    response_model=WeeklyWorkResponse,
    summary="Monthly work summary",
    description="Daily work minutes and productivity averages for a specific month.",
)
async def get_monthly_work(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyWorkResponse:
    service = ReportService(db)
    start_date, end_date = _month_range(year, month)
    result = await service.get_work_summary(current_user.user_id, start_date, end_date)
    return _build_work_response(
        service=service,
        user_id=str(current_user.user_id),
        start_date=start_date,
        end_date=end_date,
        result=result,
    )


@router.get(
    "/work/range",
    response_model=WeeklyWorkResponse,
    summary="Range work summary",
    description="Daily work minutes and productivity averages for a custom range.",
)
async def get_range_work(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WeeklyWorkResponse:
    _validate_range(start_date, end_date)
    service = ReportService(db)
    result = await service.get_work_summary(current_user.user_id, start_date, end_date)
    return _build_work_response(
        service=service,
        user_id=str(current_user.user_id),
        start_date=start_date,
        end_date=end_date,
        result=result,
    )
