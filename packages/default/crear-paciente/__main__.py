
import os
import hmac
import json
import re
from datetime import date
from decimal import Decimal

import psycopg
from psycopg.errors import UniqueViolation


CAMPOS_PERMITIDOS = {
    "nombres",
    "apellido_paterno",
    "apellido_materno",
    "tipo_documento",
    "numero_documento",
    "fecha_nacimiento",
    "sexo",
    "correo",
    "telefono_movil",
    "direccion",
    "ubigeo",
    "ocupacion",
    "estado_civil",
    "tipo_sangre",
}

LONGITUDES = {
    "nombres": 150,
    "apellido_paterno": 100,
    "apellido_materno": 100,
    "numero_documento": 20,
    "correo": 254,
    "telefono_movil": 9,
    "ubigeo": 6,
    "ocupacion": 120,
}


def responder(status, contenido):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": contenido
    }


def leer_cuerpo(args):
    if "__ow_body" in args:
        cuerpo = args["__ow_body"]

        if isinstance(cuerpo, dict):
            return cuerpo

        if isinstance(cuerpo, str):
            return json.loads(cuerpo)

        raise ValueError("El cuerpo debe ser un objeto JSON.")

    # Compatibilidad con parámetros JSON entregados
    # directamente por el runtime de DigitalOcean.
    return {
        clave: valor
        for clave, valor in args.items()
        if not clave.startswith("__ow_")
    }


def validar_datos(datos):
    errores = {}
    normalizados = {}

    if not isinstance(datos, dict):
        return {}, {"body": "Se requiere un objeto JSON."}

    for campo in CAMPOS_PERMITIDOS:
        valor = datos.get(campo)

        if valor is not None and not isinstance(valor, str):
            errores[campo] = "Debe ser una cadena de texto."
            continue

        normalizados[campo] = (
            valor.strip() if isinstance(valor, str) else ""
        )

    for campo in (
        "nombres",
        "apellido_paterno",
        "tipo_documento",
        "numero_documento",
        "correo",
        "telefono_movil",
    ):
        if campo not in errores and not normalizados.get(campo):
            errores[campo] = "Este campo es obligatorio."

    for campo, limite in LONGITUDES.items():
        valor = normalizados.get(campo, "")
        if valor and len(valor) > limite:
            errores[campo] = (
                f"No puede superar {limite} caracteres."
            )

    for campo in (
        "tipo_documento",
        "estado_civil",
        "tipo_sangre",
    ):
        valor = normalizados.get(campo, "")
        if valor and len(valor) > 10:
            errores[campo] = "Código demasiado largo."

    correo = normalizados.get("correo", "")
    if correo and not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+", correo
    ):
        errores["correo"] = "Correo electrónico inválido."

    telefono = normalizados.get("telefono_movil", "")
    if telefono and not re.fullmatch(r"9[0-9]{8}", telefono):
        errores["telefono_movil"] = (
            "Debe contener 9 dígitos y comenzar por 9."
        )

    ubigeo = normalizados.get("ubigeo", "")
    if ubigeo and not re.fullmatch(r"[0-9]{6}", ubigeo):
        errores["ubigeo"] = "Debe contener 6 dígitos."

    sexo = normalizados.get("sexo", "")
    if sexo and sexo not in ("M", "F", "X"):
        errores["sexo"] = "Valor de sexo inválido."

    fecha_texto = normalizados.get("fecha_nacimiento", "")
    if fecha_texto:
        try:
            fecha = date.fromisoformat(fecha_texto)
            if fecha > date.today():
                errores["fecha_nacimiento"] = (
                    "No puede ser una fecha futura."
                )
            else:
                normalizados["fecha_nacimiento"] = fecha
        except ValueError:
            errores["fecha_nacimiento"] = "Fecha inválida."

    partes_nombre = [
        normalizados.get(campo, "")
        for campo in (
            "nombres",
            "apellido_paterno",
            "apellido_materno",
        )
    ]

    nombre_completo = " ".join(
        parte for parte in partes_nombre if parte
    )

    if len(nombre_completo) > 150:
        errores["nombre"] = (
            "El nombre completo supera 150 caracteres."
        )

    normalizados["nombre"] = nombre_completo

    return normalizados, errores


def resolver_catalogo(cursor, tabla, codigo):
    if not codigo:
        return None

    # Los nombres de tabla provienen exclusivamente
    # de constantes definidas en este código.
    tablas = {
        "documento": "gitec.tipo_documento_identidad",
        "estado_civil": "gitec.estado_civil",
        "tipo_sangre": "gitec.tipo_sangre",
    }

    cursor.execute(
        f"SELECT id FROM {tablas[tabla]} WHERE codigo = %s",
        (codigo,)
    )

    registro = cursor.fetchone()
    return registro[0] if registro else None


def opcional(valor):
    return valor if valor != "" else None


def main(args):
    # 1. Autenticación interna
    api_key_esperada = os.environ.get("BACKEND_API_KEY")
    headers = args.get("__ow_headers") or {}

    api_key_recibida = next(
        (
            valor
            for clave, valor in headers.items()
            if clave.lower() == "x-backend-api-key"
        ),
        None
    )

    if (
        not api_key_esperada
        or not isinstance(api_key_recibida, str)
        or not hmac.compare_digest(
            api_key_recibida,
            api_key_esperada
        )
    ):
        return responder(401, {
            "error": "Unauthorized",
            "message": "Credencial de servicio inválida"
        })

    # 2. Método HTTP
    metodo = args.get("__ow_method", "").lower()

    if metodo != "post":
        return responder(405, {
            "error": "Method Not Allowed",
            "message": "Solo se permite POST"
        })

    # 3. Lectura y validación
    try:
        datos = leer_cuerpo(args)
    except (ValueError, TypeError):
        return responder(400, {
            "error": "Bad Request",
            "message": "El cuerpo JSON es inválido"
        })

    datos, errores = validar_datos(datos)

    if errores:
        return responder(400, {
            "error": "Bad Request",
            "message": "Datos del paciente inválidos",
            "detalles": errores
        })

    # 4. Configuración
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        print("DATABASE_URL: NO_CONFIGURADA")
        return responder(500, {
            "error": "Internal Server Error",
            "message": "Configuración de base de datos no disponible"
        })

    # 5. Transacción de registro
    try:
        with psycopg.connect(
            database_url,
            connect_timeout=10
        ) as conexion:
            with conexion.cursor() as cursor:
                catalogos = {}

                for campo, tabla in (
                    ("tipo_documento", "documento"),
                    ("estado_civil", "estado_civil"),
                    ("tipo_sangre", "tipo_sangre"),
                ):
                    codigo = datos[campo]
                    identificador = resolver_catalogo(
                        cursor, tabla, codigo
                    )

                    if codigo and identificador is None:
                        return responder(400, {
                            "error": "Bad Request",
                            "message": (
                                f"El catálogo {campo} "
                                "contiene un código inválido"
                            )
                        })

                    catalogos[campo] = identificador

                cursor.execute("""
                    INSERT INTO gitec.pacientes (
                        nombre,
                        estado,
                        nombres,
                        apellido_paterno,
                        apellido_materno,
                        tipo_documento_id,
                        numero_documento,
                        correo,
                        telefono_movil,
                        fecha_nacimiento,
                        sexo,
                        estado_civil_id,
                        tipo_sangre_id,
                        direccion,
                        ubigeo,
                        ocupacion
                    )
                    VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    RETURNING id
                """, (
                    datos["nombre"],
                    "ACTIVO",
                    datos["nombres"],
                    datos["apellido_paterno"],
                    opcional(datos["apellido_materno"]),
                    catalogos["tipo_documento"],
                    datos["numero_documento"],
                    datos["correo"],
                    datos["telefono_movil"],
                    opcional(datos["fecha_nacimiento"]),
                    opcional(datos["sexo"]),
                    catalogos["estado_civil"],
                    catalogos["tipo_sangre"],
                    opcional(datos["direccion"]),
                    opcional(datos["ubigeo"]),
                    opcional(datos["ocupacion"]),
                ))

                paciente_id = cursor.fetchone()[0]

        return responder(201, {
            "resultado": "OK",
            "mensaje": "Paciente registrado correctamente",
            "paciente": {
                "id": paciente_id,
                "estado": "ACTIVO"
            }
        })

    except UniqueViolation:
        return responder(409, {
            "error": "Conflict",
            "message": "El documento ya está registrado"
        })

    except psycopg.Error as error:
        print(
            "ERROR_POSTGRESQL:",
            type(error).__name__,
            "SQLSTATE:",
            error.sqlstate or "NO_DISPONIBLE"
        )

        return responder(503, {
            "error": "Service Unavailable",
            "message": "No fue posible registrar el paciente"
        })
