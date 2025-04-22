import streamlit as st
import pandas as pd
import numpy as np
import openpyxl
import zipfile
import re
from datetime import datetime
import time
import io
import base64
import altair as alt
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="KK & NIK Data Validation Tool",
    page_icon="📋",
    layout="wide"
)

st.title("KK & NIK Data Validation Tool")

# Define helper functions - EXACT SAME LOGIC AS THE NOTEBOOK
def clean_data(raw_df, kota_indonesia):
    # Define criteria for clean data
    def is_valid_kk_no(kk_no):
        return isinstance(kk_no, str) and kk_no.isdigit() and len(kk_no) == 16 and kk_no[-4:] != '0000'

    def is_valid_nik(nik):
        return isinstance(nik, str) and nik.isdigit() and len(nik) == 16 and nik[-4:] != '0000'

    def is_valid_custname(custname):
        # return isinstance(custname, str) and bool(re.match("^[A-Za-z ]*$", custname))
        return isinstance(custname, str) and not any(c.isdigit() for c in custname)

    def is_valid_jenis_kelamin(jenis_kelamin):
        return jenis_kelamin in ['LAKI-LAKI','LAKI - LAKI','LAKI LAKI', 'PEREMPUAN']

    def is_valid_tempat_lahir(tempat_lahir):
        return isinstance(tempat_lahir, str) and tempat_lahir.upper() in kota_indonesia
        # return tempat_lahir in kota_indonesia

    def is_valid_date(date_str):
        if isinstance(date_str, str):
            try:
                date_obj = datetime.strptime(date_str, '%d/%m/%Y')
                if date_obj.date() <= datetime.today().date():
                    return True
                else:
                    return False
            except ValueError:
                return False
        elif isinstance(date_str, pd.Timestamp):
            if date_str.date() <= datetime.today().date():
                return True
            else:
                return False
        else:
            return False

    # Initialize the Check_Desc column with empty strings
    raw_df['Check_Desc'] = ''

    # Apply criteria to filter clean data
    valid_kk_no = raw_df['KK_NO'].apply(is_valid_kk_no)
    valid_nik = raw_df['NIK'].apply(is_valid_nik)
    valid_custname = raw_df['CUSTNAME'].apply(is_valid_custname)
    valid_jenis_kelamin = raw_df['JENIS_KELAMIN'].apply(is_valid_jenis_kelamin)
    valid_tempat_lahir = raw_df['TEMPAT_LAHIR'].apply(is_valid_tempat_lahir)
    valid_tanggal_lahir = raw_df['TANGGAL_LAHIR'].apply(is_valid_date)

    clean_df = raw_df[valid_kk_no & valid_nik & valid_custname & valid_jenis_kelamin & valid_tempat_lahir & valid_tanggal_lahir]

    # Identify issues in the data
    raw_df.loc[~valid_kk_no, 'Check_Desc'] += raw_df.loc[~valid_kk_no, 'KK_NO'].apply(
        lambda x: f'Invalid KK_NO (length: {len(str(x))}, digits only: {str(x).isdigit()}, last_digits: {x[-4:]}); '
    )
    raw_df.loc[~valid_nik, 'Check_Desc'] += raw_df.loc[~valid_nik, 'NIK'].apply(
        lambda x: f'Invalid NIK (length: {len(str(x))}, digits only: {str(x).isdigit()}, last_digits: {x[-4:]}); '
    )
    raw_df.loc[~valid_custname, 'Check_Desc'] += raw_df.loc[~valid_custname, 'CUSTNAME'].apply(
        lambda x: f'Invalid CUSTNAME (contains special characters or digits: {x}); '
    )
    raw_df.loc[~valid_jenis_kelamin, 'Check_Desc'] += raw_df.loc[~valid_jenis_kelamin, 'JENIS_KELAMIN'].apply(
        lambda x: f'Invalid JENIS_KELAMIN (value: {x}); '
    )
    raw_df.loc[~valid_tempat_lahir, 'Check_Desc'] += raw_df.loc[~valid_tempat_lahir, 'TEMPAT_LAHIR'].apply(
        lambda x: f'Invalid TEMPAT_LAHIR (value: {str(x)}); '
    )
    raw_df.loc[~valid_tanggal_lahir, 'Check_Desc'] += raw_df.loc[~valid_tanggal_lahir, 'TANGGAL_LAHIR'].apply(
        lambda x: f'Invalid TANGGAL_LAHIR (value: {str(x)}, expected format DD/MM/YYYY); '
    )
    
    # All other rows are considered messy data
    messy_df = raw_df[raw_df['Check_Desc'] != '']

    # Remove the Check_Desc column from the clean_df
    clean_df = clean_df.drop(columns=['Check_Desc'])

    return messy_df, clean_df

def generate_summary_excel(messy_df, clean_df, total_data):
    """Generate Excel with summary and both datasets"""
    output = io.BytesIO()
    
    # Calculate statistics EXACTLY as in notebook
    messy_data = len(messy_df)
    clean_data = len(clean_df)
    
    num_rows, num_cols = messy_df.shape
    len_param = num_cols - 1
    
    invalid_kk = len(messy_df[messy_df['Check_Desc'].str.contains('Invalid KK_NO')])
    invalid_nik = len(messy_df[messy_df['Check_Desc'].str.contains('Invalid NIK')])
    invalid_name = len(messy_df[messy_df['Check_Desc'].str.contains('Invalid CUSTNAME')])
    invalid_gender = len(messy_df[messy_df['Check_Desc'].str.contains('Invalid JENIS_KELAMIN')])
    invalid_places = len(messy_df[messy_df['Check_Desc'].str.contains('Invalid TEMPAT_LAHIR')])
    invalid_date = len(messy_df[messy_df['Check_Desc'].str.contains('Invalid TANGGAL_LAHIR')])
    
    total_invalid = len(messy_df) * len_param
    messy_invalid = invalid_kk + invalid_nik + invalid_name + invalid_gender + invalid_places + invalid_date
    clean_invalid = total_invalid - messy_invalid
    
    # Prepare summary data
    summary_headers = ["Category", "Total Data", "Messy Data", "Clean Data", "", "Invalid Parameter", "Clean Parameter", "Messy Parameter", "Invalid KK", "Invalid NIK", "Invalid Name", "Invalid Gender", "Invalid Places", "Invalid Date"]
    summary_counts = ["Data", total_data, messy_data, clean_data, "", total_invalid, clean_invalid, messy_invalid, invalid_kk, invalid_nik, invalid_name, invalid_gender, invalid_places, invalid_date]
    summary_percentages = ["Data (%)", 100.0, round(messy_data / total_data * 100, 2), round(clean_data / total_data * 100, 2), "", 100.0, round(clean_invalid / total_invalid * 100, 2), round(messy_invalid / total_invalid * 100, 2), round(invalid_kk / total_invalid * 100, 2), round(invalid_nik / total_invalid * 100, 2), round(invalid_name / total_invalid * 100, 2), round(invalid_gender / total_invalid * 100, 2), round(invalid_places / total_invalid * 100, 2), round(invalid_date / total_invalid * 100, 2)]
    
    summary_df = pd.DataFrame([summary_counts, summary_percentages], columns=summary_headers)
    
    # Create Excel file with multiple sheets
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        messy_df.to_excel(writer, sheet_name='Messy Data', index=False)
        clean_df.to_excel(writer, sheet_name='Clean Data', index=False)
    
    return output.getvalue()

# Function to create executive dashboard
def create_executive_dashboard(total_data, clean_data, messy_data, invalid_kk, invalid_nik, invalid_name, 
                              invalid_gender, invalid_places, invalid_date, total_invalid):
    # Create two columns for the top metrics
    col1, col2, col3 = st.columns(3)
    
    # Display metrics in each column
    with col1:
        st.metric("Total Records", f"{total_data:,}")
    
    with col2:
        st.metric("Clean Records", f"{clean_data:,}", f"{round(clean_data/total_data*100, 1)}%")
    
    with col3:
        st.metric("Messy Records", f"{messy_data:,}", f"{round(messy_data/total_data*100, 1)}%")
    
    # Create two columns for charts
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.subheader("Data Quality Overview")
        
        # Create pie chart for clean vs messy data
        pie_data = pd.DataFrame({
            'Category': ['Clean Data', 'Messy Data'],
            'Value': [clean_data, messy_data]
        })
        
        fig = px.pie(
            pie_data, 
            values='Value', 
            names='Category',
            color='Category',
            color_discrete_map={
                'Clean Data': '#4CAF50',
                'Messy Data': '#F44336'
            },
            hole=0.4
        )
        fig.update_layout(
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with chart_col2:
        st.subheader("Invalid Data Breakdown")
        
        # Create data for the invalid breakdown
        invalid_data = pd.DataFrame({
            'Category': ['KK Number', 'NIK', 'Name', 'Gender', 'Birth Place', 'Birth Date'],
            'Count': [invalid_kk, invalid_nik, invalid_name, invalid_gender, invalid_places, invalid_date],
            'Percentage': [
                round(invalid_kk/total_invalid*100, 2),
                round(invalid_nik/total_invalid*100, 2),
                round(invalid_name/total_invalid*100, 2),
                round(invalid_gender/total_invalid*100, 2),
                round(invalid_places/total_invalid*100, 2),
                round(invalid_date/total_invalid*100, 2)
            ]
        })
        
        # Sort by count descending
        invalid_data = invalid_data.sort_values('Count', ascending=False)
        
        fig = px.bar(
            invalid_data,
            y='Category',
            x='Count',
            text='Percentage',
            orientation='h',
            labels={'Count': 'Number of Invalid Records', 'Category': 'Field'},
            color='Count',
            color_continuous_scale=px.colors.sequential.Reds
        )
        fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig.update_layout(uniformtext_minsize=8, uniformtext_mode='hide')
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Executive Summary section
    st.subheader("Executive Summary")
    
    # Find the most problematic field
    most_problematic = invalid_data.iloc[0]['Category']
    
    # Create columns for the summary cards
    sum_col1, sum_col2 = st.columns(2)
    
    with sum_col1:
        st.info(f"""
        #### Quality Metrics
        - Data quality rate: **{round(clean_data/total_data*100, 1)}%**
        - Total records processed: **{total_data:,}**
        - Clean records: **{clean_data:,}**
        - Records with issues: **{messy_data:,}**
        """)
    
    with sum_col2:
        st.warning(f"""
        #### Key Findings
        - Most common data issue: **{most_problematic}**
        - Number of {most_problematic} issues: **{invalid_data.iloc[0]['Count']:,}**
        - Percentage of total issues: **{invalid_data.iloc[0]['Percentage']}%**
        - Recommendation: Focus on improving data quality for {most_problematic} validation
        """)

# Sidebar with information and upload
with st.sidebar:
    st.header("Upload Data")
    uploaded_excel = st.file_uploader("Upload your Excel file", type=['xlsx'])
    
    st.markdown("---")
    st.header("Upload City List (Required)")
    uploaded_city_list = st.file_uploader("Upload a city list (CSV/TXT)", type=['csv', 'txt'])
    
    st.markdown("---")
    st.subheader("About This Tool")
    st.info("""
    This tool validates Indonesian ID Card (NIK) and Family Card (KK) data.
    
    Validation Rules:
    - KK_NO: 16 digits, not ending with '0000'
    - NIK: 16 digits, not ending with '0000'
    - Names: No digits allowed
    - Gender: Standard formats (LAKI-LAKI, LAKI - LAKI, LAKI LAKI, PEREMPUAN)
    - Birth place: Against city database
    - Birth date: Valid format and not future date
    """)

# Main page content
if uploaded_excel is not None and uploaded_city_list is not None:
    start_time = time.time()
    
    # Process city list
    kota_indonesia = []
    try:
        city_df = pd.read_csv(uploaded_city_list, delimiter=',')
        if 'CITY_DESC' in city_df.columns:
            # Process same as original code
            city_df['CITY_DESC'] = city_df['CITY_DESC'].str.replace('Kota ', '').str.replace('Kabupaten ', '').str.replace('Kab ', '')
            city_df['CITY_DESC'] = city_df['CITY_DESC'].str.upper()
            kota_indonesia = city_df['CITY_DESC'].tolist()
        else:
            # Assume simple list format
            kota_indonesia = [city.strip().upper() for city in city_df.iloc[:, 0].tolist()]
            
        st.sidebar.success(f"Loaded {len(kota_indonesia)} cities from uploaded list")

        # Optional: Allow adding custom cities as shown in notebook
        new_kota_option = st.sidebar.checkbox("Add default city list (from notebook)")
        if new_kota_option:
            new_kota = [
                'ACEH BARAT', 'ACEH BESAR', 'ACEH TAMIANG', 'ACEH TIMUR', 'ACEH',
                # You can include more cities from the notebook here
                'JAKARTA', 'BANDUNG', 'SURABAYA', 'MEDAN', 'MAKASSAR'
            ]
            kota_indonesia.extend(new_kota)
            st.sidebar.info(f"Added {len(new_kota)} cities from default list")
            
    except Exception as e:
        st.sidebar.error(f"Error reading city list: {e}")
        st.stop()
    
    # Process the Excel file - EXACTLY AS IN NOTEBOOK
    try:
        with st.spinner("Loading and processing data..."):
            # Read Excel file
            df_full = pd.DataFrame()
            excel_file = uploaded_excel
            
            # Read Excel workbook
            try:
                workbook = openpyxl.load_workbook(excel_file)
                sheet_names = workbook.sheetnames
                
                for sheet in sheet_names:
                    try:
                        df = pd.read_excel(excel_file, sheet_name=sheet, dtype={'KK_NO_GROSS':object, 'KK_NO':object, 'NIK_GROSS':object, 'NIK':object})
                        df_full = pd.concat([df_full, df], ignore_index=True)
                    except Exception as e:
                        st.warning(f"Error reading sheet {sheet}: {e}")
            except Exception as e:
                st.error(f"Error opening Excel file: {e}")
                st.stop()
            
            # Check if we have data
            if df_full.empty:
                st.error("No data could be read from the Excel file.")
                st.stop()
            
            # Check for required columns
            required_columns = ['KK_NO', 'NIK', 'CUSTNAME', 'JENIS_KELAMIN', 'TANGGAL_LAHIR', 'TEMPAT_LAHIR']
            missing_columns = [col for col in required_columns if col not in df_full.columns]
            
            if missing_columns:
                st.error(f"Excel file is missing required columns: {', '.join(missing_columns)}")
                st.stop()
            
            # Prepare data for validation - EXACTLY as in notebook
            df_req = df_full.loc[:, required_columns].copy()
            df_req['KK_NO'] = df_req['KK_NO'].map(str)  # Use map() instead of astype() to match notebook
            df_req['NIK'] = df_req['NIK'].map(str)
            
            # Try to convert dates - handle different formats
            try:
                df_req['TANGGAL_LAHIR'] = pd.to_datetime(df_req['TANGGAL_LAHIR'], format="%d/%m/%Y", errors='coerce')
            except:
                try:
                    df_req['TANGGAL_LAHIR'] = pd.to_datetime(df_req['TANGGAL_LAHIR'], errors='coerce')
                except:
                    st.warning("Could not parse date format. Treating as string.")
            
            # Run the validation
            messy_df, clean_df = clean_data(df_req, kota_indonesia)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Calculate statistics EXACTLY as in notebook
            total_data = len(df_req)
            messy_data = len(messy_df)
            clean_data = len(clean_df)
            
            num_rows, num_cols = messy_df.shape
            len_param = num_cols - 1
            
            invalid_kk = len(messy_df[messy_df['Check_Desc'].str.contains('Invalid KK_NO')])
            invalid_nik = len(messy_df[messy_df['Check_Desc'].str.contains('Invalid NIK')])
            invalid_name = len(messy_df[messy_df['Check_Desc'].str.contains('Invalid CUSTNAME')])
            invalid_gender = len(messy_df[messy_df['Check_Desc'].str.contains('Invalid JENIS_KELAMIN')])
            invalid_places = len(messy_df[messy_df['Check_Desc'].str.contains('Invalid TEMPAT_LAHIR')])
            invalid_date = len(messy_df[messy_df['Check_Desc'].str.contains('Invalid TANGGAL_LAHIR')])
            
            total_invalid = len(messy_df) * len_param
            messy_invalid = invalid_kk + invalid_nik + invalid_name + invalid_gender + invalid_places + invalid_date
            clean_invalid = total_invalid - messy_invalid
            
            # Display success message
            st.success(f"Processing complete in {processing_time:.2f} seconds")
            
            # Create tab-based interface
            tab1, tab2 = st.tabs(["Executive Dashboard", "Detailed Summary"])
            
            with tab1:
                # Call the executive dashboard function
                create_executive_dashboard(
                    total_data, clean_data, messy_data,
                    invalid_kk, invalid_nik, invalid_name,
                    invalid_gender, invalid_places, invalid_date,
                    total_invalid
                )
            
            with tab2:
                # Show the original text output
                output_text = f"""------------------------------
       SUMMARY INFO
------------------------------
Total Data: {total_data}
Total Data %: 100.0
Messy Data: {messy_data}
Messy Data %: {round(messy_data/total_data*100, 2)}
Clean Data: {clean_data}
Clean Data %: {round(clean_data/total_data*100, 2)}
------------------------------
       INVALID INFO
------------------------------
Invalid Parameter: {total_invalid}
Invalid Parameter %: 100.0
Clean Parameter: {clean_invalid}
Clean Parameter %: {round(clean_invalid/total_invalid*100, 2)}
Messy Parameter: {messy_invalid}
Messy Parameter %: {round(messy_invalid/total_invalid*100, 2)}
Invalid KK: {invalid_kk}
Invalid KK %: {round(invalid_kk/total_invalid*100, 2)}
Invalid NIK: {invalid_nik}
Invalid NIK %: {round(invalid_nik/total_invalid*100, 2)}
Invalid Name: {invalid_name}
Invalid Name %: {round(invalid_name/total_invalid*100, 2)}
Invalid Gender: {invalid_gender}
Invalid Gender %: {round(invalid_gender/total_invalid*100, 2)}
Invalid Places: {invalid_places}
Invalid Places %: {round(invalid_places/total_invalid*100, 2)}
Invalid Date: {invalid_date}
Invalid Date %: {round(invalid_date/total_invalid*100, 2)}
------------------------------
"""
                # Use pre-formatted text block to maintain exact spacing
                st.text(output_text)
                
                # Display sample data
                st.subheader("Sample of Clean Data")
                st.dataframe(clean_df.head(5))
                
                st.subheader("Sample of Messy Data")
                st.dataframe(messy_df.head(5))
            
            # Download button
            st.header("Download Results")
            excel_data = generate_summary_excel(messy_df, clean_df, total_data)
            
            st.download_button(
                label="Download Full Report (Excel)",
                data=excel_data,
                file_name="data_validation_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
                
    except Exception as e:
        st.error(f"An error occurred during processing: {str(e)}")
        st.exception(e)
elif uploaded_excel is not None and uploaded_city_list is None:
    st.warning("Please upload a city list file to continue.")
elif uploaded_excel is None and uploaded_city_list is not None:
    st.warning("Please upload an Excel file to continue.")
else:
    # Display instructions when no file is uploaded
    st.info("Please upload an Excel file and a city list file to begin validation.")
    st.markdown("""
    ### Required Excel Column Headers
    Your Excel file should contain these columns:
    - `KK_NO` (Family Card Number)
    - `NIK` (National ID Number)
    - `CUSTNAME` (Person's Name)
    - `JENIS_KELAMIN` (Gender)
    - `TANGGAL_LAHIR` (Date of Birth)
    - `TEMPAT_LAHIR` (Place of Birth)
    
    ### City List Format
    Your city list file should be a CSV with either:
    - A column named 'CITY_DESC' containing city names
    - Or a simple list of city names in the first column
    """)