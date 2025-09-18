"""
Field Rules Validator
====================

Validates and analyzes field rules files for common issues:
- Mixed CIF1/CIF2 formats
- Duplicate/alias fields
- Unknown fields not in dictionaries
- Format inconsistencies

Provides automated fixes and detailed issue reporting for user resolution.
"""

import re
from typing import Dict, List, Set, Optional, Tuple, NamedTuple
from dataclasses import dataclass
from pathlib import Path
from enum import Enum


class IssueType(Enum):
    """Types of validation issues"""
    MIXED_FORMAT = "mixed_format"
    DUPLICATE_ALIAS = "duplicate_alias"
    UNKNOWN_FIELD = "unknown_field"
    FORMAT_INCONSISTENCY = "format_inconsistency"
    DEPRECATED_FIELD = "deprecated_field"


class IssueCategory(Enum):
    """Issue categories for UI grouping"""
    MIXED_FORMAT = "Mixed Format Fields"
    DUPLICATE_ALIAS = "Duplicate/Alias Fields"
    UNKNOWN_FIELD = "Unknown Fields"
    DEPRECATED_FIELD = "Deprecated Fields"


class AutoFixType(Enum):
    """Types of automatic fixes available"""
    YES = "yes"                         # Direct dictionary mapping available
    CIF2_MANUAL_MAPPING = "CIF2 manual mapping"  # CIF2-only extension mapping
    NO = "no"                          # No automatic fix available


@dataclass
class ValidationIssue:
    """Represents a single validation issue"""
    issue_type: IssueType
    category: IssueCategory
    field_names: List[str]  # All related field names
    description: str
    suggested_fix: str
    auto_fix_type: AutoFixType = AutoFixType.NO
    
    @property
    def auto_fixable(self) -> bool:
        """Check if issue can be automatically fixed"""
        return self.auto_fix_type in [AutoFixType.YES, AutoFixType.CIF2_MANUAL_MAPPING]


@dataclass
class ValidationResult:
    """Results of field definition validation"""
    issues: List[ValidationIssue]
    total_fields: int
    unique_fields: int
    cif_format_detected: str  # "CIF1", "CIF2", "Mixed"
    
    @property
    def has_issues(self) -> bool:
        return len(self.issues) > 0
    
    @property
    def issues_by_category(self) -> Dict[IssueCategory, List[ValidationIssue]]:
        result = {}
        for issue in self.issues:
            if issue.category not in result:
                result[issue.category] = []
            result[issue.category].append(issue)
        return result


class CIFFormatAnalyzer:
    """Analyzes CIF files to determine predominant format"""
    
    @staticmethod
    def analyze_cif_format(cif_content: str) -> str:
        """
        Analyze CIF content to determine format.
        Returns: "CIF1", "CIF2", or "Mixed"
        """
        if not cif_content.strip():
            return "CIF1"  # Default to CIF1 for empty content
            
        # Extract all field names from valid positions in the CIF content
        # Process line by line to avoid matching fields in comments
        matches = []
        for line in cif_content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue  # Skip empty lines and comments
                
            # Look for fields at the start of the line or after action prefixes
            field_pattern = r'^(?:DELETE:|EDIT:|CHECK:)?\s*(_[a-zA-Z][a-zA-Z0-9_\-]*(?:\.[a-zA-Z][a-zA-Z0-9_\-]*)*)'
            match = re.match(field_pattern, line)
            if match:
                matches.append(match.group(1))
        
        if not matches:
            return "CIF1"  # Default if no fields found
        
        cif1_count = 0
        cif2_count = 0
        
        for field in matches:
            if '.' in field:
                cif2_count += 1
            else:
                cif1_count += 1
        
        total = cif1_count + cif2_count
        if total == 0:
            return "CIF1"
        
        cif2_ratio = cif2_count / total
        
        # Determine format based on ratio
        if cif2_ratio >= 0.7:
            return "CIF2"
        elif cif2_ratio <= 0.3:
            return "CIF1"
        else:
            return "Mixed"


class FieldRulesValidator:
    """
    Validates field rules files and identifies common issues
    """
    
    def __init__(self, dict_manager, format_converter=None):
        """
        Initialize validator with dictionary manager and optional format converter
        
        Args:
            dict_manager: CIFDictionaryManager instance
            format_converter: CIFFormatConverter instance (optional)
        """
        self.dict_manager = dict_manager
        self.format_converter = format_converter
    
    def _determine_auto_fix_type(self, field_name: str, preferred_format: str = "CIF1") -> AutoFixType:
        """
        Determine what type of automatic fix is available for a field.
        
        Args:
            field_name: The field name to check
            preferred_format: Target format ("CIF1" or "CIF2")
        
        Returns:
            AutoFixType indicating the fix availability
        """
        # Check if there's a CIF2-only mapping first (for proper categorization)
        if hasattr(self.dict_manager, 'is_cif2_only_extension'):
            if self.dict_manager.is_cif2_only_extension(field_name):
                return AutoFixType.CIF2_MANUAL_MAPPING
        
        # Check if there's an official dictionary mapping
        if preferred_format == "CIF1":
            official_equiv = self.dict_manager.get_cif1_equivalent(field_name)
        else:
            official_equiv = self.dict_manager.get_cif2_equivalent(field_name)
        
        if official_equiv:
            return AutoFixType.YES
        
        # If no conversion available
        return AutoFixType.NO
        
    def validate_field_rules(self, 
                           field_rules_content: str, 
                           cif_content: Optional[str] = None,
                           target_format: str = "CIF2") -> ValidationResult:
        """
        Validate field rules and return detailed results
        
        Args:
            field_rules_content: Content of field rules file
            cif_content: Content of CIF file to analyze format (optional)
            target_format: Target format for validation ("CIF1" or "CIF2")
            
        Returns:
            ValidationResult with all issues found
        """
        # Extract fields from rules file
        def_fields = self._extract_fields_from_content(field_rules_content)
        
        # Determine target format
        if cif_content:
            cif_format = CIFFormatAnalyzer.analyze_cif_format(cif_content)
        else:
            cif_format = "CIF1"  # Default if no CIF provided
        
        # Find all issues
        issues = []
        
        # 1. Check for mixed format issues
        mixed_format_issues = self._find_mixed_format_issues(def_fields, target_format)
        issues.extend(mixed_format_issues)
        
        # 2. Check for duplicate/alias issues
        duplicate_issues = self._find_duplicate_alias_issues(def_fields)
        issues.extend(duplicate_issues)
        
        # 3. Check for deprecated fields
        deprecated_issues = self._find_deprecated_field_issues(def_fields)
        issues.extend(deprecated_issues)
        
        # 4. Check for unknown fields
        unknown_issues = self._find_unknown_field_issues(def_fields)
        issues.extend(unknown_issues)
        
        return ValidationResult(
            issues=issues,
            total_fields=len(def_fields),
            unique_fields=len(set(def_fields)),
            cif_format_detected=cif_format
        )
    
    def _extract_fields_from_content(self, content: str) -> List[str]:
        """Extract all field names from field definition content"""
        # Pattern to match CIF field names only at valid positions:
        # 1. At start of line (with optional whitespace) - but not in comments
        # 2. After action prefixes (DELETE:, EDIT:, CHECK:)
        # This prevents matching underscores in the middle of comments
        # Include hyphens which are valid in CIF field names
        
        fields = []
        seen = set()
        
        # Process line by line to avoid matching fields in comments
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue  # Skip empty lines and comments
                
            # Look for fields at the start of the line or after action prefixes
            field_pattern = r'^(?:DELETE:|EDIT:|CHECK:)?\s*(_[a-zA-Z][a-zA-Z0-9_\-]*(?:\.[a-zA-Z][a-zA-Z0-9_\-]*)*)'
            match = re.match(field_pattern, line)
            if match:
                field = match.group(1)
                if field not in seen:
                    fields.append(field)
                    seen.add(field)
        
        return fields
    
    def _find_mixed_format_issues(self, fields: List[str], target_format: str) -> List[ValidationIssue]:
        """Find fields that don't match the target format"""
        issues = []
        
        for field in fields:
            is_cif2 = '.' in field
            field_format = "CIF2" if is_cif2 else "CIF1"
            
            # For mixed CIF files, prefer CIF2
            preferred_format = "CIF2" if target_format == "Mixed" else target_format
            
            if field_format != preferred_format:
                # Try to find the equivalent in the preferred format
                if preferred_format == "CIF2":
                    equivalent = self.dict_manager.get_cif2_equivalent(field)
                else:
                    equivalent = self.dict_manager.get_cif1_equivalent(field)
                
                if equivalent:
                    suggested_fix = f"Convert to {preferred_format} format: {equivalent}"
                    auto_fix_type = self._determine_auto_fix_type(field, preferred_format)
                    issues.append(ValidationIssue(
                        issue_type=IssueType.MIXED_FORMAT,
                        category=IssueCategory.MIXED_FORMAT,
                        field_names=[field],
                        description=f"Field {field} is in {field_format} format, but based on the current CIF file {preferred_format} is preferred",
                        suggested_fix=suggested_fix,
                        auto_fix_type=auto_fix_type
                    ))
        
        return issues
    
    def _find_duplicate_alias_issues(self, fields: List[str]) -> List[ValidationIssue]:
        """Find fields that are direct duplicates or aliases of each other"""
        issues = []
        processed = set()
        
        # First check for direct duplicates (same field name appearing multiple times)
        field_counts = {}
        for field in fields:
            field_counts[field] = field_counts.get(field, 0) + 1
        
        # Create issues for direct duplicates
        for field, count in field_counts.items():
            if count > 1:
                issues.append(ValidationIssue(
                    issue_type=IssueType.DUPLICATE_ALIAS,
                    category=IssueCategory.DUPLICATE_ALIAS,
                    field_names=[field],
                    description=f"Field {field} appears {count} times",
                    suggested_fix=f"Remove {count-1} duplicate occurrence(s) of {field}",
                    auto_fix_type=AutoFixType.YES  # Duplicate removal is always fixable
                ))
                processed.add(field)
        
        # Then check for alias duplicates (different field names that are equivalent)
        unique_fields = list(field_counts.keys())  # Only check unique field names
        field_groups = {}
        
        for field in unique_fields:
            if field in processed:
                continue  # Skip fields already identified as direct duplicates
                
            # Find all aliases for this field
            aliases = [field]
            canonical = None
            
            # Check if this field has equivalents
            cif2_equiv = self.dict_manager.get_cif2_equivalent(field)
            cif1_equiv = self.dict_manager.get_cif1_equivalent(field)
            
            if cif2_equiv:
                canonical = cif2_equiv
                if cif2_equiv in unique_fields and cif2_equiv not in aliases:
                    aliases.append(cif2_equiv)
            
            if cif1_equiv:
                if not canonical:
                    canonical = field  # Use current field as canonical if no CIF2 equiv
                if cif1_equiv in unique_fields and cif1_equiv not in aliases:
                    aliases.append(cif1_equiv)
            
            # If we found multiple aliases, it's an issue
            if len(aliases) > 1:
                canonical_key = canonical or field
                if canonical_key not in field_groups:
                    field_groups[canonical_key] = aliases
                    processed.update(aliases)
        
        # Create issues for each group of aliases
        for canonical, alias_group in field_groups.items():
            if len(alias_group) > 1:
                # Determine the best field to keep
                cif2_fields = [f for f in alias_group if '.' in f]
                cif1_fields = [f for f in alias_group if '.' not in f]
                
                # Prefer CIF2 format if available, otherwise use first CIF1
                preferred = cif2_fields[0] if cif2_fields else cif1_fields[0]
                
                issues.append(ValidationIssue(
                    issue_type=IssueType.DUPLICATE_ALIAS,
                    category=IssueCategory.DUPLICATE_ALIAS,
                    field_names=alias_group,
                    description=f"Multiple aliases found: {', '.join(alias_group)}",
                    suggested_fix=f"Keep only {preferred}, remove others",
                    auto_fix_type=AutoFixType.YES  # Alias deduplication is always fixable
                ))
        
        return issues
    
    def _find_deprecated_field_issues(self, fields: List[str]) -> List[ValidationIssue]:
        """Find fields that are deprecated and suggest modern replacements"""
        issues = []
        
        for field in fields:
            if self.dict_manager.is_field_deprecated(field):
                # Get the non-deprecated replacement (prefer CIF2 for field rules)
                modern_replacement = self.dict_manager.get_modern_equivalent(field, prefer_format="CIF2")
                
                if modern_replacement:
                    issues.append(ValidationIssue(
                        issue_type=IssueType.DEPRECATED_FIELD,
                        category=IssueCategory.DEPRECATED_FIELD,
                        field_names=[field],
                        description=f"Field {field} is deprecated",
                        suggested_fix=f"Replace with modern equivalent: {modern_replacement}",
                        auto_fix_type=AutoFixType.YES  # Deprecated field replacement is always fixable
                    ))
                else:
                    issues.append(ValidationIssue(
                        issue_type=IssueType.DEPRECATED_FIELD,
                        category=IssueCategory.DEPRECATED_FIELD,
                        field_names=[field],
                        description=f"Field {field} is deprecated",
                        suggested_fix="Remove deprecated field (no modern equivalent available)",
                        auto_fix_type=AutoFixType.NO  # No automatic fix if no replacement
                    ))
        
        return issues
    
    def _find_unknown_field_issues(self, fields: List[str]) -> List[ValidationIssue]:
        """Find fields that are not recognized by any dictionary"""
        issues = []
        
        for field in fields:
            if not self.dict_manager.is_known_field(field):
                # Check if it might be a simple format issue
                if '.' in field:
                    # CIF2 format - try CIF1 equivalent
                    potential_cif1 = field.replace('.', '_')
                    if self.dict_manager.is_known_field(potential_cif1):
                        suggested_fix = f"Use known field: {potential_cif1}"
                        auto_fix_type = AutoFixType.YES
                    else:
                        suggested_fix = "Verify field name or add to custom dictionary"
                        auto_fix_type = self._determine_auto_fix_type(field)
                else:
                    # CIF1 format - try CIF2 equivalent
                    potential_cif2 = None
                    if '_' in field[1:]:  # Skip first underscore
                        parts = field[1:].split('_')
                        if len(parts) >= 2:
                            potential_cif2 = f"_{parts[0]}.{'_'.join(parts[1:])}"
                            if self.dict_manager.is_known_field(potential_cif2):
                                suggested_fix = f"Use known field: {potential_cif2}"
                                auto_fix_type = AutoFixType.YES
                            else:
                                suggested_fix = "Verify field name or add to custom dictionary"
                                auto_fix_type = self._determine_auto_fix_type(field)
                        else:
                            suggested_fix = "Verify field name or add to custom dictionary"
                            auto_fix_type = self._determine_auto_fix_type(field)
                    else:
                        suggested_fix = "Verify field name or add to custom dictionary"
                        auto_fix_type = self._determine_auto_fix_type(field)
                
                issues.append(ValidationIssue(
                    issue_type=IssueType.UNKNOWN_FIELD,
                    category=IssueCategory.UNKNOWN_FIELD,
                    field_names=[field],
                    description=f"Unknown field: {field}",
                    suggested_fix=suggested_fix,
                    auto_fix_type=auto_fix_type
                ))
        
        return issues
    
    def apply_automatic_fixes(self, 
                            field_def_content: str, 
                            issues: List[ValidationIssue],
                            fix_obvious_only: bool = False,
                            target_format: str = "CIF2") -> Tuple[str, List[str]]:
        """
        Apply automatic fixes to field definition content
        
        Args:
            field_def_content: Original field definition content
            issues: List of issues to fix
            fix_obvious_only: Only fix obviously safe issues
            target_format: Target format for fixes ("CIF1" or "CIF2")
            
        Returns:
            Tuple of (fixed_content, list_of_changes_made)
        """
        fixed_content = field_def_content
        changes_made = []
        
        for issue in issues:
            if not issue.auto_fixable:
                continue
                
            if fix_obvious_only and issue.severity not in ["info"]:
                continue
            
            # Apply fixes based on issue type
            if issue.issue_type == IssueType.MIXED_FORMAT:
                fixed_content, change = self._fix_mixed_format(fixed_content, issue, target_format)
                if change:
                    changes_made.append(change)
                    
            elif issue.issue_type == IssueType.DUPLICATE_ALIAS:
                fixed_content, change = self._fix_duplicate_alias(fixed_content, issue, target_format)
                if change:
                    changes_made.append(change)
                    
            elif issue.issue_type == IssueType.DEPRECATED_FIELD:
                fixed_content, change = self._fix_deprecated_field(fixed_content, issue)
                if change:
                    changes_made.append(change)
                    
            elif issue.issue_type == IssueType.UNKNOWN_FIELD and issue.auto_fixable:
                fixed_content, change = self._fix_unknown_field(fixed_content, issue)
                if change:
                    changes_made.append(change)
        
        return fixed_content, changes_made
    
    def _fix_mixed_format(self, content: str, issue: ValidationIssue, target_format: str = "CIF2") -> Tuple[str, Optional[str]]:
        """Fix mixed format issue using the specified target format"""
        field = issue.field_names[0]
        
        # Determine the replacement based on target format
        if target_format == "CIF1":
            # Convert to CIF1 format
            replacement = self.dict_manager.get_cif1_equivalent(field)
            if not replacement:
                # Convert dots to underscores for generic conversion
                replacement = field.replace('.', '_')
        else:  # CIF2
            # Convert to CIF2 format
            replacement = self.dict_manager.get_cif2_equivalent(field)
            if not replacement:
                return content, None
        
        # Replace all occurrences of the field
        pattern = re.escape(field)
        new_content = re.sub(pattern, replacement, content)
        
        if new_content != content:
            return new_content, f"Converted {field} to {replacement} ({target_format} format)"
        
        return content, None
    
    def _fix_duplicate_alias(self, content: str, issue: ValidationIssue, target_format: str = "CIF2") -> Tuple[str, Optional[str]]:
        """Fix duplicate alias issue, preferring the target format"""
        preferred = None
        
        # Choose the preferred field based on target format
        for field in issue.field_names:
            if target_format == "CIF1" and '.' not in field:
                preferred = field
                break
            elif target_format == "CIF2" and '.' in field:
                preferred = field
                break
        
        # If no field matches the target format, use the first one
        if not preferred:
            preferred = issue.field_names[0]
        
        # Remove all other aliases
        removed_fields = []
        new_content = content
        
        for field in issue.field_names:
            if field != preferred:
                pattern = re.escape(field)
                field_removed = re.sub(pattern, preferred, new_content)
                if field_removed != new_content:
                    new_content = field_removed
                    removed_fields.append(field)
        
        if removed_fields:
            return new_content, f"Replaced {', '.join(removed_fields)} with {preferred} ({target_format} format)"
        
        return content, None
    
    def _fix_unknown_field(self, content: str, issue: ValidationIssue) -> Tuple[str, Optional[str]]:
        """Fix unknown field issue"""
        field = issue.field_names[0]
        
        # Extract the suggested replacement
        if "Use known field:" in issue.suggested_fix:
            replacement = issue.suggested_fix.split(": ")[1]
            
            pattern = re.escape(field)
            new_content = re.sub(pattern, replacement, content)
            
            if new_content != content:
                return new_content, f"Replaced unknown field {field} with {replacement}"
        
        return content, None
    
    def _fix_deprecated_field(self, content: str, issue: ValidationIssue) -> Tuple[str, Optional[str]]:
        """Fix deprecated field issue by replacing with modern equivalent"""
        field = issue.field_names[0]
        
        # Extract the replacement from the suggested fix
        if "Replace with modern equivalent:" in issue.suggested_fix:
            replacement = issue.suggested_fix.split(": ")[1]
            
            # Use regex to replace the field name, being careful about word boundaries
            # to avoid replacing partial matches
            pattern = r'\b' + re.escape(field) + r'\b'
            new_content = re.sub(pattern, replacement, content)
            
            if new_content != content:
                return new_content, f"Replaced deprecated field {field} with modern equivalent {replacement}"
        elif "Remove deprecated field" in issue.suggested_fix:
            # If no replacement is available, remove the field line
            lines = content.split('\n')
            new_lines = []
            removed = False
            
            for line in lines:
                # Check if this line defines the deprecated field
                if line.strip().startswith(field + ':') or line.strip().startswith(f"# {field}:"):
                    removed = True
                    continue  # Skip this line
                new_lines.append(line)
            
            if removed:
                return '\n'.join(new_lines), f"Removed deprecated field {field}"
        
        return content, None