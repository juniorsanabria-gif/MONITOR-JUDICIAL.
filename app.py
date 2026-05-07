import streamlit as st
import pandas as pd
import re
import unicodedata
import requests
from bs4 import BeautifulSoup
from io import BytesIO

# Configuración de página
st.set_page_config(page_title="IVANDAY Judicial Cloud", layout="wide")

# Estilo visual
st.markdown("""
    <style>
    .report-card { display: flex; border: 1px solid #999; margin-bottom: 2px; background: white; }
    .juz-col { width: 25%; padding: 8px; font-weight: bold; background: #f2f2f2; border-right: 1px solid #999; font-size: 11px; }
    .exp-col { width: 15%; padding: 8px; background: #FFFF00; font-weight: bold; text-align: center; border-right: 1px solid #999; }
    .txt-col { width: 60%; padding: 8px; font-size: 11px; }
    </style>
""", unsafe_allow_html=True)

def aplicar_logica_io(texto):
    if not texto or pd.isna(texto): return ""
    t = ''.join(c for c in unicodedata.normalize('NFD', str(texto).upper()) if unicodedata.category(c) != 'Mn')
    ignorar = ["VS", "SUCESION", "BIENES", "CONTRA", "EL", "LA", "DE", "LOS", "DEL", "SECRETO"]
    palabras = [p for p in re.sub(r'[^A-Z0-9/]', ' ', t).split() if p not in ignorar and len(p) > 2]
    return palabras

def norm_exp(e):
    m = re.search(r"(\d+)/(\d{4})", str(e))
    return f"{int(m.group(1))}/{m.group(2)}" if m else None

def procesar_judicial(u_drive, u_bol):
    try:
        # 1. Leer Drive
        d_url = re.sub(r'/edit.*', '/export?format=xlsx', u_drive)
        r = requests.get(d_url)
        # Importante: Asegúrate que la pestaña se llame así o cambia el nombre aquí:
        df = pd.read_excel(BytesIO(r.content), sheet_name="Ivan de abril 2026")
        
        # Filtrado de filas 100-106 (índices 99-106) y columnas C-F
        base = df.iloc[99:106, [2, 3, 4, 5]]
        base.columns = ['ID', 'EXP', 'TIPO', 'NOMBRE']

        # 2. Leer Boletín
        h = {'User-Agent': 'Mozilla/5.0'}
        rb = requests.get(u_bol, headers=h, verify=False)
        rb.encoding = rb.apparent_encoding
        texto_bol = BeautifulSoup(rb.text, 'html.parser').get_text(separator="\n")
        
        lineas = texto_bol.split("\n")
        res = []
        juzgado = "JUZGADO"

        for i, linea in enumerate(lineas):
            if any(x in linea.upper() for x in ["JUZGADO", "SALA", "FAMILIAR"]): juzgado = linea.strip()
            
            for _, row in base.iterrows():
                target = norm_exp(row['EXP'])
                if target and target in linea:
                    claves = aplicar_logica_io(row['NOMBRE'])
                    contexto = " ".join(lineas[i:i+4]).upper()
                    if any(c in contexto for c in claves):
                        res.append({"J": juzgado, "E": target, "T": linea.strip()})
        return res
    except Exception as e:
        st.error(f"Error detectado: {e}")
        return []

st.title("⚖️ MONITOR IVANDAY CLOUD")

# Inputs
drive_link = st.text_input("Enlace de Google Sheets:", "https://docs.google.com/spreadsheets/d/1ssS6Zod7sUZnJBxTyBjzD5G9Arv4UNpn/edit")
bol_link = st.text_input("Enlace del Boletín PJBC:", "https://www.pjbc.gob.mx/boletinj/2026/my_html/ti260430.htm")

if st.button("🚀 BUSCAR ACUERDOS"):
    data = procesar_judicial(drive_link, bol_link)
    if data:
        st.success(f"Encontrados {len(data)} acuerdos.")
        for r in data:
            st.markdown(f"""
                <div class="report-card">
                    <div class="juz-col">{r['J']}</div>
                    <div class="exp-col">{r['E']}</div>
                    <div class="txt-col">{r['T']}</div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("No se encontraron coincidencias para los expedientes del rango 100-106.")
