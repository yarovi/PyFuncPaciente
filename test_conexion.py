
import os
from pathlib import Path

import psycopg


def cargar_variables():
    archivo = Path(".config/.env")

    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()

        if not linea or linea.startswith("#"):
            continue

        nombre, separador, valor = linea.partition("=")

        if separador:
            os.environ[nombre.strip()] = valor.strip()


def main():
    cargar_variables()

    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        print("ERROR: DATABASE_URL no configurada")
        return

    try:
        with psycopg.connect(
            database_url,
            connect_timeout=10
        ) as conexion:

            with conexion.cursor() as cursor:
                cursor.execute("""
                    SELECT id, nombre, estado
                    FROM gitec.pacientes
                    ORDER BY id
                """)

                pacientes = cursor.fetchall()

                print("CONEXION_SUPABASE: OK")
                print(f"TOTAL_PACIENTES: {len(pacientes)}")

                for paciente in pacientes:
                    print(paciente)

    
    except psycopg.OperationalError as error:
        import re

        mensaje = str(error)

        # Ocultar posibles credenciales o cadenas de conexión
        mensaje = re.sub(
            r"(?i)postgres(?:ql)?://[^\s]+",
            "[DATABASE_URL_OCULTA]",
            mensaje
        )

        mensaje = re.sub(
            r"(?i)(password|passwd|secret)\s*[=:]\s*\S+",
            r"\1=[OCULTO]",
            mensaje
        )

        print("CONEXION_SUPABASE: ERROR")
        print("TIPO_ERROR: OperationalError")
        print("SQLSTATE:", error.sqlstate or "NO_DISPONIBLE")
        print("DIAGNOSTICO:", mensaje)



if __name__ == "__main__":
    main()
