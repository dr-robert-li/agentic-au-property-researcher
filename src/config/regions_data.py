"""
Australian regions and states data for filtering.
"""

# Australian states and territories
AUSTRALIAN_STATES = [
    "New South Wales",
    "Victoria",
    "Queensland",
    "South Australia",
    "Western Australia",
    "Tasmania",
    "Northern Territory",
    "Australian Capital Territory"
]

# Detailed regions mapped to their coverage areas
REGIONS = {
    "All Australia": {
        "description": "All states and territories across Australia",
        "states": ["NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"]
    },

    # States
    "New South Wales": {
        "description": "New South Wales state",
        "states": ["NSW"],
        "major_areas": ["Sydney", "Newcastle", "Central Coast", "Wollongong", "Parramatta"]
    },
    "Victoria": {
        "description": "Victoria state",
        "states": ["VIC"],
        "major_areas": ["Melbourne", "Geelong", "Ballarat", "Bendigo"]
    },
    "Queensland": {
        "description": "Queensland state",
        "states": ["QLD"],
        "major_areas": ["Brisbane", "Gold Coast", "Sunshine Coast", "Townsville", "Cairns"]
    },
    "South Australia": {
        "description": "South Australia state",
        "states": ["SA"],
        "major_areas": ["Adelaide", "Mount Gambier", "Whyalla"]
    },
    "Western Australia": {
        "description": "Western Australia state",
        "states": ["WA"],
        "major_areas": ["Perth", "Fremantle", "Mandurah", "Bunbury"]
    },
    "Tasmania": {
        "description": "Tasmania state",
        "states": ["TAS"],
        "major_areas": ["Hobart", "Launceston", "Devonport"]
    },
    "Northern Territory": {
        "description": "Northern Territory",
        "states": ["NT"],
        "major_areas": ["Darwin", "Alice Springs", "Palmerston"]
    },
    "Australian Capital Territory": {
        "description": "Australian Capital Territory",
        "states": ["ACT"],
        "major_areas": ["Canberra"]
    },

    # Major metro regions
    "Greater Sydney": {
        "description": "Greater Sydney metropolitan area",
        "states": ["NSW"],
        "major_areas": [
            "Sydney CBD", "Parramatta", "Penrith", "Liverpool", "Blacktown",
            "Ryde", "Hornsby", "Sutherland", "Canterbury-Bankstown", "Northern Beaches"
        ]
    },
    "Greater Melbourne": {
        "description": "Greater Melbourne metropolitan area",
        "states": ["VIC"],
        "major_areas": [
            "Melbourne CBD", "Casey", "Monash", "Whitehorse", "Knox",
            "Boroondara", "Glen Eira", "Port Phillip", "Stonnington", "Bayside"
        ]
    },
    "Greater Brisbane": {
        "description": "Greater Brisbane metropolitan area",
        "states": ["QLD"],
        "major_areas": [
            "Brisbane CBD", "Logan", "Ipswich", "Moreton Bay", "Redland",
            "Brisbane City", "Redcliffe", "Capalaba"
        ]
    },
    "Greater Perth": {
        "description": "Greater Perth metropolitan area",
        "states": ["WA"],
        "major_areas": [
            "Perth CBD", "Joondalup", "Stirling", "Wanneroo", "Cockburn",
            "Melville", "Canning", "Bayswater"
        ]
    },
    "Greater Adelaide": {
        "description": "Greater Adelaide metropolitan area",
        "states": ["SA"],
        "major_areas": [
            "Adelaide CBD", "Onkaparinga", "Salisbury", "Playford", "Tea Tree Gully",
            "Port Adelaide Enfield", "Marion", "Charles Sturt"
        ]
    },

    # Regional areas
    "South East Queensland": {
        "description": "South East Queensland region including Brisbane, Gold Coast, and Sunshine Coast",
        "states": ["QLD"],
        "major_areas": [
            "Brisbane", "Gold Coast", "Sunshine Coast", "Logan", "Ipswich",
            "Moreton Bay", "Redland", "Scenic Rim", "Lockyer Valley", "Somerset"
        ]
    },
    "Northern NSW": {
        "description": "Northern coastal and inland NSW including Newcastle and Central Coast",
        "states": ["NSW"],
        "major_areas": [
            "Newcastle", "Central Coast", "Lake Macquarie", "Port Stephens",
            "Maitland", "Cessnock", "Mid-Coast", "Port Macquarie"
        ]
    },
    "Western Sydney": {
        "description": "Western Sydney region",
        "states": ["NSW"],
        "major_areas": [
            "Parramatta", "Penrith", "Liverpool", "Blacktown", "Fairfield",
            "Cumberland", "The Hills", "Hawkesbury", "Blue Mountains"
        ]
    },
    "Eastern Suburbs Sydney": {
        "description": "Eastern Sydney region",
        "states": ["NSW"],
        "major_areas": [
            "Woollahra", "Waverley", "Randwick", "Bayside", "Sydney CBD"
        ]
    },
    "Northern Beaches Sydney": {
        "description": "Northern Beaches region of Sydney",
        "states": ["NSW"],
        "major_areas": [
            "Northern Beaches", "Manly", "Dee Why", "Mona Vale", "Pittwater"
        ]
    },
    "Illawarra": {
        "description": "Illawarra region south of Sydney",
        "states": ["NSW"],
        "major_areas": [
            "Wollongong", "Shellharbour", "Kiama", "Shoalhaven"
        ]
    },
    "Geelong Region": {
        "description": "Geelong and surrounding areas",
        "states": ["VIC"],
        "major_areas": [
            "Geelong", "Surf Coast", "Golden Plains", "Colac Otway"
        ]
    },
    "Gold Coast": {
        "description": "Gold Coast region",
        "states": ["QLD"],
        "major_areas": [
            "Gold Coast", "Southport", "Surfers Paradise", "Robina", "Burleigh Heads"
        ]
    },
    "Sunshine Coast": {
        "description": "Sunshine Coast region",
        "states": ["QLD"],
        "major_areas": [
            "Sunshine Coast", "Caloundra", "Maroochydore", "Noosa", "Nambour"
        ]
    }
}

def get_region_names():
    """Get list of all available region names."""
    return list(REGIONS.keys())

def get_region_info(region_name):
    """Get detailed information about a specific region."""
    return REGIONS.get(region_name)

def get_states_for_regions(selected_regions):
    """
    Get list of states covered by selected regions.

    Args:
        selected_regions: List of region names

    Returns:
        List of state abbreviations (e.g., ['NSW', 'VIC'])
    """
    if not selected_regions or "All Australia" in selected_regions:
        return REGIONS["All Australia"]["states"]

    states = set()
    for region in selected_regions:
        if region in REGIONS:
            states.update(REGIONS[region]["states"])

    return list(states)

def build_region_filter_description(selected_regions):
    """
    Build a human-readable description of selected regions for Perplexity prompts.

    Args:
        selected_regions: List of region names

    Returns:
        String description for use in prompts
    """
    if not selected_regions or "All Australia" in selected_regions:
        return "across all of Australia"

    if len(selected_regions) == 1:
        region_info = REGIONS.get(selected_regions[0], {})
        return f"in the {selected_regions[0]} region ({region_info.get('description', '')})"

    return f"in the following regions: {', '.join(selected_regions)}"
