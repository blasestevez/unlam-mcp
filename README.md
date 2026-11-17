# unlam-mcp

Conectá Claude (u otro asistente compatible con [MCP](https://modelcontextprotocol.io)) a tu cuenta de **MIeL** de la UNLaM y preguntale por tus materias en lenguaje natural:

- *"¿Qué subieron esta semana en Programación Avanzada?"*
- *"Bajame el programa de Base de Datos."*
- *"¿Qué respondió el profe en el foro del TP?"*
- *"¿Qué tengo que entregar esta semana y qué notas me pusieron?"*
- *"¿Hay algo nuevo en MIeL?"*
- *"Resumime el apunte de la unidad 3 de Redes."*
- *"¿Cuándo tengo los recuperatorios?"*
- *"¿Cómo vengo con las faltas en Redes?"*
- *"Anotame en el turno de las 18 del recuperatorio."*
- *"Mandale un mensaje a mi grupo de Taller Web con el informe adjunto."*
- *"Entregá este PDF en el TP 1 de Base de Datos."*
- *"¿Qué promedio tengo y cuántas materias aprobé?"*

> [!NOTE]
> Proyecto no oficial, sin relación con la UNLaM. Casi todo es de lectura. Las únicas acciones que hace a tu nombre son **reservar o cancelar turnos, mandar mensajes y entregar prácticas**, y sólo cuando se lo pedís. El foro y las evaluaciones son de solo lectura: nunca publica en el foro ni entra a rendir una evaluación.

## Qué puede hacer

### Consultar

| Tool | Qué hace |
|---|---|
| `miel_novedades` | Lo nuevo en todas tus materias: archivos, mensajes sin leer y foros con mensajes nuevos. |
| `miel_materias` | Tus materias, con comisión y pendientes (mensajes sin leer, etc.). |
| `miel_calendario` | Parciales, recuperatorios, entregas y defensas de todas tus materias, con fecha, lugar y horario. |
| `miel_contenidos` | Los archivos y enlaces que subieron los docentes, con carpeta, fecha y si son nuevos. |
| `miel_leer` | Lee un apunte (PDF, Word, PowerPoint o texto) para resumirlo o responder sobre él. |
| `miel_ver_pagina` | Muestra una página de un PDF como imagen: para escaneados, gráficos o fórmulas. |
| `miel_descargar` | Baja un archivo (o el adjunto de un mensaje) a tu compu. |
| `miel_foro` | Los temas del foro de una materia, con mensajes sin leer. |
| `miel_foro_tema` | Los mensajes de un tema del foro. |
| `miel_mensajes` | La bandeja de mensajes de una materia: avisos de los docentes, correcciones. |
| `miel_mensaje` | Un mensaje completo, con sus adjuntos. |
| `miel_destinatarios` | A quiénes les podés escribir en una materia: docentes, compañeros y tu grupo. |
| `miel_practicas` | Tus TPs y parciales: vencimiento, si entregaste, estado y nota. De una materia o de todas. |
| `miel_asistencia` | Tu asistencia clase por clase, con un resumen, y las notas de las evaluaciones online. |
| `miel_grupos` | Tus grupos de trabajo en cada materia, con sus integrantes. |
| `miel_evaluaciones` | Las evaluaciones online de una materia y si están habilitadas. Sólo las lista. |
| `miel_turnos` | Los turnos de una materia (recuperatorios, consultas): fecha, lugar, vacantes y si ya reservaste. |

### Intraconsulta

Con la misma cuenta (DNI y clave de MIeL), también lee [Intraconsulta](https://intraconsulta.unlam.edu.ar):

| Tool | Qué hace |
|---|---|
| `intraconsulta_materias_en_curso` | Las materias en las que estás inscripto este cuatrimestre: comisión, día y horario, aula y modalidad. |
| `intraconsulta_historia_academica` | Tus materias aprobadas con nota, fecha y acta, y un promedio simple calculado a partir de ellas. |
| `intraconsulta_regularizadas` | Las materias con la cursada aprobada y el final pendiente. |
| `intraconsulta_constancias` | Las materias (o mesas de final) para las que podés bajar una constancia de examen. |
| `intraconsulta_descargar_constancia` | Baja la constancia de examen en PDF a `MIEL_CARPETA/Intraconsulta`. Es gratis y no inicia ningún trámite. |

Los certificados de Intraconsulta (alumno regular, materias aprobadas, analítico parcial) son trámites **pagos**, así que este MCP no los pide ni los lista: se gestionan desde Intraconsulta.

### Hacer cosas a tu nombre

| Tool | Qué hace |
|---|---|
| `miel_reservar_turno` | Reserva un turno. Si ya tenías otro del mismo evento, MIeL lo cancela (el asistente te avisa antes). |
| `miel_cancelar_turno` | Cancela un turno reservado y libera la vacante. |
| `miel_enviar_mensaje` | Manda un mensaje por la mensajería de la materia, con un adjunto opcional (hasta 40 MB). Los destinatarios van por nombre o por grupo. |
| `miel_entregar_practica` | Entrega un TP del portafolio subiendo un archivo (hasta 40 MB). |

Después de cada acción vuelve a leer MIeL para confirmar que se hizo: si MIeL no la muestra, avisa en vez de dar por hecho que salió. Mensajes y entregas no se pueden deshacer.

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

El código son cinco archivos:

```
src/unlam_mcp/
├── server.py         # las tools que ve el asistente
├── miel.py           # entra a MIeL: login, páginas, descargas
├── parsers.py        # lee el HTML de MIeL y lo convierte en datos
├── intraconsulta.py  # entra a Intraconsulta y lee su API JSON
└── archivos.py       # saca el texto de PDF, Word y PowerPoint, y páginas como imagen
```

Intraconsulta nueva tiene una API JSON (`/backend/api/`), pero los alumnos inician sesión por la versión vieja (`alumno2.unlam.edu.ar`). Ésta redirige a la nueva con un `transferToken`, que se canjea en `Login/system-login` por la cookie de sesión.

Para correrlo desde tu copia: `git clone`, después `uv run unlam-mcp`.

MIeL no tiene una API con datos: las páginas vienen armadas desde el servidor, así que se leen del HTML. Las acciones son los mismos formularios que usa la página (por ejemplo `/turnos/event/reservarTurno/`, `/mensajeria/event/enviarMensaje/` o `/portafolio/event/nuevaEntrega/`), y después de cada una se vuelve a leer la página para confirmarla.

Para sumar algo nuevo: el parser de la página va en `parsers.py`, el método que la pide en `MielClient` (`miel.py`) y la tool en `server.py`, con nombre `miel_<accion>`. El docstring de la tool es lo que lee el asistente: contá para qué sirve y de dónde salen los parámetros.

Si algo deja de andar, lo más probable es que MIeL haya cambiado el HTML de una página: el arreglo va en `parsers.py`.

## Próximamente

- [ ] Intraconsulta: inscripciones a materias y finales

## Créditos

Inspirado en [TBalles/miel-mcp](https://github.com/TBalles/miel-mcp) y [nialvape/utn-mcp](https://github.com/nialvape/utn-mcp).

Usalo con moderación y respetá el [aviso legal de MIeL](https://miel.unlam.edu.ar/principal/legal/).

## Licencia

MIT
