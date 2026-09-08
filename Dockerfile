# Imagen del backend de Chaski Pe para Dokploy.
FROM python:3.12-slim

# Python en contenedor: sin .pyc y con logs sin buffer (si no, Dokploy no
# muestra nada en la pestana Logs hasta que el buffer se llena).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Las dependencias van antes que el codigo: mientras requirements.txt no
# cambie, Docker reutiliza esta capa y el despliegue es mucho mas rapido.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Windows no guarda el bit de ejecucion en git, y los finales de linea CRLF
# impiden que el shell encuentre el interprete: se corrigen ambas cosas aqui.
RUN sed -i 's/\r$//' start.sh && chmod +x start.sh

# No correr como root: si alguien escapa del proceso, no es administrador.
RUN useradd --create-home --uid 1000 chaskipe \
    && chown -R chaskipe:chaskipe /app
USER chaskipe

EXPOSE 8000

CMD ["./start.sh"]
