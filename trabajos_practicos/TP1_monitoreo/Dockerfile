# Imagen base con Python 3.11 (el TP pide 3.11+)
FROM python:3.11-slim

# Herramientas de sistema para COMPARAR a mano (ps, kill, etc.).
# OJO: procps NO se usa desde el código del monitor (el TP lo prohíbe); solo
# sirve para verificar contra `ps` que nuestro parseo de /proc coincide.
RUN apt-get update && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*

# Carpeta de trabajo dentro del contenedor
WORKDIR /app

# Instalar dependencias primero (mejor cache: solo se reinstala si cambia requirements)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del proyecto
COPY . .

# Entry point del monitor
CMD ["python3", "src/main.py"]
