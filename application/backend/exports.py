"""Export Excel (.xlsx, sans dépendance) et identité de l'établissement (en-tête des registres imprimés)."""
import io
import re
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape

from flask import Blueprint, jsonify, send_file

from core import ALL, CONFIG, ApiError, audit, body, get_db, login_required, text

bp = Blueprint("exports", __name__)

MAX_ROWS = 20000


def col_name(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def clean(v):
    s = "" if v is None else str(v)
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)[:2000]


def build_xlsx(titre, headers, rows):
    widths = [min(max([len(clean(h))] + [len(clean(r[i])) for r in rows if i < len(r)]) + 2, 60) for i, h in enumerate(headers)]
    def cell(ref, val, style):
        # chaînes « inline » uniquement : aucune formule ne peut s'exécuter, même si le texte commence par « = »
        return f'<c r="{ref}" t="inlineStr" s="{style}"><is><t xml:space="preserve">{escape(clean(val))}</t></is></c>'
    sheet = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
             "<sheetViews><sheetView workbookViewId=\"0\"><pane ySplit=\"1\" topLeftCell=\"A2\" activePane=\"bottomLeft\" state=\"frozen\"/></sheetView></sheetViews>",
             "<cols>" + "".join(f'<col min="{i+1}" max="{i+1}" width="{w}" customWidth="1"/>' for i, w in enumerate(widths)) + "</cols><sheetData>",
             '<row r="1">' + "".join(cell(f"{col_name(i)}1", h, 1) for i, h in enumerate(headers)) + "</row>"]
    for n, r in enumerate(rows, start=2):
        sheet.append(f'<row r="{n}">' + "".join(cell(f"{col_name(i)}{n}", r[i] if i < len(r) else "", 0) for i in range(len(headers))) + "</row>")
    sheet.append("</sheetData></worksheet>")
    name = re.sub(r"[\[\]\\/*?:]", " ", titre)[:31] or "Registre"
    files = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="{escape(name)}" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        "xl/styles.xml": '<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1F4E79"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf fontId="0" fillId="0" borderId="0"/><xf fontId="1" fillId="2" borderId="0" applyFont="1" applyFill="1"/></cellXfs></styleSheet>',
        "xl/worksheets/sheet1.xml": "".join(sheet),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for k, v in files.items():
            z.writestr(k, v)
    buf.seek(0)
    return buf


@bp.post("/api/export/xlsx")
@login_required(*ALL)
def export_xlsx():
    data = body()
    headers, rows = data.get("headers"), data.get("rows")
    if not isinstance(headers, list) or not isinstance(rows, list) or not headers or len(headers) > 40:
        raise ApiError("Export invalide.")
    if len(rows) > MAX_ROWS or any(not isinstance(r, list) for r in rows):
        raise ApiError("Export invalide ou trop volumineux.")
    titre = text(data, "titre", "Titre", 60, False) or "Registre"
    audit("export_excel", "registre", None, {"titre": titre, "lignes": len(rows)})
    return send_file(build_xlsx(titre, headers, rows), as_attachment=True,
                     download_name=f"{re.sub(r'[^A-Za-z0-9_-]+', '-', titre)}-{datetime.now():%Y%m%d}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ---------- identité de l'établissement ----------
def _get(db, key):
    r = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return r["value"] if r else ""


@bp.get("/api/etablissement")
@login_required(*ALL)
def get_etab():
    db = get_db()
    return jsonify({"nom": _get(db, "etab_nom"), "ville": _get(db, "etab_ville")})


@bp.put("/api/etablissement")
@login_required(*CONFIG)
def put_etab():
    data = body()
    db = get_db()
    vals = {"etab_nom": text(data, "nom", "Nom de l'établissement", 120), "etab_ville": text(data, "ville", "Ville", 80, False)}
    for k, v in vals.items():
        db.execute("INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (k, v))
    audit("etablissement_modifie", "settings", None, {"nom": vals["etab_nom"]})
    return jsonify({"ok": True})
