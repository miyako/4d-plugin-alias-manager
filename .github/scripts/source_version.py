"""Coordinated MARKETING_VERSION and CURRENT_PROJECT_VERSION source metadata.

The original committed Bump header explicitly coordinates both version keys and
plist versions, overriding its marketing-only/current-fallback implementation.
Prebuilt bundles and 4D counters are excluded.
"""

import argparse
from pathlib import Path
import plistlib
import re
from xml.parsers.expat import ExpatError


PRODUCT = "Alias Manager"
PROJECT = Path("Alias Manager.xcodeproj/project.pbxproj")
PLIST = Path("Info.plist")
LOCALIZED = Path("English.lproj/InfoPlist.strings")
SOURCE_PATHS = (PROJECT, PLIST, LOCALIZED)
VERSION = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
KEYS = ("MARKETING_VERSION", "CURRENT_PROJECT_VERSION")
SETTING_COUNT = 6
SETTING = re.compile(
    r'(("?(?:MARKETING_VERSION|CURRENT_PROJECT_VERSION)"?)[ \t]*=[ \t]*)([^;\n]*)(;)'
)
PROJECT_TOKEN = re.compile(
    r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|[^\s"=;{}(),/]+|[^\s]',
    re.DOTALL,
)
REFERENCES = {f"$({key})": key for key in KEYS}
REFERENCES.update({f"${{{key}}}": key for key in KEYS})
LOCALIZED_SHORT = re.compile(
    r'((?:"CFBundleShortVersionString"|CFBundleShortVersionString)'
    r'[ \t]*=[ \t]*")([^"]*)("[ \t]*;)'
)
LOCALIZED_INFO = re.compile(
    r'((?:"CFBundleGetInfoString"|CFBundleGetInfoString)'
    r'[ \t]*=[ \t]*"Alias Manager version )'
    r'([^,"]*)(, Copyright 2020 miyako\."[ \t]*;)'
)
LOCALIZED_TOKEN = re.compile(
    r'\s+|/\*.*?\*/|//[^\n]*|'
    r'(?P<key>"[A-Za-z_][A-Za-z_0-9]*"|[A-Za-z_][A-Za-z_0-9]*)'
    r'\s*=\s*"(?P<value>(?:\\.|[^"\\])*)"\s*;',
    re.DOTALL,
)
PLIST_VERSION = re.compile(
    r"(<key>CFBundle(?:ShortVersionString|Version)</key>\s*<string>)([^<]*)(</string>)"
)


class UniqueDictionary(dict):
    def __setitem__(self, key, value):
        if key in self:
            raise ValueError(f"Duplicate source plist key: {key}")
        super().__setitem__(key, value)


def unquote(value):
    return value[1:-1] if value.startswith('"') and value.endswith('"') else value


def text(path):
    return path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")


def rendered(path, transform):
    original = path.read_bytes()
    decoded = original.decode("utf-8-sig")
    endings = re.findall(r"\r\n|\r|\n", decoded)
    updated = transform(decoded.replace("\r\n", "\n").replace("\r", "\n"))
    if updated.count("\n") != len(endings):
        raise ValueError("Metadata rewrite changed line structure")
    iterator = iter(endings)
    encoding = "utf-8-sig" if original.startswith(b"\xef\xbb\xbf") else "utf-8"
    return re.sub("\n", lambda _: next(iterator), updated).encode(encoding)


def localized_matches(value, version, message):
    offset = 0
    fields = UniqueDictionary()
    positions = set()
    while offset < len(value):
        token = LOCALIZED_TOKEN.match(value, offset)
        if token is None:
            raise ValueError(f"{message}: unsupported strings serialization")
        if token["key"] is not None:
            fields[unquote(token["key"])] = token["value"]
            positions.add(token.start("key"))
        offset = token.end()
    expected = {
        "CFBundleShortVersionString": version,
        "CFBundleGetInfoString":
            f"{PRODUCT} version {version}, Copyright 2020 miyako.",
    }
    if any(fields.get(key) != wanted for key, wanted in expected.items()):
        raise ValueError(message)
    matches = []
    for pattern in (LOCALIZED_SHORT, LOCALIZED_INFO):
        selected = [m for m in pattern.finditer(value) if m.start() in positions]
        if [m[2] for m in selected] != [version]:
            raise ValueError(f"{message}: unsupported version serialization")
        matches.extend(selected)
    return matches


def validate_localized(value, version, message):
    localized_matches(value, version, message)


def project_settings(project):
    tokens = [match for match in PROJECT_TOKEN.finditer(project)
              if not match[0].startswith(("/*", "//"))]
    positions = {
        token.start(): unquote(token[0])
        for token, following in zip(tokens, tokens[1:])
        if unquote(token[0]) in KEYS and following[0] == "="
    }
    for key in KEYS:
        count = list(positions.values()).count(key)
        if count != SETTING_COUNT:
            raise ValueError(f"Expected {SETTING_COUNT} source assignments for {key}")
    settings = [match for match in SETTING.finditer(project)
                if match.start() in positions and unquote(match[2]) == positions[match.start()]]
    if any(sum(unquote(match[2]) == key for match in settings)
           != list(positions.values()).count(key) for key in KEYS):
        raise ValueError(f"Expected {SETTING_COUNT} editable source settings for each version key")
    return settings


def metadata(root=Path("."), values=None):
    root = Path(root)
    values = values if values is not None else {
        path: (root / path).read_bytes() for path in SOURCE_PATHS
    }

    def decoded(path):
        return values[path].decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")

    project = decoded(PROJECT)
    fields = {key: [] for key in KEYS}
    for match in project_settings(project):
        fields[unquote(match[2])].append(unquote(match[3].strip()))
    primary = "MARKETING_VERSION"
    marketing = set(fields[primary])
    if len(marketing) != 1 or not re.fullmatch(VERSION, next(iter(marketing))):
        raise ValueError(f"{primary} must be one strict X.Y.Z across configurations")
    version = next(iter(marketing))
    current = set(fields["CURRENT_PROJECT_VERSION"])
    for build in current:
        if build != version and REFERENCES.get(build) != "MARKETING_VERSION":
            raise ValueError("CURRENT_PROJECT_VERSION is invalid, unresolved, cyclic or has drifted")
    resolved = {key: version for key in KEYS}
    try:
        plist = plistlib.loads(values[PLIST], dict_type=UniqueDictionary)
    except (plistlib.InvalidFileException, ExpatError, UnicodeError) as exc:
        raise ValueError("Source Info.plist has invalid serialization") from exc
    if not isinstance(plist, dict):
        raise ValueError("Source Info.plist must be a dictionary")
    serialized = list(PLIST_VERSION.finditer(decoded(PLIST)))
    expected = 1 + ("CFBundleVersion" in plist)
    if len(serialized) != expected:
        raise ValueError("Source plist versions must be editable XML strings")
    for key in ("CFBundleShortVersionString", "CFBundleVersion"):
        if key == "CFBundleVersion" and key not in plist:
            continue
        value = plist.get(key)
        actual = resolved.get(REFERENCES.get(value), value) if isinstance(value, str) else None
        if not isinstance(actual, str) or actual != version:
            raise ValueError(f"{key} is missing, invalid, unresolved or has drifted")
        literal = [m[2] for m in serialized if f"<key>{key}</key>" in m[1]]
        if literal != [value]:
            raise ValueError(f"{key} has unsupported XML serialization")
    validate_localized(decoded(LOCALIZED), version,
                       "Localized source version is missing, invalid or has drifted")
    return version, resolved, plist, primary


def read(root=Path(".")):
    return metadata(root)[0]


def verify_bundle(bundle, root=Path(".")):
    version, resolved, source_plist, _ = metadata(root)
    contents = Path(bundle) / "Contents"
    data = plistlib.loads((contents / "Info.plist").read_bytes(), dict_type=UniqueDictionary)
    if not isinstance(data, dict) or data.get("CFBundleShortVersionString") != version:
        raise ValueError("Built bundle display version differs from selected source")
    build = source_plist.get("CFBundleVersion", "$(CURRENT_PROJECT_VERSION)")
    build = resolved.get(REFERENCES.get(build), build)
    if ("CFBundleVersion" in source_plist or "CFBundleVersion" in data) \
            and data.get("CFBundleVersion") != build:
        raise ValueError("Built bundle build version differs from selected source")
    localized_path = contents / "Resources/English.lproj/InfoPlist.strings"
    serialized = localized_path.read_bytes()
    # Xcode's CopyStringsFile can compile the source strings into a binary plist.
    if serialized.startswith((b"bplist00", b"<?xml")):
        localized = plistlib.loads(serialized, dict_type=UniqueDictionary)
        if not isinstance(localized, dict) or (
            localized.get("CFBundleShortVersionString") != version
            or localized.get("CFBundleGetInfoString")
            != f"{PRODUCT} version {version}, Copyright 2020 miyako."
        ):
            raise ValueError("Built localized display differs from selected source")
        return
    decoded = serialized.decode("utf-16") if serialized.startswith((b"\xff\xfe", b"\xfe\xff")) \
        else serialized.decode("utf-8-sig")
    validate_localized(decoded.replace("\r\n", "\n").replace("\r", "\n"), version,
                       "Built localized display differs from selected source")


def bump(mode, root=Path(".")):
    root = Path(root)
    current, _, _, primary = metadata(root)
    index = ("major", "minor", "patch").index(mode)
    parts = list(map(int, current.split(".")))
    parts[index] += 1
    parts[index + 1:] = [0] * (2 - index)
    new = ".".join(map(str, parts))

    def replace(match):
        literal = match[3].strip()
        if unquote(literal) in REFERENCES:
            return match[0]
        replacement = f'"{new}"' if literal.startswith('"') else new
        value = match[3].replace(literal, replacement, 1)
        return f"{match[1]}{value}{match[4]}"

    def localized(value):
        matches = localized_matches(value, current, "Invalid localized source")
        for match in sorted(matches, key=lambda match: match.start(), reverse=True):
            value = value[:match.start(2)] + new + value[match.end(2):]
        return value

    def project(value):
        starts = {match.start() for match in project_settings(value)}
        return SETTING.sub(lambda match: replace(match) if match.start() in starts else match[0],
                           value)

    transforms = (
        (PROJECT, project),
        (PLIST, lambda value: PLIST_VERSION.sub(
            lambda m: m[0] if m[2] in REFERENCES else f"{m[1]}{new}{m[3]}", value,
        )),
        (LOCALIZED, localized),
    )
    # Render all files first so unsupported encodings cannot cause a partial bump.
    updates = [(root / path, rendered(root / path, transform)) for path, transform in transforms]
    if metadata(root, {path: data for path, (_, data) in zip(SOURCE_PATHS, updates)})[0] != new:
        raise ValueError("Bumped metadata did not validate")
    for path, data in updates:
        path.write_bytes(data)
    if read(root) != new:
        raise ValueError("Bumped metadata did not validate")
    return new


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--bump", choices=("patch", "minor", "major"))
    operation.add_argument("--verify-bundle", type=Path)
    args = parser.parse_args()
    if args.verify_bundle:
        verify_bundle(args.verify_bundle)
    else:
        print(bump(args.bump) if args.bump else read())
