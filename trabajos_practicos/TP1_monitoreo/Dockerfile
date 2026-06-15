# Imagen base con Python 3.11 (el TP pide 3.11+)
FROM python:3.11-slim

# Carpeta de trabajo dentro del contenedor
WORKDIR /app

# Instalar dependencias primero (mejor cache: solo se reinstala si cambia requirements)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del proyecto
COPY . .

# Entry point del monitor
CMD ["python3", "src/main.py"]
