# Backend image: Django (REST API + admin + HTML frontend) served by gunicorn.
#
# Build context je KOŘEN repozitáře (potřebuje requirements.txt, prj/ i fixtures/).
# Stavíme ho z deploy/docker-compose.yml jako službu `web`. Není určen pro lokální
# vývoj — tam dál stačí `./manage.py runserver`.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Závislosti zvlášť, ať se vrstva cachuje, dokud se requirements.txt nemění.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Aplikační kód + ukázková data (loaddata je čte při ručním seedu, viz playbooks/seed.yml).
COPY prj/ ./prj/
COPY fixtures/ ./fixtures/
COPY deploy/web-entrypoint.sh /usr/local/bin/web-entrypoint.sh
RUN chmod +x /usr/local/bin/web-entrypoint.sh

# manage.py i wsgi modul žijí v prj/.
WORKDIR /app/prj

EXPOSE 8000

# Entrypoint pustí migrace + collectstatic a pak spustí CMD (gunicorn).
ENTRYPOINT ["/usr/local/bin/web-entrypoint.sh"]
CMD ["gunicorn", "prj.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
