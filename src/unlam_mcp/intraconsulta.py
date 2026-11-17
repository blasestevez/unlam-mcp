"""Cliente de Intraconsulta (el sistema de gestión académica de la UNLaM).

Intraconsulta nueva (intraconsulta.unlam.edu.ar) es una app con API JSON en
/backend/api/, pero no tiene login propio para alumnos: se entra por la versión
vieja (alumno2.unlam.edu.ar) con DNI y clave, ésta redirige a la nueva con un
`transferToken` en la URL, y la nueva lo canjea en Login/system-login por una
cookie de sesión. Este cliente hace exactamente ese recorrido.

Usa el mismo usuario y clave que MIeL.
"""

from __future__ import annotations

import asyncio
import base64
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from pydantic import Field

from . import __version__
from .parsers import Modelo

_VIEJA = "https://alumno2.unlam.edu.ar"
_API = "https://intraconsulta.unlam.edu.ar/backend/api/"
# Cualquier servlet de la vieja que lleve a la nueva sirve para obtener el token.
_PUENTE = "/consulta_materias_aprobadas"


class IntraError(Exception):
    """Error esperable. El mensaje se le muestra tal cual al usuario (o al modelo)."""


# ----------------------------------------------------------------- modelos


class MateriaEnCurso(Modelo):
    codigo: str
    nombre: str
    comision: str | None = None
    dia_horario: str | None = Field(default=None, description="Ej. 'Sábado: 14:00-18:00'.")
    aula: str | None = None
    modalidad: str | None = Field(default=None, description="Código de Intraconsulta, ej. 'E'.")
    carrera: str | None = None


class Cursada(Modelo):
    periodo: str
    materias: list[MateriaEnCurso]


class MateriaAprobada(Modelo):
    codigo: str
    nombre: str
    nota: str | None = None
    fecha: date | None = None
    origen: str | None = Field(default=None, description="'Promoción', 'Examen' o 'Equivalencia'.")
    acta: str | None = Field(default=None, description="Acta o resolución.")


class HistoriaAcademica(Modelo):
    carrera: str
    materias: list[MateriaAprobada]
    promedio: float | None = Field(
        default=None, description="Promedio simple de las notas numéricas (calculado acá, no de la UNLaM)."
    )


class MateriaRegularizada(Modelo):
    codigo: str
    nombre: str
    anio: str | None = None
    periodo: str | None = None


class Regularizadas(Modelo):
    carrera: str
    materias: list[MateriaRegularizada]


class InscripcionExamen(Modelo):
    """Una inscripción para la que se puede bajar la constancia de examen."""

    inscripcion: str = Field(description="Se pasa a intraconsulta_descargar_constancia.")
    codigo: str
    materia: str
    comision: str | None = None
    dias_horarios: str | None = None


# Sólo las constancias de examen: son gratis e inmediatas. Los certificados (alumno
# regular, materias aprobadas, analítico) son trámites pagos y quedan afuera a propósito.
CONSTANCIAS = {"parcial": "ConstanciaExamenParcial", "final": "ConstanciaExamenFinal"}
# Códigos de `origen` en la historia académica (los mismos que muestra la app).
_ORIGENES = {"P": "Promoción", "E": "Examen", "B": "Equivalencia"}


# ----------------------------------------------------------------- cliente


class IntraClient:
    def __init__(self, usuario: str, clave: str, *, timeout: float = 30) -> None:
        self._usuario, self._clave = usuario.strip(), clave
        self._http = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": f"unlam-mcp/{__version__} (cliente personal de Intraconsulta)"},
        )
        self._logueado = False
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._http.aclose()

    # ================================================================ consultas

    async def materias_en_curso(self) -> list[Cursada]:
        return [
            Cursada(
                periodo=str(p.get("periodo_nombre") or ""),
                materias=[
                    MateriaEnCurso(
                        codigo=str(m.get("materia_codigo") or ""),
                        nombre=_titulo(m.get("materia_nombre")),
                        comision=_vacio(m.get("comision")),
                        dia_horario=_vacio(m.get("dia_horario")),
                        aula=_vacio(m.get("aula")),
                        modalidad=_vacio(m.get("modalidad")),
                        carrera=_titulo(m.get("carrera_nombre")) or None,
                    )
                    for m in p.get("listado_materias") or []
                ],
            )
            for p in await self._get("MateriasEnCurso")
        ]

    async def historia_academica(self) -> list[HistoriaAcademica]:
        resultado = []
        for c in await self._get("HistoriaAcademica/GetHistoriaAcademica"):
            materias = [
                MateriaAprobada(
                    codigo=str(m.get("materia_codigo") or ""),
                    nombre=_titulo(m.get("materia_nombre")),
                    nota=_vacio(m.get("nota")),
                    fecha=_fecha(m.get("fecha")),
                    origen=_ORIGENES.get(str(m.get("origen") or ""), _vacio(m.get("origen"))),
                    acta=_vacio(m.get("acta_o_resolucion")),
                )
                for m in c.get("listado_materias") or []
            ]
            notas = [float(m.nota) for m in materias if m.nota and _es_numero(m.nota)]
            resultado.append(
                HistoriaAcademica(
                    carrera=_titulo(c.get("carrera_nombre")),
                    materias=materias,
                    promedio=round(sum(notas) / len(notas), 2) if notas else None,
                )
            )
        return resultado

    async def descargar_historia_academica(self, carpeta: Path) -> Path:
        """Baja el PDF de la historia académica (el mismo que el botón de Intraconsulta)."""
        datos = await self._get_datos("HistoriaAcademica/DescargarHistoriaAcademica")
        return _guardar_pdf(datos, carpeta / "Historia academica.pdf")

    async def regularizadas(self) -> list[Regularizadas]:
        return [
            Regularizadas(
                carrera=_titulo(c.get("carrera_nombre")),
                materias=[
                    MateriaRegularizada(
                        codigo=str(m.get("materia_codigo") or ""),
                        nombre=_titulo(m.get("materia_nombre")),
                        anio=_vacio(m.get("anio_academico")),
                        periodo=_vacio(m.get("periodo_lectivo_nombre")),
                    )
                    for m in c.get("listado_materias") or []
                ],
            )
            for c in await self._get("MateriasRegularizadas/GetMateriasRegularizadasPersona")
        ]

    # =============================================================== constancias

    async def inscripciones_examen(self, tipo: str) -> list[InscripcionExamen]:
        """Inscripciones para las que hay constancia de examen ('parcial' o 'final')."""
        return [
            InscripcionExamen(
                inscripcion=str(i.get("inscripcion") or ""),
                codigo=str(i.get("codigo") or ""),
                materia=_titulo(i.get("nombre")),
                comision=_vacio(i.get("cursoComision")),
                dias_horarios=_vacio(i.get("diasHorarios")),
            )
            for i in await self._get(f"{_constancia(tipo)}/inscripciones")
        ]

    async def descargar_constancia(self, tipo: str, inscripcion: str, carpeta: Path) -> Path:
        validas = {i.inscripcion: i for i in await self.inscripciones_examen(tipo)}
        if inscripcion not in validas:
            raise IntraError(
                f"No hay una inscripción {inscripcion} con constancia de examen {tipo}. "
                "Usá intraconsulta_constancias para ver las disponibles."
            )
        datos = await self._get_datos(f"{_constancia(tipo)}/descargar/{inscripcion}")
        nombre = f"Constancia examen {tipo} - {validas[inscripcion].materia}.pdf"
        return _guardar_pdf(datos, carpeta / nombre)

    # ================================================================== sesión

    async def login(self) -> None:
        if not self._usuario or not self._clave:
            raise IntraError(
                "No hay usuario y clave. El usuario tiene que correr `unlam-mcp login` en una "
                "terminal (una sola vez) y reiniciar el asistente."
            )
        async with self._lock:
            self._http.cookies.clear()
            try:
                await self._http.get(_VIEJA + "/")  # asigna la cookie de sesión de la vieja
                r = await self._http.post(
                    _VIEJA + "/index.jsp", data={"usuario": self._usuario, "clave": self._clave}
                )
                if r.status_code >= 500:  # ej. cuando está en mantenimiento
                    raise IntraError(
                        f"Intraconsulta está fallando (error {r.status_code}), puede estar en "
                        "mantenimiento. No es tu clave: probá más tarde."
                    )
                if "salir.jsp" not in r.text:  # sólo aparece con la sesión iniciada
                    raise IntraError(
                        "Intraconsulta rechazó el usuario o la clave (se usan los mismos que en MIeL). "
                        "Si la cambiaste, corré `unlam-mcp login` de nuevo."
                    )
                r = await self._http.get(_VIEJA + _PUENTE)
                token = httpx.URL(r.headers.get("location", "")).params.get("transferToken")
                if not token:
                    raise IntraError("Intraconsulta no devolvió el acceso a la versión nueva. Probá más tarde.")
                r = await self._http.post(_API + "Login/system-login", json={"TransferToken": token})
            except httpx.TimeoutException as e:
                raise IntraError("Intraconsulta tardó demasiado en responder. Probá más tarde.") from e
            except httpx.TransportError as e:
                raise IntraError(f"No se pudo conectar con Intraconsulta ({type(e).__name__}).") from e
            if r.status_code != 200:
                raise IntraError(f"Intraconsulta respondió {r.status_code} al iniciar sesión.")
            self._logueado = True

    async def _get(self, endpoint: str) -> list[dict[str, Any]]:
        """`data` de un endpoint que devuelve una lista."""
        datos = await self._get_datos(endpoint)
        return datos if isinstance(datos, list) else []

    async def _get_datos(self, endpoint: str) -> Any:
        """GET a la API nueva (sólo lectura); reloguea una vez si la sesión venció.
        Devuelve `data`."""
        for intento in range(2):
            if not self._logueado:
                await self.login()
            try:
                r = await self._http.get(_API + endpoint)
            except httpx.TimeoutException as e:
                raise IntraError("Intraconsulta tardó demasiado en responder. Probá más tarde.") from e
            except httpx.TransportError as e:
                raise IntraError(f"No se pudo conectar con Intraconsulta ({type(e).__name__}).") from e
            if r.status_code == 401 and intento == 0:
                self._logueado = False
                continue
            try:
                cuerpo = r.json()
            except ValueError:
                cuerpo = {}
            if r.status_code != 200:
                detalle = cuerpo.get("mensaje") if isinstance(cuerpo, dict) else None
                raise IntraError(
                    f"Intraconsulta respondió con error {r.status_code} en {endpoint}"
                    + (f": {detalle}" if detalle else ".")
                )
            return cuerpo.get("data") if isinstance(cuerpo, dict) else None
        raise IntraError("No se pudo mantener la sesión de Intraconsulta.")


# ==================================================================== helpers


def _constancia(tipo: str) -> str:
    if tipo not in CONSTANCIAS:
        raise IntraError("El tipo de constancia es 'parcial' o 'final'.")
    return CONSTANCIAS[tipo]


def _guardar_pdf(datos: Any, ruta: Path) -> Path:
    """La API devuelve el PDF en base64 dentro de `data.fileBytes`."""
    crudo = datos.get("fileBytes") if isinstance(datos, dict) else datos
    try:
        contenido = base64.b64decode(str(crudo or ""), validate=True)
    except ValueError as e:
        raise IntraError("Intraconsulta no devolvió un PDF.") from e
    if not contenido.startswith(b"%PDF"):
        raise IntraError("Intraconsulta no devolvió un PDF.")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(contenido)
    return ruta


def _vacio(valor: object) -> str | None:
    texto = " ".join(str(valor or "").split())
    return texto or None


def _titulo(valor: object) -> str:
    """'BASE DE DATOS II' -> 'Base de Datos II' (respeta números romanos y conectores)."""
    palabras = []
    for i, p in enumerate(str(valor or "").split()):
        if set(p) <= set("IVXLC"):
            palabras.append(p)
        elif i > 0 and p.lower() in _CONECTORES:
            palabras.append(p.lower())
        else:
            palabras.append(p.capitalize())
    return " ".join(palabras)


_CONECTORES = {"a", "al", "de", "del", "e", "el", "en", "la", "las", "los", "o", "para", "por", "u", "y"}


def _fecha(valor: object) -> date | None:
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def _es_numero(texto: str) -> bool:
    try:
        float(texto)
    except ValueError:
        return False
    return True
