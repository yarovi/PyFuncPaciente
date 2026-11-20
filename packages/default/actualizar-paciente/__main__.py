

import os

import hmac

import json

import re

from datetime import date



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



CAMPOS_OBLIGATORIOS = {

    "nombres",

    "apellido_paterno",

    "tipo_documento",

    "numero_documento",

    "correo",

    "telefono_movil",

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



CATALOGOS = {

    "tipo_documento": (

        "gitec.tipo_documento_identidad",

        "tipo_documento_id",

    ),

    "estado_civil": (

        "gitec.estado_civil",

        "estado_civil_id",

    ),

    "tipo_sangre": (

        "gitec.tipo_sangre",

        "tipo_sangre_id",

    ),

}



COLUMNAS = {

    campo: campo

    for campo in CAMPOS_PERMITIDOS

    if campo not in CATALOGOS

}



COLUMNAS.update({

    campo: columna

    for campo, (_, columna) in CATALOGOS.items()

})





def responder(status, contenido):

    return {

        "statusCode": status,

        "headers": {

            "Content-Type": "application/json"

        },

        "body": contenido,

    }





def error_validacion(detalles):

    return responder(400, {

        "error": "Bad Request",

        "message": "Datos del paciente invalidos",

        "detalles": detalles,

    })





def leer_cuerpo(args):

    if "__ow_body" in args:

        cuerpo = args["__ow_body"]



        if isinstance(cuerpo, dict):

            return cuerpo



        if isinstance(cuerpo, str):

            return json.loads(cuerpo)



        raise ValueError("El cuerpo debe ser un objeto JSON.")



    return {

        clave: valor

        for clave, valor in args.items()

        if not clave.startswith("__ow_")

        and clave not in ("paciente_id", "http")

    }





def validar_id(valor):

    if isinstance(valor, bool):

        return None



    if isinstance(valor, int):

        return valor if valor > 0 else None



    if isinstance(valor, str):

        valor = valor.strip()



        if re.fullmatch(r"[0-9]+", valor):

            numero = int(valor)

            return numero if 0 < numero <= 9223372036854775807 else None



    return None





def validar_patch(datos):

    if not isinstance(datos, dict):

        return {}, {"body": "Se requiere un objeto JSON."}



    if not datos:

        return {}, {

            "body": "Debe indicar al menos un campo para actualizar."

        }



    errores = {}

    normalizados = {}



    for campo in datos:

        if campo not in CAMPOS_PERMITIDOS:

            errores[campo] = "Campo no permitido."

            continue



        valor = datos[campo]



        if valor is None:

            if campo in CAMPOS_OBLIGATORIOS:

                errores[campo] = "Este campo no admite null."

            else:

                normalizados[campo] = None

            continue



        if not isinstance(valor, str):

            errores[campo] = "Debe ser una cadena de texto."

            continue



        valor = valor.strip()



        if not valor:

            errores[campo] = "No se permiten cadenas vacias."

            continue



        limite = LONGITUDES.get(campo)



        if limite is not None and len(valor) > limite:

            errores[campo] = (

                f"No puede superar {limite} caracteres."

            )

            continue



        if campo in CATALOGOS and len(valor) > 10:

            errores[campo] = "Codigo demasiado largo."

            continue



        if campo == "correo":

            if not re.fullmatch(r"[^@\s]+@[^@\s]+\\.[^@\s]+", valor):

                errores[campo] = "Correo electronico invalido."

                continue



        if campo == "telefono_movil":

            if not re.fullmatch(r"9[0-9]{8}", valor):

                errores[campo] = (

                    "Debe contener 9 digitos y comenzar por 9."

                )

                continue



        if campo == "ubigeo":

            if not re.fullmatch(r"[0-9]{6}", valor):

                errores[campo] = "Debe contener 6 digitos."

                continue



        if campo == "sexo":

            if valor not in ("M", "F", "X"):

                errores[campo] = "Valor de sexo invalido."

                continue



        if campo == "fecha_nacimiento":

            try:

                fecha = date.fromisoformat(valor)



                if fecha.isoformat() != valor:

                    raise ValueError("Formato no canonico")



                if fecha > date.today():

                    errores[campo] = "No puede ser una fecha futura."

                    continue



                normalizados[campo] = fecha

                continue



            except ValueError:

                errores[campo] = "Fecha invalida."

                continue



        normalizados[campo] = valor



    return normalizados, errores





def resolver_catalogo(cursor, campo, codigo):

    if codigo is None:

        return None



    tabla, _ = CATALOGOS[campo]



    cursor.execute(

        f"SELECT id FROM {tabla} WHERE codigo = %s",

        (codigo,),

    )



    registro = cursor.fetchone()



    return registro[0] if registro else None





def main(args):

# 1. Autenticacion interna

    api_key_esperada = os.environ.get("BACKEND_API_KEY")

    headers = args.get("__ow_headers") or {}



    api_key_recibida = next(

        (

            valor

            for clave, valor in headers.items()

            if clave.lower() == "x-backend-api-key"

        ),

        None,

    )



    if (

        not api_key_esperada

        or not isinstance(api_key_recibida, str)

        or not hmac.compare_digest(

            api_key_recibida,

            api_key_esperada,

        )

    ):

        return responder(401, {

            "error": "Unauthorized",

            "message": "Credencial de servicio invalida",

        })



# 2. Metodo HTTP

    metodo = args.get("__ow_method", "").lower()



    if metodo != "patch":

        return responder(405, {

            "error": "Method Not Allowed",

            "message": "Solo se permite PATCH",

        })



# 3. Identificador recibido desde Zuplo

    paciente_id = validar_id(args.get("paciente_id"))



    if paciente_id is None:

        return error_validacion({

            "paciente_id": "Identificador de paciente invalido."

        })



# 4. Lectura y validacion del JSON

    try:

        cuerpo = leer_cuerpo(args)

    except (ValueError, TypeError):

        return responder(400, {

            "error": "Bad Request",

            "message": "El cuerpo JSON es invalido",

        })



    datos, errores = validar_patch(cuerpo)



    if errores:

        return error_validacion(errores)



# 5. Configuracion

    database_url = os.environ.get("DATABASE_URL")



    if not database_url:

        return responder(500, {

            "error": "Internal Server Error",

            "message": "Configuracion de base de datos no disponible",

        })



# 6. Transaccion de actualizacion

    try:

        with psycopg.connect(

            database_url,

            connect_timeout=10,

        ) as conexion:



            with conexion.cursor() as cursor:



# Bloqueamos el registro durante la transaccion

# para evitar actualizaciones simultaneas perdidas.

                cursor.execute(

                    """

                    SELECT

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

                    FROM gitec.pacientes

                    WHERE id = %s

                    FOR UPDATE

                    """,

                    (paciente_id,),

                )



                registro = cursor.fetchone()



                if registro is None:

                    return responder(404, {

                        "error": "Not Found",

                        "message": "El paciente indicado no existe",

                    })



                columnas_actuales = [

                    "nombres",

                    "apellido_paterno",

                    "apellido_materno",

                    "tipo_documento_id",

                    "numero_documento",

                    "correo",

                    "telefono_movil",

                    "fecha_nacimiento",

                    "sexo",

                    "estado_civil_id",

                    "tipo_sangre_id",

                    "direccion",

                    "ubigeo",

                    "ocupacion",

                ]



                actuales = dict(zip(columnas_actuales, registro))

                cambios = {}

                errores_catalogo = {}



# 7. Resolver codigos de catalogo

                for campo, valor in datos.items():

                    columna = COLUMNAS[campo]



                    if campo in CATALOGOS:

                        identificador = resolver_catalogo(

                            cursor,

                            campo,

                            valor,

                        )



                        if valor is not None and identificador is None:

                            errores_catalogo[campo] = (

                                "Codigo de catalogo invalido."

                            )

                            continue



                        valor = identificador



                    if actuales[columna] != valor:

                        cambios[columna] = valor



                if errores_catalogo:

                    return error_validacion(errores_catalogo)



# 8. Recalcular el nombre completo cuando

# cambian nombres o apellidos.

                campos_nombre = {

                    "nombres",

                    "apellido_paterno",

                    "apellido_materno",

                }



                if campos_nombre.intersection(cambios):

                    partes = [

                        cambios.get(

                            campo,

                            actuales[campo],

                        )

                        for campo in (

                            "nombres",

                            "apellido_paterno",

                            "apellido_materno",

                        )

                    ]



                    nombre_completo = " ".join(

                        parte

                        for parte in partes

                        if parte

                    )



                    if len(nombre_completo) > 150:

                        return error_validacion({

                            "nombre": (

                                "El nombre completo supera "

                                "150 caracteres."

                            )

                        })



                    cambios["nombre"] = nombre_completo



# 9. No ejecutar UPDATE si no hay cambios

                if not cambios:

                    return responder(200, {

                        "resultado": "OK",

                        "mensaje": "Paciente sin cambios",

                        "paciente": {

                            "id": paciente_id,

                        },

                    })



# 10. Actualizacion parametrizada

# Las columnas provienen de una lista cerrada.

                asignaciones = ", ".join(

                    f"{columna} = %s"

                    for columna in cambios

                )



                valores = list(cambios.values())

                valores.append(paciente_id)



                cursor.execute(

                    f"""

                    UPDATE gitec.pacientes

                    SET {asignaciones}

                    WHERE id = %s

                    RETURNING id

                    """,

                    valores,

                )



                actualizado = cursor.fetchone()



                if actualizado is None:

                    return responder(404, {

                        "error": "Not Found",

                        "message": "El paciente indicado no existe",

                    })



        return responder(200, {

            "resultado": "OK",

            "mensaje": "Paciente actualizado correctamente",

            "paciente": {

                "id": paciente_id,

            },

        })



    except UniqueViolation:

        return responder(409, {

            "error": "Conflict",

            "message": "El documento ya esta registrado",

        })



    except psycopg.Error as error:

        print(

            "ERROR_POSTGRESQL:",

            type(error).__name__,

            "SQLSTATE:",

            error.sqlstate or "NO_DISPONIBLE",

        )



        return responder(503, {

            "error": "Service Unavailable",

            "message": "No fue posible actualizar el paciente",

        })
