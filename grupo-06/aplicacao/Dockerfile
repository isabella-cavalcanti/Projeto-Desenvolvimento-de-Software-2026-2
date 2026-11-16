FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt psycopg2-binary
COPY autofarma ./autofarma
COPY wsgi.py run.py ./
ENV AUTOFARMA_DEMO=0
EXPOSE 5000
# Um único processo com várias threads: o temporizador roda uma vez só.
CMD ["waitress-serve", "--host=0.0.0.0", "--port=5000", "--threads=8", "wsgi:app"]
