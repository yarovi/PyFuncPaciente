#!/usr/bin/env python3
"""Codifica una contraseña para usarla en el componente password de una URL.

No almacena la contraseña ni realiza conexiones de red.
"""

from getpass import getpass
from urllib.parse import quote


def main() -> None:
    password = getpass("Contraseña a codificar para URL: ")
    if not password:
        print("No se ingresó ninguna contraseña.")
        return

    encoded = quote(password, safe="")
    print("\nContraseña codificada para URL:")
    print(encoded)
    print("\nTrata este resultado como un secreto: es reversible y no debe compartirse.")


if __name__ == "__main__":
    main()
