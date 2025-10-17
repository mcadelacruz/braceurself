# custom template filter to get a value from a dictionary

from django import template

register = template.Library()

# allows getting a dictionary value by key in templates
@register.filter
def dict_get(d, key):
    return d.get(key)