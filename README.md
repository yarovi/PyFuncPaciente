# PyFuncPaciente

Función serverless en Python para consultar pacientes almacenados en PostgreSQL
(Supabase) y devolverlos como JSON. Está configurada para ejecutarse en
DigitalOcean Functions y puede recibir solicitudes a través de Zuplo.

## Contexto

El proyecto contiene el paquete `default` y la función web
`consultar-pacientes`. La función consulta `gitec.pacientes` y relaciona los
tipos de documento, estados civiles y tipos de sangre. La respuesta incluye el
total de registros y la lista de pacientes.

Antes de consultar la base de datos, valida el encabezado
`x-backend-api-key` con una clave configurada en el entorno. La dependencia de
PostgreSQL es `psycopg[binary]`.

## Requisitos

- Python 3.13.
- [doctl](https://docs.digitalocean.com/reference/doctl/) instalado.
- Acceso a un namespace de DigitalOcean Functions y un token con permisos
  `function:admin`.
- Una base de datos PostgreSQL accesible desde la función.

## Configuración

Desde la raíz del repositorio, crea `.config/.env` (este archivo está excluido
de Git) con las variables de runtime:

```dotenv
BACKEND_API_KEY=una-clave-secreta
DATABASE_URL=postgresql://usuario:contraseña@host:5432/base_de_datos
```

Usa valores reales de tu entorno y no compartas ni subas este archivo al
repositorio. La URL debe permitir conexiones desde DigitalOcean y acceder al
esquema `gitec` y a las tablas consultadas.

Configura doctl e instala el soporte de Serverless si aún no está instalado:

```bash
doctl auth init
doctl serverless install
doctl serverless connect
doctl serverless status
```

`doctl auth init` solicita el token de DigitalOcean. `doctl serverless connect`
permite seleccionar el namespace al que se desplegará la función.

## Deploy

Ejecuta desde la raíz del repositorio. La compilación remota prepara las
dependencias para el entorno de ejecución de DigitalOcean:

```bash
doctl serverless deploy . --env ".config/.env" --remote-build
```

## Verificación

Comprueba que la función aparece en el namespace:

```bash
doctl serverless functions list default
```

Para invocarla, crea un archivo temporal con la cabecera esperada. Reemplaza el
valor de ejemplo por el mismo `BACKEND_API_KEY` configurado en `.config/.env`:

```bash
cat > /tmp/consultar-pacientes-request.json <<'JSON'
{
  "__ow_headers": {
    "x-backend-api-key": "REEMPLAZAR_CON_BACKEND_API_KEY"
  }
}
JSON

doctl serverless functions invoke default/consultar-pacientes \
  --param-file /tmp/consultar-pacientes-request.json \
  --full
```

Una ejecución correcta devuelve `statusCode: 200` y un cuerpo con
`resultado: "OK"`, `total` y `pacientes`. La invocación requiere que la función
tenga configuradas ambas variables de entorno y que la base de datos esté
disponible.

### Respuestas de error esperadas

- `401`: falta la clave de backend o no coincide.
- `500`: no está configurada `DATABASE_URL`.
- `503`: no se pudo consultar PostgreSQL.

La respuesta correcta incluye datos personales de pacientes. Maneja la salida
de la invocación como información sensible y no la copies en tickets, logs
públicos ni canales no autorizados.

## Archivos principales

- `project.yml`: paquete, runtime Python 3.13, despliegue web y variables de
  entorno.
- `packages/default/consultar-pacientes/__main__.py`: autenticación, consulta y
  formato de respuesta.
- `packages/default/consultar-pacientes/requirements.txt`: dependencias de la
  función.
- `packages/default/consultar-pacientes/build.sh`: preparación del entorno de
  dependencias para el paquete.
- `test_conexion.py`: comprobación local de conexión a PostgreSQL usando
  `.config/.env`. Imprime registros de pacientes; úsalo solo en un entorno
  controlado.
