# unlam-mcp

[![PyPI](https://img.shields.io/pypi/v/unlam-mcp)](https://pypi.org/project/unlam-mcp/) [![Python](https://img.shields.io/pypi/pyversions/unlam-mcp)](https://pypi.org/project/unlam-mcp/) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE) [![Glama](https://glama.ai/mcp/servers/blasestevez/unlam-mcp/badges/score.svg)](https://glama.ai/mcp/servers/blasestevez/unlam-mcp) [![MCP Badge](https://lobehub.com/badge/mcp/blasestevez-unlam-mcp)](https://lobehub.com/mcp/blasestevez-unlam-mcp)

**unlam-mcp** es un servidor MCP (Model Context Protocol) para **MIeL** e **Intraconsulta** de la UNLaM: consultá tus materias, apuntes, foros, entregas, notas y turnos desde Claude, Cursor, VS Code (Copilot), Codex o Gemini CLI, en lenguaje natural.

**Sitio:** [unlam-mcp.vercel.app](https://unlam-mcp.vercel.app), con la instalación paso a paso para cada cliente y las preguntas frecuentes.

Ejemplos de consultas:

- *"¿Qué contenidos se publicaron esta semana en Programación Avanzada?"*
- *"Descargá el programa de Base de Datos."*
- *"¿Qué respondió el docente en el foro del TP?"*
- *"¿Qué entregas tengo esta semana y qué notas me asignaron?"*
- *"¿Hay novedades en MIeL?"*
- *"Resumí el apunte de la unidad 3 de Redes."*
- *"¿Cuándo son los recuperatorios?"*
- *"¿Cuál es mi asistencia en Redes?"*
- *"Reservá el turno de las 18 h del recuperatorio."*
- *"Enviá un mensaje a mi grupo de Taller Web con el informe adjunto."*
- *"Entregá este PDF en el TP 1 de Base de Datos."*
- *"¿Cuál es mi promedio y cuántas materias tengo aprobadas?"*

> [!NOTE]
> Proyecto no oficial, sin relación con la UNLaM. La mayoría de las herramientas son de solo lectura. Las únicas operaciones de escritura son **reservar y cancelar turnos, enviar mensajes y entregar prácticas**, y se ejecutan únicamente a pedido del usuario. El foro y las evaluaciones son de solo lectura: el servidor no publica en el foro ni inicia evaluaciones.

## Inicio rápido

Necesitás [uv](https://docs.astral.sh/uv/getting-started/installation/) y un cliente MCP.

```bash
uvx unlam-mcp login                        # guarda tu usuario y clave de MIeL en el sistema
claude mcp add unlam -- uvx unlam-mcp      # Claude Code; otros clientes más abajo
```

Configuración para Cursor, Claude Desktop, VS Code, Codex, Gemini CLI y más: [Instalación](#instalación) o [unlam-mcp.vercel.app/#instalar](https://unlam-mcp.vercel.app/#instalar).

## Herramientas

### Consulta (MIeL)

| Herramienta | Descripción |
|---|---|
| `miel_novedades` | Novedades de todas las materias: archivos nuevos, mensajes sin leer y foros con actividad. |
| `miel_materias` | Materias del usuario, con comisión y elementos pendientes. |
| `miel_calendario` | Parciales, recuperatorios, entregas y defensas de todas las materias, con fecha, lugar y horario. |
| `miel_contenidos` | Archivos y enlaces publicados por los docentes, con carpeta, fecha e indicador de novedad. |
| `miel_leer` | Extrae el texto de un apunte (PDF, Word, PowerPoint o texto plano) para su análisis. |
| `miel_ver_pagina` | Renderiza una página de un PDF como imagen, para documentos escaneados, gráficos o fórmulas. |
| `miel_descargar` | Descarga un archivo, o el adjunto de un mensaje, al equipo local. |
| `miel_foro` | Temas del foro de una materia, con cantidad de mensajes sin leer. |
| `miel_foro_tema` | Mensajes de un tema del foro. |
| `miel_mensajes` | Bandeja de mensajes de una materia: avisos y correcciones de los docentes. |
| `miel_mensaje` | Contenido completo de un mensaje, con sus adjuntos. |
| `miel_destinatarios` | Destinatarios disponibles en una materia: docentes, compañeros y grupo. |
| `miel_practicas` | Trabajos prácticos y parciales: vencimiento, estado de entrega, estado de corrección y nota. Por materia o para todas. |
| `miel_asistencia` | Asistencia por clase con resumen, y notas de las evaluaciones online. |
| `miel_grupos` | Grupos de trabajo de cada materia, con sus integrantes. |
| `miel_evaluaciones` | Evaluaciones online de una materia y su estado de habilitación. Solo las lista. |
| `miel_turnos` | Turnos de una materia (recuperatorios, consultas): fecha, lugar, vacantes y estado de la reserva. |

### Consulta (Intraconsulta)

Utiliza las mismas credenciales que MIeL (DNI y clave) para acceder a [Intraconsulta](https://intraconsulta.unlam.edu.ar):

| Herramienta | Descripción |
|---|---|
| `intraconsulta_materias_en_curso` | Materias inscriptas en el cuatrimestre actual: comisión, día y horario, aula y modalidad. |
| `intraconsulta_historia_academica` | Materias aprobadas con nota, fecha, acta y origen (promoción, examen o equivalencia), y el promedio simple calculado sobre ellas. |
| `intraconsulta_descargar_historia_academica` | Descarga el PDF de la historia académica en `MIEL_CARPETA/Intraconsulta`. No tiene costo ni inicia ningún trámite. |
| `intraconsulta_regularizadas` | Materias con cursada aprobada y examen final pendiente. |
| `intraconsulta_constancias` | Materias o mesas de final para las que hay constancia de examen disponible. |
| `intraconsulta_descargar_constancia` | Descarga la constancia de examen en PDF en `MIEL_CARPETA/Intraconsulta`. No tiene costo ni inicia ningún trámite. |

Los certificados de Intraconsulta (alumno regular, materias aprobadas, analítico parcial) son trámites **arancelados**, por lo que este servidor no los solicita ni los lista. Deben gestionarse desde Intraconsulta.

### Operaciones de escritura

| Herramienta | Descripción |
|---|---|
| `miel_reservar_turno` | Reserva un turno. Si existe una reserva previa para el mismo evento, MIeL la cancela; el asistente lo informa antes de ejecutar la operación. |
| `miel_cancelar_turno` | Cancela un turno reservado y libera la vacante. |
| `miel_enviar_mensaje` | Envía un mensaje por la mensajería de la materia, con un adjunto opcional (máximo 40 MB). Los destinatarios se indican por nombre o por grupo. |
| `miel_entregar_practica` | Entrega un trabajo práctico del portafolio mediante la carga de un archivo (máximo 40 MB). |

Luego de cada operación, el servidor vuelve a consultar MIeL para verificar el resultado. Si el cambio no se refleja, se informa el error en lugar de asumir que la operación fue exitosa. El envío de mensajes y las entregas son irreversibles.

Algunas consultas modifican el estado de lectura en MIeL, igual que al navegar desde el sitio: abrir un mensaje o un tema del foro los marca como leídos, y listar los contenidos quita el indicador de novedad.

El parámetro `materia` acepta el nombre completo o parcial (`"prog avanzada"`, `"base de datos"`) o el código de la materia (`3630`), sin distinción de acentos.

## Instalación

### Requisitos

- [uv](https://docs.astral.sh/uv/getting-started/installation/) (gestiona Python y las dependencias).
- Un cliente compatible con servidores MCP locales por transporte STDIO.

### 1. Configurar credenciales

```bash
uvx unlam-mcp login
```

El comando solicita el usuario y la clave de MIeL, valida el acceso y almacena las credenciales en el gestor de credenciales del sistema operativo (Administrador de credenciales en Windows, Llavero en macOS, Secret Service en Linux). Las credenciales no se guardan en archivos de texto ni en la configuración del cliente.

Si la clave de MIeL cambia, se debe ejecutar `login` nuevamente. Para eliminar las credenciales almacenadas: `uvx unlam-mcp logout`.

### 2. Registrar el servidor en el cliente

En todos los clientes, el comando de inicio es `uvx unlam-mcp`.

<details>
<summary><b>Claude Code</b></summary>

```bash
claude mcp add unlam -- uvx unlam-mcp
```
</details>

<details>
<summary><b>Claude Desktop</b></summary>

En *Settings → Developer → Edit Config*, agregar:

```json
{
  "mcpServers": {
    "unlam": {
      "command": "uvx",
      "args": ["unlam-mcp"]
    }
  }
}
```

Reiniciar Claude Desktop para aplicar los cambios.
</details>

<details>
<summary><b>Cursor</b></summary>

En `~/.cursor/mcp.json` (o desde *Settings → MCP → Add new server*):

```json
{
  "mcpServers": {
    "unlam": {
      "command": "uvx",
      "args": ["unlam-mcp"]
    }
  }
}
```
</details>

<details>
<summary><b>VS Code (Copilot)</b></summary>

```bash
code --add-mcp "{\"name\":\"unlam\",\"command\":\"uvx\",\"args\":[\"unlam-mcp\"]}"
```

Alternativamente, en `.vscode/mcp.json` (o desde *MCP: Open User Configuration*):

```json
{
  "servers": {
    "unlam": {
      "type": "stdio",
      "command": "uvx",
      "args": ["unlam-mcp"]
    }
  }
}
```

Las herramientas están disponibles en el chat en modo *Agent*.
</details>

<details>
<summary><b>Windsurf</b></summary>

En `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "unlam": {
      "command": "uvx",
      "args": ["unlam-mcp"]
    }
  }
}
```
</details>

<details>
<summary><b>Codex (CLI y extensión)</b></summary>

```bash
codex mcp add unlam -- uvx unlam-mcp
```

Alternativamente, en `~/.codex/config.toml`:

```toml
[mcp_servers.unlam]
command = "uvx"
args = ["unlam-mcp"]
```
</details>

<details>
<summary><b>Gemini CLI</b></summary>

En `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "unlam": {
      "command": "uvx",
      "args": ["unlam-mcp"]
    }
  }
}
```
</details>

<details>
<summary><b>Otros clientes (LM Studio, Cline, Zed, etc.)</b></summary>

La mayoría de los clientes utiliza el mismo bloque `mcpServers`, con `"command": "uvx"` y `"args": ["unlam-mcp"]`. Consultar la documentación del cliente para conocer la ubicación del archivo de configuración.
</details>

### Notas de compatibilidad

- **Windows:** si el cliente no encuentra `uvx`, indicar la ruta absoluta del ejecutable en `command` (se obtiene con `where uvx`). Algunos clientes no heredan el `PATH` de la terminal.
- **ChatGPT y clientes web:** solo admiten servidores MCP remotos (HTTP). Este servidor se ejecuta localmente para que las credenciales no salgan del equipo, por lo que requiere un cliente de escritorio o un editor.
- **Contenido de imagen:** `miel_ver_pagina` devuelve imágenes. En clientes sin soporte para imágenes, el resto de las herramientas funciona con normalidad.
- **Versión de desarrollo:** para usar la última versión del repositorio en lugar de la publicada en PyPI, reemplazar `uvx unlam-mcp` por `uvx --from git+https://github.com/blasestevez/unlam-mcp unlam-mcp`.

### Variables de entorno

| Variable | Valor por defecto | Descripción |
|---|---|---|
| `MIEL_CARPETA` | `~/MIeL` | Directorio de destino de las descargas. |
| `MIEL_USUARIO`, `MIEL_CLAVE` | Las credenciales de `login` | Credenciales alternativas, para entornos sin gestor de credenciales (por ejemplo, un servidor). |

Al ejecutar el proyecto desde una copia local (`uv run unlam-mcp`), las variables también pueden definirse en un archivo `.env` (ver `.env.example`).

## Desarrollo

### Estructura

```
src/unlam_mcp/
├── server.py         # definición de las herramientas MCP
├── miel.py           # cliente HTTP de MIeL: autenticación, páginas y descargas
├── parsers.py        # parseo del HTML de MIeL a estructuras de datos
├── intraconsulta.py  # cliente de la API JSON de Intraconsulta
└── archivos.py       # extracción de texto de PDF, Word y PowerPoint, y renderizado de páginas
```

Para ejecutar desde el código fuente: clonar el repositorio y ejecutar `uv run unlam-mcp`.

### Arquitectura

**MIeL** no expone una API de datos: las páginas se generan del lado del servidor, por lo que la información se obtiene parseando el HTML. Las operaciones de escritura utilizan los mismos formularios que el sitio (por ejemplo `/turnos/event/reservarTurno/`, `/mensajeria/event/enviarMensaje/` o `/portafolio/event/nuevaEntrega/`), y cada una se verifica con una nueva lectura de la página.

**Intraconsulta** dispone de una API JSON (`/backend/api/`), pero la autenticación de alumnos se realiza a través de la versión anterior (`alumno2.unlam.edu.ar`). Esta redirige a la versión nueva con un `transferToken`, que se intercambia en `Login/system-login` por la cookie de sesión.

### Agregar una herramienta

1. El parser de la página va en `parsers.py`.
2. El método que realiza la solicitud va en `MielClient` (`miel.py`).
3. La herramienta va en `server.py`, con el nombre `miel_<accion>`.

El docstring de la herramienta es la descripción que recibe el modelo: debe indicar su propósito y el origen de cada parámetro.

Ante un fallo en una herramienta existente, la causa más probable es un cambio en el HTML de MIeL; la corrección corresponde a `parsers.py`.

## Créditos

Basado en [TBalles/miel-mcp](https://github.com/TBalles/miel-mcp) y [nialvape/utn-mcp](https://github.com/nialvape/utn-mcp).

El uso de este servidor debe ser moderado y respetar el [aviso legal de MIeL](https://miel.unlam.edu.ar/principal/legal/).

## In English

unlam-mcp is an open-source MCP server for students of Universidad Nacional de La Matanza (UNLaM, Argentina). It exposes MIeL, the university's virtual campus, and Intraconsulta, the enrollment and academic records system, as 27 tools for any MCP client (Claude, Cursor, VS Code, Codex, Gemini CLI…): course files, handouts, forums, teacher messages, assignments and grades, attendance, exam slots and academic history. Almost every tool is read-only; the only write actions (booking exam slots, sending messages, submitting assignments) run only when the user asks. Runs locally over STDIO and stores credentials in the OS keychain.

```bash
uvx unlam-mcp login
claude mcp add unlam -- uvx unlam-mcp
```

Website: https://unlam-mcp.vercel.app · Unofficial project, not affiliated with UNLaM.

## Licencia

[MIT](LICENSE)

<!-- mcp-name: io.github.blasestevez/unlam-mcp -->
