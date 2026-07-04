"""Packaged ``string.Template`` sources for an instance's generated files.

These ``*.tmpl`` files are package data rendered by :mod:`mad_cli.core.templates`.
Literal ``$`` in the templates is escaped as ``$$``; ``${name}`` placeholders are
the only render-time substitutions.
"""
