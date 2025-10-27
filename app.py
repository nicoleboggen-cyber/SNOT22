import streamlit as st
import pandas as pd
import hashlib, re
from datetime import datetime, date, timezone
from pathlib import Path

st.set_page_config(page_title="SNOT-22 + EVA", page_icon="📝", layout="centered")

SALT = st.secrets.get("general", {}).get("SALT", "")
STORE_PLAINTEXT = str(st.secrets.get("general", {}).get("STORE_PLAINTEXT_RUT", "false")).lower() == "true"

GCP_INFO = st.secrets.get("gcp_service_account", None)
GOOGLE_SHEET_ID = st.secrets.get("google", {}).get("GOOGLE_SHEET_ID", "")
GOOGLE_SHEET_WS = st.secrets.get("google", {}).get("GOOGLE_SHEET_WORKSHEET", "Respuestas")

USE_SHEETS = bool(GCP_INFO and GOOGLE_SHEET_ID)

def normalize_rut(rut_raw: str) -> str:
    s = rut_raw.upper().replace(".", "").replace("-", "").strip()
    return s

def validate_rut(rut_raw: str) -> bool:
    s = normalize_rut(rut_raw)
    if len(s) < 2 or not re.match(r"^[0-9K]+$", s):
        return False
    body, dv = s[:-1], s[-1]
    try:
        digits = list(map(int, body))
    except ValueError:
        return False
    factors = [2,3,4,5,6,7]
    acc = 0
    for i, d in enumerate(reversed(digits)):
        acc += d * factors[i % len(factors)]
    remainder = 11 - (acc % 11)
    dv_calc = "0" if remainder == 11 else "K" if remainder == 10 else str(remainder)
    return dv == dv_calc

def rut_sha256_id(rut_raw: str, salt: str) -> str:
    s = normalize_rut(rut_raw)
    return hashlib.sha256((s + salt).encode("utf-8")).hexdigest()

def ensure_local_store():
    Path("data").mkdir(exist_ok=True)
    p = Path("data/data.csv")
    if not p.exists():
        cols = ["timestamp","patient_id","rut_plain","visit_date","vas_0_10"] + [f"snot22_q{i}" for i in range(1,23)] + ["snot22_total","notes"]
        pd.DataFrame(columns=cols).to_csv(p, index=False)
    return p

@st.cache_data
def load_items():
    try:
        df = pd.read_csv("snot22_items.csv")
        items = df["item_es"].tolist()
        if len(items) != 22:
            raise ValueError("snot22_items.csv debe tener 22 filas.")
        return items
    except Exception as e:
        st.error(f"Error cargando snot22_items.csv: {e}")
        return [f"Item {i}" for i in range(1,23)]

def save_to_local(row_dict):
    p = ensure_local_store()
    df = pd.read_csv(p)
    df = pd.concat([df, pd.DataFrame([row_dict])], ignore_index=True)
    df.to_csv(p, index=False)
    try:
        df.to_excel("data/data.xlsx", index=False)
    except Exception:
        pass

def save_to_sheets(row_dict):
    import gspread
    from google.oauth2.service_account import Credentials
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(dict(GCP_INFO), scopes=scopes)
    gc = gspread.Client(auth=creds)
    gc.session = gspread.auth.Session(creds)
    sh = gc.open_by_key(GOOGLE_SHEET_ID)
    try:
        ws = sh.worksheet(GOOGLE_SHEET_WS)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=GOOGLE_SHEET_WS, rows=100, cols=40)

    header = ["timestamp","patient_id","rut_plain","visit_date","vas_0_10"] + [f"snot22_q{i}" for i in range(1,23)] + ["snot22_total","notes"]
    current = ws.get_all_values()
    if not current:
        ws.update("A1", [header])

    values = [row_dict.get(col, "") for col in header]
    ws.append_row(values, value_input_option="USER_ENTERED")

st.title("SNOT-22 + EVA (VAS)")
st.caption("Registro de visitas con RUT validado y anonimizacion opcional.")

with st.expander("Informacion y consentimiento", expanded=False):
    st.write("Este formulario registra su RUT, respuestas SNOT-22 (0-5) y EVA (0-10) para seguimiento clinico. Los datos pueden guardarse en una planilla segura. Por defecto, el RUT se anonimiza (hash + SALT). Para fines clinicos, podria guardarse en texto plano si su institucion lo exige. Marque la casilla si acepta.")

with st.form("snot_form"):
    col1, col2 = st.columns(2)
    rut = col1.text_input("RUT (con digito verificador, ej. 12.345.678-K)")
    visit_date = col2.date_input("Fecha de control", value=date.today())
    vas = st.slider("EVA / VAS (0 = sin sintomas, 10 = peor)", min_value=0, max_value=10, value=0, step=1)

    st.subheader("SNOT-22")
    items = load_items()
    snot_vals = []
    for i, text in enumerate(items, start=1):
        snot_vals.append(st.select_slider(f"Q{i}. {text}", options=list(range(6)), value=0))

    notes = st.text_area("Notas (opcional)")
    consent = st.checkbox("Acepto el consentimiento informado")
    submitted = st.form_submit_button("Guardar registro")

if submitted:
    if not consent:
        st.error("Debes aceptar el consentimiento informado para guardar.")
    elif not validate_rut(rut):
        st.error("RUT invalido. Revisa formato y digito verificador.")
    elif not SALT:
        st.error("Falta configurar SALT en Secrets ([general] -> SALT).")
    else:
        pid = rut_sha256_id(rut, SALT)
        snot_total = sum(int(v) for v in snot_vals)
        now_iso = datetime.now(timezone.utc).isoformat()

        row = {
            "timestamp": now_iso,
            "patient_id": pid,
            "rut_plain": normalize_rut(rut) if STORE_PLAINTEXT else "",
            "visit_date": visit_date.isoformat(),
            "vas_0_10": int(vas),
            **{f"snot22_q{i}": int(snot_vals[i-1]) for i in range(1,23)},
            "snot22_total": int(snot_total),
            "notes": notes or ""
        }

        save_to_local(row)
        if USE_SHEETS:
            try:
                save_to_sheets(row)
                st.success("Registro guardado en Google Sheets y copia local.")
            except Exception as e:
                st.warning(f"No se pudo guardar en Google Sheets ({e}). Se guardo localmente.")
        else:
            st.success("Registro guardado localmente (CSV/XLSX).")

        st.metric("Suma SNOT-22", snot_total)
        st.metric("EVA / VAS", int(vas))

st.divider()
st.subheader("Base local")
p = Path("data/data.csv")
if p.exists():
    df = pd.read_csv(p)
    st.dataframe(df.tail(20), use_container_width=True)
    st.download_button("Descargar CSV local", data=p.read_bytes(), file_name="data.csv", mime="text/csv")
else:
    st.info("Aun no hay registros locales.")

st.caption("Ajusta el consentimiento a tu CEI y respeta Ley 19.628.")
