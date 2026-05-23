# gestor_peticiones_llm

Script para ejecutar una peticion a Responses API leyendo mensajes desde archivos.

## Requisitos

- Python 3.10+
- `pip install -r requirements.txt`
- Archivo `.env` con `OPENAI_API_KEY`
- Dependencia `openai-agents` para `apply_diff` (incluida en `requirements.txt`)

## Entorno virtual

Crear el entorno virtual:

```bash
python3 -m venv .venv
```

Activarlo en Linux/macOS:

```bash
source .venv/bin/activate
```

Activarlo en Windows (PowerShell):

```powershell
.venv\Scripts\Activate.ps1
```

Instalar dependencias dentro del entorno virtual:

```bash
pip install -r requirements.txt
```

## Archivos

- `run_request.py`: script principal
- `request_spec.example.json`: ejemplo de archivo de especificacion

No se incluyen archivos de `inputs/` por defecto. Cada usuario crea los suyos.

## Formato de especificacion

La especificacion (JSON) debe contener:

- `developer_file`: ruta al archivo que se usara como mensaje `role=developer`
- `user_files`: arreglo de rutas a archivos que se combinaran en un unico mensaje `role=user`
- `prompt_file`: ruta al archivo con la pregunta final, enviada como otro mensaje `role=user`
- `output_file` (opcional): salida de texto del modelo (default: `response_output.txt`)
- `model` (opcional): default `gpt-5.4-mini`
- `effort` (opcional): `low`, `medium` o `high` (default `low`)

## Nomenclatura del user message para archivos

El script construye el mensaje unificado de archivos asi:

1. Inicia con `<BEGIN_FILES>`
2. Por cada archivo:
   - linea con `=====`
   - linea con el nombre/ruta del archivo
   - contenido completo del archivo
3. Cierra con `<END_FILES>`

## Ejecucion

Primero crea tu archivo `.env` en la raiz del proyecto. Puedes copiar `.env.example`.
Tambien crea los archivos referenciados por `request_spec.example.json`.

```bash
python3 run_request.py --spec request_spec.example.json
```

El script genera:

- archivo de texto con la salida agregada del modelo

## Nota

El script usa `tools=[{"type": "apply_patch"}]` y aplica operaciones `create_file`,
`update_file` y `delete_file` con `apply_diff`.

Por seguridad minimalista, solo permite aplicar cambios dentro del directorio del
proyecto (bloquea rutas fuera del workspace).
