"""Servidor MCP: las tools que ve el modelo.

Cada tool es una función async con docstring (la descripción para el modelo),
parámetros tipados y una llamada al cliente de `miel.py`. La lógica va allá.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections import Counter
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager, contextmanager
from pathlib import Path
from typing import Annotated, Any

from mcp.server.mcpserver import Context, Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from . import __version__, archivos
from .archivos import Lectura
from .miel import (
    MielClient,
    MielError,
    Settings,
    borrar_credenciales,
    guardar_credenciales,
    nombre_en_url,
    normalizar,
)
from .parsers import (
    Modelo,
    Asistencia,
    Contenido,
    Destinatario,
    Evaluacion,
    Evento,
    Grupo,
    Materia,
    Mensaje,
    MensajeCompleto,
    MensajeForo,
    NotaEvaluacion,
    Practica,
    TemaForo,
    Turno,
)

INSTRUCCIONES = """\
Acceso a MIeL, el campus virtual de la UNLaM, con la cuenta del usuario.
Empezá por miel_materias. Donde se pide `materia` sirve el id de comisión, el
código o palabras del nombre, sin importar acentos ("prog avanzada", "3630")."""

SOLO_LECTURA = ToolAnnotations(read_only_hint=True, open_world_hint=True)
ESCRIBE_LOCAL = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True)
# Cambian algo en MIeL a nombre del usuario.
RESERVA = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=True
)
ENVIA = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True
)
CANCELA = ToolAnnotations(
    read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=True
)

MateriaParam = Annotated[
    str, Field(description="Id de comisión, código o parte del nombre. Ej: 'prog avanzada'.")
]
ContenidoParam = Annotated[str, Field(description="`id` de miel_contenidos. Ej: '300089'.")]
UrlParam = Annotated[str, Field(description="O la `url` de un adjunto de miel_mensaje.")]
TurnoParam = Annotated[str, Field(description="`id` del horario en miel_turnos. Ej: '465'.")]


# Respuestas de las tools (además de los modelos de parsers.py).


class Contenidos(Modelo):
    materia: str
    materia_id: str
    contenidos: list[Contenido]


class Descarga(Modelo):
    nombre: str
    ruta: str = Field(description="Ruta local del archivo descargado.")
    bytes: int


class TemasForo(Modelo):
    materia: str
    materia_id: str
    temas: list[TemaForo]


class MensajesForo(Modelo):
    materia: str
    tema_id: str
    mensajes: list[MensajeForo]


class Bandeja(Modelo):
    materia: str
    materia_id: str
    pagina: int
    hay_mas: bool = Field(description="Si es true, hay mensajes más viejos en la página siguiente.")
    mensajes: list[Mensaje]


class Destinatarios(Modelo):
    materia: str
    materia_id: str
    destinatarios: list[Destinatario]


class MensajeEnviado(Modelo):
    id: str = Field(description="Id del mensaje en tu bandeja de Enviados.")
    materia: str
    para: list[str]
    asunto: str
    adjunto: str | None = None


class PracticasMateria(Modelo):
    materia: str
    materia_id: str
    practicas: list[Practica]


class GruposMateria(Modelo):
    materia: str
    materia_id: str
    grupos: list[Grupo]


class AsistenciaMateria(Modelo):
    materia: str
    materia_id: str
    resumen: dict[str, int] = Field(
        default_factory=dict, description="Clases por estado, ej. {'Presente': 9, 'Ausente': 1}."
    )
    asistencias: list[Asistencia] = Field(default_factory=list)
    notas: list[NotaEvaluacion] = Field(default_factory=list)


class Evaluaciones(Modelo):
    materia: str
    materia_id: str
    evaluaciones: list[Evaluacion]


class Turnos(Modelo):
    materia: str
    materia_id: str
    turnos: list[Turno]


class Novedades(Modelo):
    materia: str
    materia_id: str
    contenidos_nuevos: list[Contenido] = Field(default_factory=list)
    mensajes_sin_leer: list[Mensaje] = Field(default_factory=list)
    temas_con_mensajes_nuevos: list[TemaForo] = Field(default_factory=list)
    otros: dict[str, int] = Field(
        default_factory=dict, description="Otras herramientas con pendientes, ej. {'Chat': 2}."
    )


@asynccontextmanager
async def conectar_miel(_: MCPServer[MielClient]) -> AsyncIterator[MielClient]:
    """Un cliente por servidor; el login recién ocurre en la primera tool que lo necesita."""
    async with MielClient(Settings()) as miel:
        yield miel


@contextmanager
def errores_para_el_modelo() -> Iterator[None]:
    """Un MielError llega al modelo con su mensaje (que dice qué hacer); el resto, genérico."""
    try:
        yield
    except MielError as e:
        raise ToolError(str(e)) from e


Ctx = Context[MielClient, Any]


def crear_servidor(
    lifespan: Callable[
        [MCPServer[MielClient]], AbstractAsyncContextManager[MielClient]
    ] = conectar_miel,
) -> MCPServer[MielClient]:
    mcp: MCPServer[MielClient] = MCPServer(
        "unlam", title="UNLaM", instructions=INSTRUCCIONES, version=__version__, lifespan=lifespan
    )

    def miel(ctx: Ctx) -> MielClient:
        return ctx.request_context.lifespan_context

    @mcp.tool(annotations=SOLO_LECTURA)
    async def miel_materias(ctx: Ctx, incluir_ocultas: bool = False) -> list[Materia]:
        """Lista tus materias en MIeL: id de comisión, código, comisión y herramientas
        disponibles (contenidos, foro, mensajería...) con sus pendientes. Es el punto de
        partida: el `id` sirve como `materia` en el resto de las tools."""
        with errores_para_el_modelo():
            return await miel(ctx).materias(incluir_ocultas=incluir_ocultas)

    @mcp.tool(annotations=SOLO_LECTURA)
    async def miel_contenidos(
        ctx: Ctx,
        materia: MateriaParam,
        buscar: Annotated[
            str,
            Field(description="Palabras a buscar en nombre, descripción o carpeta. Ej: 'tp 2'."),
        ] = "",
    ) -> Contenidos:
        """Archivos y enlaces que subieron los docentes a una materia, con carpeta,
        sección, fecha de subida, tamaño y si es nuevo. Para bajar un archivo, pasá su `id`
        a miel_descargar. Ojo: al consultarlo, MIeL deja de marcar los nuevos como nuevos."""
        with errores_para_el_modelo():
            m = await miel(ctx).materia(materia)
            contenidos = await miel(ctx).contenidos(m.id)
            if palabras := normalizar(buscar).split():
                contenidos = [c for c in contenidos if _coincide(c, palabras)]
            return Contenidos(materia=m.nombre, materia_id=m.id, contenidos=contenidos)

    async def bajar(ctx: Ctx, materia: str, contenido_id: str, url: str) -> tuple[str, Path]:
        m = await miel(ctx).materia(materia)
        if contenido_id:
            contenido = await miel(ctx).contenido(m.id, contenido_id)
            return contenido.nombre, await miel(ctx).descargar(m, contenido)
        if url:
            ruta = await miel(ctx).descargar_url(url, m, "Mensajes", nombre_en_url(url))
            return ruta.name, ruta
        raise MielError("Pasá `contenido_id` (de miel_contenidos) o `url` (de miel_mensaje).")

    @mcp.tool(annotations=ESCRIBE_LOCAL)
    async def miel_descargar(
        ctx: Ctx, materia: MateriaParam, contenido_id: ContenidoParam = "", url: UrlParam = ""
    ) -> Descarga:
        """Descarga un archivo de MIeL a la compu del usuario (MIEL_CARPETA) y devuelve la
        ruta. Pasá `contenido_id` (de miel_contenidos) o `url` (adjunto de miel_mensaje).
        Los enlaces externos no se descargan: pasale el link al usuario. Para leer el
        contenido de un apunte, usá miel_leer."""
        with errores_para_el_modelo():
            nombre, ruta = await bajar(ctx, materia, contenido_id, url)
            return Descarga(nombre=nombre, ruta=str(ruta), bytes=ruta.stat().st_size)

    @mcp.tool(annotations=ESCRIBE_LOCAL)
    async def miel_leer(
        ctx: Ctx,
        materia: MateriaParam,
        contenido_id: ContenidoParam = "",
        url: UrlParam = "",
        desde: Annotated[
            int, Field(ge=1, description="Página/diapositiva/parte desde donde leer. Ej: 1.")
        ] = 1,
    ) -> Lectura:
        """Lee el texto de un apunte de MIeL (PDF, Word .docx, PowerPoint .pptx o texto),
        para resumirlo, buscar algo o responder preguntas sobre él. Pasá `contenido_id`
        (de miel_contenidos) o `url` (adjunto de miel_mensaje). Si es largo viene por
        partes: para seguir, volvé a llamar con `desde` = `siguiente`."""
        with errores_para_el_modelo():
            _, ruta = await bajar(ctx, materia, contenido_id, url)
            return await asyncio.to_thread(archivos.leer, ruta, desde)

    @mcp.tool(annotations=ESCRIBE_LOCAL)
    async def miel_ver_pagina(
        ctx: Ctx,
        materia: MateriaParam,
        contenido_id: ContenidoParam = "",
        url: UrlParam = "",
        pagina: Annotated[int, Field(ge=1, description="Número de página del PDF. Ej: 1.")] = 1,
    ) -> Image:
        """Muestra una página de un PDF (o un archivo de imagen) como imagen. Usalo
        cuando miel_leer avisa que no hay texto (PDF escaneado), o para ver gráficos,
        diagramas o fórmulas que no salen bien como texto."""
        with errores_para_el_modelo():
            _, ruta = await bajar(ctx, materia, contenido_id, url)
            datos, formato, _ = await asyncio.to_thread(archivos.imagen, ruta, pagina)
            return Image(data=datos, format=formato)

    @mcp.tool(annotations=SOLO_LECTURA)
    async def miel_foro(ctx: Ctx, materia: MateriaParam) -> TemasForo:
        """Temas del foro de una materia, con cantidad de mensajes, sin leer, fecha del
        último mensaje y estado (abierto, cerrado o vencido). Para leer uno, pasá su `id` a miel_foro_tema."""
        with errores_para_el_modelo():
            m = await miel(ctx).materia(materia)
            return TemasForo(
                materia=m.nombre, materia_id=m.id, temas=await miel(ctx).temas_foro(m.id)
            )

    @mcp.tool(annotations=SOLO_LECTURA)
    async def miel_foro_tema(
        ctx: Ctx,
        materia: MateriaParam,
        tema_id: Annotated[str, Field(description="`id` de miel_foro. Ej: '9101'.")],
    ) -> MensajesForo:
        """Mensajes de un tema del foro: autor, rol (docente/alumno), fecha, texto con
        enlaces y a qué mensaje responde. Abrirlo puede marcarlo como leído en MIeL."""
        with errores_para_el_modelo():
            m = await miel(ctx).materia(materia)
            mensajes = await miel(ctx).mensajes_foro(m.id, tema_id)
            return MensajesForo(materia=m.nombre, tema_id=tema_id, mensajes=mensajes)

    @mcp.tool(annotations=SOLO_LECTURA)
    async def miel_mensajes(
        ctx: Ctx,
        materia: MateriaParam,
        pagina: Annotated[int, Field(ge=1, description="Página de la bandeja; 1 = más nuevos.")] = 1,
    ) -> Bandeja:
        """Bandeja de entrada de la mensajería de una materia (los avisos de los docentes,
        correcciones con nota, etc.): fecha, remitente, asunto, si está leído y si tiene
        adjunto. Para leer uno, pasá su `id` a miel_mensaje."""
        with errores_para_el_modelo():
            m = await miel(ctx).materia(materia)
            mensajes, hay_mas = await miel(ctx).mensajes(m.id, pagina)
            return Bandeja(
                materia=m.nombre, materia_id=m.id, pagina=pagina, hay_mas=hay_mas, mensajes=mensajes
            )

    @mcp.tool(annotations=SOLO_LECTURA)
    async def miel_mensaje(
        ctx: Ctx,
        materia: MateriaParam,
        mensaje_id: Annotated[str, Field(description="`id` de miel_mensajes. Ej: '11145418'.")],
    ) -> MensajeCompleto:
        """Abre un mensaje de la mensajería: remitente, rol, fecha, texto y adjuntos (que se
        bajan con miel_descargar pasando su `url`). MIeL lo marca como leído."""
        with errores_para_el_modelo():
            m = await miel(ctx).materia(materia)
            return await miel(ctx).mensaje(m.id, mensaje_id)

    @mcp.tool(annotations=SOLO_LECTURA)
    async def miel_destinatarios(ctx: Ctx, materia: MateriaParam) -> Destinatarios:
        """A quiénes les podés escribir en una materia: docentes, compañeros, tu grupo y
        las opciones 'todos los tutores' o 'todos los alumnos'."""
        with errores_para_el_modelo():
            m = await miel(ctx).materia(materia)
            return Destinatarios(
                materia=m.nombre, materia_id=m.id, destinatarios=await miel(ctx).destinatarios(m.id)
            )

    @mcp.tool(annotations=ENVIA)
    async def miel_enviar_mensaje(
        ctx: Ctx,
        materia: MateriaParam,
        para: Annotated[
            list[str],
            Field(
                min_length=1,
                description="Nombres (o ids de miel_destinatarios). Ej: ['caltana martin'].",
            ),
        ],
        asunto: str,
        texto: Annotated[str, Field(description="Texto plano; cada línea va como un párrafo.")],
        adjunto: Annotated[
            str, Field(description="Ruta de un archivo local para adjuntar (máx. 40 MB).")
        ] = "",
    ) -> MensajeEnviado:
        """Manda un mensaje por la mensajería de MIeL a nombre del usuario, con un
        adjunto opcional. No se puede deshacer: usalo sólo si el usuario lo pidió, y
        confirmá con él destinatarios y texto si los redactaste vos."""
        with errores_para_el_modelo():
            m = await miel(ctx).materia(materia)
            mensaje_id, enviados = await miel(ctx).enviar_mensaje(
                m.id, para, asunto, texto, Path(adjunto) if adjunto else None
            )
            return MensajeEnviado(
                id=mensaje_id,
                materia=m.nombre,
                para=[d.nombre for d in enviados],
                asunto=asunto,
                adjunto=Path(adjunto).name if adjunto else None,
            )

    @mcp.tool(annotations=SOLO_LECTURA)
    async def miel_practicas(
        ctx: Ctx,
        materia: Annotated[
            str, Field(description="Materia, o vacío para ver las de todas tus materias.")
        ] = "",
    ) -> list[PracticasMateria]:
        """Prácticas del portafolio (TPs, parciales, entregas): vencimiento, si ya entregaste,
        fecha de corrección, estado y nota. Sirve para "¿qué tengo que entregar?" o
        "¿qué nota me sacaron?". Sin `materia`, recorre todas tus materias."""
        with errores_para_el_modelo():
            if materia:
                materias = [await miel(ctx).materia(materia)]
            else:
                materias = [x for x in await miel(ctx).materias() if x.herramienta("portafolio")]
            return [
                PracticasMateria(
                    materia=m.nombre, materia_id=m.id, practicas=await miel(ctx).practicas(m.id)
                )
                for m in materias
            ]

    @mcp.tool(annotations=ENVIA)
    async def miel_entregar_practica(
        ctx: Ctx,
        materia: MateriaParam,
        practica_id: Annotated[str, Field(description="`id` de miel_practicas. Ej: '48882'.")],
        archivo: Annotated[str, Field(description="Ruta del archivo local a entregar (máx. 40 MB).")],
        mensaje: Annotated[str, Field(description="Mensaje opcional para el docente.")] = "",
    ) -> Practica:
        """Entrega una práctica del portafolio (TP, ejercicio) subiendo un archivo, a todos
        los docentes de la comisión. No se puede deshacer: usalo sólo si el usuario lo
        pidió. Devuelve la práctica con la fecha de entrega."""
        with errores_para_el_modelo():
            m = await miel(ctx).materia(materia)
            return await miel(ctx).entregar_practica(m.id, practica_id, Path(archivo), mensaje)

    @mcp.tool(annotations=SOLO_LECTURA)
    async def miel_calendario(
        ctx: Ctx,
        materia: Annotated[
            str, Field(description="Parte del nombre de la materia, o vacío para todas.")
        ] = "",
        incluir_pasados: bool = False,
    ) -> list[Evento]:
        """Calendario de MIeL: parciales, recuperatorios, entregas, defensas y otros eventos
        que cargan los docentes, con fecha, lugar y horario. Es la mejor fuente para
        "¿cuándo tengo el parcial / el recuperatorio?". Por defecto, sólo los próximos."""
        with errores_para_el_modelo():
            eventos = await miel(ctx).calendario()
            if not incluir_pasados:
                eventos = [e for e in eventos if e.proximo]
            if palabras := normalizar(materia).split():
                eventos = [
                    e for e in eventos if all(p in normalizar(e.materia or "") for p in palabras)
                ]
            return eventos

    @mcp.tool(annotations=SOLO_LECTURA)
    async def miel_grupos(
        ctx: Ctx,
        materia: Annotated[
            str, Field(description="Materia, o vacío para ver los de todas tus materias.")
        ] = "",
    ) -> list[GruposMateria]:
        """Tus grupos de trabajo en cada materia, con sus integrantes. El `id` del grupo
        sirve como destinatario en miel_enviar_mensaje para escribirle a todo el grupo."""
        with errores_para_el_modelo():
            if materia:
                materias = [await miel(ctx).materia(materia)]
            else:
                materias = [x for x in await miel(ctx).materias() if x.herramienta("portafolio")]
            resultado = []
            for m in materias:
                if grupos := await miel(ctx).grupos(m.id):
                    resultado.append(GruposMateria(materia=m.nombre, materia_id=m.id, grupos=grupos))
            return resultado

    @mcp.tool(annotations=SOLO_LECTURA)
    async def miel_asistencia(
        ctx: Ctx,
        materia: Annotated[
            str, Field(description="Materia, o vacío para ver las de todas tus materias.")
        ] = "",
    ) -> list[AsistenciaMateria]:
        """Asistencia clase por clase (presente, ausente, tarde, justificado; presencial o
        virtual) con un resumen por estado, y las notas de las evaluaciones online. Sirve
        para "¿cómo vengo con las faltas?". MIeL no informa el mínimo de asistencia exigido."""
        with errores_para_el_modelo():
            if materia:
                materias = [await miel(ctx).materia(materia)]
            else:
                materias = [x for x in await miel(ctx).materias() if x.herramienta("portafolio")]
            resultado = []
            for m in materias:
                asistencias, notas = await miel(ctx).asistencia(m.id)
                resultado.append(
                    AsistenciaMateria(
                        materia=m.nombre,
                        materia_id=m.id,
                        resumen=dict(Counter(a.estado for a in asistencias)),
                        asistencias=asistencias,
                        notas=notas,
                    )
                )
            return resultado

    @mcp.tool(annotations=SOLO_LECTURA)
    async def miel_evaluaciones(ctx: Ctx, materia: MateriaParam) -> Evaluaciones:
        """Evaluaciones online de una materia (parciales, cuestionarios): tipo, título, si
        está habilitada para rendir y estado. Sólo lista: no entra a ninguna."""
        with errores_para_el_modelo():
            m = await miel(ctx).materia(materia)
            return Evaluaciones(
                materia=m.nombre, materia_id=m.id, evaluaciones=await miel(ctx).evaluaciones(m.id)
            )

    @mcp.tool(annotations=SOLO_LECTURA)
    async def miel_turnos(ctx: Ctx, materia: MateriaParam) -> Turnos:
        """Turnos de una materia (recuperatorios, consultas, coloquios): evento, fecha,
        horario, lugar, vacantes y si ya tenés uno reservado. El `id` de cada horario se
        pasa a miel_reservar_turno o miel_cancelar_turno."""
        with errores_para_el_modelo():
            m = await miel(ctx).materia(materia)
            return Turnos(materia=m.nombre, materia_id=m.id, turnos=await miel(ctx).turnos(m.id))

    @mcp.tool(annotations=RESERVA)
    async def miel_reservar_turno(ctx: Ctx, materia: MateriaParam, turno_id: TurnoParam) -> Turno:
        """Reserva un turno (recuperatorio, consulta, coloquio) a nombre del usuario.
        Usalo sólo si el usuario lo pidió. Si el turno dice `reemplaza_otro`, reservarlo
        cancela el que ya tenía en ese evento: confirmalo con el usuario antes. Devuelve
        el turno con `reservado` en true."""
        with errores_para_el_modelo():
            m = await miel(ctx).materia(materia)
            return await miel(ctx).reservar_turno(m.id, turno_id)

    @mcp.tool(annotations=CANCELA)
    async def miel_cancelar_turno(ctx: Ctx, materia: MateriaParam, turno_id: TurnoParam) -> Turno:
        """Cancela un turno reservado del usuario y libera la vacante. Usalo sólo si el
        usuario lo pidió."""
        with errores_para_el_modelo():
            m = await miel(ctx).materia(materia)
            return await miel(ctx).cancelar_turno(m.id, turno_id)

    @mcp.tool(annotations=SOLO_LECTURA)
    async def miel_novedades(ctx: Ctx) -> list[Novedades]:
        """Lo nuevo en todas tus materias, según lo que MIeL marca como no visto: archivos
        nuevos, mensajes sin leer y temas del foro con mensajes nuevos. Ideal para
        "¿hay algo nuevo en MIeL?". No abre los mensajes ni los temas, pero al consultar
        los contenidos MIeL deja de marcarlos como nuevos."""
        with errores_para_el_modelo():
            resultado = []
            for m in await miel(ctx).materias():
                pendientes = {h.modulo: h for h in m.herramientas if h.pendientes}
                if not pendientes:
                    continue
                n = Novedades(materia=m.nombre, materia_id=m.id)
                if pendientes.pop("contenido", None):
                    n.contenidos_nuevos = [c for c in await miel(ctx).contenidos(m.id) if c.nuevo]
                if pendientes.pop("mensajeria", None):
                    bandeja, _ = await miel(ctx).mensajes(m.id)
                    n.mensajes_sin_leer = [x for x in bandeja if not x.leido]
                if pendientes.pop("forov2", None):
                    n.temas_con_mensajes_nuevos = [
                        t for t in await miel(ctx).temas_foro(m.id) if t.sin_leer
                    ]
                n.otros = {h.nombre: h.pendientes or 0 for h in pendientes.values()}
                resultado.append(n)
            return resultado

    return mcp


def _coincide(c: Contenido, palabras: list[str]) -> bool:
    texto = normalizar(" ".join(filter(None, [c.nombre, c.descripcion, c.modulo, c.seccion])))
    return all(p in texto for p in palabras)


AYUDA = """\
unlam-mcp: servidor MCP para MIeL (UNLaM).

  unlam-mcp login    Guarda tu usuario y clave de MIeL en esta compu (una sola vez).
  unlam-mcp logout   Borra el usuario y la clave guardados.
  unlam-mcp          Arranca el servidor (esto lo hace tu asistente, no vos).
"""


def main() -> None:
    # httpx loguea cada request en INFO; en un servidor MCP eso es ruido.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    comando = sys.argv[1] if len(sys.argv) > 1 else ""
    if comando == "login":
        sys.exit(_login())
    if comando == "logout":
        sys.exit(_logout())
    if comando in ("-h", "--help", "help", "ayuda"):
        print(AYUDA)
        return
    if comando:
        print(f"No conozco el comando '{comando}'.\n\n{AYUDA}", file=sys.stderr)
        sys.exit(2)
    crear_servidor().run()


def _login() -> int:
    import getpass

    print("Iniciar sesión en MIeL (UNLaM).")
    print("Tu usuario y clave quedan guardados sólo en esta compu, en el gestor de credenciales.")
    print()
    usuario = input("Usuario (DNI): ").strip()
    clave = getpass.getpass("Clave (no se ve mientras la escribís): ")
    if not usuario or not clave:
        print("\nFaltó el usuario o la clave. Probá de nuevo.")
        return 1

    print("\nProbando entrar a MIeL...")
    settings = Settings(_env_file=None, usuario=usuario, clave=clave)  # type: ignore[call-arg, arg-type]

    async def probar() -> list[Materia]:
        async with MielClient(settings) as cliente:
            return await cliente.materias()

    try:
        materias = asyncio.run(probar())
    except MielError as e:
        print(f"No se pudo entrar: {e}")
        return 1

    try:
        guardar_credenciales(usuario, clave)
    except Exception as e:
        print(f"Entraste, pero no pude guardar la clave en esta compu ({type(e).__name__}).")
        print("Podés definir MIEL_USUARIO y MIEL_CLAVE en la config de tu asistente.")
        return 1

    nombres = ", ".join(m.nombre for m in materias) or "ninguna activa"
    print(f"Listo. Entraste a MIeL y encontré {len(materias)} materias: {nombres}.")
    print("Si tu asistente ya estaba abierto, reinicialo para que tome el login.")
    return 0


def _logout() -> int:
    try:
        borrado = borrar_credenciales()
    except Exception as e:
        print(f"No pude acceder al gestor de credenciales ({type(e).__name__}).")
        return 1
    print("Listo, borré tu usuario y clave de MIeL." if borrado else "No había nada guardado.")
    return 0
