# Image de base Python
FROM python:3.11-slim

# Variables d'environnement
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DJANGO_SETTINGS_MODULE config.settings

# Définir le répertoire de travail
WORKDIR /app

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    gcc \
    libmariadb-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copier les fichiers de dépendances
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code source
COPY . .

# Créer les dossiers pour les fichiers statiques
RUN mkdir -p /app/static /app/media

# Exposer le port
EXPOSE 8000

# Commande de démarrage
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "config.wsgi:application"]