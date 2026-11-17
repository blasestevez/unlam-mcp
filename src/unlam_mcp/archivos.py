"""Leer archivos descargados: texto de PDF, Word, PowerPoint y texto plano, e
imágenes de páginas de PDF (para los escaneados) o de archivos de imagen.

El texto se devuelve por partes (páginas, diapositivas o bloques) para que un
apunte largo no llene de una sola vez el contexto del asistente.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from .miel import MielError
from .parsers import Modelo

MAX_CARACTERES = 40_000  # por respuesta; alrededor de 10.000 tokens
BLOQUE_TEXTO = 4_000  # tamaño de cada "parte" en archivos sin páginas (Word, texto)

EXTENSIONES_TEXTO = {
    ".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".html", ".htm", ".sql", ".py", ".java",
    ".c", ".h", ".cpp", ".cs", ".js", ".ts", ".php", ".rb", ".go", ".rs", ".kt", ".yml", ".yaml",
}  # fmt: skip
NO_SOPORTADOS = {
    ".doc": "Word viejo (.doc)",
    ".ppt": "PowerPoint viejo (.ppt)",
    ".pps": "PowerPoint viejo (.pps)",
    ".xls": "Excel viejo (.xls)",
    ".zip": "comprimido",
    ".rar": "comprimido",
    ".7z": "comprimido",
}


class Lectura(Modelo):
    archivo: str
    ruta: str = Field(description="Dónde quedó el archivo en la compu del usuario.")
    unidad: str = Field(description="'página', 'diapositiva' o 'parte'.")
    desde: int
    hasta: int
    total: int = Field(description="Cantidad total de páginas/diapositivas/partes.")
    siguiente: int | None = Field(
        default=None, description="Pasalo como `desde` para seguir leyendo; null si ya terminó."
    )
    aviso: str | None = None
    texto: str


def leer(ruta: Path, desde: int = 1, max_caracteres: int = MAX_CARACTERES) -> Lectura:
    """Lee `ruta` a partir de la parte `desde` (1 = el principio)."""
    unidad, partes = _partes(ruta)
    total = len(partes)
    if total == 0:
        return Lectura(
            archivo=ruta.name, ruta=str(ruta), unidad=unidad, desde=0, hasta=0, total=0,
            aviso="El archivo está vacío.", texto="",
        )  # fmt: skip
    desde = min(max(desde, 1), total)

    trozos: list[str] = []
    usados = 0
    hasta = desde - 1
    for numero in range(desde, total + 1):
        texto = partes[numero - 1].strip()
        bloque = f"--- {unidad.capitalize()} {numero} ---\n{texto}" if total > 1 else texto
        if trozos and usados + len(bloque) > max_caracteres:
            break
        trozos.append(bloque[:max_caracteres])
        usados += len(bloque)
        hasta = numero

    texto = "\n\n".join(trozos)
    aviso = None
    if not "".join(partes[desde - 1 : hasta]).strip():
        texto = ""
        aviso = (
            "No se encontró texto: parece un PDF escaneado. Usá miel_ver_pagina para "
            f"verlo como imagen. El archivo está en {ruta}."
        )
    return Lectura(
        archivo=ruta.name,
        ruta=str(ruta),
        unidad=unidad,
        desde=desde,
        hasta=hasta,
        total=total,
        siguiente=hasta + 1 if hasta < total else None,
        aviso=aviso,
        texto=texto,
    )


EXTENSIONES_IMAGEN = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".gif": "gif", ".webp": "webp"}
ANCHO_MAXIMO = 1600  # px; suficiente para leer un apunte escaneado sin mandar imágenes enormes


def imagen(ruta: Path, pagina: int = 1) -> tuple[bytes, str, int]:
    """Devuelve (bytes, formato, total de páginas) de una página de PDF o de una imagen."""
    ext = ruta.suffix.lower()
    if ext in EXTENSIONES_IMAGEN:
        return ruta.read_bytes(), EXTENSIONES_IMAGEN[ext], 1
    if ext != ".pdf":
        raise MielError(f"Sólo puedo mostrar como imagen PDFs o imágenes, no {ext or 'esto'}.")

    import io

    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(ruta))
    try:
        total = len(doc)
        if not 1 <= pagina <= total:
            raise MielError(f"El PDF tiene {total} páginas; pediste la {pagina}.")
        hoja = doc[pagina - 1]
        escala = min(2.0, ANCHO_MAXIMO / max(hoja.get_width(), 1))
        foto = hoja.render(scale=escala).to_pil().convert("RGB")
        salida = io.BytesIO()
        foto.save(salida, format="JPEG", quality=80)
        return salida.getvalue(), "jpeg", total
    finally:
        doc.close()


def _partes(ruta: Path) -> tuple[str, list[str]]:
    ext = ruta.suffix.lower()
    if ext in NO_SOPORTADOS:
        raise MielError(
            f"No puedo leer archivos de tipo {NO_SOPORTADOS[ext]}. "
            f"El usuario puede abrirlo desde {ruta}."
        )
    try:
        if ext == ".pdf":
            return "página", _pdf(ruta)
        if ext == ".docx":
            return "parte", _en_bloques(_docx(ruta))
        if ext == ".pptx":
            return "diapositiva", _pptx(ruta)
        if ext in EXTENSIONES_TEXTO:
            return "parte", _en_bloques(ruta.read_text(encoding="utf-8", errors="replace"))
    except MielError:
        raise
    except Exception as e:  # archivo dañado o con un formato raro
        raise MielError(f"No pude leer {ruta.name} ({type(e).__name__}). Está en {ruta}.") from e
    raise MielError(
        f"No sé leer archivos {ext or 'sin extensión'}. El usuario puede abrirlo desde {ruta}."
    )


def _pdf(ruta: Path) -> list[str]:
    # pypdfium2 (el motor de PDF de Chrome) respeta los espacios entre palabras en
    # PDFs hechos con LaTeX, donde otras librerías los pierden.
    import re

    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(ruta))
    try:
        paginas = []
        for hoja in doc:
            texto = hoja.get_textpage().get_text_range().replace("\r\n", "\n")
            # Las líneas de puntos de los índices ("Tema . . . . . 4") no aportan nada.
            paginas.append(re.sub(r"(?:\s?\.){4,}", " …", texto))
        return paginas
    finally:
        doc.close()


def _docx(ruta: Path) -> str:
    from docx import Document

    doc = Document(str(ruta))
    lineas = [p.text for p in doc.paragraphs if p.text.strip()]
    for tabla in doc.tables:
        for fila in tabla.rows:
            lineas.append(" | ".join(c.text.strip() for c in fila.cells))
    return "\n".join(lineas)


def _pptx(ruta: Path) -> list[str]:
    from pptx import Presentation

    diapositivas = []
    for diapo in Presentation(str(ruta)).slides:
        lineas = []
        for forma in diapo.shapes:
            if forma.has_text_frame:
                lineas += [p.text for p in forma.text_frame.paragraphs if p.text.strip()]
            if getattr(forma, "has_table", False) and forma.has_table:
                for fila in forma.table.rows:
                    lineas.append(" | ".join(c.text.strip() for c in fila.cells))
        if diapo.has_notes_slide and (notas := diapo.notes_slide.notes_text_frame.text.strip()):
            lineas.append(f"[Notas] {notas}")
        diapositivas.append("\n".join(lineas))
    return diapositivas


def _en_bloques(texto: str) -> list[str]:
    """Corta texto largo en bloques de ~BLOQUE_TEXTO caracteres, respetando las líneas."""
    bloques, actual = [], ""
    for linea in texto.splitlines(keepends=True):
        if actual and len(actual) + len(linea) > BLOQUE_TEXTO:
            bloques.append(actual)
            actual = ""
        actual += linea
    if actual.strip():
        bloques.append(actual)
    return bloques
