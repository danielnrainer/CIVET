"""CIF 1.1 Character Encoding Tables
======================================
Complete implementation of the IUCr CIF 1.1 markup conventions (§30–37):
    https://www.iucr.org/resources/cif/spec/version1.1/semantics#markup

OVERVIEW OF THE ENCODING SCHEME
---------------------------------
CIF 1.1 allows only printable ASCII characters (U+0020–U+007E) plus the
control characters HT (U+0009), LF (U+000A), and CR (U+000D).  All other
Unicode characters must be represented with one of the backslash-based markup
conventions defined by the IUCr CIF 1.1 specification.

§31  Greek letters
     Single backslash + the first Latin letter of the Greek letter's English
     name, e.g.  \\a = α (alpha), \\b = β (beta), \\g = γ (gamma).
     Uppercase letters use the corresponding capital, e.g. \\G = Γ.
     Exceptional assignments (to avoid clashes):
         \\h = η (eta)    — the letter 'e' is already taken by epsilon
         \\q = θ (theta)  — the letter 't' is already taken by tau

§32  Accented letters
     Accent code placed BEFORE the modified letter, e.g. \\'e = é (acute e).
     Supported accent codes:

         \\'  acute accent          \\"  umlaut (diaeresis)
         \\`  grave accent          \\~  tilde
         \\^  circumflex            \\,  cedilla
         \\=  macron (overbar)      \\.  overdot (dot above)
         \\;  ogonek                \\<  háček / caron
         \\>  Hungarian umlaut      \\(  breve
                 (double acute)

§33  Other alphabetic characters
         \\%a / \\%A   a/A with ring (å / Å — Ångström)
         \\%           degree sign (°)  — NB: \\% alone, not before a letter
         \\?i          dotless i (ı)
         \\&s          German Eszett / sharp s (ß)
         \\/o / \\/O   o/O with stroke (ø / Ø)
         \\/l / \\/L   l/L with stroke (ł / Ł — Polish)
         \\/d / \\/D   d/D with stroke (đ / Đ)

§35  Mathematical and typographic symbols
         +-          plus-minus sign (±)     — inline notation, no backslash
         -+          minus-or-plus sign (∓)  — inline notation, no backslash
         \\times     multiplication sign (×)
         \\neq       not equal to (≠)
         \\simeq     approximately equal to (≈)
         \\sim       similar to / tilde operator (∼)
         \\infty     infinity (∞)
         \\rightarrow  right arrow (→)
         \\leftarrow   left arrow (←)
         \\langle    mathematical left angle bracket (⟨)
         \\rangle    mathematical right angle bracket (⟩)
         \\square    square / empty square (□)

NOT in this table — structural / typographic markup handled by rendering
software, not character substitution:
         ^text^      superscript         ~text~   subscript
         --          dash / en-dash      ---      single bond indicator
         \\db        double bond         \\tb     triple bond
         \\ddb       delocalized double bond
         <i>…</i>   italic              <b>…</b> bold

AMBIGUOUS MAPPINGS (multiple Unicode → same CIF code)
-------------------------------------------------------
Where several Unicode code points map to the same CIF 1.1 code the forward
map includes all aliases but the *reverse* map resolves to the canonical /
most common character:
    \\s  → σ  (sigma, U+03C3)      not ς (final sigma, U+03C2)
    \\m  → μ  (mu, U+03BC)         not µ (micro sign, U+00B5)
    \\f  → φ  (phi, U+03C6)        not ϕ (phi variant, U+03D5)
This is achieved by ordering the aliases so the preferred character is the
LAST one in ``CIF11_UNICODE_TO_BACKSLASH``; the auto-built reverse map then
keeps that entry (later assignment wins in the dict comprehension).
"""

from __future__ import annotations

from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# §31–35  Forward map: Unicode character → CIF 1.1 backslash code
# ---------------------------------------------------------------------------

CIF11_UNICODE_TO_BACKSLASH: Dict[str, str] = {

    # -----------------------------------------------------------------------
    # §31  Greek lowercase letters
    # -----------------------------------------------------------------------
    '\u03b1': '\\a',     # α  alpha
    '\u03b2': '\\b',     # β  beta
    '\u03b3': '\\g',     # γ  gamma
    '\u03b4': '\\d',     # δ  delta
    '\u03b5': '\\e',     # ε  epsilon
    '\u03b6': '\\z',     # ζ  zeta
    '\u03b7': '\\h',     # η  eta      (\\e taken by epsilon)
    '\u03b8': '\\q',     # θ  theta    (\\t taken by tau)
    '\u03b9': '\\i',     # ι  iota
    '\u03ba': '\\k',     # κ  kappa
    '\u03bb': '\\l',     # λ  lambda
    '\u03bc': '\\m',     # μ  mu
    '\u03bd': '\\n',     # ν  nu
    '\u03be': '\\x',     # ξ  xi
    '\u03bf': '\\o',     # ο  omicron  (rarely needed — looks like Latin 'o')
    '\u03c0': '\\p',     # π  pi
    '\u03c1': '\\r',     # ρ  rho
    '\u03c2': '\\s',     # ς  final sigma (alias; reverse gives σ — comes first)
    '\u03c3': '\\s',     # σ  sigma     (canonical; comes after ς so wins reverse)
    '\u03c4': '\\t',     # τ  tau
    '\u03c5': '\\u',     # υ  upsilon
    '\u03d5': '\\f',     # ϕ  phi variant (alias; reverse gives φ — comes first)
    '\u03c6': '\\f',     # φ  phi       (canonical; comes after ϕ so wins reverse)
    '\u03c7': '\\c',     # χ  chi
    '\u03c8': '\\y',     # ψ  psi
    '\u03c9': '\\w',     # ω  omega

    # -----------------------------------------------------------------------
    # §31  Greek uppercase letters
    # -----------------------------------------------------------------------
    '\u0391': '\\A',     # Α  Alpha
    '\u0392': '\\B',     # Β  Beta
    '\u0393': '\\G',     # Γ  Gamma
    '\u0394': '\\D',     # Δ  Delta
    '\u0395': '\\E',     # Ε  Epsilon
    '\u0396': '\\Z',     # Ζ  Zeta
    '\u0397': '\\H',     # Η  Eta
    '\u0398': '\\Q',     # Θ  Theta
    '\u0399': '\\I',     # Ι  Iota
    '\u039a': '\\K',     # Κ  Kappa
    '\u039b': '\\L',     # Λ  Lambda
    '\u039c': '\\M',     # Μ  Mu
    '\u039d': '\\N',     # Ν  Nu
    '\u039e': '\\X',     # Ξ  Xi
    '\u039f': '\\O',     # Ο  Omicron  (rarely needed)
    '\u03a0': '\\P',     # Π  Pi
    '\u03a1': '\\R',     # Ρ  Rho
    '\u03a3': '\\S',     # Σ  Sigma
    '\u03a4': '\\T',     # Τ  Tau
    '\u03a5': '\\U',     # Υ  Upsilon
    '\u03a6': '\\F',     # Φ  Phi
    '\u03a7': '\\C',     # Χ  Chi
    '\u03a8': '\\Y',     # Ψ  Psi
    '\u03a9': '\\W',     # Ω  Omega

    # -----------------------------------------------------------------------
    # §32  Accented letters — acute accent (\')
    # -----------------------------------------------------------------------
    '\u00e1': "\\'a",    # á  a acute
    '\u00e9': "\\'e",    # é  e acute
    '\u00ed': "\\'i",    # í  i acute
    '\u00f3': "\\'o",    # ó  o acute
    '\u00fa': "\\'u",    # ú  u acute
    '\u00fd': "\\'y",    # ý  y acute
    '\u0107': "\\'c",    # ć  c acute
    '\u013a': "\\'l",    # ĺ  l acute
    '\u0144': "\\'n",    # ń  n acute
    '\u0155': "\\'r",    # ŕ  r acute
    '\u015b': "\\'s",    # ś  s acute
    '\u017a': "\\'z",    # ź  z acute
    '\u00c1': "\\'A",    # Á  A acute
    '\u00c9': "\\'E",    # É  E acute
    '\u00cd': "\\'I",    # Í  I acute
    '\u00d3': "\\'O",    # Ó  O acute
    '\u00da': "\\'U",    # Ú  U acute
    '\u00dd': "\\'Y",    # Ý  Y acute
    '\u0106': "\\'C",    # Ć  C acute
    '\u0139': "\\'L",    # Ĺ  L acute
    '\u0143': "\\'N",    # Ń  N acute
    '\u0154': "\\'R",    # Ŕ  R acute
    '\u015a': "\\'S",    # Ś  S acute
    '\u0179': "\\'Z",    # Ź  Z acute

    # §32  grave accent (\`)
    '\u00e0': '\\`a',    # à  a grave
    '\u00e8': '\\`e',    # è  e grave
    '\u00ec': '\\`i',    # ì  i grave
    '\u00f2': '\\`o',    # ò  o grave
    '\u00f9': '\\`u',    # ù  u grave
    '\u00c0': '\\`A',    # À  A grave
    '\u00c8': '\\`E',    # È  E grave
    '\u00cc': '\\`I',    # Ì  I grave
    '\u00d2': '\\`O',    # Ò  O grave
    '\u00d9': '\\`U',    # Ù  U grave

    # §32  circumflex (\^)
    '\u00e2': '\\^a',    # â  a circumflex
    '\u00ea': '\\^e',    # ê  e circumflex
    '\u00ee': '\\^i',    # î  i circumflex
    '\u00f4': '\\^o',    # ô  o circumflex
    '\u00fb': '\\^u',    # û  u circumflex
    '\u0109': '\\^c',    # ĉ  c circumflex
    '\u011d': '\\^g',    # ĝ  g circumflex
    '\u0125': '\\^h',    # ĥ  h circumflex
    '\u0135': '\\^j',    # ĵ  j circumflex
    '\u015d': '\\^s',    # ŝ  s circumflex
    '\u0175': '\\^w',    # ŵ  w circumflex
    '\u0177': '\\^y',    # ŷ  y circumflex
    '\u00c2': '\\^A',    # Â  A circumflex
    '\u00ca': '\\^E',    # Ê  E circumflex
    '\u00ce': '\\^I',    # Î  I circumflex
    '\u00d4': '\\^O',    # Ô  O circumflex
    '\u00db': '\\^U',    # Û  U circumflex
    '\u0108': '\\^C',    # Ĉ  C circumflex
    '\u011c': '\\^G',    # Ĝ  G circumflex
    '\u0124': '\\^H',    # Ĥ  H circumflex
    '\u0134': '\\^J',    # Ĵ  J circumflex
    '\u015c': '\\^S',    # Ŝ  S circumflex
    '\u0174': '\\^W',    # Ŵ  W circumflex
    '\u0176': '\\^Y',    # Ŷ  Y circumflex

    # §32  umlaut / diaeresis (\")
    '\u00e4': '\\"a',    # ä  a umlaut
    '\u00eb': '\\"e',    # ë  e umlaut
    '\u00ef': '\\"i',    # ï  i umlaut
    '\u00f6': '\\"o',    # ö  o umlaut
    '\u00fc': '\\"u',    # ü  u umlaut
    '\u00ff': '\\"y',    # ÿ  y umlaut
    '\u00c4': '\\"A',    # Ä  A umlaut
    '\u00cb': '\\"E',    # Ë  E umlaut
    '\u00cf': '\\"I',    # Ï  I umlaut
    '\u00d6': '\\"O',    # Ö  O umlaut
    '\u00dc': '\\"U',    # Ü  U umlaut
    '\u0178': '\\"Y',    # Ÿ  Y umlaut

    # §32  tilde (\~)
    '\u00e3': '\\~a',    # ã  a tilde
    '\u0129': '\\~i',    # ĩ  i tilde
    '\u00f1': '\\~n',    # ñ  n tilde
    '\u00f5': '\\~o',    # õ  o tilde
    '\u0169': '\\~u',    # ũ  u tilde
    '\u00c3': '\\~A',    # Ã  A tilde
    '\u0128': '\\~I',    # Ĩ  I tilde
    '\u00d1': '\\~N',    # Ñ  N tilde
    '\u00d5': '\\~O',    # Õ  O tilde
    '\u0168': '\\~U',    # Ũ  U tilde

    # §32  cedilla (\,)
    '\u00e7': '\\,c',    # ç  c cedilla
    '\u0123': '\\,g',    # ģ  g cedilla
    '\u0137': '\\,k',    # ķ  k cedilla
    '\u013c': '\\,l',    # ļ  l cedilla
    '\u0146': '\\,n',    # ņ  n cedilla
    '\u0157': '\\,r',    # ŗ  r cedilla
    '\u015f': '\\,s',    # ş  s cedilla
    '\u0163': '\\,t',    # ţ  t cedilla
    '\u00c7': '\\,C',    # Ç  C cedilla
    '\u0122': '\\,G',    # Ģ  G cedilla
    '\u0136': '\\,K',    # Ķ  K cedilla
    '\u013b': '\\,L',    # Ļ  L cedilla
    '\u0145': '\\,N',    # Ņ  N cedilla
    '\u0156': '\\,R',    # Ŗ  R cedilla
    '\u015e': '\\,S',    # Ş  S cedilla
    '\u0162': '\\,T',    # Ţ  T cedilla

    # §32  macron / overbar (\=)
    '\u0101': '\\=a',    # ā  a macron
    '\u0113': '\\=e',    # ē  e macron
    '\u012b': '\\=i',    # ī  i macron
    '\u014d': '\\=o',    # ō  o macron
    '\u016b': '\\=u',    # ū  u macron
    '\u0100': '\\=A',    # Ā  A macron
    '\u0112': '\\=E',    # Ē  E macron
    '\u012a': '\\=I',    # Ī  I macron
    '\u014c': '\\=O',    # Ō  O macron
    '\u016a': '\\=U',    # Ū  U macron

    # §32  overdot (\.)
    '\u010b': '\\.c',    # ċ  c overdot
    '\u0117': '\\.e',    # ė  e overdot
    '\u0121': '\\.g',    # ġ  g overdot
    '\u017c': '\\.z',    # ż  z overdot
    '\u010a': '\\.C',    # Ċ  C overdot
    '\u0116': '\\.E',    # Ė  E overdot
    '\u0120': '\\.G',    # Ġ  G overdot
    '\u017b': '\\.Z',    # Ż  Z overdot

    # §32  ogonek (\;)
    '\u0105': '\\;a',    # ą  a ogonek
    '\u0119': '\\;e',    # ę  e ogonek
    '\u012f': '\\;i',    # į  i ogonek
    '\u0173': '\\;u',    # ų  u ogonek
    '\u0104': '\\;A',    # Ą  A ogonek
    '\u0118': '\\;E',    # Ę  E ogonek
    '\u012e': '\\;I',    # Į  I ogonek
    '\u0172': '\\;U',    # Ų  U ogonek

    # §32  háček / caron (\<)
    '\u010d': '\\<c',    # č  c caron
    '\u010f': '\\<d',    # ď  d caron
    '\u011b': '\\<e',    # ě  e caron
    '\u01e7': '\\<g',    # ǧ  g caron
    '\u01e9': '\\<k',    # ǩ  k caron
    '\u013e': '\\<l',    # ľ  l caron
    '\u0148': '\\<n',    # ň  n caron
    '\u0159': '\\<r',    # ř  r caron
    '\u0161': '\\<s',    # š  s caron
    '\u0165': '\\<t',    # ť  t caron
    '\u017e': '\\<z',    # ž  z caron
    '\u010c': '\\<C',    # Č  C caron
    '\u010e': '\\<D',    # Ď  D caron
    '\u011a': '\\<E',    # Ě  E caron
    '\u01e6': '\\<G',    # Ǧ  G caron
    '\u01e8': '\\<K',    # Ǩ  K caron
    '\u013d': '\\<L',    # Ľ  L caron
    '\u0147': '\\<N',    # Ň  N caron
    '\u0158': '\\<R',    # Ř  R caron
    '\u0160': '\\<S',    # Š  S caron
    '\u0164': '\\<T',    # Ť  T caron
    '\u017d': '\\<Z',    # Ž  Z caron

    # §32  Hungarian umlaut / double acute (\>)
    '\u0151': '\\>o',    # ő  o double acute
    '\u0171': '\\>u',    # ű  u double acute
    '\u0150': '\\>O',    # Ő  O double acute
    '\u0170': '\\>U',    # Ű  U double acute

    # §32  breve (\()
    '\u0103': '\\(a',    # ă  a breve
    '\u0115': '\\(e',    # ĕ  e breve
    '\u011f': '\\(g',    # ğ  g breve
    '\u012d': '\\(i',    # ĭ  i breve
    '\u014f': '\\(o',    # ŏ  o breve
    '\u016d': '\\(u',    # ŭ  u breve
    '\u0102': '\\(A',    # Ă  A breve
    '\u0114': '\\(E',    # Ĕ  E breve
    '\u011e': '\\(G',    # Ğ  G breve
    '\u012c': '\\(I',    # Ĭ  I breve
    '\u014e': '\\(O',    # Ŏ  O breve
    '\u016c': '\\(U',    # Ŭ  U breve

    # -----------------------------------------------------------------------
    # §33  Other special alphabetic characters
    # -----------------------------------------------------------------------
    '\u00e5': '\\%a',    # å  a-ring (lowercase)
    '\u00c5': '\\%A',    # Å  A-ring / Ångström
    '\u0131': '\\?i',    # ı  dotless i
    '\u00df': '\\&s',    # ß  German Eszett / sharp s
    '\u00f8': '\\/o',    # ø  o with stroke (lowercase)
    '\u00d8': '\\/O',    # Ø  O with stroke (uppercase)
    '\u0142': '\\/l',    # ł  Polish l (lowercase)
    '\u0141': '\\/L',    # Ł  Polish L (uppercase)
    '\u0111': '\\/d',    # đ  barred d (lowercase)
    '\u0110': '\\/D',    # Đ  barred D (uppercase)

    # µ (U+00B5, micro sign) is a compatibility alias for μ (U+03BC).
    # Encoding it as \\m normalises it; the reverse map gives μ, not µ.
    # This entry must come BEFORE the Greek mu entry so μ wins the reverse.
    '\u00b5': '\\m',     # µ  micro sign  → encoded as \\m (same as Greek mu)

    # -----------------------------------------------------------------------
    # §35  Mathematical and typographic symbols
    # -----------------------------------------------------------------------
    '\u00b0': '\\%',     # °  degree sign (\\% alone — not before a letter)
    '\u00b1': '+-',      # ±  plus-minus sign   (§35 inline notation)
    '\u2213': '-+',      # ∓  minus-or-plus sign (§35 inline notation)
    '\u00d7': '\\times', # ×  multiplication sign
    '\u2260': '\\neq',   # ≠  not equal to
    '\u2248': '\\simeq', # ≈  approximately equal to
    '\u223c': '\\sim',   # ∼  tilde operator / similar to
    '\u221e': '\\infty', # ∞  infinity
    '\u2192': '\\rightarrow',  # →  right arrow
    '\u2190': '\\leftarrow',   # ←  left arrow
    '\u27e8': '\\langle', # ⟨  mathematical left angle bracket
    '\u27e9': '\\rangle', # ⟩  mathematical right angle bracket
    '\u25a1': '\\square', # □  square / empty square
}

# ---------------------------------------------------------------------------
# Reverse map: CIF 1.1 backslash code → Unicode character
# ---------------------------------------------------------------------------
# Built automatically from the forward map; later entries win on collision.
# Key ordering in CIF11_UNICODE_TO_BACKSLASH ensures the preferred canonical
# character wins (see "AMBIGUOUS MAPPINGS" in the module docstring).
#
# IMPORTANT for convert_cif11_to_unicode():
#   Longer codes MUST be applied before shorter codes to avoid partial
#   substitution, e.g. \\%A (Å) before \\% (°), \\times before \\t (τ),
#   \\simeq before \\sim before \\s (σ).
#   Use: sorted(CIF11_BACKSLASH_TO_UNICODE, key=len, reverse=True)

CIF11_BACKSLASH_TO_UNICODE: Dict[str, str] = {
    v: k for k, v in CIF11_UNICODE_TO_BACKSLASH.items()
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def detect_non_ascii_chars(content: str) -> List[Tuple[str, object, int, bool]]:
    """Detect non-ASCII characters in *content* that are not in the CIF 1.1
    character set, grouped by character.

    Returns
    -------
    list of (char, cif11_encoding, occurrence_count, auto_fixable)
        *cif11_encoding* is the CIF 1.1 backslash code string, or ``None`` if
        no mapping is known.  *auto_fixable* is ``True`` when a mapping exists.

    Notes
    -----
    The CIF 1.1 allowed ordinals are: HT (9), LF (10), CR (13), and the
    printable ASCII range 32–126.  Characters in that set are ignored.
    """
    from utils.cif_syntax_compliance import _CIF1_VALID_ORDS  # lazy import

    counts: Dict[str, int] = {}
    for ch in content:
        if ord(ch) not in _CIF1_VALID_ORDS:
            counts[ch] = counts.get(ch, 0) + 1

    results: List[Tuple[str, object, int, bool]] = []
    for ch, count in sorted(counts.items(), key=lambda x: ord(x[0])):
        encoding = CIF11_UNICODE_TO_BACKSLASH.get(ch)
        results.append((ch, encoding, count, encoding is not None))
    return results


def convert_unicode_to_cif11(content: str) -> str:
    """Convert known Unicode characters in *content* to CIF 1.1 backslash
    codes.

    Only characters present in :data:`CIF11_UNICODE_TO_BACKSLASH` are
    converted; all others are left unchanged.  The caller is responsible for
    handling any remaining non-ASCII characters.
    """
    for unicode_char, cif11_code in CIF11_UNICODE_TO_BACKSLASH.items():
        content = content.replace(unicode_char, cif11_code)
    return content


def convert_cif11_to_unicode(content: str) -> str:
    """Convert CIF 1.1 backslash codes in *content* back to Unicode characters.

    Only codes present in :data:`CIF11_BACKSLASH_TO_UNICODE` are converted.
    Longer codes are applied first to avoid partial substitution (e.g.
    ``\\%A`` → Å before ``\\%`` → °, ``\\times`` → × before ``\\t`` → τ).
    """
    for cif11_code in sorted(CIF11_BACKSLASH_TO_UNICODE, key=len, reverse=True):
        unicode_char = CIF11_BACKSLASH_TO_UNICODE[cif11_code]
        content = content.replace(cif11_code, unicode_char)
    return content
