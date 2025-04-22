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
    /* Hide Streamlit footer and menu */
    footer {visibility: hidden;} 
    #MainMenu {visibility: hidden;}
    /* Centered title style */
    .title {text-align: center; color: #2E86AB; font-size: 2.5rem;}
    /* Card metrics style */
    .metric-container {background-color: #F0F4F8; border-radius: 10px; padding: 1rem; margin-bottom: 1rem;}
    </style>
    """, unsafe_allow_html=True
)

# --- Helper Functions ---
def clean_data(df: pd.DataFrame, kota_list: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.copy()
    df['Check_Desc'] = ''
    # validators: (column, func, message)
    validators = [
        ('KK_NO', lambda x: isinstance(x, str) and x.isdigit() and len(x) == 16 and not x.endswith('0000'), 'Invalid KK_NO'),
        ('NIK', lambda x: isinstance(x, str) and x.isdigit() and len(x) == 16 and not x.endswith('0000'), 'Invalid NIK'),
        ('CUSTNAME', lambda x: isinstance(x, str) and not any(ch.isdigit() for ch in x), 'Invalid Name'),
        ('JENIS_KELAMIN', lambda x: str(x).upper().strip() in {'LAKI-LAKI','LAKI LAKI','PEREMPUAN'}, 'Invalid Gender'),
        ('TEMPAT_LAHIR', lambda x: isinstance(x, str) and x.upper().strip() in kota_list, 'Invalid Place'),
        ('TANGGAL_LAHIR', lambda x: _is_valid_date(x), 'Invalid Birth Date'),
    ]
    for col, fn, msg in validators:
        valid = df[col].apply(fn)
        df.loc[~valid, 'Check_Desc'] += df.loc[~valid, col].astype(str).apply(lambda v: f"{msg} ({v}); ")
    mask = df['Check_Desc'] != ''
    return df[mask], df[~mask].drop(columns=['Check_Desc'])


def _is_valid_date(x) -> bool:
    if pd.isna(x):
        return False
    if isinstance(x, pd.Timestamp):
        dt = x
    else:
        try:
            dt = datetime.strptime(str(x), '%d/%m/%Y')
        except ValueError:
            return False
    return dt.date() <= datetime.today().date()


def generate_excel(messy: pd.DataFrame, clean: pd.DataFrame, total: int) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        pd.DataFrame({'Metric': ['Total','Clean','Messy'], 'Count': [total, len(clean), len(messy)]}) \
            .to_excel(writer, sheet_name='Summary', index=False)
        clean.to_excel(writer, sheet_name='Clean', index=False)
        messy.to_excel(writer, sheet_name='Messy', index=False)
    return buffer.getvalue()

# --- Sidebar ---
st.sidebar.title("📋 KK & NIK Validator")
uploaded_excel = st.sidebar.file_uploader("Upload Excel (.xlsx)", type=['xlsx'])
uploaded_city = st.sidebar.file_uploader("Upload City List (.csv)", type=['csv','txt'])

# --- Main ---
st.markdown("<div class='title'>KK & NIK Data Validation Dashboard</div>", unsafe_allow_html=True)

if uploaded_excel and uploaded_city:
    # Load city list
    city_df = pd.read_csv(uploaded_city)
    if 'CITY_DESC' in city_df.columns:
        kota_list = city_df['CITY_DESC'].str.upper().str.strip().tolist()
    else:
        kota_list = city_df.iloc[:,0].astype(str).str.upper().str.strip().tolist()

    # Read all sheets
    try:
        xls = pd.ExcelFile(uploaded_excel)
        df_full = pd.concat([pd.read_excel(xls, sheet_name=sh, dtype=str) for sh in xls.sheet_names], ignore_index=True)
    except Exception as e:
        st.error(f"Error loading Excel file: {e}")
        st.stop()

    # Ensure columns
    req_cols = ['KK_NO','NIK','CUSTNAME','JENIS_KELAMIN','TANGGAL_LAHIR','TEMPAT_LAHIR']
    missing = [c for c in req_cols if c not in df_full.columns]
    if missing:
        st.error(f"Missing columns: {', '.join(missing)}")
        st.stop()

    df_req = df_full[req_cols].copy()
    # Normalize date strings
    df_req['TANGGAL_LAHIR'] = pd.to_datetime(df_req['TANGGAL_LAHIR'], format='%d/%m/%Y', errors='coerce') \
        .dt.strftime('%d/%m/%Y')

    # Split clean & messy
    messy_df, clean_df = clean_data(df_req, kota_list)
    total = len(df_req)
    clean_cnt, messy_cnt = len(clean_df), len(messy_df)
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
    with c1:
        st.markdown("<div class='metric-container'>", unsafe_allow_html=True)
        st.metric("Total Records", f"{total:,}")
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='metric-container'>", unsafe_allow_html=True)
        st.metric("Clean Records", f"{clean_cnt:,}", f"{clean_cnt/total*100:.1f}%")
        st.markdown("</div>", unsafe_allow_html=True)
    with c3:
        st.markdown("<div class='metric-container'>", unsafe_allow_html=True)
        st.metric("Messy Records", f"{messy_cnt:,}", f"{messy_cnt/total*100:.1f}%")
        st.markdown("</div>", unsafe_allow_html=True)

    # Invalid breakdown chart
    inv_df = pd.DataFrame({'Category': list(invalid_counts.keys()), 'Count': list(invalid_counts.values())})
    fig = px.bar(inv_df, x='Category', y='Count', text='Count', color='Category')
    fig.update_layout(showlegend=False, margin=dict(t=30, b=20, l=0, r=0))
    st.subheader("Invalid Data Breakdown")
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Lihat Detail Breakdown"):
        st.table(inv_df.style.format({'Count':'{:,}'}))

    # Samples and download
    st.subheader("Data Samples & Unduhan")
    tab1, tab2 = st.tabs(["Clean Sample","Messy Sample"])
    with tab1:
        st.dataframe(clean_df.head(10))
    with tab2:
        st.dataframe(messy_df.head(10))

    report = generate_excel(messy_df, clean_df, total)
    st.download_button(
        "📥 Download Full Report",
        data=report,
        file_name="validation_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.warning("Silakan upload file Excel dan City List di sidebar untuk memulai.")
    st.markdown(
        "- **KK_NO**: 16 digit, tidak berakhiran '0000'<br>"
        "- **NIK**: 16 digit, tidak berakhiran '0000'<br>"
        "- **Nama**: tanpa angka<br>"
        "- **Jenis Kelamin**: LAKI-LAKI / PEREMPUAN<br>"
        "- **Tanggal Lahir**: DD/MM/YYYY, tidak di masa depan<br>"
        "- **Tempat Lahir**: sesuai daftar kota", unsafe_allow_html=True
    )
