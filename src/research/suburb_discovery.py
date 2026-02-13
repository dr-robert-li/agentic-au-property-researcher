"""
Suburb discovery functionality using deep research.
"""
import json
from typing import Optional

from config import regions_data
from models.inputs import UserInput
from research.perplexity_client import get_client


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
4. Aim to find at least {user_input.num_suburbs * 3} qualifying suburbs to allow for ranking

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

    # Make the API call
    try:
        response = client.call_deep_research(
            prompt=prompt,
            timeout=180  # 3 minutes for discovery
        )

        # Parse JSON response
        try:
            data = client.parse_json_response(response)
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse JSON response: {e}")
            print(f"Raw response: {response[:500]}")
            raise Exception("Failed to parse suburb discovery response as JSON")

        # Convert to SuburbCandidate objects
        if isinstance(data, list):
            candidates = [SuburbCandidate(item) for item in data if isinstance(item, dict)]
        elif isinstance(data, dict) and "suburbs" in data:
            candidates = [SuburbCandidate(item) for item in data["suburbs"]]
        else:
            raise Exception(f"Unexpected response format: {type(data)}")

        # Filter by price (in case the API included some above threshold)
        candidates = [
            c for c in candidates
            if c.median_price > 0 and c.median_price <= user_input.max_median_price
        ]

        # Limit results if requested
        if max_results:
            candidates = candidates[:max_results]

        print(f"✓ Found {len(candidates)} qualifying suburbs")

        return candidates

    except Exception as e:
        print(f"Error during suburb discovery: {e}")
        raise


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
