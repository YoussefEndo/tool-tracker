from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Récupère une valeur d'un dictionnaire par sa clé.
    Utilisation dans le template: {{ dict|get_item:key }}
    """
    if dictionary is None:
        return ''
    if key is None:
        return ''
    return dictionary.get(key, '')