"""
Registered CIF Prefixes Module for CIVET.

This module provides access to IUCr registered ("reserved") prefixes for CIF
data names. Registered prefixes allow organizations to define their own CIF
data names without conflicting with official dictionary definitions.

The authoritative list is the official IUCr registry, published as a CIF file
that is updated whenever a new prefix is registered:

    https://cif-dictionaries.iucr.org/cifdic/dic/reserved_prefixes.cif

CIVET fetches that file and caches the result in the user config directory so
that startup never depends on network access. Load order:

1. Cached copy of the official registry (user config dir), if present.
2. Bundled snapshot (<app_dir>/dictionaries/reserved_prefixes.cif) - a raw
   mirror of the same official file, as an offline fallback for a first run
   with no cache and no network.
3. Empty defaults.

Prefixes a user wants recognised but that aren't (yet) officially registered
are a separate, per-user concern - see DataNameValidator.add_allowed_prefix
and utils.user_config.get_user_allowed_prefixes_path. They are deliberately
not mixed into this module's data, so "IUCr registered" always means exactly
what IUCr's registry says.

Reference: https://www.iucr.org/resources/cif/registries/prefix-registry
"""

import time
from pathlib import Path
from typing import Optional, Set, Dict, Tuple

from .user_config import get_prefix_cache_path, get_bundled_resource_path

# Official IUCr reserved-prefixes registry (always up to date at this URL).
IUCR_RESERVED_PREFIXES_URL = "https://cif-dictionaries.iucr.org/cifdic/dic/reserved_prefixes.cif"

# Kept minimal and separate from urllib3/requests headers used elsewhere in
# CIVET; this endpoint does not require the Cloudflare-avoidance headers that
# www.iucr.org needs, but a normal browser UA avoids generic bot filtering.
_FETCH_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; CIVET CIF editor)',
    'Accept': 'text/plain, text/html, */*',
}

# The cache file mirrors the official file's own loop shape/tags verbatim
# (no CIVET-invented CIF data names) - only the fetch time is CIVET-specific,
# and that's stored as a plain comment line, not a data item.
_CACHE_FETCHED_AT_COMMENT = "# civet-fetched-at:"

# Module-level cache for loaded prefix data: (prefix -> description, source description).
# Bundled into one Optional so the two halves can't fall out of sync.
_prefix_cache: Optional[Tuple[Dict[str, str], str]] = None


def _quote_cif_value(value: str) -> str:
    """Quote a scalar CIF value, single-quoted unless the value itself
    contains a single quote (then fall back to double quotes)."""
    if "'" not in value:
        return f"'{value}'"
    return f'"{value}"'


def get_bundled_prefixes_path() -> Path:
    """
    Get the path to the bundled reserved_prefixes.cif snapshot.

    This is a raw mirror of the official IUCr registry file, used as an
    offline fallback when there is no cached copy of the official registry
    yet and no network access is available. Handles both development and
    PyInstaller bundled scenarios.

    Returns:
        Path to the bundled CIF file.
    """
    return get_bundled_resource_path('dictionaries') / 'reserved_prefixes.cif'


def _to_descriptions(official_prefixes: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    """Reduce fetched/cached {prefix: {description, submitter, date}} entries
    down to the {prefix: description} shape used throughout this module."""
    return {prefix: info.get("description", "") for prefix, info in official_prefixes.items()}


def _parse_official_prefixes_cif(content: str) -> Dict[str, Dict[str, str]]:
    """
    Parse the official reserved_prefixes.cif loop into a plain dict.

    The file is a single CIF loop with columns
    (...reserved_prefix.prefix/.description/.submitter/.date), one value per
    line, records separated by blank lines. Blank lines are legal CIF
    whitespace within a loop's data, so this parses value-by-value rather
    than assuming one record per contiguous block.

    Args:
        content: Raw text of reserved_prefixes.cif.

    Returns:
        Dict mapping prefix -> {"description", "submitter", "date"}.

    Raises:
        ValueError: If the expected loop/columns can't be found.
    """
    lines = content.splitlines()
    n = len(lines)
    i = 0

    in_loop = False
    while i < n:
        if lines[i].strip().lower() == 'loop_':
            in_loop = True
            i += 1
            break
        i += 1
    if not in_loop:
        raise ValueError("No loop_ found in reserved-prefixes CIF content")

    field_names = []
    while i < n:
        stripped = lines[i].strip()
        if stripped.startswith('_'):
            field_names.append(stripped)
            i += 1
        else:
            break
    if not field_names:
        raise ValueError("No field names found in reserved-prefixes CIF loop")

    attrs = [name.split('.')[-1].lower() for name in field_names]
    if 'prefix' not in attrs:
        raise ValueError("reserved-prefixes CIF loop has no '...reserved_prefix.prefix' column")
    prefix_col = attrs.index('prefix')
    desc_col = attrs.index('description') if 'description' in attrs else None
    submitter_col = attrs.index('submitter') if 'submitter' in attrs else None
    date_col = attrs.index('date') if 'date' in attrs else None

    values = []
    while i < n:
        stripped = lines[i].strip()
        i += 1
        if not stripped or stripped.startswith('#'):
            continue
        if stripped.startswith('_') or stripped.lower().startswith(('loop_', 'data_')):
            break
        if len(stripped) >= 2 and stripped[0] in ("'", '"') and stripped[-1] == stripped[0]:
            values.append(stripped[1:-1])
        else:
            values.append(stripped)

    n_cols = len(field_names)
    usable = len(values) - (len(values) % n_cols)

    prefixes: Dict[str, Dict[str, str]] = {}
    for row_start in range(0, usable, n_cols):
        row = values[row_start:row_start + n_cols]
        prefix = row[prefix_col].strip()
        if not prefix:
            continue
        prefixes[prefix] = {
            "description": row[desc_col].strip() if desc_col is not None else "",
            "submitter": row[submitter_col].strip() if submitter_col is not None else "",
            "date": row[date_col].strip() if date_col is not None else "",
        }

    if not prefixes:
        raise ValueError("Parsed zero prefixes from reserved-prefixes CIF content")
    return prefixes


def _serialize_cache_cif(prefixes: Dict[str, Dict[str, str]], fetched_at: float) -> str:
    """Render prefixes + fetch metadata as the CIF content written to the cache file.

    Uses the same data_/loop_/tag names as the official file itself - this is
    simply a local copy of that file's content, plus a comment recording when
    it was fetched. No CIVET-specific CIF data names are introduced.
    """
    when = time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(fetched_at))
    lines = [
        "# CIVET cache of the official IUCr reserved-prefixes registry.",
        f"# Source: {IUCR_RESERVED_PREFIXES_URL}",
        '# Automatically written by "Update from IUCr Registry" - do not hand-edit.',
        f"{_CACHE_FETCHED_AT_COMMENT} {fetched_at!r} ({when})",
        "data_reserved_prefixes",
        "",
        "loop_",
        "_publcif_reserved_prefix.prefix",
        "_publcif_reserved_prefix.description",
        "_publcif_reserved_prefix.submitter",
        "_publcif_reserved_prefix.date",
    ]
    for prefix in sorted(prefixes.keys(), key=str.lower):
        info = prefixes[prefix]
        lines.append(_quote_cif_value(prefix))
        lines.append(_quote_cif_value(info.get("description", "")))
        lines.append(_quote_cif_value(info.get("submitter", "")))
        lines.append(_quote_cif_value(info.get("date", "")))
    return "\n".join(lines) + "\n"


def _extract_fetched_at(content: str) -> Optional[float]:
    """Read the fetch timestamp back out of a cache file's comment header."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith(_CACHE_FETCHED_AT_COMMENT):
            token = stripped[len(_CACHE_FETCHED_AT_COMMENT):].strip().split(maxsplit=1)
            if token:
                try:
                    return float(token[0])
                except ValueError:
                    return None
    return None


def _parse_cache_cif(content: str) -> Tuple[Dict[str, Dict[str, str]], Optional[float]]:
    """Parse a registered_prefixes_cache.cif file back into (prefixes, fetched_at)."""
    prefixes = _parse_official_prefixes_cif(content)
    fetched_at = _extract_fetched_at(content)
    return prefixes, fetched_at


def fetch_official_prefixes(timeout: int = 15) -> Dict[str, Dict[str, str]]:
    """
    Download and parse the official IUCr reserved-prefixes registry.

    Args:
        timeout: Request timeout in seconds.

    Returns:
        Dict mapping prefix -> {"description", "submitter", "date"}.

    Raises:
        requests.RequestException: If the download fails.
        ValueError: If the response can't be parsed as the expected loop.
    """
    import requests
    response = requests.get(IUCR_RESERVED_PREFIXES_URL, timeout=timeout, headers=_FETCH_HEADERS)
    response.raise_for_status()
    return _parse_official_prefixes_cif(response.text)


def fetch_and_cache_official_prefixes(timeout: int = 15) -> str:
    """
    Fetch the official registry, write it to the local cache, and make it
    the active prefix data for this process.

    Intended for explicit "check for updates" actions (typically run off the
    GUI thread) and for a best-effort background refresh at startup.

    Args:
        timeout: Request timeout in seconds.

    Returns:
        Human-readable source description on success.

    Raises:
        requests.RequestException: If the download fails.
        ValueError: If the response can't be parsed.
    """
    official = fetch_official_prefixes(timeout=timeout)
    cache_path = get_prefix_cache_path()
    content = _serialize_cache_cif(official, time.time())
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return reload_prefix_data()


def is_prefix_cache_stale(max_age_days: float = 30) -> bool:
    """
    Check whether the cached copy of the official registry is missing or old.

    Args:
        max_age_days: Age in days after which the cache is considered stale.

    Returns:
        True if there is no cache yet, it can't be read, or it is older than
        max_age_days. False if a readable, sufficiently fresh cache exists.
    """
    cache_path = get_prefix_cache_path()
    if not cache_path.exists():
        return True
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            content = f.read()
        _, fetched_at = _parse_cache_cif(content)
        if fetched_at is None:
            return True
        age_days = (time.time() - fetched_at) / 86400
        return age_days > max_age_days
    except (ValueError, IOError, OSError):
        return True


def _load_prefix_data() -> Tuple[Dict[str, str], str]:
    """
    Load prefix data, preferring the cached official registry.

    This never performs network access - use fetch_and_cache_official_prefixes()
    to refresh the cache. Falls back to the bundled offline snapshot, then to
    empty defaults.

    Returns:
        Tuple of (prefix_data dict, source description string)
    """
    global _prefix_cache

    if _prefix_cache is not None:
        return _prefix_cache

    cache_path = get_prefix_cache_path()
    if cache_path.exists():
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                content = f.read()
            cached_prefixes, fetched_at = _parse_cache_cif(content)
            when = time.strftime('%Y-%m-%d', time.localtime(fetched_at)) if fetched_at else "unknown date"
            _prefix_cache = (
                _to_descriptions(cached_prefixes),
                f"{cache_path} (IUCr registry cached {when})",
            )
            return _prefix_cache
        except (ValueError, IOError) as e:
            print(f"Warning: Could not load cached prefix registry {cache_path}: {e}")
            print("Falling back to bundled prefixes.")

    # No usable cache yet (e.g. first run, never been online) - fall back to
    # the bundled offline snapshot, parsed the same way as a live fetch.
    bundled_path = get_bundled_prefixes_path()
    if bundled_path.exists():
        try:
            with open(bundled_path, 'r', encoding='utf-8') as f:
                content = f.read()
            _prefix_cache = (
                _to_descriptions(_parse_official_prefixes_cif(content)),
                f"{bundled_path} (offline fallback snapshot)",
            )
            return _prefix_cache
        except (ValueError, IOError) as e:
            print(f"Error: Could not load bundled prefix file {bundled_path}: {e}")

    # Ultimate fallback - return empty data
    _prefix_cache = ({}, "none (using empty defaults)")
    return _prefix_cache


def reload_prefix_data() -> str:
    """
    Force reload of prefix data from disk (cache or bundled fallback file).

    Does not touch the network - call fetch_and_cache_official_prefixes() to
    refresh the cache first if you want up-to-date data from IUCr.

    Returns:
        The source description from which data was loaded.
    """
    global _prefix_cache
    _prefix_cache = None
    _, source = _load_prefix_data()
    return source


def get_prefix_data_source() -> str:
    """
    Get a description of where prefix data was loaded from.

    Returns:
        Source description string.
    """
    _, source = _load_prefix_data()
    return source


def get_registered_prefixes() -> Set[str]:
    """
    Get the set of all registered prefix names.

    Returns:
        Set of registered prefix strings.
    """
    data, _ = _load_prefix_data()
    return set(data.keys())


def get_registered_prefixes_lower() -> Set[str]:
    """
    Get the set of registered prefixes in lowercase for case-insensitive matching.

    Returns:
        Set of lowercase registered prefix strings.
    """
    return {p.lower() for p in get_registered_prefixes()}


def get_prefix_info(prefix: str) -> Optional[str]:
    """
    Get the description/info for a registered prefix.

    Args:
        prefix: The prefix to look up (case-insensitive).

    Returns:
        The description string if the prefix is registered, None otherwise.

    Examples:
        >>> get_prefix_info('shelx')
        'SHELXL solution and refinement programs'
        >>> get_prefix_info('CCDC')
        'Cambridge Crystallographic Data Centre'
    """
    if not prefix:
        return None

    data, _ = _load_prefix_data()

    # Try exact match first
    if prefix in data:
        return data[prefix]

    # Try case-insensitive match
    prefix_lower = prefix.lower()
    for registered, description in data.items():
        if registered.lower() == prefix_lower:
            return description

    return None


def is_registered_prefix(field_name: str) -> bool:
    """
    Check if a CIF field name uses a registered prefix.

    Registered prefixes appear after the leading underscore and before
    the next underscore in a CIF data name. For example, in
    '_shelx_res_file', the prefix is 'shelx'.

    Args:
        field_name: The CIF field name to check (with or without leading underscore).

    Returns:
        True if the field uses a registered prefix, False otherwise.

    Examples:
        >>> is_registered_prefix('_shelx_res_file')
        True
        >>> is_registered_prefix('_ccdc_geom_bond_type')
        True
        >>> is_registered_prefix('_cell_length_a')
        False
    """
    prefix = get_prefix_from_field(field_name)
    if prefix is None:
        return False
    return prefix.lower() in get_registered_prefixes_lower()


def get_prefix_from_field(field_name: str) -> Optional[str]:
    """
    Extract the prefix portion from a CIF field name.

    The prefix is the first segment after the leading underscore,
    before the next underscore. This function extracts potential
    prefixes but does not validate if they are registered.

    Args:
        field_name: The CIF field name (with or without leading underscore).

    Returns:
        The prefix string if found, or None if the field has no prefix
        structure (e.g., single-segment names).

    Examples:
        >>> get_prefix_from_field('_shelx_res_file')
        'shelx'
        >>> get_prefix_from_field('_ccdc_geom_bond_type')
        'ccdc'
        >>> get_prefix_from_field('_cell_length_a')
        'cell'
        >>> get_prefix_from_field('_diffrn.ambient_temperature')
        'diffrn'
    """
    if not field_name:
        return None

    # Remove leading underscore if present
    name = field_name.lstrip('_')

    if not name:
        return None

    # Handle modern dot notation (category.attribute)
    if '.' in name:
        # For modern format, the category is before the dot
        category = name.split('.')[0]
        # Check if category itself has underscore (rare but possible)
        if '_' in category:
            return category.split('_')[0]
        return category

    # Handle legacy underscore notation
    if '_' in name:
        return name.split('_')[0]

    # Single segment name (no prefix structure)
    return None


def get_all_prefix_info() -> Dict[str, str]:
    """
    Get all registered prefix descriptions.

    Returns:
        Dict mapping prefix names to their descriptions.
    """
    data, _ = _load_prefix_data()
    return data.copy()


# Legacy compatibility - these are now functions that return fresh data
# For code that imports these as module-level constants

def _get_REGISTERED_CIF_PREFIXES() -> Set[str]:
    """Get registered prefixes set (legacy compatibility)."""
    return get_registered_prefixes()


def _get_REGISTERED_CIF_PREFIXES_LOWER() -> Set[str]:
    """Get lowercase registered prefixes set (legacy compatibility)."""
    return get_registered_prefixes_lower()


def _get_REGISTERED_CIF_PREFIXES_INFO() -> Dict[str, str]:
    """Get prefix descriptions dict (legacy compatibility)."""
    return get_all_prefix_info()


# For backward compatibility with code that imports these constants directly
# We load them once at module import time
# Note: These will be stale if reload_prefix_data() is called
REGISTERED_CIF_PREFIXES: Set[str] = set()
REGISTERED_CIF_PREFIXES_LOWER: Set[str] = set()
REGISTERED_CIF_PREFIXES_INFO: Dict[str, str] = {}


def _initialize_legacy_constants():
    """Initialize legacy module-level constants on first import."""
    global REGISTERED_CIF_PREFIXES, REGISTERED_CIF_PREFIXES_LOWER, REGISTERED_CIF_PREFIXES_INFO
    REGISTERED_CIF_PREFIXES = _get_REGISTERED_CIF_PREFIXES()
    REGISTERED_CIF_PREFIXES_LOWER = _get_REGISTERED_CIF_PREFIXES_LOWER()
    REGISTERED_CIF_PREFIXES_INFO = _get_REGISTERED_CIF_PREFIXES_INFO()


# Initialize on module load
_initialize_legacy_constants()
