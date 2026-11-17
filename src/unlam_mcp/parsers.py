"""HTML de MIeL -> modelos de datos.

Funciones puras: reciben el HTML de una página y devuelven modelos pydantic.
Toda la dependencia del HTML de MIeL vive acá; si MIeL cambia una página, se
arregla en un solo lugar (y lo avisa un test con su fixture).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString
from typing import Any

from pydantic import BaseModel, Field, SerializerFunctionWrapHandler, model_serializer

# ----------------------------------------------------------------- modelos


class Modelo(BaseModel):
    """Base de todas las respuestas. Al serializar omite los campos vacíos (None,
    listas o dicts vacíos): cada campo cuesta contexto del asistente."""

    @model_serializer(mode="wrap")
    def _sin_vacios(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        datos: dict[str, Any] = handler(self)
        campos = type(self).model_fields
        return {
            k: v
            for k, v in self._omitir(datos).items()
            if v is not None and not (v in ([], {}) and k in campos and not campos[k].is_required())
        }

    def _omitir(self, datos: dict[str, Any]) -> dict[str, Any]:
        return datos


class Herramienta(Modelo):
    nombre: str = Field(description="Nombre visible, ej. 'Contenidos', 'Foro'.")
    # Para uso interno: el modelo no los necesita y cada campo le cuesta contexto.
    modulo: str = Field(default="", exclude=True)
    url: str = Field(default="", exclude=True)
    pendientes: int | None = Field(
        default=None, description="Número del badge (ej. mensajes sin leer); ausente si es 0."
    )


class Materia(Modelo):
    id: str = Field(description="Id de comisión en MIeL; lo usan el resto de las tools.")
    nombre: str
    codigo: str | None = Field(default=None, description="Código de la materia, ej. '3664'.")
    comision: str | None = Field(default=None, description="Comisión, ej. '01-3900'.")
    rol: str | None = Field(default=None, description="Rol del usuario, ej. 'Alumno/a'.")
    oculta: bool = False
    herramientas: list[Herramienta] = Field(default_factory=list)

    def herramienta(self, modulo: str) -> Herramienta | None:
        return next((h for h in self.herramientas if h.modulo == modulo), None)


class Contenido(Modelo):
    id: str
    nombre: str
    tipo: Literal["archivo", "enlace"]
    modulo: str | None = Field(default=None, description="Carpeta del acordeón en MIeL.")
    seccion: str | None = Field(default=None, description="Subtítulo dentro de la carpeta.")
    descripcion: str | None = None
    lectura: str | None = Field(default=None, description="'Obligatoria' o 'Complementaria'.")
    fecha_subida: date | None = None
    tamanio_bytes: int | None = None
    nombre_archivo: str | None = None
    nuevo: bool = Field(default=False, description="MIeL lo marca como nuevo (no visto).")
    url: str = Field(
        default="", description="Sólo en los enlaces externos: el link para pasarle al usuario."
    )

    def _omitir(self, datos: dict[str, Any]) -> dict[str, Any]:
        # Los archivos se bajan por `id`; su URL de descarga es larga y no le sirve al modelo.
        if self.tipo == "archivo":
            datos.pop("url", None)
        return datos


class TemaForo(Modelo):
    id: str
    titulo: str
    descripcion: str | None = None
    mensajes: int = 0
    sin_leer: int = 0
    ultimo_mensaje: datetime | None = None
    estado: str | None = Field(default=None, description="'abierto', 'cerrado' o 'vencido'.")


class MensajeForo(Modelo):
    id: str
    responde_a: str | None = Field(default=None, description="Id del mensaje al que responde.")
    autor: str
    rol: str | None = None
    enviado: datetime | None = None
    texto: str = Field(description="Contenido en texto plano; los enlaces van como [texto](url).")
    enlaces: list[str] = Field(default_factory=list)


class Mensaje(Modelo):
    """Un mensaje de la bandeja de entrada (mensajería interna de la materia)."""

    id: str
    fecha: date | None = None
    remitente: str
    asunto: str
    leido: bool
    tiene_adjunto: bool = False


class Adjunto(Modelo):
    nombre: str
    url: str = Field(description="Se descarga con miel_descargar pasando esta url.")


class MensajeCompleto(Modelo):
    id: str
    asunto: str
    de: str
    rol: str | None = Field(default=None, description="Rol del remitente, ej. 'Tutor/a'.")
    para: str | None = None
    enviado: datetime | None = None
    texto: str
    adjuntos: list[Adjunto] = Field(default_factory=list)


class Destinatario(Modelo):
    """Alguien (o un grupo) a quien se le puede mandar un mensaje en una materia."""

    id: str
    nombre: str
    tipo: str = Field(
        description="'alumno', 'tutor', 'grupo', 'tutores' (todos) o 'alumnos' (todos)."
    )


class Practica(Modelo):
    """Una práctica del portafolio (trabajo práctico, parcial, etc.)."""

    id: str
    nombre: str
    modulo: str | None = Field(default=None, description="Carpeta de contenidos a la que pertenece.")
    entrega: str | None = Field(default=None, description="Ej. 'Obligatoria', 'Opcional'.")
    vencimiento: date | None = None
    fecha_entrega: date | None = Field(default=None, description="Cuándo entregó el alumno.")
    fecha_correccion: date | None = None
    estado: str | None = Field(default=None, description="Ej. 'APROBADO', 'EN REVISION', 'VISTO'.")
    nota: str | None = None
    url_enunciado: str | None = None


class Turno(Modelo):
    """Un horario de un evento con turnos (consultas, recuperatorios, coloquios...)."""

    id: str | None = Field(
        default=None, description="Id del horario: se pasa a miel_reservar_turno / miel_cancelar_turno."
    )
    # El evento al que pertenece el horario; MIeL lo pide al reservar.
    rango_id: str = Field(default="", exclude=True)
    evento: str
    fecha: date | None = None
    dia: str | None = None
    horario: str | None = Field(default=None, description="Ej. '1800-1840'.")
    modalidad: str | None = None
    lugar: str | None = None
    vacantes: int | None = None
    reservado: bool = Field(default=False, description="True si el usuario ya reservó este turno.")
    disponible: bool = Field(default=False, description="True si se puede reservar.")
    reemplaza_otro: bool | None = Field(
        default=None,
        description="True si ya tenés otro horario de este evento: reservar este cancela aquel.",
    )


class Evaluacion(Modelo):
    id: str
    tipo: str | None = None
    titulo: str
    habilitada: str | None = Field(default=None, description="Ej. 'No habilitado para rendir'.")
    estado: str | None = Field(default=None, description="Ej. 'Cerrado'.")


# --------------------------------------------------------------- materias
# Página: /principal/interno/

_DETALLE_MATERIA = re.compile(  # "3664 - Com: 01-3900 - Alumno/a"
    r"^\s*(?P<codigo>[^-]+?)\s*-\s*Com:\s*(?P<comision>\S+)\s*-\s*(?P<rol>.+)$"
)


def parse_materias(html: str) -> list[Materia]:
    materias: list[Materia] = []
    for bloque in _sopa(html).select(".materia-bloque[data-id]"):
        titulo = bloque.select_one(".materia-titulo")
        detalle = _DETALLE_MATERIA.match(
            _texto(titulo.find_next_sibling("div") if titulo else None)
        )
        materias.append(
            Materia(
                id=str(bloque["data-id"]).strip(),
                nombre=_texto(titulo),
                codigo=detalle["codigo"].strip() if detalle else None,
                comision=detalle["comision"] if detalle else None,
                rol=detalle["rol"].strip() if detalle else None,
                oculta="materia-bloque-oculta" in (bloque.get("class") or []),
                herramientas=[
                    Herramienta(
                        nombre=_texto(a.find("div")) or _texto(a),
                        modulo=_primer_segmento(str(a["href"])),
                        url=str(a["href"]),
                        pendientes=_entero(_texto(a.select_one(".w3-badge"))) or None,
                    )
                    for a in bloque.select(".materia-herramientas a[href]")
                    if not str(a["href"]).startswith("javascript:")
                ],
            )
        )
    return materias


# ------------------------------------------------------------- contenidos
# Página: /contenido/archivos/comision/{id}
# Es un acordeón de carpetas (.desplegarModulo + .w3-accordion-content). Cada
# carpeta tiene una tabla donde cada <thead> abre una sección y las filas que
# siguen son los archivos o enlaces de esa sección.


def parse_contenidos(html: str) -> list[Contenido]:
    contenidos: list[Contenido] = []
    vistos: set[str] = set()
    for boton in _sopa(html).select("a.btnDescargar[href]"):
        fila = boton.find_parent("tr")
        celdas = fila.find_all("td", recursive=False) if fila else []
        if fila is None or len(celdas) < 5:
            continue

        href = str(boton["href"])
        es_archivo = "/descargarElemento/" in href
        identificador = _id_en_url(href) or str(boton.get("data-id-archivo", "")).strip()
        if not identificador or identificador in vistos:
            continue
        vistos.add(identificador)

        nombre = celdas[1]
        titulo = str(boton.get("title", ""))
        contenidos.append(
            Contenido(
                id=identificador,
                nombre=_texto_directo(nombre) or _texto(nombre),
                tipo="archivo" if es_archivo else "enlace",
                modulo=_carpeta(fila),
                seccion=_seccion(fila),
                descripcion=_texto(nombre.find("div")) or None,
                lectura=_texto(celdas[2]) or None,
                fecha_subida=_fecha(_texto(celdas[3])),
                tamanio_bytes=_bytes(_texto(celdas[4])),
                nombre_archivo=(titulo.removeprefix("Descargar").strip() or None)
                if es_archivo
                else None,
                nuevo="w3-pale-yellow" in (fila.get("class") or []),
                url=href,
            )
        )
    return contenidos


def _carpeta(fila: Tag) -> str | None:
    panel = fila.find_parent(class_="w3-accordion-content")
    encabezado = panel.find_previous_sibling(class_="desplegarModulo") if panel else None
    if encabezado is None:
        return None
    return _texto(encabezado.find("span")) or _texto_directo(encabezado) or None


def _seccion(fila: Tag) -> str | None:
    thead = fila.find_previous("thead")
    if thead is None or thead.find_parent("table") is not fila.find_parent("table"):
        return None
    th = thead.find("th")
    return (_texto_directo(th) or None) if th else None


# ------------------------------------------------------------------- foro
# Páginas: /forov2/temas/comision/{id} y /forov2/mensajes/comision/{id}/tema/{tema}

_ID_TEMA = re.compile(r"/tema/(\d+)")
_CANTIDAD_MENSAJES = re.compile(r"(\d+)\s+mensajes?\b", re.IGNORECASE)
_ENVIADO = re.compile(r"Enviado el", re.IGNORECASE)


def parse_temas(html: str) -> list[TemaForo]:
    temas: list[TemaForo] = []
    for bloque in _sopa(html).select(".foro-tema"):
        enlace = bloque.find("a", href=_ID_TEMA)
        m = _ID_TEMA.search(str(enlace["href"])) if enlace else None
        if m is None:
            continue
        resumen = _texto(bloque.select_one(".w3-text-grey"))
        cantidad = _CANTIDAD_MENSAJES.search(resumen)
        icono = bloque.select_one(".foro-icono")
        estado = str(icono.get("title", "")).casefold().removeprefix("tema").strip() if icono else ""
        temas.append(
            TemaForo(
                id=m.group(1),
                titulo=_texto(bloque.find("strong")),
                descripcion=_texto(bloque.select_one(".w3-padding-4")) or None,
                mensajes=int(cantidad.group(1)) if cantidad else 0,
                sin_leer=_entero(_texto(bloque.select_one(".badge-icono"))),
                ultimo_mensaje=_fecha_hora(resumen.partition("ltimo mensaje")[2]),
                estado=estado or None,
            )
        )
    return temas


def parse_mensajes(html: str) -> list[MensajeForo]:
    mensajes: list[MensajeForo] = []
    for li in _sopa(html).select("li.foro-mensaje"):
        identificador = str(li.get("id", "")).removeprefix("idMensaje-")
        padre = str(li.get("data-idmensajepadre", "")).strip()

        # La cabecera (autor, rol, fecha) es el bloque que contiene "Enviado el".
        marca = li.find(string=_ENVIADO)
        cabecera = marca.parent.parent if marca and marca.parent else None
        grises = [_texto(d) for d in cabecera.select(".w3-text-gray")] if cabecera else []
        enviado = next((g for g in grises if _ENVIADO.match(g)), "")
        rol = next((g for g in grises if g and not _ENVIADO.match(g)), "")
        cuerpo = li.select_one(".foro-contenido-mensaje")

        mensajes.append(
            MensajeForo(
                id=identificador,
                responde_a=padre if padre and padre != identificador else None,
                autor=_texto(cabecera.find("strong")) if cabecera else "",
                rol=rol or None,
                enviado=_fecha_hora(enviado),
                texto=_html_a_texto(cuerpo) if cuerpo else "",
                enlaces=[str(a["href"]) for a in cuerpo.find_all("a", href=True)] if cuerpo else [],
            )
        )
    return mensajes


# ------------------------------------------------------------- mensajería
# Páginas: /mensajeria/entrada/comision/{id}/pag/{n} y /mensajeria/verEntrada/.../id/{id}
# Columnas de la bandeja: fecha | remitente | adjunto | asunto | acciones | fecha leído


def parse_bandeja(html: str) -> tuple[list[Mensaje], bool]:
    """Devuelve los mensajes de una página de la bandeja y si hay una página siguiente."""
    doc = _sopa(html)
    mensajes: list[Mensaje] = []
    for fila in doc.select("tr.mensaje-leido, tr.mensaje-no-leido"):
        enlace = fila.select_one("a.verMensaje[href]")
        celdas = fila.find_all("td", recursive=False)
        identificador = _id_en_url(str(enlace["href"])) if enlace else None
        if identificador is None or len(celdas) < 4:
            continue
        mensajes.append(
            Mensaje(
                id=identificador,
                fecha=_fecha(_texto(celdas[0])),
                remitente=_texto(celdas[1]),
                asunto=_texto(enlace),
                leido="mensaje-leido" in (fila.get("class") or []),
                tiene_adjunto=fila.select_one('[title*="adjunto"]') is not None,
            )
        )
    actual = re.search(r"/pag/(\d+)", str(doc.select_one("a.verMensaje[href]") or ""))
    siguiente = int(actual.group(1)) + 1 if actual else 2
    hay_mas = doc.select_one(f'a[href*="/entrada/"][href$="/pag/{siguiente}"]') is not None
    return mensajes, hay_mas


def parse_mensaje(html: str, identificador: str) -> MensajeCompleto:
    doc = _sopa(html)
    main = doc.select_one("main") or doc
    remitente = main.select_one("span.w3-medium")
    cabecera = remitente.find_parent("div").find_parent("div") if remitente else None
    grises = [_texto(d) for d in cabecera.select("div.w3-text-grey")] if cabecera else []
    rol = _texto(remitente.find_next_sibling("span")) if remitente else ""
    cuerpo = main.select_one(".contrastify")
    return MensajeCompleto(
        id=identificador,
        asunto=_texto(main.find("h1")),
        de=_texto(remitente).removeprefix("De:").strip(),
        rol=rol.lstrip("·").strip() or None,
        para=next((g.removeprefix("Para:").strip() for g in grises if g.startswith("Para:")), None),
        enviado=next((f for g in grises if (f := _fecha_hora(g))), None),
        texto=_html_a_texto(cuerpo) if cuerpo else "",
        adjuntos=[
            Adjunto(nombre=_texto(a), url=str(a["href"]))
            for a in main.select('a[href*="/mensajeria/event/descargar/"]')
        ],
    )


# ------------------------------------------------------------- portafolio
# Página: /portafolio/practicas/comision/{id}
# Columnas: práctica | entrega | vencimiento | detalle | f. entrega | f. corrección | estado | nota


def parse_practicas(html: str) -> list[Practica]:
    practicas: list[Practica] = []
    for fila in _sopa(html).select("main table tr"):
        celdas = fila.find_all("td", recursive=False)
        detalle = fila.select_one('a[href*="/portafolio/entregas/"]')
        identificador = _id_en_url(str(detalle["href"])) if detalle else None
        if len(celdas) < 8 or not identificador or identificador == "0":
            continue  # encabezado, o la fila genérica "otras prácticas" (id 0)
        enunciado = celdas[0].find("a", href=True)
        practicas.append(
            Practica(
                id=identificador,
                nombre=_texto(enunciado) or _texto(celdas[0]),
                modulo=_texto_directo(celdas[0]) or None,
                entrega=_vacio(_texto(celdas[1])),
                vencimiento=_fecha(_texto(celdas[2])),
                fecha_entrega=_fecha(_texto(celdas[4])),
                fecha_correccion=_fecha(_texto(celdas[5])),
                estado=_vacio(_texto(celdas[6])),
                nota=_vacio(_texto(celdas[7])),
                url_enunciado=str(enunciado["href"]) if enunciado else None,
            )
        )
    return practicas


# ----------------------------------------------------------- evaluaciones
# Página: /evaluacion/evaluaciones/comision/{id}
# Columnas: tipo | título | habilitado | ícono | estado | opciones


def parse_evaluaciones(html: str) -> list[Evaluacion]:
    evaluaciones: list[Evaluacion] = []
    for fila in _sopa(html).select("main table tr"):
        celdas = fila.find_all("td", recursive=False)
        boton = fila.select_one("a.botonIngresar[data-id]")
        if len(celdas) < 5 or boton is None:
            continue
        habilitado = celdas[2].select_one("[data-tippy-content]")
        evaluaciones.append(
            Evaluacion(
                id=str(boton["data-id"]),
                tipo=_vacio(_texto(celdas[0])),
                titulo=_texto(celdas[1]),
                habilitada=str(habilitado["data-tippy-content"]) if habilitado else None,
                estado=_vacio(_texto(celdas[4])),
            )
        )
    return evaluaciones


# ------------------------------------------------------------ redactar mensaje
# Página: /mensajeria/redactar/comision/{id}
# Desplegable #listaDestinatarios: <a data-type="alumno|tutor|grupo|tutores|alumnos"
# data-id="...">NOMBRE</a>. Al enviar, cada uno va como `{data-type}[]={data-id}`.


def parse_enviados(html: str) -> list[tuple[str, str]]:
    """Bandeja de salida (/mensajeria/salida/...): (id, asunto) de cada mensaje, del más nuevo
    al más viejo. Las filas no traen clases: fecha | para | adjunto | asunto | ... | leído."""
    enviados = []
    for enlace in _sopa(html).select("tr a.verMensaje[href]"):
        if identificador := _id_en_url(str(enlace["href"])):
            enviados.append((identificador, _texto(enlace)))
    return enviados


def parse_destinatarios(html: str) -> list[Destinatario]:
    return [
        # Sólo el texto propio del <a>: el <i> de adentro es el nombre del ícono ("person").
        Destinatario(
            id=str(a["data-id"]),
            nombre=" ".join("".join(a.find_all(string=True, recursive=False)).split()),
            tipo=str(a["data-type"]),
        )
        for a in _sopa(html).select("#listaDestinatarios a[data-type][data-id]")
    ]


# ----------------------------------------------------------------- turnos
# Página: /turnos/turnos/comision/{id}
# Acordeón de eventos (.desplegarRango); cada uno con una tabla:
# fecha | día | horario | modalidad | lugar | vacantes | opciones (Reservar / Cancelar)
# Los botones traen data-idfranja (el horario) y data-idrango (el evento), que son lo
# que se postea a /turnos/event/reservarTurno|cancelarTurno/comision/{id}.


def parse_turnos(html: str) -> list[Turno]:
    turnos: list[Turno] = []
    # Ojo: el HTML de MIeL no trae <tbody> (lo agrega el navegador), así que no se usa.
    for fila in _sopa(html).select("main table tr"):
        celdas = fila.find_all("td", recursive=False)
        if len(celdas) < 6:
            continue
        panel = fila.find_parent(class_="w3-accordion-content")
        encabezado = panel.find_previous_sibling(class_="desplegarRango") if panel else None
        vacantes = _texto(celdas[5])
        reservar = fila.select_one(".btnReservar")
        cancelar = fila.select_one(".btnCancelar")
        boton = reservar or cancelar
        turnos.append(
            Turno(
                id=str(boton.get("data-idfranja") or "") or None if boton else None,
                rango_id=str(boton.get("data-idrango") or "") if boton else "",
                evento=_texto(encabezado.find("span")) if encabezado else "",
                fecha=_fecha(_texto(celdas[0])),
                dia=_vacio(_texto(celdas[1])),
                horario=_vacio(_texto(celdas[2])),
                modalidad=_vacio(_texto(celdas[3])),
                lugar=_vacio(_texto(celdas[4])),
                vacantes=_entero(vacantes) if re.search(r"\d", vacantes) else None,
                reservado=cancelar is not None,
                disponible=reservar is not None,
                reemplaza_otro=(reservar is not None and reservar.get("data-exclusivo") == "1")
                or None,
            )
        )
    return turnos


# ---------------------------------------------------------------- helpers


def _vacio(valor: str) -> str | None:
    """MIeL usa '---' para los campos vacíos."""
    return None if valor.strip(" -") == "" else valor


def _sopa(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _limpiar(texto: str) -> str:
    return " ".join(texto.replace("\xa0", " ").split())


def _texto(el: Tag | None) -> str:
    """Todo el texto visible de `el`, en una línea."""
    return _limpiar(el.get_text(" ")) if el is not None else ""


def _texto_directo(el: Tag) -> str:
    """Sólo el texto que cuelga directo de `el` (ignora íconos y divs internos)."""
    return _limpiar(" ".join(str(s) for s in el.children if isinstance(s, NavigableString)))


def _entero(valor: str) -> int:
    digitos = re.sub(r"\D", "", valor)
    return int(digitos) if digitos else 0


def _id_en_url(url: str) -> str | None:
    m = re.search(r"/id/(\d+)", url)
    return m.group(1) if m else None


def _primer_segmento(url: str) -> str:
    """'https://miel.unlam.edu.ar/forov2/temas/comision/1' -> 'forov2'."""
    return next((p for p in urlparse(url).path.split("/") if p), "")


def _fecha(valor: str) -> date | None:
    """dd/mm/aaaa"""
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", valor)
    if not m:
        return None
    dia, mes, anio = map(int, m.groups())
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


_ARG = timezone(timedelta(hours=-3), "ART")  # Argentina no tiene horario de verano.


def _fecha_hora(valor: str) -> datetime | None:
    """dd/mm/aaaa hh:mm[:ss], en hora local de Argentina."""
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?", valor)
    if not m:
        return None
    dia, mes, anio, hora, minuto = map(int, m.groups()[:5])
    try:
        # Con zona: el schema `date-time` (RFC 3339) exige offset.
        return datetime(anio, mes, dia, hora, minuto, int(m.group(6) or 0), tzinfo=_ARG)
    except ValueError:
        return None


_UNIDADES = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}


def _bytes(valor: str) -> int | None:
    """'2.209 KB' -> 2262016. Formato argentino: punto de miles y coma decimal."""
    m = re.search(r"([\d.,]+)\s*([KMG]?B)\b", valor, re.IGNORECASE)
    if not m:
        return None
    numero = m.group(1).replace(".", "").replace(",", ".")
    try:
        return round(float(numero) * _UNIDADES[m.group(2).upper()])
    except ValueError:
        return None


def _html_a_texto(el: Tag) -> str:
    """HTML de un mensaje -> texto legible, conservando párrafos, listas y enlaces."""
    copia = _sopa(str(el))
    for a in copia.find_all("a", href=True):
        etiqueta, href = _texto(a), str(a["href"])
        a.replace_with(f"[{etiqueta}]({href})" if etiqueta and etiqueta != href else href)
    for br in copia.find_all("br"):
        br.replace_with("\n")
    for li in copia.find_all("li"):
        li.insert_before("\n- ")
    for bloque in copia.find_all(["p", "div", "ul", "ol", "h1", "h2", "h3", "h4", "blockquote"]):
        bloque.insert_after("\n")
    lineas = (_limpiar(linea) for linea in copia.get_text().splitlines())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lineas)).strip()
