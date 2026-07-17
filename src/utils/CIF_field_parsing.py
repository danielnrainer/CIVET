"""Module containing CIF checking functionality and field definition loading."""

import ast
import operator
import re

# Safe operators for expression evaluation
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

def safe_eval_expr(expr_str, field_values):
    """
    Safely evaluate a mathematical expression with field value substitution.
    
    Args:
        expr_str: Expression string like "_field1 / (_field2 * 60)"
        field_values: Dict mapping field names to their numeric values
        
    Returns:
        Evaluated result as float, or None if evaluation fails
    """
    try:
        # Substitute field names with their values
        substituted = expr_str
        for field_name, value in field_values.items():
            # Use word boundaries to avoid partial matches
            pattern = re.escape(field_name) + r'(?![a-zA-Z0-9_\.])'
            substituted = re.sub(pattern, str(value), substituted)
        
        # Check if any field references remain (unresolved)
        remaining_fields = re.findall(r'_[a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z][a-zA-Z0-9_]*)*', substituted)
        if remaining_fields:
            return None  # Some fields couldn't be resolved
        
        # Parse and evaluate safely
        tree = ast.parse(substituted, mode='eval')
        return _eval_node(tree.body)
    except Exception:
        return None

def _eval_node(node):
    """Recursively evaluate an AST node for safe math expressions."""
    if isinstance(node, ast.Constant):  # Python 3.8+
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"Unsupported constant type: {type(node.value)}")
    elif isinstance(node, ast.Num):  # Python 3.7 compatibility
        return float(node.n)
    elif isinstance(node, ast.BinOp):
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            return SAFE_OPERATORS[op_type](left, right)
        raise ValueError(f"Unsupported operator: {op_type}")
    elif isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand)
        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            return SAFE_OPERATORS[op_type](operand)
        raise ValueError(f"Unsupported unary operator: {op_type}")
    elif isinstance(node, ast.Expression):
        return _eval_node(node.body)
    else:
        raise ValueError(f"Unsupported node type: {type(node)}")


class CIFField:
    """Class representing a CIF field definition."""
    def __init__(self, name, default_value, description="", action="CHECK", suggestions=None,
                 rename_to=None, expression=None, condition=None, then_fields=None):
        self.name = name
        self.default_value = default_value
        self.description = description
        self.action = action  # "CHECK", "DELETE", "EDIT", "APPEND", "RENAME", "CALCULATE", or "IF"
        self.suggestions = suggestions or []
        self.rename_to = rename_to  # Target field name for RENAME action
        self.expression = expression  # Mathematical expression for CALCULATE action
        self.condition = condition  # CIFCondition guarding an "IF" block
        self.then_fields = then_fields or []  # Nested rules run when the condition is true


class CIFCondition:
    """A single IF/IF NOT condition guarding a block of nested rules."""
    def __init__(self, field_name, operator, value=None):
        self.field_name = field_name
        self.operator = operator  # "exists", "not_exists", "equals", or "not_equals"
        self.value = value


def evaluate_condition(condition, get_field_value):
    """Evaluate a CIFCondition against the current CIF content.

    Args:
        condition: CIFCondition to evaluate
        get_field_value: callable(field_name) -> str value or None if the field is absent

    Returns:
        bool: whether the condition holds
    """
    current_value = get_field_value(condition.field_name)
    exists = current_value is not None

    if condition.operator == 'exists':
        return exists
    if condition.operator == 'not_exists':
        return not exists
    if not exists:
        # equals/not_equals require the field to be present; use "IF NOT:" for absence.
        return False

    clean_current = str(current_value).strip().strip("'\"")
    clean_target = str(condition.value).strip().strip("'\"") if condition.value is not None else ""

    if condition.operator == 'equals':
        return clean_current == clean_target
    if condition.operator == 'not_equals':
        return clean_current != clean_target
    return False

def _parse_condition_line(line):
    """Parse an 'IF: ...' or 'IF NOT: ...' condition line (with the trailing inline
    comment already stripped).

    Supported forms:
        IF: _field_name                # exists (field present, any value)
        IF: _field_name value          # field present and equal to value
        IF: _field_name != value       # field present and not equal to value
        IF NOT: _field_name            # field absent

    Returns:
        CIFCondition, or None if the line is malformed.
    """
    upper = line.upper()
    if upper.startswith('IF NOT:'):
        rest = line[len('IF NOT:'):].strip()
        field = rest.split(maxsplit=1)[0] if rest else ''
        if not field.startswith('_'):
            return None
        return CIFCondition(field, 'not_exists')

    if upper.startswith('IF:'):
        rest = line[len('IF:'):].strip()
        parts = rest.split(maxsplit=1)
        if not parts or not parts[0].startswith('_'):
            return None
        field = parts[0]
        condition_text = parts[1].strip() if len(parts) > 1 else ''

        if not condition_text:
            return CIFCondition(field, 'exists')
        if condition_text.startswith('!='):
            return CIFCondition(field, 'not_equals', condition_text[2:].strip())
        return CIFCondition(field, 'equals', condition_text)

    return None


def _strip_inline_comment(line):
    """Split a stripped line into (rule_text, inline_comment_description)."""
    if '#' in line:
        rule_text, comment_desc = line.split('#', 1)
        return rule_text.strip(), comment_desc.strip()
    return line, ""


def _report_issue(issues, line_no, message, field_name=None):
    """Record a structural/parse issue if the caller is collecting them."""
    if issues is not None:
        issues.append((line_no, message, field_name))


def _process_rule_line(line, comment_desc, descriptions, all_fields, check_agg, append_agg,
                        issues=None, line_no=None):
    """Parse a single non-blank, non-comment, non-block rule line and append the
    resulting CIFField(s) to all_fields, aggregating CHECK/APPEND entries via the
    supplied dicts.

    Lines that don't match any recognised form are silently dropped from
    all_fields (as before), but are now also reported via `issues` (a list of
    (line_no, message, field_name) tuples) when the caller supplies one, so
    malformed rules are surfaced instead of vanishing without a trace.
    """
    original_line = line
    # Detect action type (DELETE:, EDIT:, APPEND:, RENAME:, CALCULATE:, CHECK:, or bare = CHECK)
    action = "CHECK"
    if line.upper().startswith('CHECK:'):
        line = line[6:].strip()  # Remove optional explicit "CHECK:" prefix
    elif line.upper().startswith('DELETE:'):
        action = "DELETE"
        line = line[7:].strip()  # Remove "DELETE:" prefix
    elif line.upper().startswith('EDIT:'):
        action = "EDIT"
        line = line[5:].strip()  # Remove "EDIT:" prefix
    elif line.upper().startswith('APPEND:'):
        action = "APPEND"
        line = line[7:].strip()  # Remove "APPEND:" prefix
    elif line.upper().startswith('RENAME:'):
        line = line[7:].strip()  # Remove "RENAME:" prefix
        # RENAME expects: _old_name _new_name
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith('_') and parts[1].startswith('_'):
            field = parts[0]
            rename_to = parts[1]
            description = descriptions.get(field, comment_desc) or comment_desc
            field_obj = CIFField(field, "", description, "RENAME", [], rename_to)
            all_fields.append(field_obj)
        else:
            _report_issue(
                issues, line_no,
                f"Malformed RENAME '{original_line}' - expected 'RENAME: _old_name _new_name'; line skipped",
                parts[0] if parts else None,
            )
        return
    elif line.upper().startswith('CALCULATE:'):
        line = line[10:].strip()  # Remove "CALCULATE:" prefix
        # CALCULATE expects: _target_field = expression
        if '=' in line:
            field_part, expr_part = line.split('=', 1)
            field = field_part.strip()
            expression = expr_part.strip()
            if field.startswith('_') and expression:
                description = descriptions.get(field, comment_desc) or comment_desc
                field_obj = CIFField(field, "", description, "CALCULATE", [], None, expression)
                all_fields.append(field_obj)
            else:
                _report_issue(
                    issues, line_no,
                    f"Malformed CALCULATE '{original_line}' - expected 'CALCULATE: _field = expression'; line skipped",
                    field if field.startswith('_') else None,
                )
        else:
            _report_issue(
                issues, line_no,
                f"Malformed CALCULATE '{original_line}' - expected 'CALCULATE: _field = expression'; line skipped",
            )
        return

    # For DELETE action, we only need the field name
    if action == "DELETE":
        if line.startswith('_'):
            field = line
            description = descriptions.get(field, comment_desc) or comment_desc
            field_obj = CIFField(field, "", description, action, [])
            all_fields.append(field_obj)
        else:
            _report_issue(
                issues, line_no,
                f"Malformed DELETE '{original_line}' - expected 'DELETE: _field_name'; line skipped",
            )
        return

    # For CHECK and EDIT actions, we need field and value
    parts = line.split(maxsplit=1)
    if len(parts) < 1:
        _report_issue(issues, line_no, f"Empty {action} rule '{original_line}'; line skipped")
        return
    elif len(parts) == 1:
        field = parts[0]
        value = ""
    else:
        field, value = parts

    # Skip if not a valid field name
    if not field.startswith('_'):
        _report_issue(
            issues, line_no,
            f"'{original_line}' does not look like a CIF field name (must start with '_'); line skipped",
        )
        return

    description = descriptions.get(field, comment_desc) or comment_desc

    # Add options to description if present in comments
    if description and 'options:' in description.lower():
        options_idx = description.lower().find('options:')
        options_text = description[options_idx:].strip()
        description = f"{description[:options_idx].strip()}\n{options_text}"

    # Aggregate repeated CHECK entries as suggestions for dropdowns;
    # aggregate repeated APPEND entries by concatenation.
    # All other action types (EDIT, RENAME, DELETE, CALCULATE) are kept
    # as distinct ordered entries so rules are processed sequentially.
    if action == "CHECK" and field in check_agg:
        existing = check_agg[field]
        if value and value not in existing.suggestions:
            existing.suggestions.append(value)
        if not existing.default_value and value:
            existing.default_value = value
        if not existing.description and description:
            existing.description = description
    elif action == "APPEND" and field in append_agg:
        # Aggregate multiple APPEND entries for the same field
        existing = append_agg[field]
        if value:
            # Concatenate with blank line separator
            if existing.default_value:
                existing.default_value += "\n\n" + value
            else:
                existing.default_value = value
    else:
        suggestions = [value] if value else []
        field_obj = CIFField(field, value, description, action, suggestions)
        all_fields.append(field_obj)
        if action == "CHECK":
            check_agg[field] = field_obj
        elif action == "APPEND":
            append_agg[field] = field_obj


def _parse_rule_lines(raw_lines, start_index, num_lines, descriptions, nested, issues=None):
    """Parse rule lines starting at start_index, expanding IF:/IF NOT: ... ENDIF
    blocks recursively (so blocks may be nested to any depth).

    Args:
        raw_lines: full file, as a list of raw (unstripped) lines
        start_index: index to start parsing from
        num_lines: len(raw_lines), passed in to avoid recomputing at each level
        descriptions: field_name -> description, collected in the first pass
        nested: True when parsing the body of an IF block (so a bare ENDIF line
            closes and returns from this call); False for the top-level file
            scope, which has no ENDIF to find and simply runs to EOF
        issues: optional list collecting (line_no, message, field_name) tuples
            for anything malformed/dropped, so problems can be surfaced to the
            user instead of silently vanishing

    Returns:
        (fields, next_index, closed) where fields is the list of CIFField
        objects parsed at this level (IF fields carry their nested body in
        then_fields), next_index is where the caller should resume scanning,
        and closed is False only when nested is True and EOF was reached
        without a matching ENDIF (the caller discards the block in that case).
    """
    fields = []
    check_agg = {}   # field_name -> CIFField, aggregation scoped to this block/level
    append_agg = {}
    i = start_index

    while i < num_lines:
        line = raw_lines[i].strip()
        i += 1
        line_no = i

        if not line or line.startswith('#') or line.startswith('//'):
            continue

        line, comment_desc = _strip_inline_comment(line)
        if not line:
            continue

        upper = line.upper()

        if upper == 'ENDIF':
            if nested:
                return fields, i, True
            _report_issue(issues, line_no, "Stray 'ENDIF' with no matching IF/IF NOT; line ignored")
            continue  # Stray ENDIF at top level with no matching IF; ignore

        if upper.startswith('IF:') or upper.startswith('IF NOT:'):
            condition = _parse_condition_line(line)
            if condition is None:
                # Malformed condition: still consume and discard the block body
                # (if any) so it can't silently leak into the outer scope and
                # run unconditionally - a guarded rule that fails to parse its
                # guard must never fall back to "always run".
                _discarded, i, _closed = _parse_rule_lines(
                    raw_lines, i, num_lines, descriptions, nested=True, issues=issues
                )
                _report_issue(
                    issues, line_no,
                    f"Malformed condition '{line}' - IF/IF NOT requires a field name "
                    "starting with '_'; the block was skipped",
                )
                continue

            then_fields, i, closed = _parse_rule_lines(
                raw_lines, i, num_lines, descriptions, nested=True, issues=issues
            )
            if not closed:
                _report_issue(
                    issues, line_no,
                    f"IF block '{line}' has no matching ENDIF; the block and its "
                    "nested rules were skipped",
                    condition.field_name,
                )
                return fields, i, not nested

            description = descriptions.get(condition.field_name, comment_desc) or comment_desc
            if_field = CIFField(
                condition.field_name, "", description, "IF", [],
                condition=condition, then_fields=then_fields
            )
            fields.append(if_field)
            continue

        _process_rule_line(
            line, comment_desc, descriptions, fields, check_agg, append_agg,
            issues=issues, line_no=line_no
        )

    return fields, i, not nested


def load_cif_field_rules(filepath):
    """Load CIF field rules from a CIF-style file.

    The file format is CIF-like with each line having:
    _field_name value # description
    or
    # _field_name: description
    _field_name value

    Special actions can be specified with prefixes:
    DELETE: _field_name  # This will remove the field entirely
    EDIT: _field_name new_value  # This will replace the field's value
    APPEND: _field_name append_text  # This will append text to existing multiline value
    RENAME: _old_name _new_name  # This will rename a field to a new name
    CALCULATE: _field = expression  # Calculate field value from expression using other fields
    _field_name value  # Normal check (default behavior)

    Conditional blocks run a set of nested rules only when a condition holds, and may
    be nested inside one another to any depth:
    IF: _field_name                    # condition: field exists
    IF: _field_name value              # condition: field exists and equals value
    IF: _field_name != value           # condition: field exists and differs from value
    IF NOT: _field_name                # condition: field is absent
        CHECK: _other_field value      # nested rule(s), same syntax as top-level rules
        EDIT: _another_field value
        IF: _yet_another_field value   # blocks may nest inside a THEN body
            CHECK: _deeply_nested_field value
        ENDIF
    ENDIF

    Values can be quoted or unquoted. The function preserves the quotation style.
    Comments starting with # can contain field descriptions.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return parse_field_rules_content(content, print_warnings=True)
    except Exception as e:
        print(f"Error loading CIF field definitions: {e}")
        return []


def parse_field_rules_content(content, issues=None, print_warnings=False):
    """Parse already-read .cif_rules content into a list of CIFField.

    This is the content-string counterpart to load_cif_field_rules(), for
    callers that have text in hand rather than a file on disk (e.g. a
    validator checking unsaved manual-editor content). See
    load_cif_field_rules() for the supported rule syntax.

    Args:
        content: the .cif_rules file content
        issues: optional list that malformed/dropped lines are appended to,
            as (line_no, message, field_name) tuples - use this to surface
            problems that would otherwise silently vanish (e.g. an IF block
            missing its ENDIF, which the loader discards entirely)
        print_warnings: if True, also print() unclosed-block warnings (kept
            for load_cif_field_rules()'s existing console-warning behavior)

    Returns:
        List of CIFField.
    """
    descriptions = {}

    # First pass: collect descriptions from comments
    for line in content.splitlines():
        line = line.strip()
        # Description on its own line
        if line.startswith('#'):
            parts = line[1:].strip().split(':', 1)
            if len(parts) == 2 and parts[0].strip().startswith('_'):
                field_name = parts[0].strip()
                descriptions[field_name] = parts[1].strip()
        # Description at end of line
        elif '#' in line and not line.startswith('//'):
            value_part, comment_part = line.split('#', 1)
            if value_part.strip().startswith('_'):
                field_name = value_part.split()[0].strip()
                descriptions[field_name] = comment_part.strip()

    # Second pass: collect field definitions, aggregate suggestions, and expand
    # (possibly nested) IF: / IF NOT: ... ENDIF blocks.
    raw_lines = content.splitlines()

    if not print_warnings:
        all_fields, _, _ = _parse_rule_lines(raw_lines, 0, len(raw_lines), descriptions, nested=False, issues=issues)
        return all_fields

    # load_cif_field_rules() has always print()-ed unclosed-block warnings to
    # the console; preserve that by capturing issues regardless of what the
    # caller passed and printing the unclosed-block ones after the fact.
    local_issues = [] if issues is None else issues
    before = len(local_issues)
    all_fields, _, _ = _parse_rule_lines(raw_lines, 0, len(raw_lines), descriptions, nested=False, issues=local_issues)
    for _line_no, message, _field_name in local_issues[before:]:
        if "no matching ENDIF" in message:
            print(f"Warning: {message}")
    return all_fields


class CIFFieldChecker:
    """Class that manages CIF field checking with support for multiple field sets."""
    
    def __init__(self):
        self.field_sets = {}
        
    def load_field_set(self, name, filepath):
        """Load a named set of field rules from a file."""
        fields = load_cif_field_rules(filepath)
        if fields:
            self.field_sets[name] = fields
            return True
        return False
    
    def get_field_set(self, name):
        """Get a list of fields for a named set."""
        return self.field_sets.get(name, [])

    def apply_field_operations(self, text_content, field_set_name):
        """Apply DELETE, EDIT, and RENAME operations to CIF content.
        
        Args:
            text_content (str): The CIF file content
            field_set_name (str): Name of the field set to apply
            
        Returns:
            tuple: (modified_content, operations_applied)
        """
        fields = self.get_field_set(field_set_name)
        if not fields:
            return text_content, []
        
        lines = text_content.splitlines()
        operations_applied = []
        
        for field_def in fields:
            if field_def.action == "DELETE":
                lines, deleted = self._delete_field(lines, field_def.name)
                if deleted:
                    operations_applied.append(f"DELETED: {field_def.name}")
            elif field_def.action == "EDIT":
                lines, edited = self._edit_field(lines, field_def.name, field_def.default_value)
                if edited:
                    operations_applied.append(f"EDITED: {field_def.name} -> {field_def.default_value}")
            elif field_def.action == "RENAME":
                lines, renamed = self._rename_field(lines, field_def.name, field_def.rename_to)
                if renamed:
                    operations_applied.append(f"RENAMED: {field_def.name} -> {field_def.rename_to}")
        
        return '\n'.join(lines), operations_applied
    
    def _delete_field(self, lines, field_name):
        """Delete a field from the CIF content.
        
        Args:
            lines (list): List of lines in the CIF file
            field_name (str): Name of field to delete
            
        Returns:
            tuple: (modified_lines, was_deleted)
        """
        modified_lines = []
        deleted = False
        
        for line in lines:
            if line.strip().startswith(field_name):
                # Skip this line (delete it)
                deleted = True
                continue
            modified_lines.append(line)
        
        return modified_lines, deleted
    
    def _edit_field(self, lines, field_name, new_value):
        """Edit a field's value in the CIF content.
        
        Args:
            lines (list): List of lines in the CIF file
            field_name (str): Name of field to edit
            new_value (str): New value for the field
            
        Returns:
            tuple: (modified_lines, was_edited)
        """
        modified_lines = []
        edited = False
        
        for line in lines:
            if line.strip().startswith(field_name):
                # Replace the line with new value
                if new_value:
                    modified_lines.append(f"{field_name}    {new_value}")
                else:
                    # If new_value is empty, skip the line (same as delete)
                    edited = True
                    continue
                edited = True
            else:
                modified_lines.append(line)
        
        return modified_lines, edited
    
    def _append_field(self, lines, field_name, append_text):
        """Append text to a multiline field's value in the CIF content.

        Skips the append if the text to add is already present in the existing
        field value (case-insensitive, whitespace-normalised comparison), so
        running the same rules file twice never duplicates content.

        Args:
            lines (list): List of lines in the CIF file
            field_name (str): Name of field to append to
            append_text (str): Text to append (will be added with blank line separator)

        Returns:
            tuple: (modified_lines, was_appended)
        """
        modified_lines = []
        appended = False
        i = 0

        while i < len(lines):
            line = lines[i]

            # Check if this is the target field with semicolon delimiter
            if line.strip().startswith(field_name):
                # Check if it's a multiline value starting with semicolon
                if i + 1 < len(lines) and lines[i + 1].strip() == ';':
                    # Add field name and opening semicolon
                    modified_lines.append(line)
                    modified_lines.append(lines[i + 1])
                    i += 2

                    # Collect existing body content until closing semicolon
                    body_lines = []
                    closing_line = None
                    while i < len(lines):
                        if lines[i].strip() == ';':
                            closing_line = lines[i]
                            i += 1
                            break
                        else:
                            body_lines.append(lines[i])
                            i += 1

                    # Check whether append_text is already present
                    existing_body = '\n'.join(body_lines)
                    already_present = (
                        ' '.join(append_text.split()).lower()
                        in ' '.join(existing_body.split()).lower()
                    )

                    # Write body back out
                    modified_lines.extend(body_lines)

                    if not already_present:
                        # Insert the new content before the closing semicolon
                        modified_lines.append('')  # Blank line separator
                        modified_lines.append(append_text)
                        appended = True

                    if closing_line is not None:
                        modified_lines.append(closing_line)
                    continue
                else:
                    # Not a multiline field - just copy as-is
                    modified_lines.append(line)
            else:
                modified_lines.append(line)

            i += 1

        return modified_lines, appended

    def _rename_field(self, lines, old_name, new_name):
        """Rename a field in the CIF content.
        
        This is used to correct erroneously named fields output by some programs.
        For example, Olex2 outputs _refine_diff_density_max for 3D ED data,
        but the correct name should be _refine_diff.potential_max.
        
        Args:
            lines (list): List of lines in the CIF file
            old_name (str): Current (incorrect) field name
            new_name (str): Correct field name to rename to
            
        Returns:
            tuple: (modified_lines, was_renamed)
        """
        import re
        modified_lines = []
        renamed = False
        i = 0
        
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Check for exact field name match (including loop columns)
            # Match the old field name at the start of the line
            if stripped.startswith(old_name):
                # Get the rest after the field name
                rest = stripped[len(old_name):]
                # Check it's a complete field name (followed by whitespace, value, or end of line)
                if rest == '' or rest[0] in ' \t':
                    # Preserve leading whitespace
                    leading_ws = line[:len(line) - len(line.lstrip())]
                    # Replace old name with new name
                    new_line = leading_ws + new_name + rest
                    modified_lines.append(new_line)
                    renamed = True
                    i += 1
                    continue
            
            modified_lines.append(line)
            i += 1
        
        return modified_lines, renamed
