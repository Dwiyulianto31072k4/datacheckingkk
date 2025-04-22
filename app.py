import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io
import base64
import plotly.express as px

# --- Page Config ---
st.set_page_config(
    page_title="KK & NIK Validation Dashboard",
    page_icon="📋",
    layout="wide"
)

# --- Custom CSS for UI Enhancement ---
st.markdown(
    """
    <style>
    footer {visibility: hidden;} 
    #MainMenu {visibility: hidden;}
    .title {text-align: center; color: #2E86AB; font-size: 2.5rem; margin-bottom: 1rem;}
    .metric-container {background-color: #F0F4F8; border-radius: 10px; padding: 1rem; text-align: center;}
    </style>
    """, unsafe_allow_html=True
)

# --- Validation Logic from Original Code ---
def is_valid_kk_no(x):
    return isinstance(x, str) and x.isdigit() and len(x) == 16 and not x.endswith('0000')

def is_valid_nik(x):
    return isinstance(x, str) and x.isdigit() and len(x) == 16 and not x.endswith('0000')

def is_valid_custname(x):
    return isinstance(x, str) and not any(ch.isdigit() for ch in x)

def is_valid_jenis_kelamin(x):
    return str(x).upper().strip() in {'LAKI-LAKI','LAKI - LAKI','LAKI LAKI','PEREMPUAN'}

def is_valid_tempat_lahir(x, kota_list):
    return isinstance(x, str) and x.upper().strip() in kota_list

def is_valid_tanggal_lahir(x):
    if pd.isna(x): return False
    if isinstance(x, pd.Timestamp):
        dt = x
    else:
        try:
            dt = datetime.strptime(str(x), '%d/%m/%Y')
        except Exception:
            return False
    return dt.date() <= datetime.today().date()

# --- Data Cleaning Function ---
def clean_data(raw_df: pd.DataFrame, kota_list: list[str]):
    df = raw_df.copy()
    df['Check_Desc'] = ''

    # Apply validations
    valid_kk = df['KK_NO'].apply(is_valid_kk_no)
    valid_nik = df['NIK'].apply(is_valid_nik)
    valid_name = df['CUSTNAME'].apply(is_valid_custname)
    valid_gender = df['JENIS_KELAMIN'].apply(is_valid_jenis_kelamin)
    valid_place = df['TEMPAT_LAHIR'].apply(lambda x: is_valid_tempat_lahir(x, kota_list))
    valid_date = df['TANGGAL_LAHIR'].apply(is_valid_tanggal_lahir)

    # Build clean_df
    clean_mask = valid_kk & valid_nik & valid_name & valid_gender & valid_place & valid_date
    clean_df = df[clean_mask].drop(columns=['Check_Desc'])

    # Annotate issues
    df.loc[~valid_kk, 'Check_Desc'] += df.loc[~valid_kk, 'KK_NO'].astype(str).apply(lambda v: f"Invalid KK_NO ({v}); ")
    df.loc[~valid_nik, 'Check_Desc'] += df.loc[~valid_nik, 'NIK'].astype(str).apply(lambda v: f"Invalid NIK ({v}); ")
    df.loc[~valid_name, 'Check_Desc'] += df.loc[~valid_name, 'CUSTNAME'].astype(str).apply(lambda v: f"Invalid Name ({v}); ")
    df.loc[~valid_gender, 'Check_Desc'] += df.loc[~valid_gender, 'JENIS_KELAMIN'].astype(str).apply(lambda v: f"Invalid Gender ({v}); ")
    df.loc[~valid_place, 'Check_Desc'] += df.loc[~valid_place, 'TEMPAT_LAHIR'].astype(str).apply(lambda v: f"Invalid Place ({v}); ")
    df.loc[~valid_date, 'Check_Desc'] += df.loc[~valid_date, 'TANGGAL_LAHIR'].astype(str).apply(lambda v: f"Invalid Birth Date ({v}); ")

    messy_df = df[df['Check_Desc'] != '']
    return messy_df, clean_df

# --- Excel Report Generation ---
def generate_excel(messy: pd.DataFrame, clean: pd.DataFrame, total: int):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        pd.DataFrame({
            'Metric': ['Total', 'Clean', 'Messy'],
            'Count': [total, len(clean), len(messy)]
        }).to_excel(writer, sheet_name='Summary', index=False)
        clean.to_excel(writer, sheet_name='Clean', index=False)
        messy.to_excel(writer, sheet_name='Messy', index=False)
    return buffer.getvalue()

# --- Sidebar UI ---
st.sidebar.header("📋 Upload Files")
uploaded_excel = st.sidebar.file_uploader("Excel (.xlsx)", type=['xlsx'])
uploaded_city = st.sidebar.file_uploader("City List (.csv/.txt)", type=['csv','txt'])

# --- Main UI ---
st.markdown("<div class='title'>KK & NIK Data Validation Dashboard</div>", unsafe_allow_html=True)

if uploaded_excel and uploaded_city:
    # Load city list
    city_df = pd.read_csv(uploaded_city)
    if 'CITY_DESC' in city_df.columns:
        kota_list = city_df['CITY_DESC'].str.upper().str.strip().tolist()
    else:
        kota_list = city_df.iloc[:,0].astype(str).str.upper().str.strip().tolist()

    # Read all sheets from Excel
    try:
        xls = pd.ExcelFile(uploaded_excel)
        df_full = pd.concat(
            [pd.read_excel(xls, sheet_name=sh, dtype=str) for sh in xls.sheet_names],
            ignore_index=True
        )
    except Exception as e:
        st.error(f"Error reading Excel: {e}")
        st.stop()

    # Required columns
    req = ['KK_NO','NIK','CUSTNAME','JENIS_KELAMIN','TANGGAL_LAHIR','TEMPAT_LAHIR']
    missing = [c for c in req if c not in df_full.columns]
    if missing:
        st.error(f"Missing columns: {', '.join(missing)}")
        st.stop()

    df_req = df_full[req].copy()
    # Normalize date to consistent string
    df_req['TANGGAL_LAHIR'] = pd.to_datetime(
        df_req['TANGGAL_LAHIR'], format='%d/%m/%Y', errors='coerce'
    ).dt.strftime('%d/%m/%Y')

    # Run cleaning
    messy_df, clean_df = clean_data(df_req, kota_list)
    total = len(df_req)
    clean_cnt = len(clean_df)
    messy_cnt = len(messy_df)
    invalid_counts = {
        'KK_NO': messy_df['Check_Desc'].str.contains('Invalid KK_NO').sum(),
        'NIK': messy_df['Check_Desc'].str.contains('Invalid NIK').sum(),
        'Name': messy_df['Check_Desc'].str.contains('Invalid Name').sum(),
        'Gender': messy_df['Check_Desc'].str.contains('Invalid Gender').sum(),
        'Place': messy_df['Check_Desc'].str.contains('Invalid Place').sum(),
        'Birth Date': messy_df['Check_Desc'].str.contains('Invalid Birth Date').sum(),
    }

    # --- Dashboard ---
    st.subheader("Overview Metrics")
    c1, c2, c3 = st.columns(3)
    for col, label, count, pct in [
        (c1, "Total Records", total, None),
        (c2, "Clean Records", clean_cnt, clean_cnt/total*100),
        (c3, "Messy Records", messy_cnt, messy_cnt/total*100),
    ]:
        with col:
            st.markdown("<div class='metric-container'>", unsafe_allow_html=True)
            if pct is None:
                st.metric(label, f"{count:,}")
            else:
                st.metric(label, f"{count:,}", f"{pct:.1f}%")
            st.markdown("</div>", unsafe_allow_html=True)

    # Invalid breakdown chart
    inv_df = pd.DataFrame({
        'Category': list(invalid_counts.keys()),
        'Count': list(invalid_counts.values())
    })
    fig = px.bar(inv_df, x='Category', y='Count', text='Count', color='Category')
    fig.update_layout(showlegend=False, margin=dict(t=30, b=20, l=0, r=0))
    st.subheader("Invalid Data Breakdown")
    st.plotly_chart(fig, use_container_width=True)

    # Detailed samples
    tab1, tab2 = st.tabs(["Clean Sample","Messy Sample"])
    with tab1:
        st.dataframe(clean_df.head(10))
    with tab2:
        st.dataframe(messy_df[['Check_Desc'] + req].head(10))

    # Download report
    report = generate_excel(messy_df, clean_df, total)
    st.download_button(
        "📥 Download Full Report",
        data=report,
        file_name="validation_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.warning("Silakan upload Excel dan City List di sidebar untuk memulai.")
    st.markdown(
        "- **KK_NO**: 16 digit, tidak berakhiran '0000'<br>"
        "- **NIK**: 16 digit, tidak berakhiran '0000'<br>"
        "- **Nama**: tanpa angka<br>"
        "- **Jenis Kelamin**: dua format (LAKI-LAKI / PEREMPUAN)<br>"
        "- **Tanggal Lahir**: DD/MM/YYYY, bukan di masa depan<br>"
        "- **Tempat Lahir**: sesuai daftar kota",
        unsafe_allow_html=True
    )
