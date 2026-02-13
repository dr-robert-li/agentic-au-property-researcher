"""
Per-suburb detailed research functionality using deep research.
"""
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Callable

from config import settings
from research.cache import get_cache

logger = logging.getLogger(__name__)

from models.suburb_metrics import (
    SuburbMetrics,
    SuburbIdentification,
    MarketMetricsCurrent,
    MarketMetricsHistory,
    PhysicalConfig,
    Demographics,
    Infrastructure,
    GrowthProjections,
    TimePoint
)
from research.suburb_discovery import SuburbCandidate
from research.perplexity_client import (
    get_client, PerplexityRateLimitError, PerplexityAuthError, PerplexityAPIError
)
from research.anthropic_client import (
    AnthropicRateLimitError, AnthropicAuthError, AnthropicAPIError
)

# Account-level errors (auth, credits, rate limits) — stop the batch immediately
API_ACCOUNT_ERRORS = (
    PerplexityRateLimitError, PerplexityAuthError,
    AnthropicRateLimitError, AnthropicAuthError,
)
# Per-request API errors (timeouts, server errors) — skip suburb, continue batch
API_TRANSIENT_ERRORS = (PerplexityAPIError, AnthropicAPIError)


def research_suburb(
    candidate: SuburbCandidate,
    dwelling_type: str,
    max_price: float,
    provider: str = "perplexity"
) -> SuburbMetrics:
    """
    Perform exhaustive research on a single suburb.

    Args:
        candidate: SuburbCandidate from discovery phase
        dwelling_type: Type of dwelling (house, apartment, townhouse)
        max_price: Maximum median price threshold
        provider: Research provider ("perplexity" or "anthropic")

    Returns:
        Complete SuburbMetrics object with all available data

    Raises:
        Exception: If API call fails or response cannot be parsed
    """
    client = get_client(provider)

    # Build the detailed research prompt
    prompt = f"""
You are an Australian property research agent. Perform EXHAUSTIVE research on {candidate.name}, {candidate.state} for {dwelling_type} properties.

Use web_search and fetch_url tools to gather comprehensive, current data.

RETURN ONLY VALID JSON IN THIS EXACT STRUCTURE (no additional text):

{{
  "identification": {{
    "name": "{candidate.name}",
    "state": "{candidate.state}",
    "lga": "{candidate.lga}",
    "region": "{candidate.region}"
  }},
  "market_current": {{
    "median_price": {candidate.median_price},
    "average_price": 0,
    "auction_clearance_current": 0.0,
    "days_on_market_current": 0.0,
    "turnover_rate_current": 0.0,
    "rental_yield_current": 0.0
  }},
  "market_history": {{
    "price_history": [{{"year": 2020, "value": 0}}, {{"year": 2021, "value": 0}}, {{"year": 2022, "value": 0}}, {{"year": 2023, "value": 0}}, {{"year": 2024, "value": 0}}],
    "dom_history": [],
    "clearance_history": [],
    "turnover_history": []
  }},
  "physical_config": {{
    "land_size_median_sqm": 0,
    "floor_size_median_sqm": 0,
    "typical_bedrooms": 0,
    "typical_bathrooms": 0,
    "typical_car_spaces": 0
  }},
  "demographics": {{
    "population_trend": "",
    "median_age": 0.0,
    "household_types": {{}},
    "income_distribution": {{}}
  }},
  "infrastructure": {{
    "current_transport": [],
    "future_transport": [],
    "current_infrastructure": [],
    "planned_infrastructure": [],
    "major_events_relevance": "",
    "shopping_access": "",
    "schools_summary": "",
    "crime_stats": {{}}
  }},
  "growth_projections": {{
    "projected_growth_pct": {{
      "1": 0.0,
      "2": 0.0,
      "3": 0.0,
      "5": 0.0,
      "10": 0.0,
      "25": 0.0
    }},
    "confidence_intervals": {{
      "1": [0.0, 0.0],
      "2": [0.0, 0.0],
      "3": [0.0, 0.0],
      "5": [0.0, 0.0],
      "10": [0.0, 0.0],
      "25": [0.0, 0.0]
    }},
    "risk_analysis": "",
    "key_drivers": [],
    "growth_score": 0.0,
    "risk_score": 0.0,
    "composite_score": 0.0
  }}
}}

CRITICAL INSTRUCTIONS:
1. Fill ALL fields with real, researched data where available
2. Use 0, "", [], or {{}} ONLY when data truly cannot be found
3. For price_history: Include actual historical data points from 2020-2024
4. For growth_projections: Calculate realistic percentage growth for 1, 2, 3, 5, 10, and 25 year horizons
5. For confidence_intervals: Provide [low, high] ranges for each projection
6. For growth_score: Calculate 0-100 score based on projected growth potential
7. For risk_score: Calculate 0-100 score based on market volatility and risks
8. For composite_score: Growth score adjusted for risk (higher growth + lower risk = higher score)
9. Include all available transport, infrastructure, and amenity information
10. Research major events relevance (Brisbane 2032 Olympics, infrastructure projects, etc.)

Focus on {dwelling_type} properties. Be thorough and accurate.

Begin your response with the opening brace {{
"""

    print(f"Researching {candidate.name}, {candidate.state} in detail...")

    # Check cache first
    cache = get_cache()
    cache_key_parts = dict(
        suburb_name=candidate.name.lower(),
        state=candidate.state.lower(),
        dwelling_type=dwelling_type,
    )

    cached = cache.get("research", **cache_key_parts)
    if cached is not None:
        logger.info("Cache HIT for %s", candidate.name)
        print(f"   (Using cached research data)")
        try:
            metrics = _parse_metrics_from_json(cached)
            print(f"✓ Research complete for {candidate.name} (cached)")
            return metrics
        except Exception as e:
            logger.warning("Cached data failed to parse for %s, will re-fetch: %s", candidate.name, e)
            print(f"   Cached data invalid, re-fetching from API...")
            cache.invalidate("research", **cache_key_parts)

    logger.info("Cache MISS for %s", candidate.name)

    try:
        # Make the API call with extended timeout for deep research
        response = client.call_deep_research(
            prompt=prompt,
            timeout=settings.RESEARCH_TIMEOUT
        )

        # Parse JSON response
        try:
            data = client.parse_json_response(response)
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse JSON for {candidate.name}: {e}")
            # Fall back to basic data from candidate
            return _create_fallback_metrics(candidate)

        # Cache the raw parsed data
        cache.put("research", data, **cache_key_parts)

        # Parse into SuburbMetrics
        metrics = _parse_metrics_from_json(data)

        print(f"✓ Research complete for {candidate.name}")
        return metrics

    except API_ACCOUNT_ERRORS as e:
        # Re-raise account-level errors immediately - no point continuing
        print(f"❌ Account-level API error for {candidate.name}")
        raise
    except Exception as e:
        print(f"⚠️  Error researching {candidate.name}: {e}")
        print(f"   Using fallback metrics for this suburb...")
        # Return fallback metrics rather than failing
        return _create_fallback_metrics(candidate)


def _coerce_to_str_list(items: list) -> list[str]:
    """Coerce a list of mixed items (strings, dicts, etc.) to a list of strings.

    The API sometimes returns structured dicts where we expect plain strings,
    e.g. {"mode": "bus", "name": "Route 520", "description": "..."} instead of
    "Route 520 (bus) - ...". This preserves the information as a readable string.
    """
    result = []
    for item in items:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            # Build a readable string from the dict values
            parts = [str(v) for v in item.values() if v]
            result.append(" — ".join(parts))
        else:
            result.append(str(item))
    return result


def _parse_metrics_from_json(data: dict) -> SuburbMetrics:
    """Parse JSON data into SuburbMetrics object.

    Each section is parsed independently so one bad section doesn't
    lose all the other researched data.
    """

    # Parse identification (required — let it raise if broken)
    identification = SuburbIdentification(**data.get("identification", {}))

    # Parse market metrics (required — let it raise if broken)
    market_current = MarketMetricsCurrent(**data.get("market_current", {}))

    # Parse market history
    try:
        market_history_data = data.get("market_history", {})
        market_history = MarketMetricsHistory(
            price_history=[TimePoint(**tp) for tp in market_history_data.get("price_history", [])],
            dom_history=[TimePoint(**tp) for tp in market_history_data.get("dom_history", [])],
            clearance_history=[TimePoint(**tp) for tp in market_history_data.get("clearance_history", [])],
            turnover_history=[TimePoint(**tp) for tp in market_history_data.get("turnover_history", [])]
        )
    except Exception as e:
        logger.warning("Failed to parse market_history: %s", e)
        market_history = MarketMetricsHistory()

    # Parse physical config
    try:
        physical_config = PhysicalConfig(**data.get("physical_config", {}))
    except Exception as e:
        logger.warning("Failed to parse physical_config: %s", e)
        physical_config = PhysicalConfig()

    # Parse demographics
    try:
        demographics = Demographics(**data.get("demographics", {}))
    except Exception as e:
        logger.warning("Failed to parse demographics: %s", e)
        demographics = Demographics()

    # Parse infrastructure — coerce list fields that the API may return as dicts
    try:
        infra_data = data.get("infrastructure", {})
        for list_field in ("current_transport", "future_transport",
                           "current_infrastructure", "planned_infrastructure"):
            if list_field in infra_data and isinstance(infra_data[list_field], list):
                infra_data[list_field] = _coerce_to_str_list(infra_data[list_field])
        infrastructure = Infrastructure(**infra_data)
    except Exception as e:
        logger.warning("Failed to parse infrastructure: %s", e)
        infrastructure = Infrastructure()

    # Parse growth projections
    try:
        growth_data = data.get("growth_projections", {})

        # Convert string keys to int for growth projections
        projected_growth = {}
        for k, v in growth_data.get("projected_growth_pct", {}).items():
            projected_growth[int(k)] = float(v)

        confidence_intervals = {}
        for k, v in growth_data.get("confidence_intervals", {}).items():
            if isinstance(v, list) and len(v) == 2:
                confidence_intervals[int(k)] = (float(v[0]), float(v[1]))

        growth_projections = GrowthProjections(
            projected_growth_pct=projected_growth,
            confidence_intervals=confidence_intervals,
            risk_analysis=growth_data.get("risk_analysis", ""),
            key_drivers=growth_data.get("key_drivers", []),
            growth_score=float(growth_data.get("growth_score", 0)),
            risk_score=float(growth_data.get("risk_score", 0)),
            composite_score=float(growth_data.get("composite_score", 0))
        )
    except Exception as e:
        logger.warning("Failed to parse growth_projections: %s", e)
        growth_projections = GrowthProjections()

    # Create and return SuburbMetrics
    return SuburbMetrics(
        identification=identification,
        market_current=market_current,
        market_history=market_history,
        physical_config=physical_config,
        demographics=demographics,
        infrastructure=infrastructure,
        growth_projections=growth_projections
    )


def _create_fallback_metrics(candidate: SuburbCandidate) -> SuburbMetrics:
    """
    Create basic SuburbMetrics from SuburbCandidate when detailed research fails.

    Args:
        candidate: SuburbCandidate object

    Returns:
        Minimal SuburbMetrics object
    """
    return SuburbMetrics(
        identification=SuburbIdentification(
            name=candidate.name,
            state=candidate.state,
            lga=candidate.lga,
            region=candidate.region or ""
        ),
        market_current=MarketMetricsCurrent(
            median_price=candidate.median_price
        ),
        growth_projections=GrowthProjections(
            key_drivers=candidate.growth_signals,
            projected_growth_pct={1: 3.0, 2: 6.0, 3: 9.5, 5: 16.0, 10: 35.0, 25: 95.0},
            growth_score=50.0,  # Default medium score
            risk_score=50.0,
            composite_score=50.0
        ),
        infrastructure=Infrastructure(
            major_events_relevance=candidate.major_events_relevance
        )
    )


def batch_research_suburbs(
    candidates: list[SuburbCandidate],
    dwelling_type: str,
    max_price: float,
    max_suburbs: Optional[int] = None,
    provider: str = "perplexity",
    progress_callback: Optional[Callable[[str], None]] = None
) -> list[SuburbMetrics]:
    """
    Research multiple suburbs in batch.

    Args:
        candidates: List of SuburbCandidate objects
        dwelling_type: Type of dwelling
        max_price: Maximum median price
        max_suburbs: Maximum number to research (None = all)
        provider: Research provider ("perplexity" or "anthropic")
        progress_callback: Optional callback for progress updates

    Returns:
        List of SuburbMetrics objects
    """
    if max_suburbs:
        candidates = candidates[:max_suburbs]

    results = []
    total = len(candidates)

    print(f"\nResearching {total} suburbs in detail...")
    print("=" * 60)

    for i, candidate in enumerate(candidates, 1):
        msg = f"Researching suburb {i}/{total}: {candidate.name}, {candidate.state}..."
        print(f"\n[{i}/{total}] {candidate.name}, {candidate.state}")
        if progress_callback:
            progress_callback(msg)
        try:
            metrics = research_suburb(candidate, dwelling_type, max_price, provider)
            results.append(metrics)
            if progress_callback:
                progress_callback(f"Research complete for {candidate.name}")
        except API_ACCOUNT_ERRORS as e:
            # Stop immediately on account-level errors (auth, credits, rate limit)
            print(f"\n{'='*60}")
            print(f"❌ STOPPING: Account-level API error encountered")
            print(f"   Successfully researched: {len(results)}/{total} suburbs")
            print(f"   Failed at: {candidate.name}")
            print(f"{'='*60}")
            if progress_callback:
                progress_callback(f"FATAL: API account error at {candidate.name}")
            raise
        except API_TRANSIENT_ERRORS as e:
            # Continue on per-request API errors (timeouts, server errors)
            print(f"⚠️  API error for {candidate.name}: {e}")
            print(f"   Skipping and continuing with remaining suburbs...")
            results.append(_create_fallback_metrics(candidate))
            if progress_callback:
                progress_callback(f"API error for {candidate.name}, using fallback data")
        except Exception as e:
            print(f"⚠️  Failed to research {candidate.name}: {e}")
            print(f"   Using fallback metrics and continuing...")
            results.append(_create_fallback_metrics(candidate))
            if progress_callback:
                progress_callback(f"Error researching {candidate.name}, using fallback data")

    print(f"\n✓ Batch research complete: {len(results)}/{total} suburbs")
    return results


def parallel_research_suburbs(
    candidates: list[SuburbCandidate],
    dwelling_type: str,
    max_price: float,
    max_suburbs: Optional[int] = None,
    provider: str = "perplexity",
    progress_callback: Optional[Callable[[str], None]] = None,
    max_workers: Optional[int] = None,
) -> list[SuburbMetrics]:
    """
    Research multiple suburbs in parallel using a thread pool.

    Preserves partial results: if some suburbs fail, the successfully
    researched ones are still returned. Account-level errors (auth,
    rate limit) stop all workers but return partial results.

    Args:
        candidates: List of SuburbCandidate objects
        dwelling_type: Type of dwelling
        max_price: Maximum median price
        max_suburbs: Maximum number to research (None = all)
        provider: Research provider ("perplexity" or "anthropic")
        progress_callback: Optional callback for progress updates
        max_workers: Max concurrent research workers (default from settings)

    Returns:
        List of SuburbMetrics in the same order as candidates (where available)
    """
    if max_suburbs:
        candidates = candidates[:max_suburbs]

    if not candidates:
        return []

    if max_workers is None:
        max_workers = settings.RESEARCH_MAX_WORKERS

    total = len(candidates)

    # Use AccountErrorSignal from suburb_discovery
    from research.suburb_discovery import AccountErrorSignal
    account_error = AccountErrorSignal()

    # Results dict keyed by index to preserve ordering
    results_by_index: dict[int, SuburbMetrics] = {}
    results_lock = threading.Lock()
    completed_count = 0
    completed_lock = threading.Lock()

    print(f"\nResearching {total} suburbs in parallel ({max_workers} workers)...")
    print("=" * 60)

    if progress_callback:
        progress_callback(
            f"Starting parallel research: {total} suburbs, "
            f"{max_workers} workers"
        )

    def _research_one(index: int, candidate: SuburbCandidate) -> tuple[int, SuburbMetrics]:
        """Research a single suburb in a thread pool worker."""
        nonlocal completed_count

        if account_error.is_set:
            return (index, _create_fallback_metrics(candidate))

        try:
            metrics = research_suburb(candidate, dwelling_type, max_price, provider)
            return (index, metrics)
        except API_ACCOUNT_ERRORS as e:
            account_error.set(e)
            raise
        except API_TRANSIENT_ERRORS as e:
            logger.warning("Transient error for %s: %s", candidate.name, e)
            if progress_callback:
                progress_callback(f"API error for {candidate.name}, using fallback data")
            return (index, _create_fallback_metrics(candidate))
        except Exception as e:
            logger.warning("Error researching %s: %s", candidate.name, e)
            if progress_callback:
                progress_callback(f"Error researching {candidate.name}, using fallback data")
            return (index, _create_fallback_metrics(candidate))
        finally:
            with completed_lock:
                completed_count += 1
                cnt = completed_count
            if progress_callback:
                progress_callback(f"Research progress: {cnt}/{total} complete")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_info = {}
        for i, candidate in enumerate(candidates):
            future = executor.submit(_research_one, i, candidate)
            future_to_info[future] = (i, candidate)

        for future in as_completed(future_to_info):
            i, candidate = future_to_info[future]
            try:
                idx, metrics = future.result()
                with results_lock:
                    results_by_index[idx] = metrics
            except API_ACCOUNT_ERRORS:
                # Cancel remaining futures
                for f in future_to_info:
                    f.cancel()
                # Preserve partial results collected so far
                break
            except Exception as e:
                logger.warning("Unexpected error for %s: %s", candidate.name, e)
                with results_lock:
                    results_by_index[i] = _create_fallback_metrics(candidate)

    # Build ordered results list
    ordered_results = []
    for i in range(total):
        if i in results_by_index:
            ordered_results.append(results_by_index[i])

    print(f"\n{'='*60}")
    print(f"Parallel research complete: {len(ordered_results)}/{total} suburbs")
    if account_error.is_set:
        print(f"Stopped early due to account error: {type(account_error.error).__name__}")
        print(f"Partial results preserved: {len(ordered_results)} suburbs")
    print(f"{'='*60}")

    if progress_callback:
        progress_callback(
            f"Research complete: {len(ordered_results)}/{total} suburbs"
        )

    return ordered_results
