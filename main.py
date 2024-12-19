import streamlit as st
import pandas as pd
import io

st.title("Asset ID Generator")

# Streamlit file uploader for Excel files
uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx"])

if uploaded_file is not None:
    # Select sheet name (or provide a text input if needed)
    sheet_name = st.text_input("Enter sheet name", value="Asset,location")

    # Once user provides sheet name, we can process
    if st.button("Process File"):
        try:
            # Read the sheet into a DataFrame
            df = pd.read_excel(uploaded_file, sheet_name=sheet_name)

            # Check for required columns
            required_cols = ["Building", "Location", "Space", "Subspace", "Asset System", "Asset / Equipment"]
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                st.error(f"Missing required columns: {', '.join(missing_cols)}")
            else:
                # Define helper functions
                def get_short_form(text):
                    if pd.isna(text) or str(text).strip() == "":
                        return "UNK"
                    text = str(text).strip()
                    return text[:3].upper() if len(text) >= 3 else text.upper()

                def generate_asset_id(row, asset_counts):
                    fac = get_short_form(row['Building'])
                    loc = get_short_form(row['Location'])
                    spa = get_short_form(row['Space'])
                    ssp = get_short_form(row['Subspace'])

                    # Equipment short form
                    if pd.notna(row['Asset / Equipment']) and str(row['Asset / Equipment']).strip() != "":
                        eqp = get_short_form(row['Asset / Equipment'])
                    elif pd.notna(row['Asset System']) and str(row['Asset System']).strip() != "":
                        eqp = get_short_form(row['Asset System'])
                    else:
                        eqp = "UNK"

                    base_id = f"{fac}-{loc}-{spa}-{ssp}-{eqp}"
                    if base_id not in asset_counts:
                        asset_counts[base_id] = 1
                        return f"{base_id}-1"
                    else:
                        asset_counts[base_id] += 1
                        return f"{base_id}-{asset_counts[base_id]}"

                # Generate asset IDs
                asset_counts = {}
                df["Asset ID"] = df.apply(lambda row: generate_asset_id(row, asset_counts), axis=1)

                st.success("File processed successfully!")
                st.dataframe(df)

                # Provide a download button
                # Save processed DataFrame to a BytesIO object as Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name=sheet_name)
                processed_data = output.getvalue()

                st.download_button(
                    label="Download Processed Excel",
                    data=processed_data,
                    file_name="processed_assets.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        except FileNotFoundError:
            st.error(f"Error: File not found.")
        except ValueError as e:
            st.error(f"Error: {e}")
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")