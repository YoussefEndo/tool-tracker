#!/bin/bash

echo "🚀 Démarrage de l'application..."

# Démarrer les conteneurs
docker-compose up -d --build

# Attendre que la base de données soit prête
echo "⏳ Attente de la base de données..."
sleep 10

# Appliquer les migrations
echo "📊 Application des migrations..."
docker-compose exec web python manage.py migrate

# Collecter les fichiers statiques
echo "📁 Collecte des fichiers statiques..."
docker-compose exec web python manage.py collectstatic --noinput

echo "✅ Application démarrée avec succès !"
echo "🌐 Accédez à l'application : http://localhost"
echo "🔧 Admin : http://localhost/admin"