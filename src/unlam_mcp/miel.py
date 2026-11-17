"""Cliente de MIeL: configuración, sesión HTTP y operaciones.

No sabe nada de MCP: se puede usar solo, desde un script o una notebook.

    async with MielClient(Settings()) as miel:
        for m in await miel.materias():
            print(m.nombre)
"""

from __future__ import annotations

import asyncio
import base64
import re
from html import escape as html_escape
import time
import unicodedata
from pathlib import Path
from types import TracebackType
from typing import Any, Self
from urllib.parse import unquote

import httpx
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from . import __version__, parsers
from .intraconsulta import IntraClient
from .parsers import (
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


class MielError(Exception):
    """Error esperable. El mensaje se le muestra tal cual al usuario (o al modelo)."""


class Settings(BaseSettings):
    """Se lee de variables de entorno con prefijo `MIEL_` o de un archivo `.env`.

    Si no hay usuario y clave ahí, se usan los que guardó `unlam-mcp login` en el
    gestor de credenciales del sistema.
    """

    model_config = SettingsConfigDict(env_prefix="MIEL_", env_file=".env", extra="ignore")

    usuario: str = ""
    clave: SecretStr = SecretStr("")
    carpeta: Path = Field(
        default_factory=lambda: Path.home() / "MIeL", description="Dónde se guardan las descargas."
    )
    intervalo_minimo: float = Field(default=0.5, ge=0, description="Segundos entre requests.")
    cache_ttl: float = Field(default=120, ge=0, description="Segundos que dura una página.")
    timeout: float = Field(default=30, gt=0)
    base_url: str = "https://miel.unlam.edu.ar"

    @field_validator("carpeta", mode="before")
    @classmethod
    def _carpeta(cls, valor: object) -> object:
        # `MIEL_CARPETA=` vacío en el .env no tiene que terminar en el directorio actual.
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            return Path.home() / "MIeL"
        return Path(str(valor)).expanduser().resolve()

    @model_validator(mode="after")
    def _credenciales_guardadas(self) -> Self:
        if not (self.usuario.strip() and self.clave.get_secret_value()):
            guardadas = leer_credenciales()
            if guardadas:
                self.usuario, self.clave = guardadas[0], SecretStr(guardadas[1])
        return self


# ================================================ credenciales del sistema
# `unlam-mcp login` guarda usuario y clave en el gestor de credenciales del sistema
# operativo (Administrador de credenciales en Windows, Llavero en macOS, Secret
# Service en Linux). Nunca quedan en un archivo de texto.

SERVICIO_KEYRING = "unlam-mcp/miel"
_CLAVE_USUARIO = "__usuario__"  # bajo esta entrada se guarda cuál es el usuario


def leer_credenciales() -> tuple[str, str] | None:
    try:
        import keyring

        usuario = keyring.get_password(SERVICIO_KEYRING, _CLAVE_USUARIO)
        clave = keyring.get_password(SERVICIO_KEYRING, usuario) if usuario else None
    except Exception:  # sin gestor de credenciales disponible (ej. Linux sin escritorio)
        return None
    return (usuario, clave) if usuario and clave else None


def guardar_credenciales(usuario: str, clave: str) -> None:
    import keyring

    borrar_credenciales()
    keyring.set_password(SERVICIO_KEYRING, usuario, clave)
    keyring.set_password(SERVICIO_KEYRING, _CLAVE_USUARIO, usuario)


def borrar_credenciales() -> bool:
    import keyring
    from keyring.errors import PasswordDeleteError

    usuario = keyring.get_password(SERVICIO_KEYRING, _CLAVE_USUARIO)
    if not usuario:
        return False
    for entrada in (usuario, _CLAVE_USUARIO):
        try:
            keyring.delete_password(SERVICIO_KEYRING, entrada)
        except PasswordDeleteError:
            pass
    return True


# El formulario de login sólo aparece en páginas públicas: si una página interna
# lo trae, MIeL nos mandó al home porque la sesión venció.
_MARCA_LOGIN = 'id="formLogin"'
_MAX_ADJUNTO = 40 * 1024 * 1024  # el formulario valida `filesize: 40` (MB)


class MielClient:
    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self._http = httpx.AsyncClient(
            base_url=settings.base_url.rstrip("/"),
            follow_redirects=True,
            timeout=settings.timeout,
            headers={"User-Agent": f"unlam-mcp/{__version__} (cliente personal de MIeL)"},
            transport=transport,
        )
        self._logueado = False
        self._lock_login = asyncio.Lock()
        self._lock_turno = asyncio.Lock()
        self._ultimo_request = 0.0
        self._cache: dict[str, tuple[float, str]] = {}
        self._descargas: dict[str, Path] = {}  # url -> archivo ya bajado en esta sesión
        # Intraconsulta usa el mismo usuario y clave; su sesión es aparte.
        self.intra = IntraClient(
            settings.usuario, settings.clave.get_secret_value(), timeout=settings.timeout
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self, tipo: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        await self._http.aclose()
        await self.intra.aclose()

    # ================================================================ materias

    async def materias(self, *, incluir_ocultas: bool = False) -> list[Materia]:
        todas = parsers.parse_materias(await self._html("/principal/interno/"))
        return [m for m in todas if incluir_ocultas or not m.oculta]

    async def materia(self, consulta: str) -> Materia:
        """Busca una materia por id de comisión, código o palabras del nombre.

        Ignora mayúsculas y acentos, y todas las palabras tienen que aparecer
        en el nombre: "prog avanzada" encuentra "Programación Avanzada".
        """
        todas = await self.materias(incluir_ocultas=True)
        buscado = normalizar(consulta)

        exactas = [m for m in todas if buscado and buscado in (m.id, normalizar(m.codigo or ""))]
        if len(exactas) == 1:
            return exactas[0]

        candidatas = [m for m in todas if all(p in normalizar(m.nombre) for p in buscado.split())]
        activas = [m for m in candidatas if not m.oculta]
        if len(candidatas) == 1:
            return candidatas[0]
        if len(activas) == 1:  # ante la duda gana la activa (ej. cursadas viejas ocultas)
            return activas[0]
        if not buscado or not candidatas:
            raise MielError(f"No encontré la materia '{consulta}'. {_opciones(todas)}")
        raise MielError(f"'{consulta}' coincide con varias materias. {_opciones(candidatas)}")

    # ============================================================== contenidos

    async def contenidos(self, materia_id: str) -> list[Contenido]:
        html = await self._html(f"/contenido/archivos/comision/{materia_id}")
        return parsers.parse_contenidos(html)

    async def contenido(self, materia_id: str, contenido_id: str) -> Contenido:
        for c in await self.contenidos(materia_id):
            if c.id == contenido_id:
                return c
        raise MielError(
            f"No hay un contenido con id {contenido_id} en esa materia. "
            "Usá miel_contenidos para ver los ids."
        )

    async def descargar(self, materia: Materia, contenido: Contenido) -> Path:
        """Descarga un archivo a `<carpeta>/<materia>/<carpeta de MIeL>/` y devuelve la ruta."""
        if contenido.tipo == "enlace":
            raise MielError(f"'{contenido.nombre}' es un enlace externo: {contenido.url}")
        carpeta = nombre_seguro(contenido.modulo or "General")
        return await self.descargar_url(
            contenido.url, materia, carpeta, contenido.nombre_archivo or contenido.nombre
        )

    async def descargar_url(
        self, url_texto: str, materia: Materia, subcarpeta: str, nombre_sugerido: str
    ) -> Path:
        """Descarga cualquier archivo de MIeL (contenido, adjunto de un mensaje, etc.)."""
        if (ya := self._descargas.get(url_texto)) and ya.exists():
            return ya
        url = self._http.base_url.join(url_texto)
        # Las cookies de sesión nunca viajan a otro dominio.
        if url.host != self._http.base_url.host:
            raise MielError(f"Sólo se descargan archivos de MIeL, no de {url.host}.")

        carpeta = self.settings.carpeta / nombre_seguro(materia.nombre) / nombre_seguro(subcarpeta)
        for _ in range(2):  # un reintento si la sesión venció
            await self._asegurar_login()
            await self._esperar_turno()
            async with self._http.stream("GET", url) as r:
                es_html = "text/html" in r.headers.get("content-type", "")
                if es_html and _MARCA_LOGIN in (await r.aread()).decode(errors="replace"):
                    self._logueado = False
                    continue
                _verificar(r)
                nombre = _nombre_en_headers(r.headers) or nombre_sugerido
                carpeta.mkdir(parents=True, exist_ok=True)
                ruta = carpeta / nombre_seguro(nombre)
                parcial = ruta.with_name(ruta.name + ".part")  # nunca queda un archivo a medias
                with parcial.open("wb") as f:
                    async for bloque in r.aiter_bytes():
                        f.write(bloque)
                parcial.replace(ruta)
                self._descargas[url_texto] = ruta
                return ruta
        raise MielError("No se pudo mantener la sesión para descargar el archivo.")

    # ==================================================================== foro

    async def temas_foro(self, materia_id: str) -> list[TemaForo]:
        return parsers.parse_temas(await self._html(f"/forov2/temas/comision/{materia_id}"))

    async def mensajes_foro(self, materia_id: str, tema_id: str) -> list[MensajeForo]:
        html = await self._html(f"/forov2/mensajes/comision/{materia_id}/tema/{tema_id}")
        return parsers.parse_mensajes(html)

    # ============================================================== mensajería

    async def mensajes(self, materia_id: str, pagina: int = 1) -> tuple[list[Mensaje], bool]:
        """Una página de la bandeja de entrada y si hay más páginas."""
        html = await self._html(f"/mensajeria/entrada/comision/{materia_id}/pag/{pagina}")
        return parsers.parse_bandeja(html)

    async def mensaje(self, materia_id: str, mensaje_id: str) -> MensajeCompleto:
        """Abre un mensaje (MIeL lo marca como leído)."""
        ruta = f"/mensajeria/verEntrada/comision/{materia_id}/pag/1/from/entrada/id/{mensaje_id}"
        html = await self._html(ruta)
        if "<h1" not in html:
            raise MielError(f"No encontré el mensaje {mensaje_id}. Usá miel_mensajes.")
        return parsers.parse_mensaje(html, mensaje_id)

    async def destinatarios(self, materia_id: str) -> list[Destinatario]:
        return parsers.parse_destinatarios(await self._html(f"/mensajeria/redactar/comision/{materia_id}"))

    async def destinatario(self, materia_id: str, consulta: str) -> Destinatario:
        """Busca por id o por palabras del nombre (sin importar acentos ni el orden)."""
        todos = await self.destinatarios(materia_id)
        buscado = normalizar(consulta)
        if exacto := [d for d in todos if buscado in (d.id, normalizar(d.nombre))]:
            return exacto[0]
        palabras = buscado.replace(",", " ").split()
        candidatos = [d for d in todos if palabras and all(p in normalizar(d.nombre) for p in palabras)]
        if len(candidatos) == 1:
            return candidatos[0]
        if not candidatos:
            raise MielError(f"No hay nadie llamado '{consulta}' en esa materia. Usá miel_destinatarios.")
        nombres = "; ".join(f"{d.nombre} (id {d.id})" for d in candidatos)
        raise MielError(f"'{consulta}' coincide con varios: {nombres}. Pasá el id.")

    async def enviar_mensaje(
        self,
        materia_id: str,
        para: list[str],
        asunto: str,
        texto: str,
        adjunto: Path | None = None,
    ) -> tuple[str, list[Destinatario]]:
        """Manda un mensaje por la mensajería de la materia. Devuelve su id (en Enviados)
        y a quiénes se envió."""
        if not para:
            raise MielError("Falta al menos un destinatario.")
        if not asunto.strip() or not texto.strip():
            raise MielError("El mensaje necesita asunto y texto.")
        destinatarios = [await self.destinatario(materia_id, p) for p in para]

        # MIeL espera el HTML del editor en base64 (de UTF-8).
        html = "".join(f"<p>{html_escape(linea)}</p>" for linea in texto.strip().splitlines())
        datos: dict[str, Any] = {
            "borrador": "0",
            "asunto": asunto.strip(),
            "texto": base64.b64encode(html.encode()).decode(),
            "adjuntoReenvio": "",
        }
        for d in destinatarios:
            datos.setdefault(f"{d.tipo}[]", []).append(d.id)

        # Siempre multipart, como el formulario: sin adjunto va un campo de archivo vacío.
        archivo: tuple[str, bytes] = ("", b"")
        if adjunto is not None:
            adjunto = adjunto.expanduser()
            if not adjunto.is_file():
                raise MielError(f"No existe el archivo {adjunto}.")
            if adjunto.stat().st_size > _MAX_ADJUNTO:
                raise MielError("MIeL no acepta adjuntos de más de 40 MB.")
            archivo = (adjunto.name, await asyncio.to_thread(adjunto.read_bytes))
        salida = f"/mensajeria/salida/comision/{materia_id}/pag/1"
        self._cache.pop(salida, None)
        antes = {i for i, _ in parsers.parse_enviados(await self._html(salida))}

        ruta = f"/mensajeria/event/enviarMensaje/comision/{materia_id}"
        await self._postear(ruta, datos, files={"archivo": archivo})

        # Se confirma buscándolo en la bandeja de salida.
        self._cache.pop(salida, None)
        for identificador, titulo in parsers.parse_enviados(await self._html(salida)):
            if identificador not in antes and titulo == asunto.strip():
                return identificador, destinatarios
        raise MielError("MIeL no muestra el mensaje en Enviados: revisá en MIeL si salió.")

    # ========================================================= portafolio y más

    async def practicas(self, materia_id: str, *, actualizado: bool = False) -> list[Practica]:
        ruta = f"/portafolio/practicas/comision/{materia_id}"
        if actualizado:
            self._cache.pop(ruta, None)
        return parsers.parse_practicas(await self._html(ruta))

    async def entregar_practica(
        self, materia_id: str, practica_id: str, archivo: Path, mensaje: str = ""
    ) -> Practica:
        """Sube un archivo como entrega de una práctica del portafolio (a todos los
        docentes de la comisión). Devuelve la práctica ya con la fecha de entrega."""
        practica = next(
            (p for p in await self.practicas(materia_id, actualizado=True) if p.id == practica_id),
            None,
        )
        if practica is None:
            raise MielError(f"No hay una práctica con id {practica_id}. Usá miel_practicas.")
        archivo = archivo.expanduser()
        if not archivo.is_file():
            raise MielError(f"No existe el archivo {archivo}.")
        if archivo.stat().st_size > _MAX_ADJUNTO:
            raise MielError("MIeL no acepta entregas de más de 40 MB.")

        await self._postear(
            f"/portafolio/event/nuevaEntrega/comision/{materia_id}",
            {"codPractica": practica_id, "tutorDestinatario": "0", "observaciones": mensaje.strip()},
            files={"archivo": (archivo.name, await asyncio.to_thread(archivo.read_bytes))},
        )
        # Se confirma viendo el archivo en la página de entregas de la práctica.
        self._cache.pop(f"/portafolio/entregas/comision/{materia_id}/id/{practica_id}", None)
        if not await self._en_entregas(materia_id, practica_id, archivo.name):
            raise MielError("MIeL no muestra la entrega. Revisá la práctica en MIeL.")
        return next(
            (p for p in await self.practicas(materia_id, actualizado=True) if p.id == practica_id),
            practica,
        )

    async def _en_entregas(self, materia_id: str, practica_id: str, nombre: str) -> bool:
        """Si el archivo figura en la página de entregas de la práctica."""
        html = await self._html(f"/portafolio/entregas/comision/{materia_id}/id/{practica_id}")
        return nombre in html

    async def turnos(self, materia_id: str, *, actualizado: bool = False) -> list[Turno]:
        ruta = f"/turnos/turnos/comision/{materia_id}"
        if actualizado:
            self._cache.pop(ruta, None)
        return parsers.parse_turnos(await self._html(ruta))

    async def reservar_turno(self, materia_id: str, turno_id: str) -> Turno:
        """Reserva un horario. Si ya tenías otro del mismo evento, MIeL cancela aquel."""
        turno = await self._turno(materia_id, turno_id)
        if turno.reservado:
            return turno
        if not turno.disponible:
            raise MielError(f"El turno {turno_id} no se puede reservar (sin vacantes o cerrado).")
        await self._postear(
            f"/turnos/event/reservarTurno/comision/{materia_id}",
            {"idFranjaReservar": turno_id, "idRangoReservar": turno.rango_id},
        )
        turno = await self._turno(materia_id, turno_id)
        if not turno.reservado:
            raise MielError("MIeL no confirmó la reserva. Revisá el turno en MIeL.")
        return turno

    async def cancelar_turno(self, materia_id: str, turno_id: str) -> Turno:
        turno = await self._turno(materia_id, turno_id)
        if not turno.reservado:
            raise MielError(f"No tenés reservado el turno {turno_id}.")
        await self._postear(
            f"/turnos/event/cancelarTurno/comision/{materia_id}",
            {"idFranjaCancelar": turno_id, "idRangoCancelar": turno.rango_id},
        )
        turno = await self._turno(materia_id, turno_id)
        if turno.reservado:
            raise MielError("MIeL no confirmó la cancelación. Revisá el turno en MIeL.")
        return turno

    async def _turno(self, materia_id: str, turno_id: str) -> Turno:
        for t in await self.turnos(materia_id, actualizado=True):
            if t.id == turno_id:
                return t
        raise MielError(f"No hay un turno con id {turno_id}. Usá miel_turnos para ver los ids.")

    async def calendario(self) -> list[Evento]:
        """Eventos próximos y pasados de todas las materias (y del calendario personal)."""
        return parsers.parse_calendario(await self._html("/calendario/calendario/"))

    async def grupos(self, materia_id: str) -> list[Grupo]:
        return parsers.parse_grupos(await self._html(f"/portafolio/grupos/comision/{materia_id}"))

    async def asistencia(self, materia_id: str) -> tuple[list[Asistencia], list[NotaEvaluacion]]:
        """Asistencia clase por clase y notas de las evaluaciones online."""
        return parsers.parse_asistencia(await self._html(f"/portafolio/notas/comision/{materia_id}"))

    async def evaluaciones(self, materia_id: str) -> list[Evaluacion]:
        html = await self._html(f"/evaluacion/evaluaciones/comision/{materia_id}")
        return parsers.parse_evaluaciones(html)

    # ================================================================== sesión

    async def login(self) -> None:
        usuario, clave = self.settings.usuario.strip(), self.settings.clave.get_secret_value()
        if not usuario or not clave:
            raise MielError(
                "No hay usuario y clave de MIeL. El usuario tiene que correr "
                "`unlam-mcp login` en una terminal (una sola vez) y reiniciar el asistente."
            )
        async with self._lock_login:
            await self._enviar("GET", "/principal/home/")  # asigna la cookie de sesión
            await self._enviar(
                "POST",
                "/principal/event/login/",
                data={"usuario": usuario, "clave": clave, "recordar": "1"},
            )
            estado = await self._enviar("GET", "/principal/event/isLogged/")
            if estado.text.strip() != "1":
                raise MielError(
                    "MIeL rechazó el usuario o la clave. Si la cambiaste, corré "
                    "`unlam-mcp login` de nuevo."
                )
            self._logueado = True
            self._cache.clear()

    async def _asegurar_login(self) -> None:
        if not self._logueado:
            await self.login()

    async def _html(self, ruta: str) -> str:
        """GET de una página interna: con caché, login y un reintento si la sesión venció."""
        if guardado := self._cache.get(ruta):
            momento, html = guardado
            if time.monotonic() - momento < self.settings.cache_ttl:
                return html

        await self._asegurar_login()
        r = await self._enviar("GET", ruta)
        if _MARCA_LOGIN in r.text:
            self._logueado = False
            await self.login()
            r = await self._enviar("GET", ruta)
        _verificar(r)

        self._cache[ruta] = (time.monotonic(), r.text)
        return r.text

    async def _postear(self, ruta: str, datos: dict[str, Any], files: Any = None) -> None:
        """POST de un formulario de MIeL, con un reintento si la sesión venció."""
        await self._asegurar_login()
        r = await self._enviar("POST", ruta, data=datos, files=files)
        if _MARCA_LOGIN in r.text:
            self._logueado = False
            await self.login()
            r = await self._enviar("POST", ruta, data=datos, files=files)
        _verificar(r)

    async def _esperar_turno(self) -> None:
        """Respeta `intervalo_minimo` entre requests, para no cargar al servidor de la facultad."""
        async with self._lock_turno:
            espera = self._ultimo_request + self.settings.intervalo_minimo - time.monotonic()
            if espera > 0:
                await asyncio.sleep(espera)
            self._ultimo_request = time.monotonic()

    async def _enviar(self, method: str, ruta: str, **kwargs: Any) -> httpx.Response:
        await self._esperar_turno()
        try:
            return await self._http.request(method, ruta, **kwargs)
        except httpx.TimeoutException as e:
            raise MielError("MIeL tardó demasiado en responder. Probá más tarde.") from e
        except httpx.TransportError as e:
            raise MielError(f"No se pudo conectar con MIeL ({type(e).__name__}).") from e


# ==================================================================== helpers


def _verificar(r: httpx.Response) -> None:
    if r.status_code in (403, 404):
        raise MielError(f"No existe o no tenés acceso: {r.url.path}")
    if r.status_code >= 400:
        raise MielError(f"MIeL respondió con error {r.status_code} en {r.url.path}.")


def _opciones(materias: list[Materia]) -> str:
    if not materias:
        return "No tenés materias en MIeL."
    return "Opciones: " + "; ".join(f"{m.nombre} (id {m.id})" for m in materias)


def _nombre_en_headers(headers: httpx.Headers) -> str | None:
    """Nombre de archivo del header Content-Disposition (RFC 6266)."""
    valor = headers.get("content-disposition", "")
    if m := re.search(r"filename\*\s*=\s*[^']*'[^']*'([^;]+)", valor, re.IGNORECASE):
        return unquote(m.group(1).strip())
    if m := re.search(r'filename\s*=\s*"([^"]+)"|filename\s*=\s*([^;]+)', valor, re.IGNORECASE):
        return (m.group(1) or m.group(2)).strip()
    return None


def nombre_en_url(url: str) -> str:
    """Nombre del archivo en una URL de descarga de MIeL.

    '.../a/2634%5C_46703993%5C_out%5C_Resultados.pdf/t/P' -> 'Resultados.pdf'
    (MIeL antepone códigos separados por una barra invertida y un guion bajo).
    """
    m = re.search(r"/a/([^/]+)", url)
    crudo = unquote(m.group(1)) if m else unquote(url.rstrip("/").rsplit("/", 1)[-1])
    return crudo.rsplit("\\_", 1)[-1] or "archivo"


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos y espacios colapsados: para comparar nombres."""
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return " ".join(sin_acentos.casefold().split())


_RESERVADOS_WINDOWS = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10))} | {
    f"LPT{i}" for i in range(1, 10)
}


def nombre_seguro(nombre: str, max_largo: int = 120) -> str:
    """Nombre de archivo o carpeta válido en Windows, macOS y Linux."""
    limpio = " ".join(re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", nombre).split()).strip(" .")
    if not limpio:
        return "sin_nombre"
    base, _, ext = limpio.rpartition(".")
    if not base or len(ext) > 10:
        base, ext = limpio, ""
    if base.upper() in _RESERVADOS_WINDOWS:
        base = f"_{base}"
    sufijo = f".{ext}" if ext else ""
    return base[: max_largo - len(sufijo)].rstrip(" .") + sufijo
