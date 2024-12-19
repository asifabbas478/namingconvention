import streamlit as st
import pandas as pd
import logging
import io
import sys
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'asset_management_{datetime.now().strftime("%Y%m%d")}.log')
    ]
)
logger = logging.getLogger(__name__)

def handle_error(func):
    """Decorator for error handling"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_msg = f"Error in {func.__name__}: {str(e)}"
            logger.error(error_msg)
            st.error(error_msg)
            return None
    return wrapper

@handle_error
def clean_and_truncate_facility_name(name, substrings_to_ignore):
    """Clean and truncate facility names"""
    if isinstance(name, str):
        for substring in substrings_to_ignore:
            name = name.replace(substring, "")
        return name.split(",")[0].strip()
    return name

@handle_error
def process_facility_data(facility_file, template_file, namespace):
    """Process facility data"""
    logger.info("Starting facility data processing")
    
    # Load the AFM file and the facility template
    afm_data = pd.read_excel(facility_file, sheet_name='Building (Facility)')
    facility_template_data = pd.read_csv(template_file)
    
    # Define the required column mappings
    required_columns = {
        "name*": "Building Name",
        "facilityType*": "Facility Type",
        "criticality": "Building Criticality",
        "location.longitude": "Longitude",
        "location.latitude": "Latitude",
    }
    
    # Validate required columns
    missing_cols = [col for col, mapped_col in required_columns.items() 
                   if mapped_col not in afm_data.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {', '.join(missing_cols)}")
    
    # Normalize the criticality values
    afm_data["Building Criticality"] = afm_data["Building Criticality"].str.extract(r"(C\d)")
    
    # Prepare the new data
    facility_data = pd.DataFrame({
        "name*": afm_data[required_columns["name*"]],
        "facilityType*": afm_data[required_columns["facilityType*"]],
        "criticality": afm_data[required_columns["criticality"]],
        "location.longitude": pd.to_numeric(afm_data[required_columns["location.longitude"]], errors='coerce'),
        "location.latitude": pd.to_numeric(afm_data[required_columns["location.latitude"]], errors='coerce'),
        "isActive*": True,
        "namespace*": namespace,
    })
    
    # Clean and filter data
    valid_criticality_values = ["C1", "C2", "C3"]
    cleaned_facility_data = facility_data[
        (facility_data["name*"].notna()) &
        (~facility_data["name*"].str.contains("Mandatory|name", case=False, na=False)) &
        (~facility_data["facilityType*"].str.contains("Mandatory|facility type", case=False, na=False)) &
        (facility_data["criticality"].isin(valid_criticality_values))
    ]
    
    # Remove placeholder rows and merge
    facility_template_data = facility_template_data.drop(index=[0, 1], errors='ignore').reset_index(drop=True)
    updated_facility_data = pd.concat([facility_template_data, cleaned_facility_data], ignore_index=True)
    
    logger.info(f"Processed {len(cleaned_facility_data)} facility records")
    return updated_facility_data

@handle_error
def process_location_data(asset_location_file, location_template, namespace):
    """Process location data"""
    logger.info("Starting location data processing")
    
    # Load files
    asset_location_data = pd.read_excel(asset_location_file, sheet_name='Asset,location')
    template_data = pd.read_csv(location_template)
    
    # Extract and clean building/floor data
    unique_building_floor = asset_location_data[['Building', 'Floor']].drop_duplicates().dropna()
    valid_data = unique_building_floor[
        (unique_building_floor['Building'] != 'Mandatory') & 
        (unique_building_floor['Building'].notna()) & 
        (unique_building_floor['Floor'] != 'Mandatory') & 
        (unique_building_floor['Floor'].notna())
    ]
    
    # Create new location data
    new_location_data = pd.DataFrame({
        'facility*': [None] * len(valid_data),
        'facility name': valid_data['Building'].reset_index(drop=True),
        'name*': valid_data['Floor'].reset_index(drop=True),
        'namespace*': namespace,
        'isActive*': True
    })
    
    # Merge with template
    template_data_cleaned = template_data.iloc[1:]
    updated_location_data = pd.concat([template_data_cleaned, new_location_data], ignore_index=True)
    
    logger.info(f"Processed {len(new_location_data)} location records")
    return updated_location_data

@handle_error
def process_space_data(asset_location_file, space_template, namespace):
    """Process space data"""
    logger.info("Starting space data processing")
    
    # Load data
    asset_location_data = pd.read_excel(asset_location_file, sheet_name='Asset,location')
    template_data = pd.read_csv(space_template)
    
    # Extract unique data
    unique_data = asset_location_data[['Building', 'Floor', 'Sublocation']].drop_duplicates().dropna()
    valid_data = unique_data[
        (unique_data['Building'] != 'Mandatory') &
        (unique_data['Building'].notna()) &
        (unique_data['Floor'] != 'Mandatory') &
        (unique_data['Floor'].notna()) &
        (unique_data['Sublocation'] != 'Mandatory') &
        (unique_data['Sublocation'].notna())
    ]
    
    # Create new space data
    new_space_data = pd.DataFrame({
        'facility name': valid_data['Building'].reset_index(drop=True),
        'location name': valid_data['Floor'].reset_index(drop=True),
        'name*': valid_data['Sublocation'].reset_index(drop=True),
        'namespace*': namespace,
        'isActive*': True
    })
    
    # Merge with template
    template_data_cleaned = template_data.iloc[1:]
    updated_space_data = pd.concat([template_data_cleaned, new_space_data], ignore_index=True)
    
    logger.info(f"Processed {len(new_space_data)} space records")
    return updated_space_data

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
    
    # Create new equipment data
    new_equipment_data = pd.DataFrame({
        'barcode': valid_data['Barcode'].reset_index(drop=True),
        'name*': valid_data.apply(
            lambda x: x['Asset / Equipment'] if pd.notna(x['Asset / Equipment']) else x['Asset System'],
            axis=1
        ).reset_index(drop=True),
        'criticality': valid_data['Asset Criticality'].reset_index(drop=True),
        'space name': valid_data['Sublocation'].reset_index(drop=True),
        'namespace*': namespace,
        'isActive*': True
    })
    
    # Merge with template
    template_data_cleaned = template_data.iloc[1:]
    updated_equipment_data = pd.concat([template_data_cleaned, new_equipment_data], ignore_index=True)
    
    logger.info(f"Processed {len(new_equipment_data)} equipment records")
    return updated_equipment_data

@handle_error
def process_system_asset_mapping(location_file, space_file):
    """Process system asset ID mapping"""
    logger.info("Starting system asset ID mapping")
    
    # Load the files
    location_data = pd.read_csv(location_file)
    space_data = pd.read_csv(space_file)

    # Clean the relevant columns
    location_data['name_cleaned'] = location_data['name*'].str.strip()
    space_data['asset_name_cleaned'] = space_data['asset name'].astype(str).str.strip()

    # Create mapping dictionary
    location_mapping = location_data.set_index('name_cleaned')['id'].to_dict()

    # Map asset IDs
    space_data['asset*'] = space_data['asset_name_cleaned'].map(location_mapping)

    # Clean up temporary column
    space_data.drop(columns=['asset_name_cleaned'], inplace=True)
    
    logger.info(f"Mapped {len(space_data[space_data['asset*'].notna()])} asset IDs")
    return space_data

def main():
    st.set_page_config(page_title="Asset Management System", layout="wide")
    st.title("Asset Management System")
    
    # Sidebar for navigation
    page = st.sidebar.selectbox(
        "Select Process",
        ["Asset ID Generator", "Facility Processing", "Location Processing", 
         "Space Processing", "Equipment Processing", "System Asset ID Mapping"]
    )
    
    # Common inputs
    namespace = st.sidebar.text_input("Namespace*", help="Required for all operations")
    
    if page == "Asset ID Generator":
        st.header("Asset ID Generator")
        uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx"])
        
        if uploaded_file:
            sheet_name = st.text_input("Enter sheet name", value="Asset,location")
            
            if st.button("Process File"):
                try:
                    df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
                    
                    required_cols = ["Building", "Location", "Space", "Subspace", 
                                   "Asset System", "Asset / Equipment"]
                    missing_cols = [col for col in required_cols if col not in df.columns]
                    
                    if missing_cols:
                        st.error(f"Missing required columns: {', '.join(missing_cols)}")
                    else:
                        def get_short_form(text):
                            if pd.isna(text) or str(text).strip() == "":
                                return "UNK"
                            text = str(text).strip()
                            return text[:3].upper() if len(text) >= 3 else text.upper()

                        def generate_asset_id(row, asset_counts):
                            components = [
                                get_short_form(row['Building']),
                                get_short_form(row['Location']),
                                get_short_form(row['Space']),
                                get_short_form(row['Subspace'])
                            ]
                            
                            eqp = ("UNK" if pd.isna(row['Asset / Equipment']) 
                                  else get_short_form(row['Asset / Equipment']))
                            if eqp == "UNK" and not pd.isna(row['Asset System']):
                                eqp = get_short_form(row['Asset System'])
                            
                            components.append(eqp)
                            base_id = "-".join(components)
                            
                            if base_id not in asset_counts:
                                asset_counts[base_id] = 1
                            else:
                                asset_counts[base_id] += 1
                            return f"{base_id}-{asset_counts[base_id]}"

                        asset_counts = {}
                        df["Asset ID"] = df.apply(
                            lambda row: generate_asset_id(row, asset_counts), axis=1
                        )
                        
                        st.success("File processed successfully!")
                        st.dataframe(df)
                        
                        # Prepare download
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df.to_excel(writer, index=False, sheet_name=sheet_name)
                        
                        st.download_button(
                            label="Download Processed Excel",
                            data=output.getvalue(),
                            file_name="processed_assets.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                        
                except Exception as e:
                    logger.error(f"Error processing file: {str(e)}")
                    st.error(f"Error processing file: {str(e)}")
    
    elif page == "Facility Processing":
        st.header("Facility Processing")
        facility_file = st.file_uploader("Upload Facility File (Excel)", type=["xlsx"])
        template_file = st.file_uploader("Upload Template File (CSV)", type=["csv"])
        
        if facility_file and template_file and namespace:
            if st.button("Process Facility Data"):
                result = process_facility_data(facility_file, template_file, namespace)
                if result is not None:
                    st.success("Facility data processed successfully!")
                    st.dataframe(result)
                    
                    # Prepare download
                    csv = result.to_csv(index=False)
                    st.download_button(
                        label="Download Processed CSV",
                        data=csv,
                        file_name="processed_facility.csv",
                        mime="text/csv"
                    )
    
    elif page == "Location Processing":
        st.header("Location Processing")
        location_file = st.file_uploader("Upload Asset Location File (Excel)", type=["xlsx"])
        template_file = st.file_uploader("Upload Template File (CSV)", type=["csv"])
        
        if location_file and template_file and namespace:
            if st.button("Process Location Data"):
                result = process_location_data(location_file, template_file, namespace)
                if result is not None:
                    st.success("Location data processed successfully!")
                    st.dataframe(result)
                    
                    csv = result.to_csv(index=False)
                    st.download_button(
                        label="Download Processed CSV",
                        data=csv,
                        file_name="processed_location.csv",
                        mime="text/csv"
                    )
    
    elif page == "Space Processing":
        st.header("Space Processing")
        space_file = st.file_uploader("Upload Asset Location File (Excel)", type=["xlsx"])
        template_file = st.file_uploader("Upload Template File (CSV)", type=["csv"])
        
        if space_file and template_file and namespace:
            if st.button("Process Space Data"):
                result = process_space_data(space_file, template_file, namespace)
                if result is not None:
                    st.success("Space data processed successfully!")
                    st.dataframe(result)
                    
                    csv = result.to_csv(index=False)
                    st.download_button(
                        label="Download Processed CSV",
                        data=csv,
                        file_name="processed_space.csv",
                        mime="text/csv"
                    )
    
    elif page == "Equipment Processing":
        st.header("Equipment Processing")
        equipment_file = st.file_uploader("Upload Asset Location File (Excel)", type=["xlsx"])
        template_file = st.file_uploader("Upload Template File (CSV)", type=["csv"])
        
        if equipment_file and template_file and namespace:
            if st.button("Process Equipment Data"):
                result = process_equipment_data(equipment_file, template_file, namespace)
                if result is not None:
                    st.success("Equipment data processed successfully!")
                    st.dataframe(result)
                    
                    csv = result.to_csv(index=False)
                    st.download_button(
                        label="Download Processed CSV",
                        data=csv,
                        file_name="processed_equipment.csv",
                        mime="text/csv"
                    )

    elif page == "System Asset ID Mapping":
        st.header("System Asset ID Mapping")
        location_file = st.file_uploader("Upload Location File (CSV)", type=["csv"], key="location_map")
        space_file = st.file_uploader("Upload Space File (CSV)", type=["csv"], key="space_map")
        
        if location_file and space_file:
            if st.button("Map System Asset IDs"):
                try:
                    result = process_system_asset_mapping(location_file, space_file)
                    if result is not None:
                        st.success("System asset IDs mapped successfully!")
                        st.dataframe(result)
                        
                        csv = result.to_csv(index=False)
                        st.download_button(
                            label="Download Mapped CSV",
                            data=csv,
                            file_name="mapped_system_assets.csv",
                            mime="text/csv"
                        )
                except Exception as e:
                    logger.error(f"Error mapping system asset IDs: {str(e)}")
                    st.error(f"Error mapping system asset IDs: {str(e)}")

if __name__ == "__main__":
    main()
