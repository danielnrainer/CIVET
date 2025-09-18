"""
Dictionary Suggestion Manager for CIF Checker

This module analyzes CIF content and suggests relevant COMCIFS dictionaries
based on field patterns that indicate specialized structure types.
"""

from typing import Dict, List, Tuple, Set, Optional
import re
from dataclasses import dataclass


@dataclass
class DictionarySuggestion:
    """Represents a suggested dictionary to load."""
    name: str
    description: str
    url: str
    local_file: Optional[str] = None
    trigger_fields: List[str] = None
    confidence: float = 1.0


class DictionarySuggestionManager:
    """
    Analyzes CIF content and suggests relevant COMCIFS dictionaries.
    
    This system detects specialized CIF field patterns and suggests appropriate
    dictionaries to enhance validation and field recognition.
    """
    
    def __init__(self):
        """Initialize with predefined dictionary suggestions."""
        self._suggestions = self._initialize_suggestions()
        
    def _initialize_suggestions(self) -> Dict[str, DictionarySuggestion]:
        """Initialize the dictionary of available suggestions."""
        return {
            'modulated': DictionarySuggestion(
                name="Modulated Structures Dictionary",
                description="Dictionary for modulated and superspace group structures",
                url="https://raw.githubusercontent.com/COMCIFS/Modulated_Structures/refs/heads/main/cif_ms.dic",
                trigger_fields=[
                    "_cell_modulation_dimension",      # CIF1 format
                    "_cell.modulation_dimension",      # CIF2 format
                    "_cell_wave_vector_seq_id",        # CIF1
                    "_cell.wave_vector_seq_id",        # CIF2
                    "_space_group_ssg_name",           # CIF1
                    "_space_group.ssg_name"            # CIF2
                ]
            ),
            
            'powder': DictionarySuggestion(
                name="Powder Diffraction Dictionary",
                description="Dictionary for powder diffraction data and refinement",
                url="https://raw.githubusercontent.com/COMCIFS/Powder_Dictionary/refs/heads/master/cif_pow.dic",
                trigger_fields=[
                    "_pd_meas_2theta_range_min",       # CIF1
                    "_pd_meas.2theta_range_min",       # CIF2
                    "_pd_proc_2theta_range_min",       # CIF1
                    "_pd_proc.2theta_range_min",       # CIF2
                    "_pd_phase_name",                  # CIF1
                    "_pd_phase.name"                   # CIF2
                ]
            ),
            
            'magnetic': DictionarySuggestion(
                name="Magnetic Structure Dictionary", 
                description="Dictionary for magnetic structures and properties",
                url="https://raw.githubusercontent.com/COMCIFS/magnetic_dic/refs/heads/main/cif_mag.dic",
                trigger_fields=[
                    "_atom_site_moment_label",         # CIF1
                    "_atom_site.moment_label",         # CIF2
                    "_space_group_magn_name_BNS",      # CIF1
                    "_space_group.magn_name_BNS",      # CIF2
                    "_cell_magnetic_transform_Pp",     # CIF1
                    "_cell.magnetic_transform_Pp"      # CIF2
                ]
            ),
            
            'twinning': DictionarySuggestion(
                name="Twinning Dictionary",
                description="Dictionary for twinned crystal structures",
                url="https://raw.githubusercontent.com/COMCIFS/Twinning_Dictionary/refs/heads/main/cif_twin.dic",
                local_file="dictionaries/cif_twin.dic",
                trigger_fields=[
                    "_twin_individual_id",             # CIF1
                    "_twin.individual_id",             # CIF2
                    "_twin_individual_mass_fraction_refined", # CIF1
                    "_twin.individual_mass_fraction_refined", # CIF2
                ]
            ),
            
        #     'electron_diffraction': DictionarySuggestion(
        #         name="Electron Diffraction Dictionary",
        #         description="Dictionary for electron diffraction experiments",
        #         url="https://raw.githubusercontent.com/COMCIFS/cif_core/master/cif_emd.dic",
        #         trigger_fields=[

        #         ]
        #     )
        }
    
    def analyze_cif_content(self, cif_content: str) -> List[DictionarySuggestion]:
        """
        Analyze CIF content and return suggested dictionaries.
        
        Args:
            cif_content: CIF file content as string
            
        Returns:
            List of DictionarySuggestion objects for relevant dictionaries
        """
        # Extract all fields from CIF content (excluding text blocks)
        fields = self._extract_fields_excluding_text_blocks(cif_content)
        
        suggestions = []
        for suggestion_key, suggestion in self._suggestions.items():
            # Check if any trigger fields are present
            matching_fields = []
            for trigger_field in suggestion.trigger_fields:
                if trigger_field in fields:
                    matching_fields.append(trigger_field)
            
            if matching_fields:
                # Calculate confidence based on number of matching fields
                confidence = min(1.0, len(matching_fields) / len(suggestion.trigger_fields) * 2)
                suggestion_copy = DictionarySuggestion(
                    name=suggestion.name,
                    description=suggestion.description,
                    url=suggestion.url,
                    local_file=suggestion.local_file,
                    trigger_fields=matching_fields,  # Only include matched fields
                    confidence=confidence
                )
                suggestions.append(suggestion_copy)
        
        # Sort by confidence (highest first)
        suggestions.sort(key=lambda x: x.confidence, reverse=True)
        return suggestions
    
    def _extract_fields_excluding_text_blocks(self, cif_content: str) -> Set[str]:
        """
        Extract field names from CIF content, excluding those within text blocks.
        
        Args:
            cif_content: CIF file content as string
            
        Returns:
            Set of field names found outside text blocks
        """
        # Remove text blocks (semicolon-delimited content) first
        text_block_pattern = r';[^;]*?;'
        content_without_text_blocks = re.sub(text_block_pattern, '', cif_content, flags=re.DOTALL)
        
        # Extract all field names using regex
        field_pattern = r'(_[a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)*)'
        field_matches = re.findall(field_pattern, content_without_text_blocks)
        
        # Return unique fields as a set
        return set(field_matches)
    
    def detect_cif_format(self, cif_content: str) -> str:
        """
        Detect whether CIF content is in CIF1 or CIF2 format.
        
        Args:
            cif_content: CIF file content as string
            
        Returns:
            'CIF1' or 'CIF2' based on field naming patterns
        """
        fields = self._extract_fields_excluding_text_blocks(cif_content)
        
        # Count CIF2-style fields (with dots) vs CIF1-style fields (underscores only)
        cif2_fields = sum(1 for field in fields if '.' in field)
        cif1_fields = len(fields) - cif2_fields
        
        # If significant number of dotted fields, assume CIF2
        if cif2_fields > 0 and cif2_fields >= cif1_fields * 0.3:
            return 'CIF2'
        else:
            return 'CIF1'
    
    def get_format_appropriate_triggers(self, cif_format: str) -> Dict[str, List[str]]:
        """
        Get trigger fields appropriate for the detected CIF format.
        
        Args:
            cif_format: 'CIF1' or 'CIF2'
            
        Returns:
            Dictionary mapping suggestion keys to format-appropriate trigger fields
        """
        result = {}
        for key, suggestion in self._suggestions.items():
            if cif_format == 'CIF1':
                # Filter for CIF1-style fields (no dots)
                triggers = [f for f in suggestion.trigger_fields if '.' not in f]
            else:
                # Filter for CIF2-style fields (with dots)
                triggers = [f for f in suggestion.trigger_fields if '.' in f]
            
            if triggers:  # Only include if there are appropriate triggers
                result[key] = triggers
        
        return result
    
    def add_custom_suggestion(self, key: str, suggestion: DictionarySuggestion) -> None:
        """
        Add a custom dictionary suggestion.
        
        Args:
            key: Unique identifier for the suggestion
            suggestion: DictionarySuggestion object
        """
        self._suggestions[key] = suggestion
    
    def get_suggestion_summary(self, suggestions: List[DictionarySuggestion]) -> str:
        """
        Generate a human-readable summary of dictionary suggestions.
        
        Args:
            suggestions: List of DictionarySuggestion objects
            
        Returns:
            Formatted string summary
        """
        if not suggestions:
            return "No specialized dictionaries suggested for this CIF file."
        
        summary = "Suggested dictionaries based on CIF content:\n\n"
        for i, suggestion in enumerate(suggestions, 1):
            summary += f"{i}. {suggestion.name}\n"
            summary += f"   {suggestion.description}\n"
            summary += f"   Confidence: {suggestion.confidence:.1%}\n"
            summary += f"   Triggered by fields: {', '.join(suggestion.trigger_fields[:3])}\n"
            if len(suggestion.trigger_fields) > 3:
                summary += f"   (and {len(suggestion.trigger_fields) - 3} more)\n"
            summary += "\n"
        
        return summary