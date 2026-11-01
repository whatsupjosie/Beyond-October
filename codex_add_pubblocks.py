from pathlib import Path
p = Path(r"C:\Users\hardc\Downloads\big zip\codex_construction_pubcast_20260614\modules\voxel_set_contract.py")
text = p.read_text(encoding="utf-8")
if "PUB_BLOCK_INCHES" not in text:
    marker = "AI_AUTHORITY_MODES = {"
    constants = '''PUB_BLOCK_INCHES = 10
PUB_BLOCK_METERS = 0.254
PUB_BLOCK_SUBDIVISIONS = {"full": 1, "half": 2, "quarter": 4}
DEFAULT_UNIT_PROFILE = "pub_block_10in"
DEFAULT_SUBDIVISION = 1

'''
    text = text.replace(marker, constants + marker)
if "def pub_block_measurement" not in text:
    insert_after = '''def dimensions_for_blocks(blocks: Iterable[Mapping[str, Any]]) -> Dict[str, int]:
    coords = [(_as_int(b.get("x"), "block.x"), _as_int(b.get("y"), "block.y"), _as_int(b.get("z"), "block.z")) for b in blocks]
    if not coords:
        return {"x": 0, "y": 0, "z": 0}
    xs, ys, zs = zip(*coords)
    return {
        "x": max(xs) - min(xs) + 1,
        "y": max(ys) - min(ys) + 1,
        "z": max(zs) - min(zs) + 1,
    }
'''
    helpers = '''\n\ndef pub_block_measurement(subdivision: int = DEFAULT_SUBDIVISION) -> Dict[str, Any]:
    """Return canonical PubBlock measurement metadata.

    One full PubBlock is 10 inches. Subdivision 2 means coordinates are stored
    in half-block units (5 inches). Subdivision 4 means quarter-block units
    (2.5 inches) for fine work without floating point coordinates.
    """

    subdivision = _as_int(subdivision, "subdivision")
    if subdivision not in set(PUB_BLOCK_SUBDIVISIONS.values()):
        raise VoxelSetValidationError("subdivision must be 1, 2, or 4")
    unit_inches = PUB_BLOCK_INCHES / subdivision
    return {
        "unit_profile": DEFAULT_UNIT_PROFILE,
        "base_block_inches": PUB_BLOCK_INCHES,
        "base_block_meters": PUB_BLOCK_METERS,
        "subdivision": subdivision,
        "unit_inches": unit_inches,
        "unit_meters": PUB_BLOCK_METERS / subdivision,
        "coordinate_rule": "integer coordinates in subdivision units; 4 quarter units equal one full PubBlock",
    }


def inches_to_pub_units(inches: float, subdivision: int = DEFAULT_SUBDIVISION, rounding: str = "round") -> int:
    measurement = pub_block_measurement(subdivision)
    value = float(inches) / measurement["unit_inches"]
    if rounding == "floor":
        import math
        return int(math.floor(value))
    if rounding == "ceil":
        import math
        return int(math.ceil(value))
    return int(round(value))


def pub_units_to_inches(units: int, subdivision: int = DEFAULT_SUBDIVISION) -> float:
    measurement = pub_block_measurement(subdivision)
    return _as_int(units, "units") * measurement["unit_inches"]
'''
    text = text.replace(insert_after, insert_after + helpers)
if 'measurement = payload.get("measurement")' not in text:
    text = text.replace('''    origin = _dict_xyz(payload, "origin")
    blocks_raw = payload.get("blocks")
''', '''    origin = _dict_xyz(payload, "origin")
    measurement_raw = payload.get("measurement") or {}
    if not isinstance(measurement_raw, Mapping):
        raise VoxelSetValidationError("measurement must be an object")
    subdivision = _as_int(measurement_raw.get("subdivision", payload.get("subdivision", DEFAULT_SUBDIVISION)), "measurement.subdivision")
    measurement = pub_block_measurement(subdivision)
    unit_profile = str(measurement_raw.get("unit_profile") or payload.get("unit_profile") or DEFAULT_UNIT_PROFILE).strip()
    if unit_profile != DEFAULT_UNIT_PROFILE:
        raise VoxelSetValidationError(f"unit_profile must be {DEFAULT_UNIT_PROFILE!r}")
    blocks_raw = payload.get("blocks")
''')
    text = text.replace('''        "origin": origin,
        "blocks": blocks,
''', '''        "origin": origin,
        "measurement": measurement,
        "unit_profile": DEFAULT_UNIT_PROFILE,
        "blocks": blocks,
''')
if '"measurement": pub_block_measurement()' not in text:
    text = text.replace('''        "units": "voxel",
        "dimensions": {"x": 7, "y": 3, "z": 5},
''', '''        "units": "voxel",
        "measurement": pub_block_measurement(),
        "dimensions": {"x": 7, "y": 3, "z": 5},
''')
if '"PUB_BLOCK_INCHES"' not in text.split('__all__ = [',1)[-1]:
    text = text.replace('''__all__ = [
    "AI_AUTHORITY_MODES",
''', '''__all__ = [
    "AI_AUTHORITY_MODES",
    "DEFAULT_UNIT_PROFILE",
    "PUB_BLOCK_INCHES",
    "PUB_BLOCK_METERS",
    "PUB_BLOCK_SUBDIVISIONS",
''')
    text = text.replace('''    "normalize_voxel_set",
    "save_voxel_set",
''', '''    "inches_to_pub_units",
    "normalize_voxel_set",
    "pub_block_measurement",
    "pub_units_to_inches",
    "save_voxel_set",
''')
p.write_text(text, encoding="utf-8")
