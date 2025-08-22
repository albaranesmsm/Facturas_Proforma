import io
import re
import os
from datetime import datetime
import pandas as pd
import streamlit as st
from PIL import Image
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Table, TableStyle
# Configuración
st.set_page_config(page_title="Factura Proforma", page_icon="🧾", layout="wide")
# =========================
# Funciones de ayuda
# =========================
def load_excel(path, required_cols):
   if not os.path.exists(path):
       st.error(f"No se encuentra el archivo requerido: {path}")
       st.stop()
   df = pd.read_excel(path)
   missing = [c for c in required_cols if c not in df.columns]
   if missing:
       st.error(f"Faltan columnas en {path}: {missing}")
       st.stop()
   return df
def lookup_catalog(catalog_df, ref):
   row = catalog_df.loc[catalog_df["Referencia"].astype(str).str.strip().str.upper() == str(ref).strip().upper()]
   if row.empty:
       return None, None
   desc = row.iloc[0]["Descripcion"]
   price = row.iloc[0]["PrecioUD"]
   return desc, float(price)
def lookup_warehouse(wh_df, code):
   row = wh_df.loc[wh_df["Almacen"].astype(str).str.strip() == str(code).strip()]
   if row.empty:
       return None
   return row.iloc[0]["Descripcion"]
# =========================
# Cargar datos fijos
# =========================
CATALOGO_PATH = "data/catalogo.xlsx"
ALMACENES_PATH = "data/almacenes.xlsx"
DESTINOS_PATH = "data/destinos.xlsx"
IMG1_PATH = "images/logo.png"
IMG2_PATH = "images/footer.png"
catalog_df = load_excel(CATALOGO_PATH, ["Referencia", "Descripcion", "PrecioUD"])
wh_df = load_excel(ALMACENES_PATH, ["Almacen", "Descripcion"])
dest_df = load_excel(DESTINOS_PATH, ["Nombre", "Direccion", "CP", "Ciudad", "Pais", "CIF"])
img1 = Image.open(IMG1_PATH) if os.path.exists(IMG1_PATH) else None
img2 = Image.open(IMG2_PATH) if os.path.exists(IMG2_PATH) else None
# =========================
# Estado de sesión
# =========================
if "lines" not in st.session_state:
   st.session_state.lines = [{"ref": "", "qty": 1, "desc": "", "price": None, "amount": 0.0}]
# =========================
# Formulario
# =========================
st.title("🧾 Generador de Factura Proforma")
with st.form("form_proforma"):
   st.subheader("1) Solicitante")
   solicitante = st.selectbox("Solicitante", ["BO/Taller", "Almacén Central", "Proveedor"])
   wh_code = None
   wh_desc = None
   proveedor_nombre = None
   if solicitante == "BO/Taller":
       wh_code = st.text_input("Número de almacén solicitante")
       if wh_code:
           wh_desc = lookup_warehouse(wh_df, wh_code)
           if wh_desc:
               st.success(f"Almacén válido: {wh_desc}")
           else:
               st.error("Almacén no encontrado.")
   elif solicitante == "Proveedor":
       proveedor_nombre = st.text_input("Nombre del proveedor")
   st.subheader("2) Datos de la operación")
   oa_sgr = st.text_input("OA/Traspaso SGR*", placeholder="Ej.: OA123456 o SGR98765")
   st.subheader("3) Destino de la mercancía")
   destino = st.selectbox("Destino*", dest_df["Nombre"].tolist())
   dest_row = dest_df[dest_df["Nombre"] == destino].iloc[0].to_dict()
   st.subheader("4) Referencias")
   lines_to_remove = []
   for i, line in enumerate(st.session_state.lines):
       cols = st.columns([2, 1, 4, 2, 2, 1])
       with cols[0]:
           ref = st.text_input(f"Referencia #{i+1}", value=line["ref"], key=f"ref_{i}")
       with cols[1]:
           qty = st.number_input(f"Cantidad #{i+1}", min_value=1, value=int(line["qty"]), step=1, key=f"qty_{i}")
       desc, price = lookup_catalog(catalog_df, ref)
       desc = desc or line["desc"]
       price = price or line["price"]
       amount = (price or 0) * qty
       with cols[2]:
           st.text_input(f"Descripción #{i+1}", value=desc or "", key=f"desc_{i}")
       with cols[3]:
           st.number_input(f"Precio/UD #{i+1}", min_value=0.0, value=float(price) if price else 0.0, step=0.01, key=f"price_{i}")
       with cols[4]:
           st.number_input(f"Importe € #{i+1}", min_value=0.0, value=float(amount), step=0.01, key=f"amount_{i}", disabled=True)
       with cols[5]:
           if st.button("🗑️", key=f"del_{i}"):
               lines_to_remove.append(i)
       st.session_state.lines[i] = {
           "ref": st.session_state[f"ref_{i}"],
           "qty": st.session_state[f"qty_{i}"],
           "desc": st.session_state[f"desc_{i}"],
           "price": st.session_state[f"price_{i}"],
           "amount": st.session_state[f"amount_{i}"],
       }
   for idx in sorted(lines_to_remove, reverse=True):
       st.session_state.lines.pop(idx)
   if st.form_submit_button("Generar Factura Proforma"):
       # Validaciones
       if not oa_sgr or not re.match(r"^(OA|SGR)\d+$", oa_sgr.strip(), re.IGNORECASE):
           st.error("El campo OA/SGR es obligatorio y debe tener formato correcto.")
           st.stop()
       if solicitante == "BO/Taller" and not wh_desc:
           st.error("El almacén introducido no es válido.")
           st.stop()
       if solicitante == "Proveedor" and not proveedor_nombre:
           st.error("Debes indicar el nombre del proveedor.")
           st.stop()
       if not st.session_state.lines:
           st.error("Debes añadir al menos una línea de referencia.")
           st.stop()
       # Generar PDF
       buffer = io.BytesIO()
       c = canvas.Canvas(buffer, pagesize=landscape(A4))
       width, height = landscape(A4)
       margin = 15 * mm
       # Logo
       if img1:
           c.drawImage(IMG1_PATH, margin, height - 40 * mm, width=50*mm, height=20*mm, preserveAspectRatio=True)
       # Textos fijos
       c.setFont("Helvetica-Bold", 10)
       c.drawString(margin, height - 45 * mm, "Material gratuito sin valor comercial (Valor a precio estadístico)")
       c.setFont("Helvetica", 9)
       c.drawString(margin, height - 55 * mm, "Servicio POSTVENTA - C/TITAN 15 - 28045 MADRID (ESPAÑA) CIF A28078202")
       # Destinatario
       x_dest = width/2
       c.setFont("Helvetica-Bold", 10)
       c.drawString(x_dest, height - 30*mm, "DESTINATARIO:")
       c.setFont("Helvetica", 9)
       c.drawString(x_dest, height - 35*mm, f"{dest_row['Nombre']}")
       c.drawString(x_dest, height - 40*mm, f"{dest_row['Direccion']} {dest_row['CP']} {dest_row['Ciudad']}")
       c.drawString(x_dest, height - 45*mm, f"{dest_row['Pais']} - CIF: {dest_row['CIF']}")
       # Nº Factura
       c.setFont("Helvetica-Bold", 10)
       c.drawString(x_dest, height - 55*mm, f"NÚMERO FACTURA PROFORMA: {oa_sgr}")
       # Tabla
       data = [["Referencia", "Cantidad", "Descripción", "Precio/UD", "Importe €"]]
       for l in st.session_state.lines:
           data.append([l["ref"], l["qty"], l["desc"], f"{l['price']:.2f}", f"{l['amount']:.2f}"])
       table = Table(data, colWidths=[50*mm, 25*mm, 80*mm, 25*mm, 25*mm])
       table.setStyle(TableStyle([
           ("GRID", (0,0), (-1,-1), 0.5, colors.black),
           ("BACKGROUND", (0,0), (-1,0), colors.grey),
           ("ALIGN", (1,1), (-1,-1), "CENTER")
       ]))
       table.wrapOn(c, width, height)
       table.drawOn(c, margin, height - 110*mm)
       # Imagen pie
       if img2:
           c.drawImage(IMG2_PATH, margin, margin, width=50*mm, height=20*mm, preserveAspectRatio=True)
       c.save()
       pdf_bytes = buffer.getvalue()
       # Botón descarga
       st.download_button(
           "📥 Descargar Factura Proforma",
           pdf_bytes,
           file_name=f"Factura_{oa_sgr}.pdf",
           mime="application/pdf"
       )
