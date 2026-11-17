# unlam-mcp

Conectá Claude (u otro asistente compatible con [MCP](https://modelcontextprotocol.io)) a tu cuenta de **MIeL** de la UNLaM y preguntale por tus materias en lenguaje natural:

- *"¿Qué subieron esta semana en Programación Avanzada?"*
- *"Bajame el programa de Base de Datos."*
- *"¿Qué respondió el profe en el foro del TP?"*
- *"¿Qué tengo que entregar esta semana y qué notas me pusieron?"*
- *"¿Hay algo nuevo en MIeL?"*
- *"Resumime el apunte de la unidad 3 de Redes."*
- *"¿Qué turnos hay para el recuperatorio y quedan vacantes?"*

> [!NOTE]
> Proyecto no oficial, sin relación con la UNLaM. Es **de solo lectura**: no publica ni modifica nada en MIeL.

## Qué puede hacer

| Tool | Qué hace |
|---|---|
| `miel_novedades` | Lo nuevo en todas tus materias: archivos, mensajes sin leer y foros con mensajes nuevos. |
| `miel_materias` | Tus materias, con comisión y pendientes (mensajes sin leer, etc.). |
| `miel_contenidos` | Los archivos y enlaces que subieron los docentes, con carpeta, fecha y si son nuevos. |
| `miel_leer` | Lee un apunte (PDF, Word, PowerPoint o texto) para resumirlo o responder sobre él. |
| `miel_ver_pagina` | Muestra una página de un PDF como imagen: para escaneados, gráficos o fórmulas. |
| `miel_descargar` | Baja un archivo (o el adjunto de un mensaje) a tu compu. |
| `miel_foro` | Los temas del foro de una materia, con mensajes sin leer. |
| `miel_foro_tema` | Los mensajes de un tema del foro. |
| `miel_mensajes` | La bandeja de mensajes de una materia: avisos de los docentes, correcciones. |
| `miel_mensaje` | Un mensaje completo, con sus adjuntos. |
| `miel_practicas` | Tus TPs y parciales: vencimiento, si entregaste, estado y nota. De una materia o de todas. |
| `miel_evaluaciones` | Las evaluaciones online de una materia y si están habilitadas. |
| `miel_turnos` | Los turnos de una materia (recuperatorios, consultas): fecha, lugar, vacantes y si ya reservaste. |

Algunas cosas se marcan como vistas en MIeL al consultarlas, igual que si entraras desde el navegador: abrir un mensaje o un tema del foro los marca como leídos, y listar los contenidos deja de mostrar los nuevos como nuevos.

Podés nombrar la materia como quieras: `"prog avanzada"`, `"base de datos"` o el código (`3630`).

## Instalación

1. Instalá [uv](https://docs.astral.sh/uv/getting-started/installation/) (una sola vez).
2. Iniciá sesión con tu usuario y clave de MIeL:

   ```bash
   uvx --from git+https://github.com/<tu-usuario>/unlam-mcp unlam-mcp login
   ```

   Te los pide en la terminal, prueba entrar a MIeL y los guarda en el gestor de credenciales de tu compu (el Administrador de credenciales en Windows, el Llavero en macOS). No quedan en ningún archivo de texto ni en la config del asistente.

3. Agregá el MCP a tu asistente.

**Claude Code**

```bash
claude mcp add unlam -- uvx --from git+https://github.com/<tu-usuario>/unlam-mcp unlam-mcp
```

**Claude Desktop**: en *Settings → Developer → Edit Config*, agregá:

```json
{
  "mcpServers": {
    "unlam": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/<tu-usuario>/unlam-mcp", "unlam-mcp"]
    }
  }
}
```

y reiniciá Claude Desktop. Si en Windows no arranca, poné la ruta completa a `uvx.exe` en `command` (la ves con `where uvx`).

**Otros asistentes** (Cursor, VS Code, etc.): cualquiera que acepte servidores MCP por STDIO sirve, con el comando `uvx --from git+https://github.com/<tu-usuario>/unlam-mcp unlam-mcp`.

Si cambiás la clave de MIeL, volvé a correr `login`. Para borrar los datos guardados: `unlam-mcp logout`.

### Opciones

| Variable | Por defecto | Para qué |
|---|---|---|
| `MIEL_CARPETA` | `~/MIeL` | Dónde se guardan las descargas. |
| `MIEL_USUARIO`, `MIEL_CLAVE` | los de `login` | Para usar otras credenciales sin `login` (por ejemplo, en un servidor sin gestor de credenciales). |

Si corrés el proyecto desde una copia local (`uv run unlam-mcp`), también podés ponerlas en un archivo `.env` (copiá `.env.example`).

## Para quien quiera colaborar

El código son cuatro archivos:

```
src/unlam_mcp/
├── server.py    # las tools que ve el asistente
├── miel.py      # entra a MIeL: login, páginas, descargas
├── parsers.py   # lee el HTML de MIeL y lo convierte en datos
└── archivos.py  # saca el texto de PDF, Word y PowerPoint, y páginas como imagen
```

Para correrlo desde tu copia: `git clone`, después `uv run unlam-mcp`.

MIeL no tiene una API con datos: las páginas vienen armadas desde el servidor, así que se leen del HTML. Los endpoints AJAX que existen (`/mensajeria/event/marcarLeido/`, `/forov2/event/nuevaRespuestaAjax/`, etc.) son sólo para acciones.

Para sumar algo nuevo: el parser de la página va en `parsers.py`, el método que la pide en `MielClient` (`miel.py`) y la tool en `server.py`, con nombre `miel_<accion>`. El docstring de la tool es lo que lee el asistente: contá para qué sirve y de dónde salen los parámetros.

Si algo deja de andar, lo más probable es que MIeL haya cambiado el HTML de una página: el arreglo va en `parsers.py`.

## Próximamente

- [ ] Autoguías, encuestas y chat (todavía no hay ejemplos reales para mapearlos)
- [ ] Intraconsulta: materias en curso e historia académica

## Créditos

Inspirado en [TBalles/miel-mcp](https://github.com/TBalles/miel-mcp) y [nialvape/utn-mcp](https://github.com/nialvape/utn-mcp).

Usalo con moderación y respetá el [aviso legal de MIeL](https://miel.unlam.edu.ar/principal/legal/).

## Licencia

MIT
