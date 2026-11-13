
import os
import hmac
import psycopg


def responder(status, contenido):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": contenido
    }


def main(args):
    # 1. Autenticación interna Zuplo → DigitalOcean
    api_key_esperada = os.environ.get("BACKEND_API_KEY")
    api_key_recibida = args.get("__ow_headers", {}).get(
        "x-backend-api-key"
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

    # 2. Consultar Supabase PostgreSQL
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        print("DATABASE_URL: NO_CONFIGURADA")
        return responder(500, {
            "error": "Internal Server Error",
            "message": "Configuración de base de datos no disponible"
        })

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
                        p.fecha_nacimiento,
                        p.sexo,
                        p.donador_organos,
                        ec.descripcion AS estado_civil,
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
                    ORDER BY p.id
                """)

                registros = cursor.fetchall()

        pacientes = [
            {
                "id": registro[0],
                "nombre": registro[1],
                "nombres": registro[2],
                "apellido_paterno": registro[3],
                "apellido_materno": registro[4],
                "estado": registro[5],
                "numero_documento": registro[6],
                "tipo_documento": registro[7],
                "correo": registro[8],
                "fecha_nacimiento": (
                    registro[9].isoformat()
                    if registro[9] is not None else None
                ),
                "sexo": registro[10],
                "donador_organos": registro[11],
                "estado_civil": registro[12],
                "tipo_sangre": registro[13],
                "direccion": registro[14],
                "ubigeo": registro[15],
                "ocupacion": registro[16],
                "creado_en": (
                    registro[17].isoformat()
                    if registro[17] is not None else None
                ),
                "modificado_en": (
                    registro[18].isoformat()
                    if registro[18] is not None else None
                )
                
            }
            for registro in registros
        ]

        return responder(200, {
            "resultado": "OK",
            "total": len(pacientes),
            "pacientes": pacientes
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
            "message": "No fue posible consultar los pacientes"
        })
