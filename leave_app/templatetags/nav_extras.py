from django import template

register = template.Library()

@register.filter
def has_group(user, group_name):
    if user.is_anonymous:
        return False
    return user.groups.filter(name=group_name).exists()