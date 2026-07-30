from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.db.models import Q
from django.core.paginator import Paginator

# Vérifier si l'utilisateur est un Supervisor
def is_supervisor(user):
    return user.is_superuser or user.groups.filter(name='Supervisor').exists()


@login_required
@user_passes_test(is_supervisor)
def user_list(request):
    """Liste des utilisateurs avec recherche et filtres"""
    
    users = User.objects.all().order_by('-date_joined')
    
    # Recherche
    search = request.GET.get('search', '')
    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(users, 10)
    page_number = request.GET.get('page', 1)
    users_page = paginator.get_page(page_number)
    
    context = {
        'users': users_page,
        'search': search,
        'total_users': User.objects.count(),
        'supervisors': User.objects.filter(is_superuser=True).count(),
        'active_users': User.objects.filter(is_active=True).count(),
    }
    
    return render(request, 'accounts/user_list.html', context)


@login_required
@user_passes_test(is_supervisor)
def user_create(request):
    """Créer un nouvel utilisateur"""
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        is_superuser = request.POST.get('is_superuser') == 'on'
        is_active = request.POST.get('is_active') == 'on'
        
        # Validation
        if not username or not email or not password:
            messages.error(request, "Tous les champs obligatoires doivent être remplis")
            return render(request, 'accounts/user_create.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, "Ce nom d'utilisateur existe déjà")
            return render(request, 'accounts/user_create.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, "Cet email est déjà utilisé")
            return render(request, 'accounts/user_create.html')
        
        if password != password2:
            messages.error(request, "Les mots de passe ne correspondent pas")
            return render(request, 'accounts/user_create.html')
        
        if len(password) < 8:
            messages.error(request, "Le mot de passe doit contenir au moins 8 caractères")
            return render(request, 'accounts/user_create.html')
        
        # Créer l'utilisateur
        user = User.objects.create(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_superuser=is_superuser,
            is_active=is_active,
            password=make_password(password)
        )
        
        # Ajouter au groupe Supervisor si demandé
        if is_superuser:
            group, _ = Group.objects.get_or_create(name='Supervisor')
            user.groups.add(group)
        
        messages.success(request, f"✅ Utilisateur {username} créé avec succès !")
        return redirect('accounts:user_list')
    
    return render(request, 'accounts/user_create.html')


@login_required
@user_passes_test(is_supervisor)
def user_edit(request, user_id):
    """Modifier un utilisateur existant"""
    
    user = get_object_or_404(User, id=user_id)
    
    # Empêcher la modification de son propre compte (sécurité)
    if user.id == request.user.id:
        messages.error(request, "❌ Vous ne pouvez pas modifier votre propre compte")
        return redirect('accounts:user_list')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        is_superuser = request.POST.get('is_superuser') == 'on'
        is_active = request.POST.get('is_active') == 'on'
        password = request.POST.get('password', '')
        
        # Validation
        if not username or not email:
            messages.error(request, "Le nom d'utilisateur et l'email sont obligatoires")
            return render(request, 'accounts/user_edit.html', {'user': user})
        
        if User.objects.filter(username=username).exclude(id=user.id).exists():
            messages.error(request, "Ce nom d'utilisateur existe déjà")
            return render(request, 'accounts/user_edit.html', {'user': user})
        
        if User.objects.filter(email=email).exclude(id=user.id).exists():
            messages.error(request, "Cet email est déjà utilisé")
            return render(request, 'accounts/user_edit.html', {'user': user})
        
        # Mettre à jour
        user.username = username
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.is_superuser = is_superuser
        user.is_active = is_active
        
        # Mettre à jour le mot de passe si fourni
        if password:
            if len(password) < 8:
                messages.error(request, "Le mot de passe doit contenir au moins 8 caractères")
                return render(request, 'accounts/user_edit.html', {'user': user})
            user.password = make_password(password)
        
        user.save()
        
        # Mettre à jour le groupe Supervisor
        group, _ = Group.objects.get_or_create(name='Supervisor')
        if is_superuser:
            user.groups.add(group)
        else:
            user.groups.remove(group)
        
        messages.success(request, f"✅ Utilisateur {username} modifié avec succès !")
        return redirect('accounts:user_list')
    
    return render(request, 'accounts/user_edit.html', {'user': user})


@login_required
@user_passes_test(is_supervisor)
def user_delete(request, user_id):
    """Supprimer un utilisateur (réservé aux Supervisors)"""
    
    user = get_object_or_404(User, id=user_id)
    
    # Empêcher la suppression de son propre compte
    if user.id == request.user.id:
        messages.error(request, "❌ Vous ne pouvez pas supprimer votre propre compte")
        return redirect('accounts:user_list')
    
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f"🗑️ Utilisateur {username} supprimé avec succès !")
        return redirect('accounts:user_list')
    
    return render(request, 'accounts/user_delete.html', {'user': user})


@login_required
@user_passes_test(is_supervisor)
def user_toggle_active(request, user_id):
    """Activer/Désactiver un utilisateur"""
    
    user = get_object_or_404(User, id=user_id)
    
    if user.id == request.user.id:
        messages.error(request, "❌ Vous ne pouvez pas modifier votre propre compte")
        return redirect('accounts:user_list')
    
    user.is_active = not user.is_active
    user.save()
    
    status = "activé" if user.is_active else "désactivé"
    messages.success(request, f"✅ Utilisateur {user.username} {status} avec succès !")
    return redirect('accounts:user_list')