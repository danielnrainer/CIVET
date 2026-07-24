"""
CIVET headless CLI.

Wraps the same validation and conversion modules the GUI uses so CIF
files can be screened or converted in CI/batch pipelines without
launching the editor:

- ``check``       syntax (CIF1.1/CIF2.0), data-name, and data-value validation
- ``convert``     CIF1<->CIF2 syntax and legacy<->modern notation conversion
- ``lint-rules``  structural validation of a .cif_rules file itself

The functions below (``check_content``, ``convert_content``,
``build_dictionary_manager``) are the programmatic API half of this
feature - import them directly if you want CIVET's checks from Python
rather than through the ``civet`` command line.
"""

import argparse
import json
import sys
from io import TextIOWrapper
from typing import Dict, List, Optional

from utils.CIF_parser import CIFParser, list_data_block_names
from utils.cif_dictionary_manager import CIFDictionaryManager, CIFSyntaxVersion
from utils.cif_syntax_compliance import check_compliance
from utils.cif_data_validator import CIFDataValidator
from utils.data_name_validator import DataNameValidator, FieldCategory
from utils.cif_format_converter import CIFFormatConverter
from utils.field_rules_validator import FieldRulesValidator

MINIMUM_PYTHON = (3, 11)

# Data-name categories severe enough to report from `check`. VALID,
# REGISTERED_LOCAL, and USER_ALLOWED are not issues, so they're omitted.
_NAME_ISSUE_SEVERITY = {
    FieldCategory.UNKNOWN: "warning",
    FieldCategory.MALFORMED: "warning",
    FieldCategory.DEPRECATED: "info",
}


def _configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, TextIOWrapper):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, TypeError):
                pass


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def build_dictionary_manager(extra_dictionaries: Optional[List[str]] = None) -> CIFDictionaryManager:
    """Build a CIFDictionaryManager, optionally with extra dictionaries loaded.

    This is the same manager class the GUI uses. Construct one per CLI
    invocation and reuse it across files/checks for speed.
    """
    manager = CIFDictionaryManager()
    for path in extra_dictionaries or []:
        manager.add_dictionary(path)
    return manager


def check_content(
    content: str,
    dict_manager: CIFDictionaryManager,
    *,
    check_syntax: bool = True,
    check_data_names: bool = True,
    check_data_values: bool = True,
    check_links: bool = False,
    syntax_version: str = "auto",
) -> Dict:
    """Run the requested checks against CIF content; return a plain-dict report.

    This is the programmatic entry point - the ``check`` CLI subcommand
    is a thin formatter around this function.

    Args:
        syntax_version: which spec to check syntax compliance against -
            "cif1", "cif2", or "auto" (the file's own declared/detected
            version, defaulting to CIF1.1 if that's ambiguous). A CIF1.1
            file is never CIF2.0 compliant and vice versa (each requires
            the other's version header to be absent/replaced), so checking
            both unconditionally would always fail one of them.
    """
    detected_syntax_version = dict_manager.detect_syntax_version(content)
    report: Dict = {
        "blocks": list_data_block_names(content),
        "notation": dict_manager.detect_notation(content).value,
        "syntax_version": detected_syntax_version.value,
        "issues": [],
    }

    if check_syntax:
        if syntax_version == "auto":
            spec_key = "cif2" if detected_syntax_version == CIFSyntaxVersion.CIF2 else "cif1"
        else:
            spec_key = syntax_version
        compliance = check_compliance(content)
        for issue in compliance[spec_key]:
            report["issues"].append({
                "source": "syntax",
                "spec": issue.spec,
                "severity": issue.severity,
                "issue_type": issue.issue_type,
                "line": issue.line_number,
                "column": issue.column,
                "message": issue.description,
                "auto_fixable": issue.auto_fixable,
            })

    if check_data_names:
        name_report = DataNameValidator(dict_manager).validate_cif_content(content)
        for category, results in (
            (FieldCategory.UNKNOWN, name_report.unknown_fields),
            (FieldCategory.MALFORMED, name_report.malformed_fields),
            (FieldCategory.DEPRECATED, name_report.deprecated_fields),
        ):
            for result in results:
                report["issues"].append({
                    "source": "data_name",
                    "severity": _NAME_ISSUE_SEVERITY[category],
                    "issue_type": category.value,
                    "line": result.line_number,
                    "field": result.field_name,
                    "message": result.description or category.value,
                })

    if check_data_values or check_links:
        parser = CIFParser()
        parser.parse_file(content)
        value_validator = CIFDataValidator()

        if check_data_values:
            for issue in value_validator.validate(parser, dict_manager):
                report["issues"].append({
                    "source": "data_value",
                    "severity": issue.severity,
                    "issue_type": issue.issue_type,
                    "line": issue.line_number,
                    "field": issue.field_name,
                    "message": issue.message,
                    "value": issue.value,
                    "expected": issue.expected,
                })

        if check_links:
            for issue in value_validator.check_parent_child_links(parser, dict_manager):
                report["issues"].append({
                    "source": "data_value",
                    "severity": issue.severity,
                    "issue_type": issue.issue_type,
                    "line": issue.line_number,
                    "field": issue.field_name,
                    "message": issue.message,
                    "value": issue.value,
                    "expected": issue.expected,
                })

    report["issues"].sort(key=lambda i: (i.get("line") is None, i.get("line") or 0))
    report["error_count"] = sum(1 for i in report["issues"] if i["severity"] == "error")
    report["warning_count"] = sum(1 for i in report["issues"] if i["severity"] == "warning")
    report["info_count"] = sum(1 for i in report["issues"] if i["severity"] == "info")
    return report


def convert_content(
    content: str,
    dict_manager: CIFDictionaryManager,
    *,
    to_notation: Optional[str] = None,
    to_syntax: Optional[str] = None,
) -> "tuple[str, List[str]]":
    """Convert CIF content's data-name notation and/or syntax version.

    Args:
        to_notation: "modern" or "legacy", or None to leave notation untouched.
        to_syntax: "cif1" or "cif2", or None to leave the syntax version untouched.

    Returns:
        (converted_content, change_log). Raises ValueError if conversion to
        CIF1.1 is impossible because CIF2-only constructs are present.
    """
    converter = CIFFormatConverter(dict_manager)
    changes: List[str] = []

    if to_notation == "modern":
        content, notation_changes = converter.convert_to_modern_notation(content)
        changes.extend(notation_changes)
    elif to_notation == "legacy":
        content, notation_changes = converter.convert_to_legacy_notation(content)
        changes.extend(notation_changes)

    if to_syntax == "cif2":
        content, syntax_changes = converter.ensure_cif2_compliant(content)
        changes.extend(syntax_changes)
    elif to_syntax == "cif1":
        content, syntax_changes = converter.ensure_cif1_compliant(content)
        changes.extend(syntax_changes)

    return content, changes


def _print_text_report(reports: List[Dict], overall: Dict, *, quiet: bool, verbose: bool) -> None:
    for report in reports:
        path = report["file"]
        issues = report["issues"] if verbose else [i for i in report["issues"] if i["severity"] != "info"]

        if quiet:
            print(f"{path}: {report['error_count']} error(s), {report['warning_count']} warning(s)")
            continue

        blocks = ", ".join(report["blocks"]) or "(none)"
        print(f"== {path} ==  [blocks: {blocks}; notation: {report['notation']}; syntax: {report['syntax_version']}]")
        if not issues:
            print("  no issues found")
        for issue in issues:
            loc = f"line {issue['line']}" if issue.get("line") else "?"
            label = issue.get("field") or issue.get("spec") or issue["source"]
            fix = " [auto-fixable]" if issue.get("auto_fixable") else ""
            print(f"  [{issue['severity'].upper()}] {loc}: {label}: {issue['message']}{fix}")
        print()

    print(f"TOTAL: {overall['errors']} error(s), {overall['warnings']} warning(s), {overall['info']} info")


def cmd_check(args: argparse.Namespace) -> int:
    _configure_utf8_stdio()
    dict_manager = build_dictionary_manager(args.dictionary)

    exit_code = 0
    overall = {"errors": 0, "warnings": 0, "info": 0}
    all_reports: List[Dict] = []

    for path in args.files:
        try:
            content = _read_text(path)
        except OSError as exc:
            print(f"{path}: error: could not read file: {exc}", file=sys.stderr)
            exit_code = max(exit_code, 2)
            continue

        report = check_content(
            content,
            dict_manager,
            check_syntax=not args.no_syntax,
            check_data_names=not args.no_data_names,
            check_data_values=not args.no_data_values,
            check_links=args.check_links,
            syntax_version=args.syntax_version,
        )
        report["file"] = path
        all_reports.append(report)

        overall["errors"] += report["error_count"]
        overall["warnings"] += report["warning_count"]
        overall["info"] += report["info_count"]

        if report["error_count"]:
            exit_code = max(exit_code, 1)

    if args.format == "json":
        print(json.dumps({"files": all_reports, "summary": overall}, indent=2))
    else:
        _print_text_report(all_reports, overall, quiet=args.quiet, verbose=args.verbose)

    return exit_code


def cmd_convert(args: argparse.Namespace) -> int:
    _configure_utf8_stdio()

    if not args.to_notation and not args.to_syntax:
        print("error: specify at least one of --to-notation / --to-syntax", file=sys.stderr)
        return 2

    try:
        content = _read_text(args.file)
    except OSError as exc:
        print(f"{args.file}: error: could not read file: {exc}", file=sys.stderr)
        return 2

    dict_manager = build_dictionary_manager(args.dictionary)

    try:
        converted, changes = convert_content(
            content,
            dict_manager,
            to_notation=args.to_notation,
            to_syntax=args.to_syntax,
        )
    except ValueError as exc:
        print(f"{args.file}: error: {exc}", file=sys.stderr)
        return 1

    if args.in_place:
        with open(args.file, "w", encoding="utf-8") as fh:
            fh.write(converted)
        destination = args.file
    elif args.output and args.output != "-":
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(converted)
        destination = args.output
    else:
        destination = None
        print(converted)

    if not args.quiet:
        for change in changes:
            print(f"# {change}", file=sys.stderr)
        if destination:
            print(f"# wrote {destination}", file=sys.stderr)

    return 0


def cmd_lint_rules(args: argparse.Namespace) -> int:
    _configure_utf8_stdio()

    try:
        rules_content = _read_text(args.rules_file)
    except OSError as exc:
        print(f"{args.rules_file}: error: could not read file: {exc}", file=sys.stderr)
        return 2

    cif_content = None
    if args.cif:
        try:
            cif_content = _read_text(args.cif)
        except OSError as exc:
            print(f"{args.cif}: error: could not read file: {exc}", file=sys.stderr)
            return 2

    dict_manager = build_dictionary_manager(args.dictionary)
    validator = FieldRulesValidator(dict_manager, CIFFormatConverter(dict_manager))
    result = validator.validate_field_rules(rules_content, cif_content, target_format=args.target_format)

    if args.format == "json":
        print(json.dumps({
            "total_fields": result.total_fields,
            "unique_fields": result.unique_fields,
            "cif_format_detected": result.cif_format_detected,
            "target_format_used": result.target_format_used,
            "issues": [
                {
                    "issue_type": issue.issue_type.value,
                    "category": issue.category.value,
                    "fields": issue.field_names,
                    "description": issue.description,
                    "suggested_fix": issue.suggested_fix,
                    "auto_fixable": issue.auto_fixable,
                }
                for issue in result.issues
            ],
        }, indent=2))
    else:
        print(
            f"{args.rules_file}: {result.total_fields} field(s), {result.unique_fields} unique, "
            f"detected format: {result.cif_format_detected}"
        )
        if not result.issues:
            print("  no issues found")
        for issue in result.issues:
            fix = " [auto-fixable]" if issue.auto_fixable else ""
            print(f"  [{issue.category.value}] {', '.join(issue.field_names)}: {issue.description}{fix}")

    return 1 if result.has_issues else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="civet",
        description="Headless CIF validation and conversion (CIVET's non-GUI companion).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser(
        "check", help="Validate CIF file(s) for syntax, data-name, and data-value issues.")
    check_parser.add_argument("files", nargs="+", help="CIF file(s) to check.")
    check_parser.add_argument(
        "-d", "--dictionary", action="append", default=[],
        help="Additional DDLm/DDL1 dictionary file to load (repeatable).")
    check_parser.add_argument(
        "--no-syntax", action="store_true", help="Skip CIF1.1/CIF2.0 syntax compliance checks.")
    check_parser.add_argument(
        "--syntax-version", choices=["auto", "cif1", "cif2"], default="auto",
        help="Which spec to check syntax compliance against (default: the file's own "
             "declared/detected version - a file is never compliant with both at once).")
    check_parser.add_argument(
        "--no-data-names", action="store_true", help="Skip data-name (dictionary/deprecation) checks.")
    check_parser.add_argument(
        "--no-data-values", action="store_true", help="Skip data-value (type/enum/loop) checks.")
    check_parser.add_argument(
        "--check-links", action="store_true",
        help="Also run the opt-in DDL1 parent/child relational check.")
    check_parser.add_argument("-f", "--format", choices=["text", "json"], default="text")
    check_parser.add_argument(
        "-q", "--quiet", action="store_true", help="Print one summary line per file only.")
    check_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Also show info-level issues in text output.")
    check_parser.set_defaults(func=cmd_check)

    convert_parser = subparsers.add_parser(
        "convert", help="Convert a CIF file's data-name notation and/or syntax version.")
    convert_parser.add_argument("file", help="CIF file to convert.")
    convert_parser.add_argument(
        "--to-notation", choices=["modern", "legacy"], help="Convert data-name notation.")
    convert_parser.add_argument(
        "--to-syntax", choices=["cif1", "cif2"],
        help="Convert syntax version header/quoting (cif1 rejects files with CIF2-only constructs).")
    convert_parser.add_argument(
        "-o", "--output", help="Write converted content to this path instead of stdout.")
    convert_parser.add_argument(
        "--in-place", action="store_true", help="Overwrite the input file with the converted content.")
    convert_parser.add_argument(
        "-d", "--dictionary", action="append", default=[],
        help="Additional DDLm/DDL1 dictionary file to load (repeatable).")
    convert_parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress the change log on stderr.")
    convert_parser.set_defaults(func=cmd_convert)

    lint_parser = subparsers.add_parser(
        "lint-rules", help="Validate a .cif_rules file's own structure (not the CIF it targets).")
    lint_parser.add_argument("rules_file", help=".cif_rules file to lint.")
    lint_parser.add_argument("--cif", help="Optional CIF file, used only to detect the target format.")
    lint_parser.add_argument("--target-format", choices=["modern", "legacy"], default="modern")
    lint_parser.add_argument(
        "-d", "--dictionary", action="append", default=[],
        help="Additional DDLm/DDL1 dictionary file to load (repeatable).")
    lint_parser.add_argument("-f", "--format", choices=["text", "json"], default="text")
    lint_parser.set_defaults(func=cmd_lint_rules)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    if sys.version_info < MINIMUM_PYTHON:
        required_version = ".".join(str(part) for part in MINIMUM_PYTHON)
        current_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        print(f"CIVET requires Python {required_version}+; found Python {current_version}.", file=sys.stderr)
        return 2

    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
