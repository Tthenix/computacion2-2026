#!/usr/bin/env python3
"""Mini-shell con redirección."""
import os
import sys

def parsear_linea(linea):
    """
    Parsea una línea de comando.
    Retorna (comando, args, archivo_salida, archivo_entrada, modo_append)
    """
    partes = linea.split()
    if not partes:
        return None, [], None, None, False
        
    comando = partes[0]
    args = []
    archivo_salida = None
    archivo_entrada = None
    modo_append = False

    i = 1
    while i < len(partes):
        if partes[i] == ">":
            if i + 1 < len(partes):
                archivo_salida = partes[i + 1]
                modo_append = False
                i += 2
            else:
                print("Error: falta archivo de salida")
                return None, [], None, None, False
        elif partes[i] == ">>":
            if i + 1 < len(partes):
                archivo_salida = partes[i + 1]
                modo_append = True
                i += 2
            else:
                print("Error: falta archivo de salida")
                return None, [], None, None, False
        elif partes[i] == "<":
            if i + 1 < len(partes):
                archivo_entrada = partes[i + 1]
                i += 2
            else:
                print("Error: falta archivo de entrada")
                return None, [], None, None, False
        else:
            args.append(partes[i])
            i += 1

    return comando, args, archivo_salida, archivo_entrada, modo_append

def ejecutar(comando, args, archivo_salida=None, archivo_entrada=None, append=False):
    """Ejecuta un comando con redirección opcional."""
    try:
        pid = os.fork()
    except OSError as e:
        print(f"Error al crear proceso: {e}")
        return

    if pid == 0:
        # 1. Configurar entrada
        if archivo_entrada:
            try:
                fd_in = os.open(archivo_entrada, os.O_RDONLY)
                os.dup2(fd_in, 0)
                os.close(fd_in)
            except OSError as e:
                print(f"Error al abrir entrada '{archivo_entrada}': {e}")
                os._exit(1)

        # 2. Configurar salida
        if archivo_salida:
            try:
                flags = os.O_CREAT | os.O_WRONLY
                if append:
                    flags |= os.O_APPEND
                else:
                    flags |= os.O_TRUNC
                
                fd_out = os.open(archivo_salida, flags, 0o644)
                os.dup2(fd_out, 1)
                os.close(fd_out)
            except OSError as e:
                print(f"Error al abrir salida '{archivo_salida}': {e}")
                os._exit(1)

        # 3. Ejecutar
        try:
            os.execvp(comando, [comando] + args)
        except OSError as e:
            print(f"Error al ejecutar '{comando}': {e}", file=sys.stderr)
            os._exit(127)
    else:
        # PADRE: Esperar al comando
        _, status = os.wait()
        return os.WEXITSTATUS(status)

def main():
    print("Mini-Shell Iniciado (exit para salir)")
    while True:
        try:
            linea = input("minish$ ").strip()
        except EOFError:
            print("\nChau!")
            break

        if not linea:
            continue
        if linea == "exit":
            break

        comando, args, salida, entrada, append = parsear_linea(linea)
        if comando:
            ejecutar(comando, args, salida, entrada, append)

if __name__ == "__main__":
    main()
