"""
AoE2 Definitive Edition civilization ID → name mapping.

IDs correspond to the internal civilization_id from the WorldsEdge API.
"""

CIVILIZATIONS = {
    0: "Random",
    1: "Britons",
    2: "Franks",
    3: "Goths",
    4: "Teutons",
    5: "Japanese",
    6: "Chinese",
    7: "Byzantines",
    8: "Persians",
    9: "Saracens",
    10: "Turks",
    11: "Vikings",
    12: "Mongols",
    13: "Celts",
    14: "Spanish",
    15: "Aztecs",
    16: "Mayans",
    17: "Huns",
    18: "Koreans",
    19: "Italians",
    20: "Indians",
    21: "Incas",
    22: "Magyars",
    23: "Slavs",
    24: "Portuguese",
    25: "Ethiopians",
    26: "Malians",
    27: "Berbers",
    28: "Khmer",
    29: "Malay",
    30: "Burmese",
    31: "Vietnamese",
    32: "Bulgarians",
    33: "Cumans",
    34: "Lithuanians",
    35: "Tatars",
    36: "Burgundians",
    37: "Sicilians",
    38: "Bohemians",
    39: "Poles",
    40: "Dravidians",
    41: "Bengalis",
    42: "Gurjaras",
    43: "Romans",
    44: "Armenians",
    45: "Georgians",
    46: "Achaemenids",
    47: "Athenians",
    48: "Spartans",
    49: "Jurchens",
    50: "Chimu",
    51: "Gaels",
    52: "Swahili",
    53: "Helvetii",
    54: "Xianbei",
}

MATCH_TYPES = {
    0: "Custom",
    6: "Ranked 1v1 RM",
    7: "Ranked 2v2 RM",
    8: "Ranked 3v3 RM",
    9: "Ranked 4v4 RM",
    13: "Ranked 1v1 EW",
    14: "Ranked 2v2 EW",
    18: "Quick Play 1v1",
    19: "Quick Play 2v2",
    20: "Quick Play 3v3",
    21: "Quick Play 4v4",
}


def get_civ_name(civ_id: int) -> str:
    return CIVILIZATIONS.get(civ_id, f"Unknown ({civ_id})")


def get_match_type(matchtype_id: int) -> str:
    return MATCH_TYPES.get(matchtype_id, f"Unknown ({matchtype_id})")
