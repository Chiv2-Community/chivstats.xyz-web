from django import template

register = template.Library()

@register.filter(name='format_with_commas')
def format_with_commas(value):
    return "{:,}".format(value)
