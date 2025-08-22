import io
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# PDF (ReportLab)
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader

st.set_page_config(page_title="Factura Proforma", page_icon="🧾", layout="wide")

# =====================================
# Rutas fijas (archivos dentro del repo)
# =====================================
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
IMG_DIR = BASE_DIR / "images"

CAT_PATH = DATA_DIR / "catalogo.xlsx" # Requerido
WH_PATH = DATA_DIR / "almacenes.xlsx" # Requerido si se elige BO/Taller
DST_PATH = DATA_DIR / "destinos.xlsx" # Requerido siempre

LOGO_PATH = IMG_DIR / "logo.png" # Opcional pero recomendado
FOOTER_PATH = IMG_DIR / "footer.png" # Opcional

# =========================
# Utilidades / Carga datos
# =========================
@st.cache_data(show_spinner=False)
def read_table(path: Path, required_cols):
if not path.exists():
return None, f"No se encontró: {path}"
try:
if path.suffix.lower() in (".xlsx", ".xls"):
df = pd.read_excel(path)
else:
df = pd.read_csv(path, sep=None, engine="python")
except Exception as e:
return None, f"Error leyendo {path.name}: {e}"

missing = [c for c in required_cols if c not in df.columns]
if missing:
return None, f"En {path.name} faltan columnas: {missing}"
return df, None

def lookup_catalog(catalog_df, ref):
if catalog_df is None or catalog_df.empty or not ref:
return None, None
row = catalog_df.loc[
catalog_df["Referencia"].astype(str).str.strip().str.upper() ==
str(ref).strip().upper()
]
if row.empty:
return None, None
desc = row.iloc[0]["Descripcion"]
price = row.iloc[0]["PrecioUD"]
try:
price = float(price)
except Exception:
price = None
return desc, price

def lookup_warehouse(wh_df, code):
if wh_df is None or wh_df.empty or not code:
return None
row = wh_df.loc[wh_df["Almacen"].astype(str).str.strip() == str(code).strip()]
if row.empty:
return None
return row.iloc[0]["Descripcion"]

def load_image_reader(path: Path):
"""Devuelve (ImageReader, (w_px, h_px)) o (None, (0,0)) si no existe."""
if not path.exists():
return None, (0, 0)
try:
# ImageReader soporta path directamente
reader = ImageReader(str(path))
w, h = reader.getSize()
return reader, (w, h)
except Exception:
return None, (0, 0)

# =========================
# Estado de sesión (líneas)
# =========================
def ensure_session_state():
if "lines" not in st.session_state:
st.session_state.lines = [{
"ref": "", "qty": 1, "desc": "", "price": None, "amount": 0.0
}]

ensure_session_state()

# ================
# Cargar ficheros
# ================
catalog_df, cat_err = read_table(CAT_PATH, ["Referencia", "Descripcion", "PrecioUD"])
wh_df, wh_err = read_table(WH_PATH, ["Almacen", "Descripcion"])
dest_df, dst_err = read_table(DST_PATH, ["Nombre", "Direccion", "CP", "Ciudad", "Pais", "CIF"])

# Mostrar errores bloqueantes
fatal_errors = []
if cat_err: fatal_errors.append(cat_err) # si no hay catálogo, aún permitimos precio manual, pero avisamos
if dst_err: fatal_errors.append(dst_err) # destino es obligatorio

if fatal_errors:
st.error("No se puede iniciar la aplicación por errores en los datos:\n\n- " + "\n- ".join(fatal_errors))
st.stop()

# Cargar imágenes (no son fatales)
logo_reader, logo_size = load_image_reader(LOGO_PATH)
footer_reader, footer_sz = load_image_reader(FOOTER_PATH)

if not logo_reader:
st.warning("No se encontró la imagen de cabecera: `images/logo.png` (se generará el PDF sin logo).")

# =========================
# UI
# =========================
st.title("🧾 Generador de Factura Proforma (PDF)")
st.caption("Los datos se leen del repositorio (carpetas `data/` e `images/`). El usuario no carga ficheros en la app.")

with st.form("form_proforma", clear_on_submit=False):
st.subheader("1) Datos del solicitante")
solicitante = st.selectbox("Solicitante", ["BO/Taller", "Almacén Central", "Proveedor"])
wh_code = None
wh_desc = None
proveedor_nombre = None

if solicitante == "BO/Taller":
wh_code = st.text_input("Número de almacén solicitante")
if wh_code:
if wh_err:
st.error(f"No se pudo cargar `almacenes.xlsx`: {wh_err}")
else:
wh_desc = lookup_warehouse(wh_df, wh_code)
if wh_desc:
st.success(f"Almacén válido: {wh_desc}")
else:
st.warning("Almacén no encontrado en `almacenes.xlsx`.")
elif solicitante == "Proveedor":
proveedor_nombre = st.text_input("Nombre del proveedor", placeholder="Ej.: Proveedor XYZ, S.L.")

st.markdown("---")
st.subheader("2) Datos de la operación")
oa_sgr = st.text_input("OA/Traspaso SGR*", placeholder="Ej.: OA123456 o SGR98765")

st.markdown("---")
st.subheader("3) Destino (desde data/destinos.xlsx)")
destino_opts = dest_df["Nombre"].astype(str).tolist()
destino_sel = st.selectbox("Selecciona destino*", destino_opts)
dest_row = dest_df[dest_df["Nombre"] == destino_sel].iloc[0].to_dict()

st.caption("Se usará la dirección, CP, ciudad, país y CIF de la fila seleccionada para la cabecera del PDF.")

st.markdown("---")
st.subheader("4) Referencias")
st.caption("Introduce referencias y cantidades. Si existen en el catálogo, se completan descripción y precio.")

# Líneas dinámicas
lines_to_remove = []
for i, line in enumerate(st.session_state.lines):
cols = st.columns([2, 1, 4, 2, 2, 1])
with cols[0]:
ref = st.text_input(f"Referencia #{i+1}", value=line["ref"], key=f"ref_{i}")
with cols[1]:
qty = st.number_input(f"Cantidad #{i+1}", min_value=1, value=int(line["qty"]), step=1, key=f"qty_{i}")

# Completar desde catálogo si existe
desc, price = lookup_catalog(catalog_df, ref)
if desc is None:
desc = line.get("desc", "")
if price is None:
price = line.get("price", None)

amount = (price or 0) * qty

with cols[2]:
st.text_input(f"Descripción #{i+1}", value=str(desc) if desc else "", key=f"desc_{i}")
with cols[3]:
st.number_input(f"Precio/UD #{i+1}", min_value=0.0, value=float(price) if price else 0.0, step=0.01, key=f"price_{i}")
with cols[4]:
st.number_input(f"Importe € #{i+1}", min_value=0.0, value=float(amount), step=0.01, key=f"amount_{i}", disabled=True)
with cols[5]:
if st.button("🗑️", key=f"del_{i}", help="Eliminar línea"):
lines_to_remove.append(i)

# Persistir
st.session_state.lines[i] = {
"ref": st.session_state[f"ref_{i}"],
"qty": st.session_state[f"qty_{i}"],
"desc": st.session_state[f"desc_{i}"],
"price": st.session_state[f"price_{i}"],
"amount": st.session_state[f"amount_{i}"],
}

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

submitted = st.form_submit_button("🔵 Generar Factura Proforma", use_container_width=True)

# =========================
# Validaciones
# =========================
def validate(oa_sgr, solicitante, wh_code, wh_desc, proveedor_nombre, lines, catalog_df):
errors = []
# OA / SGR
if not oa_sgr:
errors.append("El campo OA/Traspaso SGR es obligatorio.")
elif not re.match(r"^(OA|SGR)\d+$", oa_sgr.strip(), flags=re.IGNORECASE):
errors.append("OA/SGR debe comenzar por 'OA' o 'SGR' y seguir con números (sin espacios).")

# Solicitante
if solicitante == "BO/Taller":
if not wh_code:
errors.append("Debes indicar el número de almacén solicitante.")
elif wh_err:
errors.append(f"Listado de almacenes no disponible: {wh_err}")
elif not wh_desc:
errors.append("El almacén indicado no existe en `almacenes.xlsx`.")
elif solicitante == "Proveedor":
if not proveedor_nombre or not proveedor_nombre.strip():
errors.append("Debes indicar el nombre del proveedor.")

# Líneas
valid_lines = []
if not lines or all((not l["ref"]) for l in lines):
errors.append("Debes introducir al menos una referencia.")
else:
for idx, l in enumerate(lines, start=1):
ref = str(l["ref"]).strip()
if not ref:
continue
qty = int(l["qty"]) if l["qty"] else 0
desc, price = lookup_catalog(catalog_df, ref)
final_desc = l["desc"] or desc or ""
final_price = l["price"] if l["price"] not in (None, "") else price
if catalog_df is not None and not desc:
errors.append(f"Línea {idx}: la referencia '{ref}' no existe en el catálogo.")
if qty <= 0:
errors.append(f"Línea {idx}: la cantidad debe ser mayor que 0.")
if final_price in (None, ""):
errors.append(f"Línea {idx}: falta Precio/UD (catálogo o manual).")
amount = (float(final_price) if final_price not in (None, "") else 0.0) * qty
valid_lines.append({
"ref": ref,
"qty": qty,
"desc": final_desc,
"price": float(final_price) if final_price not in (None, "") else 0.0,
"amount": float(amount)
})
return errors, valid_lines

# =========================
# Generación de PDF
# =========================
def generate_pdf(logo_reader, footer_reader, destinatario, solicitante, wh_code, wh_desc, proveedor_nombre, oa_sgr, lines):
buffer = io.BytesIO()
c = canvas.Canvas(buffer, pagesize=landscape(A4))
width, height = landscape(A4)

margin = 15 * mm
x_left = margin
y_top = height - margin

# 1) Cabecera: logo
if logo_reader:
# Alto máximo 22mm manteniendo proporción
w_px, h_px = logo_reader.getSize()
max_h = 22 * mm
ratio = max_h / h_px
new_w, new_h = w_px * ratio, h_px * ratio
c.drawImage(logo_reader, x_left, y_top - new_h, width=new_w, height=new_h, mask='auto')
y_after_logo = y_top - new_h - 4 * mm
else:
y_after_logo = y_top

# 2) Recuadro
box_text = "Material gratuito sin valor comercial (Valor a precio estadístico)"
box_x, box_y = x_left, y_after_logo - 12 * mm
box_w, box_h = 120 * mm, 10 * mm
c.setStrokeColor(colors.black)
c.rect(box_x, box_y, box_w, box_h, stroke=1, fill=0)
c.setFont("Helvetica-Bold", 10)
c.drawCentredString(box_x + box_w / 2, box_y + 3.2 * mm, box_text)

# 3) Texto fijo
fixed_lines = [
"Servicio POSTVENTA",
"C/TITAN 15",
"28045 - MADRID (ESPAÑA) CIF A28078202"
]
text_y0 = box_y - 16 * mm
c.setFont("Helvetica", 10)
for i, line in enumerate(fixed_lines):
c.drawString(x_left, text_y0 - i * 5.2 * mm, line)

# 4) Bloque DESTINO (derecha)
dest_block_x = width - margin - 110 * mm
dest_block_y = y_top - 5 * mm
c.setFont("Helvetica-Bold", 12)
c.drawString(dest_block_x, dest_block_y, "DESTINO")
c.setFont("Helvetica", 10)
dlines = [
destinatario.get("Nombre", ""),
destinatario.get("Direccion", ""),
f"{destinatario.get('CP','')} {destinatario.get('Ciudad','')}".strip(),
destinatario.get("Pais", ""),
f"CIF: {destinatario.get('CIF','')}".strip()
]
for i, line in enumerate([l for l in dlines if l]):
c.drawString(dest_block_x, dest_block_y - (6 * mm) * (i + 1), line)

# 5) Número de factura proforma
c.setFont("Helvetica-Bold", 11)
c.drawString(x_left, text_y0 - 22 * mm, f"NUMERO DE FACTURA PROFORMA: {oa_sgr}")

# 6) Info solicitante
c.setFont("Helvetica", 9)
sol_text = f"Solicitante: {solicitante}"
if solicitante == "BO/Taller" and wh_code:
sol_text += f" · Almacén {wh_code} ({wh_desc or 'No encontrado'})"
if solicitante == "Proveedor" and proveedor_nombre:
sol_text += f" · {proveedor_nombre}"
c.drawString(x_left, text_y0 - 28 * mm, sol_text)

# 7) Tabla de referencias
table_data = [["Referencia", "Cantidad", "Descripción", "Precio/UD", "Importe/Euros"]]
total = 0.0
for l in lines:
total += float(l["amount"])
table_data.append([
str(l["ref"]),
int(l["qty"]),
str(l["desc"]),
f"{float(l['price']):.2f}",
f"{float(l['amount']):.2f}",
])
table_data.append(["", "", "", "TOTAL €", f"{total:.2f}"])

table = Table(table_data, colWidths=[30*mm, 22*mm, 110*mm, 25*mm, 30*mm])
style = TableStyle([
("FONT", (0,0), (-1,0), "Helvetica-Bold", 10),
("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
("GRID", (0,0), (-1,-1), 0.5, colors.black),
("ALIGN", (1,1), (1,-2), "RIGHT"), # Cantidad
("ALIGN", (3,1), (4,-2), "RIGHT"), # Precio / Importe
("VALIGN", (0,0), (-1,-1), "MIDDLE"),
("FONT", (0,1), (-1,-2), "Helvetica", 9),
("FONT", (-2,-1), (-1,-1), "Helvetica-Bold", 10),
("ALIGN", (-2,-1), (-1,-1), "RIGHT"),
])
table.setStyle(style)

table_x = x_left
table_y = text_y0 - 45 * mm
w, h = table.wrapOn(c, width - 2*margin, height)
table.drawOn(c, table_x, table_y - h)

# 8) Imagen de pie
if footer_reader:
w2, h2 = footer_reader.getSize()
max_h2 = 18 * mm
ratio2 = max_h2 / h2
new_w2, new_h2 = w2 * ratio2, h2 * ratio2
c.drawImage(footer_reader, x_left, margin, width=new_w2, height=new_h2, mask='auto')

# Pie con fecha/hora
c.setFont("Helvetica-Oblique", 8)
c.drawRightString(width - margin, margin, f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}")

c.showPage()
c.save()
buffer.seek(0)
return buffer

# ================
# Acción principal
# ================
if submitted:
errs, valid_lines = validate(
oa_sgr=oa_sgr,
solicitante=solicitante,
wh_code=wh_code,
wh_desc=lookup_warehouse(wh_df, wh_code) if solicitante == "BO/Taller" and wh_code else None,
proveedor_nombre=proveedor_nombre,
lines=st.session_state.lines,
catalog_df=catalog_df
)
if errs:
st.error("Corrige los siguientes errores:\n\n- " + "\n- ".join(errs))
else:
destinatario = {
"Nombre": dest_row.get("Nombre", ""),
"Direccion": dest_row.get("Direccion", ""),
"CP": dest_row.get("CP", ""),
"Ciudad": dest_row.get("Ciudad", ""),
"Pais": dest_row.get("Pais", ""),
"CIF": dest_row.get("CIF", ""),
}
pdf_buffer = generate_pdf(
logo_reader=logo_reader,
footer_reader=footer_reader,
destinatario=destinatario,
solicitante=solicitante,
wh_code=wh_code,
wh_desc=lookup_warehouse(wh_df, wh_code) if solicitante == "BO/Taller" and wh_code else None,
proveedor_nombre=proveedor_nombre,
oa_sgr=oa_sgr.strip().upper(),
lines=valid_lines
)
st.success("✅ Factura Proforma generada correctamente.")
st.download_button(
"📥 Descargar PDF",
data=pdf_buffer,
file_name=f"Factura_Proforma_{oa_sgr.strip().upper()}.pdf",
mime="application/pdf",
use_container_width=True
)

# Ayuda
with st.expander("ℹ️ Notas"):
st.markdown("""
- Los datos se leen de `data/` y las imágenes de `images/`.
- **destinos.xlsx** es obligatorio (columnas: `Nombre`, `Direccion`, `CP`, `Ciudad`, `Pais`, `CIF`).
- **almacenes.xlsx** se usa para validar si el solicitante es **BO/Taller** (columnas: `Almacen`, `Descripcion`).
- **catalogo.xlsx** rellena automáticamente descripción y precio (columnas: `Referencia`, `Descripcion`, `PrecioUD`). Si una referencia no está, podrás indicar el precio manualmente.
- El PDF se genera en **A4 horizontal** con logo, recuadro, datos fijos, bloque de **DESTINO**, número de proforma y tabla de referencias.
""")
