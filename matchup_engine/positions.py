"""Position normalization and formation-role compatibility rules."""

_POSITION_ALIASES = {
    "GOALKEEPER": "GK",
    "KEEPER": "GK",
    "DEFENDER": "DF",
    "DEFENCE": "DF",
    "MIDFIELDER": "MF",
    "MIDFIELD": "MF",
    "FORWARD": "FW",
    "ATTACKER": "FW",
    "STRIKER": "ST",
    "CENTRE-BACK": "CB",
    "CENTER-BACK": "CB",
    "CENTRE BACK": "CB",
    "CENTER BACK": "CB",
}

_ROLE_GROUPS = {
    "GK": "GK",
    "RB": "DF",
    "RCB": "DF",
    "CB": "DF",
    "LCB": "DF",
    "LB": "DF",
    "RWB": "DF",
    "LWB": "DF",
    "DM": "MF",
    "CDM": "MF",
    "RCM": "MF",
    "CM": "MF",
    "LCM": "MF",
    "AM": "MF",
    "CAM": "MF",
    "RW": "FW",
    "ST": "FW",
    "CF": "FW",
    "LW": "FW",
}


def normalize_position(position: str | None) -> str | None:
    """Normalize provider position text into the engine vocabulary."""
    if position is None:
        return None
    normalized = position.strip().upper()
    return _POSITION_ALIASES.get(normalized, normalized)


def position_compatibility(position: str | None, role: str) -> float:
    """Return a deterministic 0-1 compatibility score for a formation role."""
    position = normalize_position(position)
    role = normalize_position(role)
    if position is None or role is None:
        return 0.0
    if position == role:
        return 1.0
    if position == "CB" and role in {"RCB", "LCB"}:
        return 0.95
    if position in {"RB", "RWB"} and role == "RB":
        return 0.9
    if position in {"LB", "LWB"} and role == "LB":
        return 0.9
    if position in {"CM", "AM", "CAM", "CDM"} and role in {"DM", "RCM", "LCM"}:
        return 0.8
    if position in {"CF", "ST"} and role == "ST":
        return 0.9
    if position in {"RW", "LW"} and role in {"RW", "LW"}:
        return 0.85 if position != role else 1.0
    broad_position = position if position in {"GK", "DF", "MF", "FW"} else None
    position_group = _ROLE_GROUPS.get(position, broad_position)
    role_group = _ROLE_GROUPS.get(role)
    if position_group == role_group:
        return 0.65
    return 0.0
