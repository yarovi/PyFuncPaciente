
import json
import os
import logging

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body, ensure_ascii=False)
    }


def consultar_catalogo(conn, tabla):
    tablas_permitidas = {
        "tipo_documento_identidad",
        "estado_civil",
        "tipo_sangre"
    }

    if tabla not in tablas_permitidas:
        raise ValueError("Catálogo no permitido")

    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            f"""
            SELECT id, codigo, descripcion
            FROM gitec.{tabla}
            ORDER BY id
            """
        )
        return cursor.fetchall()


def main(args):
    api_key = os.getenv("BACKEND_API_KEY")
    received_key = (
        args.get("__ow_headers", {}).get("x-backend-api-key")
        or args.get("x-backend-api-key")
    )

    if not api_key or received_key != api_key:
        return response(401, {
            "resultado": "ERROR",
            "mensaje": "Acceso no autorizado"
        })

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        logger.error("DATABASE_URL no configurada")
        return response(503, {
            "resultado": "ERROR",
            "mensaje": "Servicio no disponible"
        })

    try:
        with psycopg.connect(
            database_url,
            connect_timeout=10
        ) as conn:

            catalogos = {
                "tipos_documento": consultar_catalogo(
                    conn, "tipo_documento_identidad"
                ),
                "estados_civiles": consultar_catalogo(
                    conn, "estado_civil"
                ),
                "tipos_sangre": consultar_catalogo(
                    conn, "tipo_sangre"
                )
            }

        return response(200, {
            "resultado": "OK",
            "catalogos": catalogos
        })

    except psycopg.Error:
        logger.exception("Error consultando catálogos")
        return response(503, {
            "resultado": "ERROR",
            "mensaje": "No fue posible consultar los catálogos"
        })
