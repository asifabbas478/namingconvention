import os
import sys
import pandas as pd
from io import StringIO

# Add the parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from utils.error_handler import handle_error, logger
from utils.validation_constants import EQUIPMENT_TYPES, EQUIPMENT_CLASSES

def validate_equipment_data(df, source_data):
    """Validate equipment types and classes in the dataframe"""
    errors = []
    
    # Convert sets to case-insensitive for comparison
    valid_types = {t.lower().strip() for t in EQUIPMENT_TYPES}
    valid_classes = {c.lower().strip() for c in EQUIPMENT_CLASSES}
    
    # Check equipment class (Asset System)
    for idx, row in source_data.iterrows():
        asset_system = row['Asset System']
        if pd.notna(asset_system) and asset_system != 'Mandatory':
            if asset_system.lower().strip() not in valid_classes:
                errors.append(f"Row {idx + 2}: Invalid equipment class '{asset_system}' in Asset System column")
    
    # Check equipment type (Asset / Equipment)
    for idx, row in source_data.iterrows():
        asset_equipment = row['Asset / Equipment']
        if pd.notna(asset_equipment) and asset_equipment != 'Mandatory':
            if asset_equipment.lower().strip() not in valid_types:
                errors.append(f"Row {idx + 2}: Invalid equipment type '{asset_equipment}' in Asset/Equipment column")
    
    return errors

@handle_error
def process_equipment_data(asset_location_file, equipment_template, namespace):
    """Process equipment data"""
    logger.info("Starting equipment data processing")
    
    # Load data
    asset_location_data = pd.read_excel(asset_location_file, sheet_name='Asset,location')
    template_data = pd.read_csv(equipment_template)
    
    # Extract unique equipment data
    unique_data = asset_location_data[
        ['Barcode', 'Asset System', 'Asset / Equipment', 'Asset Criticality', 'Sublocation']
    ].drop_duplicates()
    
    # Filter valid data
    valid_data = unique_data[
        (unique_data['Asset System'].notna() | unique_data['Asset / Equipment'].notna()) &
        (unique_data['Asset System'] != 'Mandatory') &
        (unique_data['Asset / Equipment'] != 'Mandatory')
    ]
    
    # Validate equipment data before processing
    validation_errors = validate_equipment_data(template_data, valid_data)
    
    if validation_errors:
        # Create error log file content
        error_log = "\n".join([
            "Equipment Validation Errors:",
            "========================",
            *validation_errors,
            "\nNote: Row numbers include header row. Actual Excel row numbers may be different."
        ])
        
        # Create StringIO object with error log
        error_file = StringIO()
        error_file.write(error_log)
        error_file.seek(0)
        
        logger.warning(f"Found {len(validation_errors)} validation errors in equipment data")
        return None, error_file
    
    # Create new equipment data
    new_equipment_data = pd.DataFrame({
        'barcode': valid_data['Barcode'].reset_index(drop=True),
        'name*': valid_data.apply(
            lambda x: x['Asset / Equipment'] if pd.notna(x['Asset / Equipment']) else x['Asset System'],
            axis=1
        ).reset_index(drop=True),
        'type': valid_data['Asset / Equipment'].reset_index(drop=True),  # Equipment Type
        'class': valid_data['Asset System'].reset_index(drop=True),      # Equipment Class
        'criticality': valid_data['Asset Criticality'].reset_index(drop=True),
        'space name': valid_data['Sublocation'].reset_index(drop=True),
        'namespace*': namespace,
        'isActive*': True
    })
    
    # Merge with template
    template_data_cleaned = template_data.iloc[1:]
    updated_equipment_data = pd.concat([template_data_cleaned, new_equipment_data], ignore_index=True)
    
    logger.info(f"Processed {len(new_equipment_data)} equipment records successfully")
    return updated_equipment_data, None
