"""
CIF2-Only Field Extension for CIF Dictionary Manager
====================================================

Extends the CIF dictionary manager to handle CIF2-only fields that exist in the 
official cif_core.dic but have no CIF1 aliases defined. These fields are typically
newer additions to the CIF standard that were introduced with CIF2.

This addresses the issue where legitimate CIF2 fields like:
- _refine.diffraction_theory
- _diffrn_measurement.rotation_mode

exist in the official dictionary but cannot be converted to CIF1 format because
they have no official CIF1 equivalents. This module provides reasonable CIF1
equivalents to prevent data loss during format conversion.
"""

import os
from typing import Dict, List, Optional

# CIF2-only field mappings
# Maps CIF2 format -> CIF1 format for fields that exist in the official dictionary
# but have no CIF1 aliases defined (CIF2-only fields)
CIF2_ONLY_FIELD_MAPPINGS = {
    # Refinement fields (CIF2-only, no CIF1 alias in dictionary)
    '_refine.diffraction_theory': '_refine_diffraction_theory',
    '_refine.diffraction_theory_details': '_refine_diffraction_theory_details',
    '_refine_diff.potential_max': '_refine_diff_potential_max',
    '_refine_diff.potential_min': '_refine_diff_potential_min',
    '_refine_diff.potential_RMS': '_refine_diff_potential_RMS',
    '_refine_ls.abs_structure_z-score': '_refine_ls_abs_structure_z-score',
    '_refine_ls.sample_thickness': '_refine_ls_sample_thickness',
    '_refine_ls.sample_shape_expression': '_refine_ls_sample_shape_expression',
    '_refine_ls.sample_shape_details': '_refine_ls_sample_shape_details',
    
    # Measurement fields (CIF2-only, no CIF1 alias in dictionary)
    '_diffrn_measurement.method_precession': '_diffrn_measurement_method_precession',
    '_diffrn_measurement.rotation_mode': '_diffrn_measurement_rotation_mode',
    '_diffrn_measurement.sample_tracking': '_diffrn_measurement_sample_tracking',
    '_diffrn_measurement.sample_tracking_method': '_diffrn_measurement_sample_tracking_method',
    # Source fields (for electron diffraction applications)
    '_diffrn_source.convergence_angle': '_diffrn_source_convergence_angle',
    '_diffrn_source.device': '_diffrn_source',
    '_diffrn_source.ed_diffracting_area_selection': '_diffrn_source_ed_diffracting_area_selection',
    # Radiation and illumination fields
    '_diffrn_radiation.illumination_mode': '_diffrn_radiation_illumination_mode',
    # Precession fields
    '_diffrn.precession_semi_angle': '_diffrn_precession_semi_angle',
    
    # Computing fields
    '_computing.sample_tracking': '_computing_sample_tracking',
    
    # Experimental fields
    '_exptl_crystal.mosaicity': '_exptl_crystal_mosaicity',
    '_exptl_crystal.mosaic_method': '_exptl_crystal_mosaic_method',
    '_exptl_crystal.mosaic_block_size': '_exptl_crystal_mosaic_block_size',
    
    # Flux and dose fields
    '_diffrn.flux_density': '_diffrn_flux_density',
    '_diffrn.total_dose': '_diffrn_total_dose',
    '_diffrn.total_exposure_time': '_diffrn_total_exposure_time',
}

# Reverse mappings (CIF1 -> CIF2)
CIF2_ONLY_REVERSE_MAPPINGS = {v: k for k, v in CIF2_ONLY_FIELD_MAPPINGS.items()}


class ExtendedCIFDictionaryManager:
    """
    Extended CIF Dictionary Manager that includes CIF2-only field support.
    
    This class wraps the standard CIFDictionaryManager and adds support for
    CIF2-only fields that exist in the official dictionary but have no CIF1
    aliases defined.
    """
    
    def __init__(self, base_manager):
        """Initialize with a base dictionary manager"""
        self.base_manager = base_manager
        self.cif2_only_extensions = CIF2_ONLY_FIELD_MAPPINGS
        self.cif2_only_reverse = CIF2_ONLY_REVERSE_MAPPINGS
    
    def get_cif2_equivalent(self, field_name: str) -> Optional[str]:
        """
        Get CIF2 equivalent of a field name, including ED extensions.
        
        Args:
            field_name: CIF1 field name
            
        Returns:
            CIF2 equivalent or None if not found
        """
        # First try the official dictionary
        result = self.base_manager.get_cif2_equivalent(field_name)
        if result:
            return result
        
        # Check CIF2-only field extensions
        return self.cif2_only_reverse.get(field_name)
    
    def get_cif1_equivalent(self, field_name: str) -> Optional[str]:
        """
        Get CIF1 equivalent of a field name, including CIF2-only field extensions.
        
        Args:
            field_name: CIF2 field name
            
        Returns:
            CIF1 equivalent or None if not found
        """
        # First try the official dictionary
        result = self.base_manager.get_cif1_equivalent(field_name)
        if result:
            return result
        
        # Check CIF2-only field extensions
        return self.cif2_only_extensions.get(field_name)
    
    def is_known_field(self, field_name: str) -> bool:
        """
        Check if field is known (official dictionary + ED extensions).
        
        Args:
            field_name: Field name to check
            
        Returns:
            True if field is known
        """
        # Check official dictionary first
        if self.base_manager.is_known_field(field_name):
            return True
        
        # Check CIF2-only extensions
        return (field_name in self.cif2_only_extensions or 
                field_name in self.cif2_only_reverse)
    
    def is_cif2_only_extension(self, field_name: str) -> bool:
        """
        Check if field is a CIF2-only extension (not in official dictionary).
        
        Args:
            field_name: Field name to check
            
        Returns:
            True if field is a CIF2-only extension
        """
        return (field_name in self.cif2_only_extensions or 
                field_name in self.cif2_only_reverse)
    
    def get_field_status(self, field_name: str) -> str:
        """
        Get status of a field: 'official', 'cif2_only_extension', or 'unknown'.
        
        Args:
            field_name: Field name to check
            
        Returns:
            Status string
        """
        if self.base_manager.is_known_field(field_name):
            return 'official'
        elif self.is_cif2_only_extension(field_name):
            return 'cif2_only_extension'
        else:
            return 'unknown'
    
    # Delegate other methods to base manager
    def __getattr__(self, name):
        return getattr(self.base_manager, name)