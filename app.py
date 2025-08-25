import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
import os
# ==========================
# FUNCIONES DE APOYO
# ==========================
def load_excel(path):
   """Carga un Excel si existe."""
   if not os.path.exists(path):
       st.error(f"No se encuentra el archivo requerido: {path}")
       return pd.DataFrame()
   return pd.read_excel(path)
def ruta_imagen(nombre_archivo):
   """Devuelve la ruta absoluta a la carpeta images/"""
   base_path = os.path.dirname(os.path.abspath(__file__))
   return os.path.join(base_path, "images", nombre_archivo)
def generar_pdf(solicitante, almacen_desc, proveedor, oa_sgr, destino_row, referencias):
   """Genera el PDF de la factura proforma."""
   buffer = BytesIO()
   doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
   elementos = []
   styles = getSampleStyleSheet()
   styleN = styles["Normal"]
   # === LOGO CENTRADO ARRIBA ===
   logo_path = ruta_imagen("logo.png")
   if os.path.exists(logo_path):
       logo = Image(logo_path, width=150, height=80)
       logo.hAlign = "CENTER"
       elementos.append(logo)
       elementos.append(Spacer(1, 20))
   else:
       elementos.append(Paragraph("⚠️ LOGO NO DISPONIBLE", styleN))
       elementos.append(Spacer(1, 20))
   # Título
   elementos.append(Paragraph("<b>FACTURA PROFORMA</b>", styleN))
   elementos.append(Spacer(1, 12))
   # Datos solicitante
   texto_solicitante = f"Solicitante: {solicitante}"
   if almacen_desc:
       texto_solicitante += f"<br/>Almacén: {almacen_desc}"
   if proveedor:
       texto_solicitante += f"<br/>Proveedor: {proveedor}"
   texto_solicitante += f"<br/>Número OA/SGR: {oa_sgr}"
   elementos.append(Paragraph(texto_solicitante, styleN))
   elementos.append(Spacer(1, 12))
   # Destino
   if destino_row is not None:
       dest_text = f"""
<b>DESTINO:</b><br/>
       {destino_row.get('Nombre','')}<br/>
       {destino_row.get('Direccion','')}<br/>
       {destino_row.get('CP','')} {destino_row.get('Ciudad','')} ({destino_row.get('Pais','')})<br/>
       CIF: {destino_row.get('CIF','')}
       """
   else:
       dest_text = "<b>DESTINO:</b> No encontrado"
   elementos.append(Paragraph(dest_text, styleN))
   elementos.append(Spacer(1, 12))
   # Tabla de referencias
   if referencias:
       data = [["Referencia", "Cantidad", "Descripción", "Precio/UD", "Importe"]]
       for ref in referencias:
           data.append([
               ref["Referencia"],
               ref["Cantidad"],
               ref["Descripcion"],
               f"{ref['PrecioUD']:.2f}",
               f"{ref['Importe']:.2f}"
           ])
       t = Table(data, repeatRows=1)
       t.setStyle(TableStyle([
           ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
           ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
           ("ALIGN", (0, 0), (-1, -1), "CENTER"),
           ("GRID", (0, 0), (-1, -1), 1, colors.black),
       ]))
       elementos.append(t)
   elementos.append(Spacer(1, 30))
   # === FOOTER CENTRADO ABAJO ===
   footer_path = ruta_imagen("footer.png")
   if os.path.exists(footer_path):
       footer = Image(footer_path, width=200, height=70)
       footer.hAlign = "CENTER"
       elementos.append(footer)
   else:
       elementos.append(Paragraph("⚠️ FOOTER NO DISPONIBLE", styleN))
   # Construcción del PDF
   doc.build(elementos)
   pdf = buffer.getvalue()
   buffer.close()
   return pdf
# ==========================
# CARGA DE DATOS
# ==========================
catalogo = load_excel("data/catalogo.xlsx")
destinos = load_excel("data/destinos.xlsx")
almacenes = load_excel("data/almacenes.xlsx")
# ==========================
# INTERFAZ STREAMLIT
# ==========================
st.title("📄 Generador de Factura Proforma")
with st.form("form_factura"):
   st.subheader("1) Solicitante")
   solicitante = st.selectbox("Seleccione el solicitante", ["BO/Taller", "Almacén Central", "Proveedor"])
   almacen_desc = ""
   proveedor = ""
   if solicitante == "BO/Taller":
       cod_alm = st.text_input("Código de Almacén Solicitante")
       if cod_alm and "Codigo" in almacenes.columns:
           fila = almacenes[almacenes["Codigo"].astype(str).str.upper() == cod_alm.upper()]
           if not fila.empty:
               almacen_desc = str(fila.iloc[0]["Descripcion"])
               st.success(f"Descripción: {almacen_desc}")
           else:
               st.error("Código de almacén no encontrado")
   elif solicitante == "Proveedor":
       proveedor = st.text_input("Nombre del proveedor")
   st.subheader("2) OA / Traspaso SGR")
   oa_sgr = st.text_input("Número OA/SGR (obligatorio)")
   if oa_sgr and not (oa_sgr.startswith("OA") or oa_sgr.startswith("SGR")):
       st.error("El número debe comenzar por 'OA' o 'SGR'")
   st.subheader("3) Destino de la mercancía")
   if not destinos.empty and "Nombre" in destinos.columns:
       destino = st.selectbox("Seleccione destino", destinos["Nombre"].dropna().astype(str).tolist())
       destino_row = destinos[destinos["Nombre"] == destino].iloc[0] if destino else None
   else:
       destino = None
       destino_row = None
       st.error("No hay destinos disponibles en el archivo")
   st.subheader("4) Referencias")
   if "referencias" not in st.session_state:
       st.session_state["referencias"] = []
   col1, col2 = st.columns([2, 1])
   with col1:
       nueva_ref = st.text_input("Referencia", key="nueva_ref")
   with col2:
       nueva_cant = st.number_input("Cantidad", min_value=1, value=1, key="nueva_cant")
   # Botón para añadir referencias
   add_ref = st.form_submit_button("➕ Añadir referencia")
   if add_ref and nueva_ref:
       if not catalogo.empty and "Referencia" in catalogo.columns:
           fila = catalogo[catalogo["Referencia"].astype(str) == str(nueva_ref)]
           if not fila.empty:
               descripcion = str(fila.iloc[0]["Descripcion"])
               precio = float(fila.iloc[0]["PrecioUD"])
               importe = precio * nueva_cant
               st.session_state["referencias"].append({
                   "Referencia": nueva_ref,
                   "Cantidad": nueva_cant,
                   "Descripcion": descripcion,
                   "PrecioUD": precio,
                   "Importe": importe
               })
           else:
               st.error("Referencia no encontrada en el catálogo")
       else:
           st.error("El catálogo no está disponible o no tiene columna 'Referencia'")
   if st.session_state["referencias"]:
       st.write("### Referencias añadidas")
       df_refs = pd.DataFrame(st.session_state["referencias"])
       st.table(df_refs)
   generar = st.form_submit_button("📄 Generar Factura Proforma")
# ==========================
# GENERAR PDF
# ==========================
if generar:
   if not oa_sgr:
       st.error("Debes introducir un número OA/SGR válido")
   elif destino_row is not None and st.session_state["referencias"]:
       pdf = generar_pdf(solicitante, almacen_desc, proveedor, oa_sgr, destino_row, st.session_state["referencias"])
       st.download_button(
           "⬇️ Descargar PDF",
           data=pdf,
           file_name=f"FacturaProforma_{oa_sgr}.pdf",
           mime="application/pdf"
       )
   else:
       st.error("Faltan datos para generar la factura")
