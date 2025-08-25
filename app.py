import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
import os
from datetime import datetime
# ==========================
# LOGIN
# ==========================
# --- Credenciales desde secrets ---
USERNAME = st.secrets["credentials"]["username"]
PASSWORD = st.secrets["credentials"]["password"]
# --- Control de sesión ---
if "logged_in" not in st.session_state:
   st.session_state.logged_in = False
if not st.session_state.logged_in:
   st.title("🔐 Acceso privado")
   usuario = st.text_input("Usuario")
   password = st.text_input("Contraseña", type="password")
   login_btn = st.button("Iniciar sesión")
   if login_btn:
       if usuario == USERNAME and password == PASSWORD:
           st.session_state.logged_in = True
           st.success("✅ Acceso concedido")
           st.rerun()
       else:
           st.error("❌ Usuario o contraseña incorrectos")
# ==========================
# SOLO SE MUESTRA LA APP SI HAY LOGIN
# ==========================
if st.session_state.logged_in:
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
   def generar_pdf(oa_sgr, destino_row, referencias):
       """Genera el PDF de la factura proforma."""
       buffer = BytesIO()
       # Márgenes ajustados
       doc = SimpleDocTemplate(
           buffer,
           pagesize=landscape(A4),
           leftMargin=40,
           rightMargin=40,
           topMargin=40,
           bottomMargin=40
       )
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
       # === CABECERA (2 COLUMNAS) ===
       fecha_hoy = datetime.today().strftime("%d/%m/%Y")
       datos_izq = """<b>SERVICIO POSTVENTA</b><br/>
       C/TITAN 15<br/>
       28045 - MADRID (ESPAÑA)<br/>
       C.I.F. A-28.078.202"""
       if destino_row is not None:
           datos_der = f"""
<b>DESTINO</b><br/>
           {destino_row.get('Nombre','')}<br/>
           {destino_row.get('Direccion','')}<br/>
           {destino_row.get('CP','')} {destino_row.get('Ciudad','')} ({destino_row.get('Pais','')})<br/>
           CIF: {destino_row.get('CIF','')}<br/>
<b>FECHA:</b> {fecha_hoy}
           """
       else:
           datos_der = f"<b>DESTINO:</b> No encontrado<br/><b>FECHA:</b> {fecha_hoy}"
       tabla_cabecera = Table([
           [Paragraph(datos_izq, styleN), Paragraph(datos_der, styleN)]
       ], colWidths=[380, 380])
       tabla_cabecera.setStyle(TableStyle([
           ("VALIGN", (0, 0), (-1, -1), "TOP"),
       ]))
       elementos.append(tabla_cabecera)
       elementos.append(Spacer(1, 20))
       # === TÍTULO FACTURA ===
       elementos.append(Paragraph("<b>FACTURA PROFORMA</b>", styleN))
       elementos.append(Paragraph(f"<b>{oa_sgr}</b>", styleN))
       elementos.append(Spacer(1, 20))
       # === TABLA REFERENCIAS ===
       if referencias:
           data = [["Referencia", "Cantidad", "Descripción", "Precio/UD", "Importe/EUROS"]]
           total = 0
           for ref in referencias:
               data.append([
                   ref["Referencia"],
                   ref["Cantidad"],
                   ref["Descripcion"],
                   f"{ref['PrecioUD']:.2f}",
                   f"{ref['Importe']:.2f}"
               ])
               total += ref["Importe"]
           # fila de TOTAL
           data.append(["", "", "", "TOTAL", f"{total:.2f}"])
           t = Table(data, repeatRows=1, colWidths=[100, 80, 400, 100, 120])
           t.setStyle(TableStyle([
               ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
               ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
               ("ALIGN", (0, 0), (-1, -1), "CENTER"),
               ("GRID", (0, 0), (-1, -1), 1, colors.black),
               ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
               ("FONTNAME", (-2, -1), (-1, -1), "Helvetica-Bold"),
           ]))
           elementos.append(t)
           elementos.append(Spacer(1, 20))
       # === TEXTO FIJO BAJO TABLA ===
       texto_fijo = Paragraph(
           "<b>Material gratuito SIN valor comercial (Valor a precio estadístico)</b>",
           styles["Title"]
       )
       texto_fijo.style.alignment = 1  # centrado
       elementos.append(texto_fijo)
       elementos.append(Spacer(1, 20))
       # === FOOTER ABAJO ===
       footer_path = ruta_imagen("footer.png")
       if os.path.exists(footer_path):
           footer = Image(footer_path, width=200, height=70)
           footer.hAlign = "CENTER"
           elementos.append(footer)
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
   # ==========================
   # INTERFAZ STREAMLIT
   # ==========================
   st.title("📄 Generador de Factura Proforma")
   with st.form("form_factura"):
       st.subheader("1) OA / Traspaso SGR")
       oa_sgr = st.text_input("Número OA/SGR (obligatorio)")
       if oa_sgr and not (oa_sgr.startswith("OA") or oa_sgr.startswith("SGR")):
           st.error("El número debe comenzar por 'OA' o 'SGR'")
       st.subheader("2) Destino de la mercancía")
       if not destinos.empty and "Nombre" in destinos.columns:
           destino = st.selectbox("Seleccione destino", destinos["Nombre"].dropna().astype(str).tolist())
           destino_row = destinos[destinos["Nombre"] == destino].iloc[0] if destino else None
       else:
           destino = None
           destino_row = None
           st.error("No hay destinos disponibles en el archivo")
       st.subheader("3) Referencias")
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
       # Mostrar tabla en app (sin precios)
       if st.session_state["referencias"]:
           st.write("### Referencias añadidas")
           df_refs = pd.DataFrame(st.session_state["referencias"])[["Referencia", "Cantidad", "Descripcion"]]
           st.table(df_refs)
       generar = st.form_submit_button("📄 Generar Factura Proforma")
   # ==========================
   # GENERAR PDF
   # ==========================
   if generar:
       if not oa_sgr:
           st.error("Debes introducir un número OA/SGR válido")
       elif destino_row is not None and st.session_state["referencias"]:
           pdf = generar_pdf(oa_sgr, destino_row, st.session_state["referencias"])
           st.download_button(
               "⬇️ Descargar PDF",
               data=pdf,
               file_name=f"FacturaProforma_{oa_sgr}.pdf",
               mime="application/pdf"
           )
       else:
           st.error("Faltan datos para generar la factura")
