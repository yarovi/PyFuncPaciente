# Guía operativa — DigitalOcean Functions con `doctl`

**Proyecto:** `pacientes`  
**Actualizado:** 15 de noviembre de 2026  
**Objetivo:** desplegar funciones Python de forma independiente y reproducible sin reconstruir otras funciones que ya están operativas.

## 1. Contexto validado

- Namespace: `pacientes-functions-dev`.
- Runtime utilizado: `python:3.13`.
- CLI observada durante el diagnóstico: `doctl 1.167.0-release`.
- Software Serverless observado: `5.0.22`.
- Funciones existentes: `consultar-pacientes` y `consultar-catalogos`.
- **Procedimiento exitoso:** despliegue selectivo con `--include`, variables con `--env` y construcción con `--remote-build`.
- Se confirmó que `consultar-catalogos` se desplegó y posteriormente respondió correctamente tras resolver su autenticación.

> Los nombres, versiones y comandos reflejan este proyecto. Comprueba los valores vigentes antes de utilizarlos en otro namespace.

## 2. Estructura del repositorio

```text
pacientes/
├── .config/
│   └── .env                  # Secretos locales: NO versionar
├── packages/
│   └── default/
│       ├── consultar-pacientes/
│       │   ├── __main__.py
│       │   ├── build.sh
│       │   └── requirements.txt
│       └── consultar-catalogos/
│           ├── __main__.py
│           ├── build.sh
│           └── requirements.txt
└── project.yml
```

Cada función dispone de su propio código y dependencias. Las declaraciones de las funciones se mantienen juntas en `project.yml`. Todos los comandos de despliegue siguientes se ejecutan **desde la raíz** del proyecto.

### Ejemplo de `project.yml`

```yaml
packages:
  - name: default
    functions:
      - name: consultar-pacientes
        runtime: python:3.13
        web: true
        environment:
          BACKEND_API_KEY: "${BACKEND_API_KEY}"
          DATABASE_URL: "${DATABASE_URL}"
      - name: consultar-catalogos
        runtime: python:3.13
        web: true
        environment:
          BACKEND_API_KEY: "${BACKEND_API_KEY}"
          DATABASE_URL: "${DATABASE_URL}"
```

**Nota:** ambas funciones pueden declarar su propio runtime. `--include` filtra el despliegue, pero no debe asumirse que omite toda la validación del archivo `project.yml`.

## 3. Preparación y conexión con `doctl`

### Verificar instalación y sesión

```bash
doctl version
doctl auth list
```

Si todavía no has configurado la autenticación en el equipo, inicia el flujo de autenticación:

```bash
doctl auth init
```

No incluyas tokens API en el repositorio ni en registros compartidos.

### Consultar namespaces

```bash
doctl serverless namespaces list
```

### Conectarse al namespace del proyecto

```bash
doctl serverless connect pacientes-functions-dev
```

Si tu versión de `doctl` no admite el nombre como identificador, consulta la ayuda y utiliza el identificador del namespace:

```bash
doctl serverless connect --help
```

### Confirmar conexión y runtimes disponibles

```bash
doctl serverless status
doctl serverless status --languages
```

Antes de desplegar, comprueba que el namespace conectado sea el esperado y que admita `python:3.13`.

## 4. Comandos de despliegue — procedimiento recomendado

### Desplegar únicamente `consultar-catalogos`

```bash
doctl serverless deploy . \
  --include default/consultar-catalogos \
  --env ".config/.env" \
  --remote-build \
  --verbose-build
```

### Desplegar únicamente `consultar-pacientes`

```bash
doctl serverless deploy . \
  --include default/consultar-pacientes \
  --env ".config/.env" \
  --remote-build \
  --verbose-build
```

**Precaución:** si `consultar-pacientes` conserva artefactos locales (`virtualenv/`, `__deployer__.zip`), una construcción remota de esa función puede rechazarlos. Limpia o excluye los artefactos derivados **de esa función** antes de intentar su despliegue remoto; no borres código fuente ni dependencias declaradas.

### Nueva función: patrón reutilizable

Tras crear `packages/default/crear-pacientes/`, declarar la función en `project.yml` y preparar su código y dependencias:

```bash
doctl serverless deploy . \
  --include default/crear-pacientes \
  --env ".config/.env" \
  --remote-build \
  --verbose-build
```

### Despliegue completo (usar deliberadamente)

```bash
doctl serverless deploy . \
  --env ".config/.env" \
  --remote-build
```

Sin `--include`, el comando intenta procesar todas las funciones incluidas en el proyecto. Antes de usarlo, comprueba que ninguna contenga artefactos locales incompatibles con la construcción remota.

### Significado de las opciones

| Opción | Propósito |
|---|---|
| `.` | Directorio raíz del proyecto |
| `--include default/<funcion>` | Selecciona la función que se quiere desplegar |
| `--env ".config/.env"` | Proporciona variables de entorno para la configuración de ejecución |
| `--remote-build` | Solicita construir en la infraestructura remota |
| `--verbose-build` | Muestra detalles de la construcción |
| `--incremental` | Despliega solamente cambios según el mecanismo incremental; no se requiere para el procedimiento validado |

**Importante:** `--remote-build` no significa que cualquier `build.sh` funcione automáticamente. El script y las dependencias deben ser compatibles con el entorno de construcción remoto.

## 5. Comandos básicos de administración y diagnóstico

```bash
# Versión de doctl
doctl version

# Contextos de autenticación
doctl auth list

# Namespaces disponibles
doctl serverless namespaces list

# Conexión al namespace
doctl serverless connect pacientes-functions-dev

# Estado del namespace
doctl serverless status

# Runtimes admitidos
doctl serverless status --languages

# Listar funciones desplegadas
doctl serverless functions list

# Consultar información de una función
doctl serverless functions get default/consultar-catalogos

# Obtener URL pública de una función
doctl serverless functions get default/consultar-catalogos --url

# Consultar metadatos del proyecto SIN desplegar
doctl serverless get-metadata . \
  --include default/consultar-catalogos \
  --env ".config/.env"

# Ayuda y opciones disponibles
doctl serverless deploy --help
doctl serverless functions --help
```

Los comandos de consulta y sus argumentos deben verificarse contra `--help` si cambia la versión de `doctl`.

## 6. Variables de entorno y autenticación

Archivo local `.config/.env` (ejemplo **sin secretos reales**):

```dotenv
BACKEND_API_KEY=valor_secreto
DATABASE_URL=postgresql://usuario:clave@servidor:5432/base
```

- Mantener `.config/.env` fuera de Git (`.gitignore`).
- No imprimir valores de `BACKEND_API_KEY` o `DATABASE_URL` en logs.
- El hecho de que una variable exista en el archivo local no prueba que la función remota la haya recibido correctamente.
- La petición HTTP debe enviar el encabezado o credencial exacta que valida el código de `__main__.py`.
- El mensaje `{"resultado":"ERROR","mensaje":"Acceso no autorizado"}` observado tras el despliegue fue un **problema de invocación/autenticación**, no un error de construcción. Se resolvió posteriormente y la función respondió correctamente.

## 7. Errores que ya encontramos y cómo interpretarlos

### A. `Invalid project configuration file: 'python:3.13' is not a valid runtime value`

Ocurrió durante la validación de `project.yml`, antes de construir. También se observó un rechazo con `python:3.12`, pese a que el namespace anunciaba soporte para ambas versiones.

**Estado:** el flujo de despliegue volvió a avanzar y se desplegó una función en `python:3.13`, pero no quedó demostrada la causa raíz de aquel error de validación. No atribuirlo definitivamente a un bug o a una versión de `doctl` sin evidencia adicional.

**Acción:** confirmar archivo `project.yml`, conexión al namespace, `doctl version`, `doctl serverless status --languages` y el comando exacto ejecutado. Evitar cambiar runtimes a ciegas.

### B. `./build.sh: line 4: virtualenv: command not found` (código 127)

La construcción local ejecutó un script que requería `virtualenv`, herramienta no disponible en ese entorno.

**Solución aplicada al proyecto:** utilizar el procedimiento de construcción remota previamente validado:

```bash
doctl serverless deploy . \
  --include default/consultar-catalogos \
  --env ".config/.env" \
  --remote-build
```

Si el error reaparece en construcción remota, revisar el `build.sh` real y las herramientas disponibles en ese entorno.

### C. `Remote build is requested ... but it appears to have been built locally. Remove derived artifacts first.`

El proyecto conservaba artefactos derivados de una construcción local anterior en `consultar-pacientes`. El despliegue remoto completo intentó procesar también esa función.

**Solución aplicada:** seleccionar solo `consultar-catalogos` mediante `--include`. Para reconstruir remotamente la función afectada, revisar y limpiar sus artefactos derivados antes de desplegarla.

### D. `Successfully installed psycopg...` y advertencia de `pip` como root

Se instalaron `psycopg` y `psycopg-binary` en la construcción remota. La advertencia de `pip` no fue un fallo de despliegue; el resultado incluyó `Deployed functions: consultar-catalogos`.

### E. `Acceso no autorizado`

La función ya estaba desplegada. El error apareció al invocarla y correspondía a la validación de credenciales. Verificar variables remotas, encabezados HTTP y lógica de autenticación; no reconstruir por reflejo.

## 8. Checklist antes de cada despliegue

- [ ] Estoy en la raíz de `pacientes/`.
- [ ] `doctl serverless status` muestra el namespace correcto.
- [ ] `project.yml` declara la función y el runtime previsto.
- [ ] La nueva función tiene `__main__.py`, `requirements.txt` y `build.sh` según corresponda.
- [ ] `.config/.env` contiene las variables necesarias y no está versionado.
- [ ] Utilizo `--include default/<funcion>` para evitar actualizar otras funciones.
- [ ] Utilizo `--remote-build` para mantener el procedimiento validado en esta PoC.
- [ ] La función seleccionada no contiene artefactos locales incompatibles con construcción remota.
- [ ] Tras desplegar, verifico lista, versión, URL y respuesta funcional (por ejemplo, desde Bruno).

## 9. Flujo estándar para incorporar otra Function

1. Crear `packages/default/<nueva-funcion>/` con sus archivos.
2. Añadir una entrada a `project.yml` sin modificar las funciones existentes.
3. Definir dependencias y variables requeridas.
4. Comprobar el namespace y el runtime.
5. Desplegar **solo** la nueva función con `--include`, `--env` y `--remote-build`.
6. Confirmar la nueva versión con `doctl serverless functions list`.
7. Obtener la URL y probar la respuesta HTTP y la autenticación.
8. Registrar el resultado y cualquier particularidad del `build.sh`.

## 10. Referencias oficiales

- [Estructura de proyectos de Functions](https://docs.digitalocean.com/products/functions/how-to/structure-projects/)
- [Configuración de proyectos (`project.yml`)](https://docs.digitalocean.com/products/functions/reference/project-configuration/)
- [Referencia de `doctl serverless deploy`](https://docs.digitalocean.com/reference/doctl/reference/serverless/deploy/)
- [Referencia de `doctl serverless get-metadata`](https://docs.digitalocean.com/reference/doctl/reference/serverless/get-metadata/)

---

**Regla operativa del proyecto:** preferir despliegues selectivos y construcción remota. Un despliegue correcto se considera terminado **solo después** de comprobar que la función está desplegada y responde como se espera.
