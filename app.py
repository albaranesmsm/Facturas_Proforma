import io
import re
from datetime import datetime
import pandas as pd
import streamlit as st
from PIL import Image
# --- PDF (ReportLab) ---
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
st.set_page_config(page_title="Factura Proforma", page_icon="🧾", layout="wide")
# =========================
# Helpers de carga de datos
# =========================
@st.cache_data(show_spinner=False)
def load_table(file, required_cols):
   if file is None:
       return None, "Sin archivo"
   try:
       if file.name.lower().endswith((".xlsx", ".xls")):
           df = pd.read_excel(file)
       else:
           df = pd.read_csv(file)
       missing = [c for c in required_cols if c not in df.columns]
       if missing:
           return None, f"Faltan columnas: {missing}"
       return df, None
   except Exception as e:
       return None, f"Error leyendo {file.name}: {e}"
def lookup_catalog(catalog_df, ref):
   if catalog_df is None or catalog_df.empty or not ref:
       return None, None
   row = catalog_df.loc[catalog_df["Referencia"].astype(str).str.strip().str.upper() == str(ref).strip().upper()]
   if row.empty:
       return None, None
   desc = row.iloc[0]["Descripcion"]
   price = row.iloc[0]["PrecioUD"]
   try:
       price = float(price)
   except Exception:
       price = None
   return desc, price
# =========================
# Estado de sesión
# =========================
def ensure_session_state():
   if "lines" not in st.session_state:
       st.session_state.lines = [{"ref": "", "qty": 1, "desc": "", "price": None, "amount": 0.0}]
   if "img1" not in st.session_state:
       st.session_state.img1 = None
   if "img2" not in st.session_state:
       st.session_state.img2 = None
ensure_session_state()
# =========================
# Barra lateral: ficheros
# =========================
st.sidebar.header("Fuentes de datos")
cat_file = st.sidebar.file_uploader("Catálogo (Referencia, Descripcion, PrecioUD) · Excel/CSV", type=["csv", "xlsx", "xls"])
catalog_df, cat_err = load_table(cat_file, ["Referencia", "Descripcion", "PrecioUD"])
if cat_err and cat_file is not None:
   st.sidebar.error(cat_err)
dest_file = st.sidebar.file_uploader("Destinos / Destinatarios · Excel/CSV", type=["csv", "xlsx", "xls"])
dest_df, dest_err = load_table(dest_file, ["Nombre", "Direccion", "CP", "Ciudad", "Pais", "CIF"])
if dest_err and dest_file is not None:
   st.sidebar.error(dest_err)
st.sidebar.header("Imágenes")
img1_up = st.sidebar.file_uploader("Imagen 1 (cabecera)", type=["png", "jpg", "jpeg"])
img2_up = st.sidebar.file_uploader("Imagen 2 (pie)", type=["png", "jpg", "jpeg"])
if img1_up:
   st.session_state.img1 = Image.open(img1_up)
if img2_up:
   st.session_state.img2 = Image.open(img2_up)
# =========================
# Formulario principal
# =========================
st.title("🧾 Generador de Factura Proforma (PDF)")
st.caption("Rellena el formulario y pulsa 'Generar Factura Proforma'.")
with st.form("form_proforma", clear_on_submit=False):
   st.subheader("1) Datos del solicitante")
   solicitante = st.selectbox("Solicitante", ["BO/Taller", "Almacén Central", "Proveedor"])
   wh_code = None
   wh_desc = None
   proveedor_nombre = None
   if solicitante == "BO/Taller":
       wh_code = st.text_input("Número de almacén solicitante")
   elif solicitante == "Proveedor":
       proveedor_nombre = st.text_input("Nombre del proveedor")
   st.subheader("2) Datos de la operación")
   oa_sgr = st.text_input("OA/Traspaso SGR*", placeholder="Ej.: OA123456 o SGR98765")
   # =========================
   # Destino desde Excel
   # =========================
   if dest_df is not None and not dest_df.empty:
       destino_opts = dest_df["Nombre"].tolist()
       destino = st.selectbox("Destino de la mercancía*", destino_opts)
       dest_row = dest_df[dest_df["Nombre"] == destino].iloc[0].to_dict()
   else:
       st.error("⚠️ Debes cargar un Excel de destinos en la barra lateral.")
       st.stop()
   st.subheader("3) Referencias")
   st.caption("Añade tantas líneas como necesites. Se validan contra el catálogo.")
   # Dibujar líneas dinámicas
   lines_to_remove = []
   for i, line in enumerate(st.session_state.lines):
       cols = st.columns([2,1,4,2,2,1])
       with cols[0]:
           ref = st.text_input(f"Referencia #{i+1}", value=line["ref"], key=f"ref_{i}")
       with cols[1]:
           qty = st.number_input(f"Cantidad #{i+1}", min_value=1, value=int(line["qty"]), step=1, key=f"qty_{i}")
       desc, price = lookup_catalog(catalog_df, ref)
       if desc is None:
           desc = line.get("desc","")
       if price is None:
           price = line.get("price", None)
       amount = (price or 0) * qty
       with cols[2]:
           st.text_input(f"Descripción #{i+1}", value=str(desc) if desc else "", key=f"desc_{i}")
       with cols[3]:
           price_in = st.number_input(f"Precio/UD #{i+1}", min_value=0.0, value=float(price) if price else 0.0, step=0.01, key=f"price_{i}")
       with cols[4]:
           st.number_input(f"Importe € #{i+1}", min_value=0.0, value=float(amount), step=0.01, key=f"amount_{i}", disabled=True)
       with cols[5]:
           if st.button("🗑️", key=f"del_{i}"):
               lines_to_remove.append(i)
       st.session_state.lines[i] = {"ref": st.session_state[f"ref_{i}"],
                                    "qty": st.session_state[f"qty_{i}"],
                                    "desc": st.session_state[f"desc_{i}"],
                                    "price": st.session_state[f"price_{i}"],
                                    "amount": st.session_state[f"amount_{i}"]}
   for idx in sorted(lines_to_remove, reverse=True):
       st.session_state.lines.pop(idx)
   cols_btn = st.columns(2)
   with cols_btn[0]:
       if st.button("➕ Añadir línea"):
           st.session_state.lines.append({"ref": "", "qty": 1, "desc": "", "price": None, "amount": 0.0})
           st.experimental_rerun()
   with cols_btn[1]:
       if st.button("🧹 Vaciar líneas"):
           st.session_state.lines = [{"ref": "", "qty": 1, "desc": "", "price": None, "amount": 0.0}]
           st.experimental_rerun()
   submitted = st.form_submit_button("🔵 Generar Factura Proforma")
# =========================
# Validaciones
# =========================
def validate(oa_sgr, solicitante, wh_code, proveedor_nombre, lines, catalog_df):
   errors = []
   if not oa_sgr:
       errors.append("El campo OA/Traspaso SGR es obligatorio.")
   elif not re.match(r"^(OA|SGR)\d+$", oa_sgr.strip(), flags=re.IGNORECASE):
       errors.append("El campo OA/Traspaso SGR debe comenzar por 'OA' o 'SGR' seguido de números.")
   if solicitante == "BO/Taller":
       if not wh_code:
           errors.append("Debes indicar el número de almacén.")
   elif solicitante == "Proveedor":
       if not proveedor_nombre:
           errors.append("Debes indicar el nombre del proveedor.")
   valid_lines = []
   if not lines or all((not l["ref"]) for l in lines):
       errors.append("Debes introducir al menos una referencia.")
   else:
       for idx, l in enumerate(lines, start=1):
           ref = l["ref"].strip()
           qty = int(l["qty"])
           desc, price = lookup_catalog(catalog_df, ref)
           final_desc = l["desc"] or desc or ""
           final_price = l["price"] if l["price"] not in (None,"") else price
           if not ref:
               continue
           if catalog_df is not None and not desc:
               errors.append(f"Línea {idx}: la referencia '{ref}' no existe en el catálogo.")
           amount = (float(final_price) if final_price else 0.0) * qty
           valid_lines.append({"ref": ref, "qty": qty, "desc": final_desc, "price": float(final_price) if final_price else 0.0, "amount": amount})
   return errors, valid_lines
# =========================
# PDF generator (simplificado)
# =========================
def generate_pdf(img1, img2, destino_row, solicitante, wh_code, proveedor_nombre, oa_sgr, lines):
   buffer = io.BytesIO()
   c = canvas.Canvas(buffer, pagesize=landscape(A4))
   width, height = landscape(A4)
   margin = 15*mm
   y = height - margin
   # Imagen cabecera
   if img1:
       img1_io = io.BytesIO()
       img1.save(img1_io, format="PNG")
       img1_io.seek(0)
       c.drawImage(Image.open(img1_io), margin, y-30*mm, width=100*mm, preserveAspectRatio=True, mask='auto')
   y -= 35*mm
   # Texto fijo
   c.setFont("Helvetica-Bold", 10)
   c.drawString(margin, y, "Material gratuito sin valor comercial (Valor a precio estadístico)")
   y -= 8*mm
   c.setFont("Helvetica", 10)
   c.drawString(margin, y, "Servicio POSTVENTA C/TITAN 15 28045 - MADRID (ESPAÑA) CIF A28078202")
   # DESTINATARIO
   c.drawRightString(width-margin, y+8*mm, f"DESTINATARIO: {destino_row['Nombre']}")
   y -= 10*mm
   c.drawRightString(width-margin, y, f"NUMERO DE FACTURA PROFORMA: {oa_sgr}")
   y -= 10*mm
   # Tabla referencias
   data = [["Referencia","Cantidad","Descripción","Precio/UD","Importe €"]]
   for l in lines:
       data.append([l["ref"], l["qty"], l["desc"], f"{l['price']:.2f}", f"{l['amount']:.2f}"])
   table = Table(data, colWidths=[30*mm, 25*mm, 80*mm, 30*mm, 30*mm])
   style = TableStyle([('GRID',(0,0),(-1,-1),0.5,colors.black),
                       ('BACKGROUND',(0,0),(-1,0),colors.lightgrey),
                       ('ALIGN',(1,1),(-1,-1),'CENTER')])
   table.setStyle(style)
   table.wrapOn(c, width, height)
   table.drawOn(c, margin, y - 20*mm)
   # Imagen pie
   if img2:
       img2_io = io.BytesIO()
       img2.save(img2_io, format="PNG")
       img2_io.seek(0)
       c.drawImage(Image.open(img2_io), margin, 10*mm, width=100*mm, preserveAspectRatio=True, mask='auto')
   c.showPage()
   c.save()
   buffer.seek(0)
   return buffer
# =========================
# Generar PDF
# =========================
if submitted:
   errors, valid_lines = validate(oa_sgr, solicitante, wh_code, proveedor_nombre, st.session_state.lines, catalog_df)
   if errors:
       st.error("Errores:\n- " + "\n- ".join(errors))
   else:
       pdf_buffer = generate_pdf(st.session_state.img1, st.session_state.img2, dest_row, solicitante, wh_code, proveedor_nombre, oa_sgr, valid_lines)
       st.success("✅ Factura Proforma generada correctamente")
       st.download_button("📥 Descargar PDF", data=pdf_buffer, file_name=f"Factura_{oa_sgr}.pdf", mime="application/pdf")