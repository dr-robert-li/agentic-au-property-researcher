"""
Suburb discovery functionality using deep research.
"""
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Callable

from config import regions_data, settings
from models.inputs import UserInput
from research.perplexity_client import get_client
from research.cache import get_cache, ResearchCache
from research.validation import validate_discovery_response
from security.exceptions import ACCOUNT_ERRORS

logger = logging.getLogger(__name__)

# Account-level errors that should stop all parallel workers
API_ACCOUNT_ERRORS = ACCOUNT_ERRORS


class AccountErrorSignal:
    """Thread-safe flag for propagating account-level errors across workers."""

    def __init__(self):
        self._error: Optional[Exception] = None
        self._lock = threading.Lock()

    def set(self, error: Exception):
        with self._lock:
            if self._error is None:
                self._error = error

    @property
    def is_set(self) -> bool:
        return self._error is not None

    @property
    def error(self) -> Optional[Exception]:
        return self._error


class SuburbCandidate:
    """A candidate suburb discovered during initial search."""

    def __init__(self, data: dict):
        self.name = data.get("name", "")
        self.state = data.get("state", "")
        self.lga = data.get("lga", "")
        self.region = data.get("region", "")
        self.median_price = float(data.get("median_price", 0))
        self.growth_signals = data.get("growth_signals", [])
        self.major_events_relevance = data.get("major_events_relevance", "")
        self.data_quality = data.get("data_quality", "medium")

    def __repr__(self):
        return f"SuburbCandidate({self.name}, {self.state}, ${self.median_price:,.0f})"


def discover_suburbs(
    user_input: UserInput,
    max_results: Optional[int] = None
) -> list[SuburbCandidate]:
    """
    Discover suburbs matching the user criteria using deep research.

    Args:
        user_input: User input specifying search criteria
        max_results: Maximum number of results to return (None = unlimited)

    Returns:
        List of SuburbCandidate objects matching the criteria

    Raises:
        Exception: If API call fails or response cannot be parsed
    """
    client = get_client(user_input.provider)

    # Build region filter description
    region_desc = regions_data.build_region_filter_description(user_input.regions)

    # Build the discovery prompt
    prompt = f"""
You are a property research agent specializing in Australian real estate.

TASK: Identify suburbs {region_desc} where the current median price for {user_input.dwelling_type} properties is below ${user_input.max_median_price:,.0f} AUD.

IMPORTANT INSTRUCTIONS:
1. Use web_search to find current, accurate property price data
2. Focus on suburbs with growth potential and good investment characteristics
3. Include a variety of suburbs across different areas within the selected regions
4. You MUST find at least {user_input.num_suburbs * 3} qualifying suburbs (the user wants {user_input.num_suburbs} final suburbs, so we need extra candidates for ranking and filtering)
5. If you cannot find {user_input.num_suburbs * 3} suburbs, find as many as possible but aim for the target

OUTPUT FORMAT:
Return ONLY valid JSON array with NO additional text or commentary. Format:

[
  {{
    "name": "Suburb Name",
    "state": "STATE_CODE",
    "lga": "Local Government Area",
    "region": "Region Name",
    "median_price": 650000,
    "growth_signals": ["New metro station announced", "Major development underway", "Rising rental yields"],
    "major_events_relevance": "Description of relevance to major events like Brisbane 2032 Olympics, infrastructure projects, etc.",
    "data_quality": "high|medium|low"
  }}
]

CONSTRAINTS:
- Only include suburbs where median_price is BELOW ${user_input.max_median_price:,.0f}
- Provide accurate, current data from reliable sources
- Include state abbreviation (NSW, VIC, QLD, SA, WA, TAS, NT, ACT)
- Growth signals should be factual and specific

Begin your response with the opening square bracket [
"""

    provider_label = user_input.provider.title()
    print(f"Discovering suburbs {region_desc} under ${user_input.max_median_price:,.0f} for {user_input.dwelling_type}s...")
    print(f"   Provider: {provider_label}")

    # Check cache first
    cache = get_cache()
    price_bucket = ResearchCache.bucket_price(user_input.max_median_price)
    sorted_regions = ",".join(sorted(user_input.regions))
    # Bucket the target count so similar requests share cache (e.g., 3->10, 5->10, 10->10, 15->20)
    target_count = user_input.num_suburbs * 3
    count_bucket = max(10, ((target_count + 9) // 10) * 10)  # round up to nearest 10, min 10
    cache_key_parts = dict(
        price_bucket=str(price_bucket),
        dwelling_type=user_input.dwelling_type,
        regions=sorted_regions,
        min_count=str(count_bucket),
    )

    cached = cache.get("discovery", **cache_key_parts)
    if cached is not None:
        logger.info("Cache HIT for discovery")
        print("   (Using cached discovery results)")
        # Validate cached data before using it
        validation_result = validate_discovery_response(cached)
        if not validation_result.is_valid:
            logger.warning("Cached discovery data failed validation, re-fetching")
            print("   Cached data invalid, re-fetching from API...")
            cache.invalidate("discovery", **cache_key_parts)
            cached = None
        else:
            if validation_result.warnings:
                for warning in validation_result.warnings:
                    logger.warning("Cached discovery data warning: %s", warning)
            candidates = [SuburbCandidate(item) for item in validation_result.data if isinstance(item, dict)]
            pre_filter_count = len(candidates)
            candidates = [
                c for c in candidates
                if c.median_price > 0 and c.median_price <= user_input.max_median_price
            ]
            if pre_filter_count != len(candidates):
                print(f"   Price filter: {pre_filter_count} -> {len(candidates)} candidates ({pre_filter_count - len(candidates)} removed)")
            if max_results:
                candidates = candidates[:max_results]
            print(f"✓ Found {len(candidates)} qualifying suburbs (cached)")
            return candidates

    logger.info("Cache MISS for discovery")

    # Make the API call
    try:
        response = client.call_deep_research(
            prompt=prompt,
            timeout=settings.DISCOVERY_TIMEOUT
        )

        # Parse JSON response
        try:
            data = client.parse_json_response(response)
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse JSON response: {e}")
            print(f"Raw response: {response[:500]}")
            raise Exception("Failed to parse suburb discovery response as JSON")

        # Normalize data to list format for validation
        if isinstance(data, list):
            raw_list = [item for item in data if isinstance(item, dict)]
        elif isinstance(data, dict) and "suburbs" in data:
            raw_list = data["suburbs"]
        else:
            raise Exception(f"Unexpected response format: {type(data)}")

        # Validate the response before caching
        validation_result = validate_discovery_response(raw_list)
        if not validation_result.is_valid:
            raise Exception("Discovery validation failed: " + "; ".join(validation_result.warnings))

        # Log warnings for items that failed validation
        if validation_result.warnings:
            for warning in validation_result.warnings:
                logger.warning("Discovery validation warning: %s", warning)

        # Cache the validated data
        cache.put("discovery", validation_result.data, **cache_key_parts)

        # Convert to SuburbCandidate objects
        candidates = [SuburbCandidate(item) for item in validation_result.data]

        # Filter by price (in case the API included some above threshold)
        pre_filter_count = len(candidates)
        candidates = [
            c for c in candidates
            if c.median_price > 0 and c.median_price <= user_input.max_median_price
        ]
        if pre_filter_count != len(candidates):
            print(f"   Price filter: {pre_filter_count} -> {len(candidates)} candidates ({pre_filter_count - len(candidates)} removed)")

        # Limit results if requested
        if max_results:
            candidates = candidates[:max_results]

        print(f"✓ Found {len(candidates)} qualifying suburbs")

        return candidates

    except Exception as e:
        print(f"Error during suburb discovery: {e}")
        raise


def _discover_for_single_region(
    user_input: UserInput,
    region: str,
    max_results: Optional[int],
    account_error: AccountErrorSignal,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> list[SuburbCandidate]:
    """
    Discover suburbs for a single region. Designed to run in a thread.

    Checks account_error before starting — returns [] if another thread
    hit an auth/rate-limit error.
    """
    if account_error.is_set:
        return []

    region_input = user_input.model_copy(update={"regions": [region]})

    try:
        candidates = discover_suburbs(region_input, max_results=max_results)
        if progress_callback:
            progress_callback(f"Discovered {len(candidates)} suburbs in {region}")
        return candidates
    except API_ACCOUNT_ERRORS as e:
        account_error.set(e)
        raise
    except Exception as e:
        logger.warning("Discovery failed for region %s: %s", region, e)
        if progress_callback:
            progress_callback(f"Discovery failed for {region}: {e}")
        return []


def parallel_discover_suburbs(
    user_input: UserInput,
    max_results: Optional[int] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> list[SuburbCandidate]:
    """
    Discover suburbs across multiple regions in parallel.

    For single-region requests, delegates directly to discover_suburbs()
    (no threading overhead). For multi-region or "All Australia", splits
    into per-region parallel calls.

    Returns deduplicated, price-filtered candidates merged from all regions.
    """
    regions = user_input.regions

    # Determine which regions to query
    if "All Australia" in regions:
        query_regions = list(regions_data.AUSTRALIAN_STATES)
    else:
        query_regions = list(regions)

    # Single region — no parallelism needed
    if len(query_regions) == 1:
        return discover_suburbs(user_input, max_results=max_results)

    # Multi-region — parallel discovery
    account_error = AccountErrorSignal()
    all_candidates: list[SuburbCandidate] = []
    max_workers = min(len(query_regions), settings.DISCOVERY_MAX_WORKERS)
    total_regions = len(query_regions)
    completed_count = 0

    if progress_callback:
        progress_callback(
            f"Discovering suburbs across {total_regions} regions "
            f"({max_workers} parallel workers)..."
        )

    print(f"\nParallel discovery: {total_regions} regions, {max_workers} workers")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_region = {}
        for region in query_regions:
            future = executor.submit(
                _discover_for_single_region,
                user_input, region, max_results,
                account_error, progress_callback,
            )
            future_to_region[future] = region

        for future in as_completed(future_to_region):
            region = future_to_region[future]
            completed_count += 1

            try:
                candidates = future.result()
                all_candidates.extend(candidates)
                print(f"   Region {completed_count}/{total_regions}: {region} ({len(candidates)} suburbs)")
            except API_ACCOUNT_ERRORS:
                # Account error — cancel remaining futures
                for f in future_to_region:
                    f.cancel()
                raise account_error.error
            except Exception as e:
                logger.warning("Region %s failed: %s", region, e)
                print(f"   Region {completed_count}/{total_regions}: {region} (FAILED: {e})")

    # Deduplicate by (name, state)
    seen: set[tuple[str, str]] = set()
    deduped: list[SuburbCandidate] = []
    for c in all_candidates:
        key = (c.name.lower().strip(), c.state.upper().strip())
        if key not in seen:
            seen.add(key)
            deduped.append(c)

    # Price filter
    pre_filter = len(deduped)
    deduped = [
        c for c in deduped
        if c.median_price > 0 and c.median_price <= user_input.max_median_price
    ]
    if pre_filter != len(deduped):
        print(f"   Price filter: {pre_filter} -> {len(deduped)} candidates ({pre_filter - len(deduped)} removed)")

    if max_results and len(deduped) > max_results:
        deduped = deduped[:max_results]

    print(f"✓ Parallel discovery complete: {len(deduped)} unique suburbs from {total_regions} regions")

    if progress_callback:
        progress_callback(
            f"Discovery complete: {len(deduped)} unique suburbs "
            f"from {total_regions} regions"
        )

    return deduped


def get_discovery_summary(candidates: list[SuburbCandidate]) -> str:
    """
    Get a text summary of discovered suburbs.

    Args:
        candidates: List of SuburbCandidate objects

    Returns:
        Formatted summary string
    """
    if not candidates:
        return "No suburbs found matching criteria"

    summary_lines = [
        f"Discovered {len(candidates)} suburbs:",
        ""
    ]

    # Group by state
    by_state = {}
    for candidate in candidates:
        if candidate.state not in by_state:
            by_state[candidate.state] = []
        by_state[candidate.state].append(candidate)

    for state in sorted(by_state.keys()):
        suburbs = by_state[state]
        summary_lines.append(f"{state}: {len(suburbs)} suburbs")
        for suburb in sorted(suburbs, key=lambda s: s.median_price)[:5]:  # Top 5 by price
            summary_lines.append(
                f"  - {suburb.name} (${suburb.median_price:,.0f})"
            )
        if len(suburbs) > 5:
            summary_lines.append(f"  ... and {len(suburbs) - 5} more")
        summary_lines.append("")

    return "\n".join(summary_lines)
