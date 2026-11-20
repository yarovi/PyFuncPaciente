
import os
import hmac
import re

import psycopg


def responder(status, contenido):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": contenido
    }


def validar_id(valor):
    if isinstance(valor, bool):
        return None

    if isinstance(valor, int):
        return valor if 0 < valor <= 9223372036854775807 else None

    if isinstance(valor, str):
        valor = valor.strip()

        if re.fullmatch(r"[0-9]+", valor):
            numero = int(valor)

            if 0 < numero <= 9223372036854775807:
                return numero

    return None


def main(args):
    # 1. Autenticacion interna Zuplo -> DigitalOcean
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
            "message": "Credencial de servicio invalida"
        })

    # 2. Validar metodo HTTP
    metodo = args.get("__ow_method", "").lower()

    if metodo != "get":
        return responder(405, {
            "error": "Method Not Allowed",
            "message": "Solo se permite GET"
        })

    # 3. Validar identificador del paciente
    paciente_id = validar_id(args.get("paciente_id"))

    if paciente_id is None:
        return responder(400, {
            "error": "Bad Request",
            "message": "Identificador de paciente invalido"
        })

    # 4. Configuracion de base de datos
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        print("DATABASE_URL: NO_CONFIGURADA")

        return responder(500, {
            "error": "Internal Server Error",
            "message": "Configuracion de base de datos no disponible"
        })

    # 5. Consultar paciente individual
    try:
        with psycopg.connect(
            database_url,
            connect_timeout=10
        ) as conexion:

            with conexion.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        p.id,
                        p.nombre,
                        p.nombres,
                        p.apellido_paterno,
                        p.apellido_materno,
                        p.estado,
                        p.numero_documento,
                        td.codigo AS tipo_documento,
                        p.correo,
                        p.telefono_movil,
                        p.fecha_nacimiento,
                        p.sexo,
                        p.donador_organos,
                        ec.codigo AS estado_civil,
                        ts.codigo AS tipo_sangre,
                        p.direccion,
                        p.ubigeo,
                        p.ocupacion,
                        p.creado_en,
                        p.modificado_en
                    FROM gitec.pacientes p
                    LEFT JOIN gitec.tipo_documento_identidad td
                        ON td.id = p.tipo_documento_id
                    LEFT JOIN gitec.estado_civil ec
                        ON ec.id = p.estado_civil_id
                    LEFT JOIN gitec.tipo_sangre ts
                        ON ts.id = p.tipo_sangre_id
                    WHERE p.id = %s
                """, (paciente_id,))

                registro = cursor.fetchone()

        # 6. Paciente inexistente
        if registro is None:
            return responder(404, {
                "error": "Not Found",
                "message": "El paciente indicado no existe"
            })

        # 7. Construir respuesta
        paciente = {
            "id": registro[0],
            "nombre": registro[1],
            "nombres": registro[2],
            "apellido_paterno": registro[3],
            "apellido_materno": registro[4],
            "estado": registro[5],
            "numero_documento": registro[6],
            "tipo_documento": registro[7],
            "correo": registro[8],
            "telefono_movil": registro[9],
            "fecha_nacimiento": (
                registro[10].isoformat()
                if registro[10] is not None else None
            ),
            "sexo": registro[11],
            "donador_organos": registro[12],
            "estado_civil": registro[13],
            "tipo_sangre": registro[14],
            "direccion": registro[15],
            "ubigeo": registro[16],
            "ocupacion": registro[17],
            "creado_en": (
                registro[18].isoformat()
                if registro[18] is not None else None
            ),
            "modificado_en": (
                registro[19].isoformat()
                if registro[19] is not None else None
            )
        }

        return responder(200, {
            "resultado": "OK",
            "paciente": paciente
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
            "message": "No fue posible consultar el paciente"
        })
