FROM python:3.12-slim

WORKDIR /app

# Primero solo requirements: si no cambian, Docker reusa la capa con las
# dependencias instaladas y el rebuild es instantáneo.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Forma exec (lista JSON), no shell: así python es el PID 1 del contenedor y
# recibe directo el SIGTERM de `docker compose stop` (clave en la fase 6).
CMD ["python", "src/main.py"]
