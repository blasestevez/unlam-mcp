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
from datetime import date
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
    origen: str | None = Field(default=None, description="Código de Intraconsulta, ej. 'P' o 'E'.")
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
                    origen=_vacio(m.get("origen")),
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
        """GET a la API nueva; reloguea una vez si la sesión venció. Devuelve `data`."""
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
            if r.status_code != 200:
                raise IntraError(f"Intraconsulta respondió con error {r.status_code} en {endpoint}.")
            datos = r.json().get("data")
            return datos if isinstance(datos, list) else []
        raise IntraError("No se pudo mantener la sesión de Intraconsulta.")


# ==================================================================== helpers


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
