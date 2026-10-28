from utils.CIF_parser import iter_structural_lines

def is_in_deprecated_section(content:str, line_num:int) -> bool:
        """Check if a line is within a deprecated section of the CIF file."""
        lines = content.splitlines()

        # Find the deprecated section boundaries
        deprecated_section_start = None
        deprecated_section_end = None

        for i in range(len(lines)):
            line = lines[i].strip()
            if "# DEPRECATED FIELDS" in line:
                deprecated_section_start = i
                # Look for the end of this section (closing ###... line)
                for j in range(i + 1, len(lines)):
                    end_line = lines[j].strip()
                    if end_line.startswith('#') and len(end_line) > 70 and all(c == '#' for c in end_line):
                        # Check if this is actually a closing border
                        if j + 1 < len(lines):
                            next_line = lines[j + 1].strip()
                            if not next_line or next_line.startswith('data_'):
                                deprecated_section_end = j
                                break
                        else:
                            # End of file
                            deprecated_section_end = j
                            break
                break

        # Check if our target line is within the deprecated section
        if deprecated_section_start is not None:
            end_line = deprecated_section_end if deprecated_section_end is not None else len(lines) - 1
            target_line_index = line_num - 1  # Convert to 0-based indexing
            return deprecated_section_start <= target_line_index <= end_line

        return False

def filter_conflicts(conflicts:dict[str,str] ,content:str ,lines: list[str]) -> dict[str,str]:
    """ Filters a list of conflicts (i.e a dictionary of field_names and their prsent aliases) to identify
        duplicated or aliased fields that are actually present in the non deperecated section of the cif file

        Returns:
        filtered_conflicts: dict - 
                           Dictionary of conflicts, with field names as keys, and present duplciates or aliases 
                           of those field names as values"""
    filtered_conflicts={}
    for canonical, alias_list in conflicts.items():
                # Check if this conflict involves fields that are in both main and deprecated sections
                main_section_fields = []
                deprecated_section_fields = []

                for alias in alias_list:
                    # Find this field in the content
                    field_in_deprecated = False
                    for idx, line in iter_structural_lines(lines):
                        line_num = idx + 1
                        line_stripped = line.strip()
                        if line_stripped.startswith(alias + ' ') or line_stripped.startswith(alias + '\t'):
                            if is_in_deprecated_section(content, line_num):
                                deprecated_section_fields.append(alias)
                                field_in_deprecated = True
                                break

                    if not field_in_deprecated:
                        # Check if field exists in main section
                        for idx, line in iter_structural_lines(lines):
                            line_num = idx + 1
                            line_stripped = line.strip()
                            if line_stripped.startswith(alias + ' ') or line_stripped.startswith(alias + '\t'):
                                if not is_in_deprecated_section(content, line_num):
                                    main_section_fields.append(alias)
                                    break

                # Only report as conflict if:
                # 1. Multiple fields in main section, OR
                # 2. Multiple fields in deprecated section, OR
                # 3. Fields only in one section but duplicated
                if (len(main_section_fields) > 1 or len(deprecated_section_fields) > 1 or
                    (len(main_section_fields) == 0 and len(deprecated_section_fields) > 0) or
                    (len(main_section_fields) > 0 and len(deprecated_section_fields) == 0)):
                    filtered_conflicts[canonical] = alias_list
                # If we have one field in main and one in deprecated, this is by design, not a conflict

    conflicts = filtered_conflicts
    return conflicts

def detail_conflicts(conflicts:dict[str,str], lines:list[str], dict_manager:"DictManager") -> dict[str,dict[str or int or bool]]:
    """ Takes a dictionary of conflicts (i.e a dictionary of field_names and their present duplicates/aliases) and gathers useful
        information for reporting the issue - such as line numbers and the values seen in each case

        Returns:
        detailed_conflicts: dict -
                           Dictionary of conflicts, with field names as keys, and values being dictionaries, containing important 
                           details for error reporting"""

    detailed_conflicts = {}
    for canonical, alias_list in conflicts.items():
        detailed_conflicts[canonical] = []
        for alias in set(alias_list):
            # Find line number and value for this alias
            for idx, line in iter_structural_lines(lines):
                line_num = idx + 1
                line_stripped = line.strip()
                if line_stripped.startswith(alias + ' ') or line_stripped.startswith(alias + '\t'):
                    # Extract value
                    parts = line_stripped.split(None, 1)
                    value = parts[1] if len(parts) > 1 else ''
                            
                    detailed_conflicts[canonical].append({
                      'line_num': line_num,
                      'alias': alias,
                      'value': value,
                      'is_deprecated': dict_manager.is_field_deprecated(alias)
                       })
                # Sort found duplicate entries by line number
        detailed_conflicts[canonical]=sorted(detailed_conflicts[canonical],key=lambda k : k['line_num'])
    return detailed_conflicts
