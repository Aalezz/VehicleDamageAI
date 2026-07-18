"""Repair cost estimation engine (rule-based).

Adjusts to the specific vehicle (brand tier + age) AND the country where the
repair happens. Returns full breakdown: parts / labor / paint + repair time.
"""

COST_TABLE: dict[tuple[str, str], tuple[int, int, str]] = {
    ("Bonnet", "minor"): (200, 600, "Surface repair + repaint"),
    ("Bonnet", "moderate"): (600, 1500, "Panel repair + repaint"),
    ("Bonnet", "severe"): (1500, 4000, "Full panel replacement"),
    ("Bumper", "minor"): (150, 400, "Touch-up + polish"),
    ("Bumper", "moderate"): (400, 900, "Partial replacement"),
    ("Bumper", "severe"): (900, 2500, "Full bumper replacement"),
    ("Dickey", "minor"): (200, 500, "Dent repair + repaint"),
    ("Dickey", "moderate"): (500, 1200, "Panel repair"),
    ("Dickey", "severe"): (1200, 3000, "Panel replacement"),
    ("Door", "minor"): (150, 500, "PDR + touch-up"),
    ("Door", "moderate"): (500, 1200, "Body filler + repaint"),
    ("Door", "severe"): (1200, 3500, "Door panel replacement"),
    ("Fender", "minor"): (150, 400, "PDR + polish"),
    ("Fender", "moderate"): (400, 1000, "Repair + repaint"),
    ("Fender", "severe"): (1000, 2800, "Fender replacement"),
    ("Light", "minor"): (100, 300, "Bulb/lens replacement"),
    ("Light", "moderate"): (300, 700, "Assembly repair"),
    ("Light", "severe"): (700, 2000, "Full assembly replacement"),
    ("Windshield", "minor"): (200, 400, "Chip repair"),
    ("Windshield", "moderate"): (400, 900, "Partial replacement"),
    ("Windshield", "severe"): (900, 2500, "Full windshield replacement"),
}

DEFAULT_COST = (200, 1000, "Inspection required")

# Country/region labor+parts market multipliers (US average = 1.0)
COUNTRY_MULTIPLIERS = {
    "US": 1.00, "SA": 0.80, "AE": 0.95, "QA": 1.00, "KW": 0.90,
    "TR": 0.55, "YE": 0.40, "UK": 1.15, "EU": 1.05,
}
COUNTRY_NAMES = {
    "US": "United States", "SA": "Saudi Arabia", "AE": "UAE", "QA": "Qatar",
    "KW": "Kuwait", "TR": "Turkey", "YE": "Yemen", "UK": "United Kingdom",
    "EU": "Europe",
}

REPAIR_DAYS = {"minor": "0.5 - 1 day", "moderate": "1 - 3 days", "severe": "3 - 7 days"}

# Brand tiers -> parts/labor price multiplier
ECONOMY = {
    "toyota", "honda", "nissan", "hyundai", "kia", "mazda", "suzuki", "mitsubishi",
    "chevrolet", "ford", "volkswagen", "skoda", "renault", "peugeot", "fiat", "seat",
    "dacia", "chery", "geely", "byd", "mg", "proton", "perodua", "opel", "citroen",
    "isuzu", "changan", "ram",
}
PREMIUM = {
    "audi", "bmw", "mercedes", "mercedes-benz", "lexus", "volvo", "infiniti", "acura",
    "genesis", "jaguar", "land rover", "range rover", "cadillac", "lincoln", "alfa romeo",
    "mini", "tesla", "gmc", "jeep", "dodge", "subaru",
}
LUXURY = {
    "porsche", "maserati", "bentley", "rolls-royce", "ferrari", "lamborghini",
    "aston martin", "mclaren", "bugatti", "lotus",
}


def vehicle_multiplier(make: str = "", year: int = 0, country: str = "US") -> float:
    """Combined cost multiplier for a specific vehicle in a specific market."""
    m = COUNTRY_MULTIPLIERS.get((country or "US").upper(), 1.0)
    make_l = (make or "").strip().lower()
    if make_l in PREMIUM:
        m *= 1.35
    elif make_l in LUXURY:
        m *= 1.75
    if year:
        if year >= 2023:
            m *= 1.15   # new parts, sensors in panels
        elif year <= 2012:
            m *= 0.85   # cheaper aftermarket parts available
    return round(m, 3)


def estimate_cost(damage_type: str, severity: str, multiplier: float = 1.0) -> dict:
    mn, mx, desc = COST_TABLE.get((damage_type, severity.lower()), DEFAULT_COST)
    mn_i, mx_i = int(round(mn * multiplier)), int(round(mx * multiplier))
    return {
        "cost_min": mn_i,
        "cost_max": mx_i,
        "cost_avg": (mn_i + mx_i) // 2,
        "repair": desc,
        "parts_cost": [int(mn_i * 0.45), int(mx_i * 0.45)],
        "labor_cost": [int(mn_i * 0.35), int(mx_i * 0.35)],
        "paint_cost": [int(mn_i * 0.20), int(mx_i * 0.20)],
        "repair_time": REPAIR_DAYS.get(severity.lower(), "1 - 3 days"),
    }
