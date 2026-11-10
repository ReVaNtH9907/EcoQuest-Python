"""
EcoQuest — Mission-Specific Verification Criteria & Rules.

Defines separate, domain-specific evaluation matrices for all 18 individual missions
and six broad environmental categories:
1. Cleanup (public areas, storm drains, waterways)
2. Tree Plantation (native saplings, micro-forests, community orchards)
3. Recycling (source separation, e-waste, cardboard/paper compacting)
4. Water Conservation (leak detection/repairs, rainwater harvesting, xeriscaping/drip)
5. Sustainable Transport (bicycle commutes, public transit, walking exploration)
6. Environmental Awareness (composting workshops, energy audits, plastic pledges)

Implements rigorous mission-specific verification:
- Checks evidence relevance against specific mission requirements, not just generic category words.
- Low-confidence or uncertain submissions are flagged for administrator Manual Review.
- Identifies anti-signals and inconsistencies (e.g. car dashboard for bike commute, potted plant for tree planting).
"""

from typing import Dict, Any, List, Optional

# Generic Category Baseline Rules
MISSION_VERIFICATION_RULES: Dict[str, Dict[str, Any]] = {
    "cleanup": {
        "category_name": "Cleanup",
        "primary_objects": [
            "litter", "plastic", "wrappers", "bottles", "trash bag", "garbage bag",
            "waste bin", "gloves", "debris", "leaves", "sidewalk", "park", "drain grate"
        ],
        "expected_before": "Visible litter, dispersed plastics, or clogged drain/trail debris.",
        "expected_after": "Cleared landscape with gathered, bagged, or disposed waste sacks.",
        "activity_signals": [
            "picked", "collected", "swept", "bagged", "cleared", "disposed",
            "segregated", "cleaned", "gathered", "removed"
        ],
        "inconsistency_indicators": [
            "no visible waste in before photo",
            "litter unmoved between before and after",
            "indoor unrelated setting",
            "no collection bags or tools"
        ],
        "min_description_words": 8,
    },
    "tree-plantation": {
        "category_name": "Tree Plantation",
        "primary_objects": [
            "sapling", "tree", "soil", "pit", "hole", "roots", "bamboo stake",
            "watering can", "water hose", "shovel", "trowel", "mulch", "earth", "garden"
        ],
        "expected_before": "Empty ground, marked planting pit, soil preparation site.",
        "expected_after": "Planted sapling standing erect in soil with stake and watered root zone.",
        "activity_signals": [
            "dug", "planted", "sapling", "soil", "watered", "staked",
            "mulched", "root", "neem", "bamboo", "earth"
        ],
        "inconsistency_indicators": [
            "potted artificial plant",
            "mature adult tree claiming new planting",
            "indoor living room floor",
            "no fresh earth or watering"
        ],
        "min_description_words": 8,
    },
    "recycling": {
        "category_name": "Recycling",
        "primary_objects": [
            "cardboard", "paper", "pet bottles", "plastic containers", "aluminum cans",
            "segregated bins", "dry waste", "e-waste", "scrap", "weighing scale"
        ],
        "expected_before": "Unsorted recyclables, stacked boxes, or mixed dry materials.",
        "expected_after": "Sorted streams (paper, plastic, metal) packaged or deposited at collection point.",
        "activity_signals": [
            "sorted", "segregated", "weighed", "cardboard", "bottles", "flattened",
            "recycled", "kabadiwala", "collection center", "dry waste"
        ],
        "inconsistency_indicators": [
            "unsorted wet organic garbage",
            "commercial factory stock photos",
            "non-recyclable toxic waste without facility confirmation"
        ],
        "min_description_words": 7,
    },
    "water-conservation": {
        "category_name": "Water Conservation",
        "primary_objects": [
            "tap", "faucet", "aerator", "pipe", "washer", "wrench", "bucket",
            "rainwater barrel", "filter", "drip irrigation", "water meter"
        ],
        "expected_before": "Leaking faucet, high-flow aerator, or unharvested gutter downspout.",
        "expected_after": "Installed flow aerator, sealed plumbing joint, or diverted rainwater storage.",
        "activity_signals": [
            "leak", "aerator", "fixed", "installed", "plumbing", "washer",
            "rainwater", "harvested", "conserved", "liters", "dripping"
        ],
        "inconsistency_indicators": [
            "open running tap in after photo",
            "unconnected loose pipe",
            "no hardware or plumbing shown"
        ],
        "min_description_words": 6,
    },
    "sustainable-transport": {
        "category_name": "Sustainable Transport",
        "primary_objects": [
            "bicycle", "helmet", "bike lane", "bus", "metro train", "transit pass",
            "pedestrian path", "walking shoes", "gps route", "odometer"
        ],
        "expected_before": "Start of route, transit station entrance, or bicycle before trip.",
        "expected_after": "Destination arrival, validated ticket/token, trip odometer or tracking summary.",
        "activity_signals": [
            "cycled", "commuted", "metro", "bus", "walked", "km", "transit",
            "pedal", "ticket", "station", "low-carbon"
        ],
        "inconsistency_indicators": [
            "fossil fuel car interior",
            "single static photo with no movement evidence",
            "expired transit pass from months ago"
        ],
        "min_description_words": 6,
    },
    "environmental-awareness": {
        "category_name": "Environmental Awareness",
        "primary_objects": [
            "poster", "chart", "presentation", "whiteboard", "audience", "classroom",
            "pamphlet", "eco-pledge", "community members", "laptop slides"
        ],
        "expected_before": "Preparation of educational material, blank bulletin board, or workshop setup.",
        "expected_after": "Conducted presentation with attendees, displayed poster in public venue, or signed pledge.",
        "activity_signals": [
            "presented", "workshop", "explained", "poster", "students", "session",
            "awareness", "pledge", "discussed", "demonstrated"
        ],
        "inconsistency_indicators": [
            "empty room with no presentation materials",
            "downloaded stock graphic with watermark",
            "unrelated personal selfie"
        ],
        "min_description_words": 8,
    },
}

# Individual Mission Criteria Registry
MISSION_SPECIFIC_CRITERIA: Dict[str, Dict[str, Any]] = {
    "clean-a-public-area": {
        "required_elements": ["litter", "plastic", "waste", "trash", "bags", "park", "trail", "cleanup"],
        "field_actions": ["picked", "collected", "bagged", "swept", "cleared", "disposed"],
        "anti_signals": ["indoor living room", "kitchen sink", "bedroom floor"],
        "proof_requirement": "Before photo showing litter on public ground; After photo showing clean site and gathered bags.",
    },
    "urban-storm-drain-debris-clearance": {
        "required_elements": ["drain", "grate", "storm", "silt", "leaves", "sediment", "clogged", "cleared", "runoff"],
        "field_actions": ["cleared", "unclogged", "removed", "scooped", "swept"],
        "anti_signals": ["park bench only", "indoor", "living room"],
        "proof_requirement": "Before photo of clogged drain grate; After photo of unobstructed drainage grates.",
    },
    "riverbank-waterway-plastic-sweep": {
        "required_elements": ["river", "stream", "waterway", "bank", "shore", "riparian", "floating", "plastics"],
        "field_actions": ["swept", "retrieved", "collected", "cleared", "bagged"],
        "anti_signals": ["indoor", "pavement only with no water proximity"],
        "proof_requirement": "Before photo of riverbank plastic; After photo of cleared shoreline with collected sacks.",
    },
    "plant-a-native-tree": {
        "required_elements": ["sapling", "tree", "pit", "hole", "dug", "soil", "roots", "watered", "stake"],
        "field_actions": ["dug", "planted", "positioned", "watered", "staked", "mulched"],
        "anti_signals": ["potted houseplant", "plastic pot", "desk plant", "indoor floor", "mature adult tree"],
        "proof_requirement": "Before photo of excavated soil pit; After photo of planted sapling standing erect in earth.",
    },
    "urban-micro-forest-sapling-care": {
        "required_elements": ["sapling", "mulch", "weeds", "basin", "soil", "protection", "hydration", "care"],
        "field_actions": ["weeded", "mulched", "aerated", "watered", "cleared"],
        "anti_signals": ["indoor room", "artificial flowers"],
        "proof_requirement": "Before photo of unmulched dry root zone; After photo of weeded and freshly mulched tree basin.",
    },
    "fruit-bearing-tree-community-planting": {
        "required_elements": ["fruit", "sapling", "orchard", "soil", "pit", "compost", "watered", "tree"],
        "field_actions": ["planted", "dug", "amended", "watered", "supported"],
        "anti_signals": ["cut fruit on plate", "grocery store", "indoor"],
        "proof_requirement": "Before photo of orchard planting spot; After photo of young fruit tree planted and watered.",
    },
    "collect-recyclable-waste": {
        "required_elements": ["recyclable", "sorted", "dry waste", "paper", "plastic", "bottles", "cans", "bins"],
        "field_actions": ["segregated", "sorted", "cleaned", "weighed", "separated"],
        "anti_signals": ["wet kitchen trash only", "rotting food"],
        "proof_requirement": "Before photo of mixed waste; After photo of categorized dry recyclables.",
    },
    "e-waste-safe-drop-off-collection": {
        "required_elements": ["e-waste", "electronic", "cables", "charger", "batteries", "drop-off", "center", "bin"],
        "field_actions": ["collected", "gathered", "dropped off", "handed over", "disposed"],
        "anti_signals": ["organic trash", "plastic bottles only"],
        "proof_requirement": "Before photo of segregated electronics; After photo at authorized collection point/bin.",
    },
    "cardboard-paper-bulk-compacting": {
        "required_elements": ["cardboard", "paper", "boxes", "flattened", "compacted", "tied", "bundle"],
        "field_actions": ["flattened", "compressed", "tied", "stacked", "bundled"],
        "anti_signals": ["wet paper", "plastic bags only"],
        "proof_requirement": "Before photo of loose packaging boxes; After photo of neat bound cardboard bundles.",
    },
    "home-plumbing-leak-audit": {
        "required_elements": ["leak", "tap", "faucet", "aerator", "washer", "plumbing", "pipe", "repaired"],
        "field_actions": ["inspected", "replaced", "tightened", "installed", "fixed"],
        "anti_signals": ["open running water", "garden hose only"],
        "proof_requirement": "Before photo of dripping joint/fixture; After photo of sealed fixture or replaced washer.",
    },
    "diy-rainwater-catchment-barrel-installation": {
        "required_elements": ["rainwater", "barrel", "catchment", "downspout", "gutter", "mesh", "filter", "cistern"],
        "field_actions": ["connected", "installed", "fitted", "diverted", "positioned"],
        "anti_signals": ["kitchen sink", "indoor bathroom"],
        "proof_requirement": "Before photo of open downspout; After photo of downspout connected to filtered rain barrel.",
    },
    "xeriscape-mulch-drip-irrigation-upgrade": {
        "required_elements": ["drip", "irrigation", "mulch", "tubing", "emitters", "drought", "xeriscape", "garden"],
        "field_actions": ["laid", "installed", "connected", "mulched", "converted"],
        "anti_signals": ["lawn sprinkler on", "flood irrigation"],
        "proof_requirement": "Before photo of bare high-water soil; After photo of drip lines and protective mulch layer.",
    },
    "zero-emissions-bicycle-commute-week": {
        "required_elements": ["bicycle", "bike", "cycling", "pedal", "commute", "helmet", "km", "route"],
        "field_actions": ["cycled", "commuted", "pedaled", "rode", "travelled"],
        "anti_signals": ["car interior", "dashboard", "steering wheel", "motorcycle"],
        "proof_requirement": "Before photo of bicycle prepared at origin; After photo of bicycle parked at destination.",
    },
    "public-transit-metro-bus-challenge": {
        "required_elements": ["metro", "bus", "transit", "pass", "ticket", "station", "stop", "train", "commute"],
        "field_actions": ["boarded", "travelled", "commuted", "swiped", "rode"],
        "anti_signals": ["personal car driving", "taxi only"],
        "proof_requirement": "Before photo at station entrance / transit card; After photo upon arrival at destination.",
    },
    "pedestrian-urban-exploration": {
        "required_elements": ["walk", "walking", "pedestrian", "foot", "steps", "sidewalk", "distance", "km"],
        "field_actions": ["walked", "explored", "navigated", "clocked", "tracked"],
        "anti_signals": ["driving car", "riding bus"],
        "proof_requirement": "Before photo at start of pedestrian route; After photo showing arrival and step count/distance.",
    },
    "host-community-composting-workshop": {
        "required_elements": ["compost", "workshop", "demonstration", "attendees", "organic", "greens", "browns", "neighbors"],
        "field_actions": ["presented", "demonstrated", "explained", "hosted", "guided"],
        "anti_signals": ["empty room", "landfill dumping"],
        "proof_requirement": "Before photo of setup materials; After photo of active session with community attendees.",
    },
    "campus-energy-waste-audit": {
        "required_elements": ["audit", "energy", "waste", "campus", "presentation", "slides", "students", "data"],
        "field_actions": ["presented", "calculated", "audited", "shared", "analyzed"],
        "anti_signals": ["personal selfie only", "no presentation materials"],
        "proof_requirement": "Before photo of audit data/slides; After photo of presentation delivered to student group.",
    },
    "neighborhood-plastic-pledge-drive": {
        "required_elements": ["pledge", "plastic", "signatures", "residents", "drive", "reusable", "neighbors"],
        "field_actions": ["collected", "engaged", "signed", "distributed", "campaigned"],
        "anti_signals": ["trash pile with no pledges", "empty table"],
        "proof_requirement": "Before photo of blank pledge forms; After photo of signed community pledge commitments.",
    },
}


def get_rules_for_category(category_name_or_slug: str) -> Dict[str, Any]:
    """Retrieve criteria specification by category slug or friendly name."""
    clean = (category_name_or_slug or "").strip().lower().replace(" ", "-")
    if clean in MISSION_VERIFICATION_RULES:
        return MISSION_VERIFICATION_RULES[clean]

    for key, spec in MISSION_VERIFICATION_RULES.items():
        if key in clean or clean in key:
            return spec

    return MISSION_VERIFICATION_RULES["cleanup"]


def evaluate_mission_match(
    category_slug: str,
    mission_title: str,
    description: str,
    has_video: bool = False,
    has_gps: bool = False,
    is_identical_images: bool = False,
    is_reused_evidence: bool = False,
    mission_slug: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluates mission matching using strict mission-specific rules and anti-signals.

    Outcomes:
    - High confidence (>= 80.0%) and high relevance -> Eligible for 'Verified'.
    - Uncertain, borderline, or missing specific mission criteria (40.0% - 79.9%) -> 'Requires Manual Review'.
    - Fraud, duplicate files, or unrelated evidence (< 40.0%) -> 'Rejected'.
    """
    cat_spec = get_rules_for_category(category_slug)
    desc_lower = (description or "").lower()
    words = desc_lower.split()

    # Identify mission specific criteria
    slug_key = (mission_slug or "").strip().lower()
    if not slug_key and mission_title:
        slug_key = mission_title.strip().lower().replace(" ", "-").replace("&", "").replace(",", "")

    mission_spec = None
    for key, spec in MISSION_SPECIFIC_CRITERIA.items():
        if key in slug_key or slug_key in key or key.replace("-", " ") in (mission_title or "").lower():
            mission_spec = spec
            break

    detected_objects = []
    matched_actions = []
    inconsistencies = []

    # 1. Evaluate Category Objects & Actions
    for obj in cat_spec["primary_objects"]:
        if obj in desc_lower:
            detected_objects.append(obj)

    for act in cat_spec["activity_signals"]:
        if act in desc_lower:
            matched_actions.append(act)

    # 2. Evaluate Specific Mission Requirements
    specific_matches = 0
    if mission_spec:
        for elem in mission_spec["required_elements"]:
            if elem in desc_lower and elem not in detected_objects:
                detected_objects.append(elem)
                specific_matches += 1

        for act in mission_spec["field_actions"]:
            if act in desc_lower and act not in matched_actions:
                matched_actions.append(act)
                specific_matches += 1

        # Check for Anti-Signals (indicators that the submitted proof does NOT match the mission)
        for anti in mission_spec.get("anti_signals", []):
            if anti in desc_lower:
                inconsistencies.append(f"Contradiction detected: '{anti}' conflicts with mission requirements.")

    # 3. Calculate Objective Confidence Score
    score = 50.0  # Base confidence

    # Word count and detail depth
    min_words = cat_spec["min_description_words"]
    if len(words) >= min_words + 5:
        score += 15.0
    elif len(words) >= min_words:
        score += 8.0
    else:
        score -= 15.0
        inconsistencies.append("Field notes lack sufficient detail describing completed actions.")

    # Relevance signals
    score += min(20.0, len(detected_objects) * 4.0)
    score += min(15.0, len(matched_actions) * 4.0)

    # Specific mission alignment bonus
    if mission_spec:
        if specific_matches >= 2:
            score += 10.0
        elif specific_matches == 0 and len(detected_objects) > 0:
            # Generic category words were mentioned, but none of the mission-specific actions!
            # Do NOT approve solely because generic category words were present.
            score -= 15.0
            inconsistencies.append(
                f"Evidence contains generic category keywords but lacks specific actions required for '{mission_title}'."
            )

    # Media bonus
    if has_video:
        score += 5.0
    if has_gps:
        score += 5.0

    # Severe fraud penalties
    if is_identical_images:
        score = 15.0
        inconsistencies.append("Before and after photographs are identical files; no fieldwork transformation occurred.")

    if is_reused_evidence:
        score = min(score, 30.0)
        inconsistencies.append("Image hash matches an existing submission in the platform audit ledger.")

    if len(detected_objects) == 0 and len(matched_actions) == 0:
        score = min(score, 25.0)
        inconsistencies.append(f"Submission shows no evidence matching {cat_spec['category_name']} or the selected mission.")

    # Penalize for any detected inconsistencies
    if inconsistencies and not (is_identical_images or is_reused_evidence):
        score -= (len(inconsistencies) * 12.0)

    # Clamp confidence score
    final_score = max(5.0, min(98.0, round(score, 1)))

    # Determine Relevance Level
    if final_score >= 78.0 and not inconsistencies:
        relevance = "high"
    elif final_score >= 45.0:
        relevance = "medium"
    elif final_score >= 30.0:
        relevance = "low"
    else:
        relevance = "unrelated"

    return {
        "category": cat_spec["category_name"],
        "confidence_score": final_score,
        "evidence_relevance": relevance,
        "detected_objects": detected_objects,
        "matched_actions": matched_actions,
        "inconsistencies": inconsistencies,
        "expected_before": cat_spec["expected_before"],
        "expected_after": cat_spec["expected_after"],
        "specific_mission_matched": specific_matches > 0 if mission_spec else True,
        "proof_requirement": mission_spec.get("proof_requirement", "") if mission_spec else "",
    }
