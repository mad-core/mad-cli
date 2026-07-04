"""User-facing presentation layer (rich console + prompts).

This package never talks to ``subprocess`` or the filesystem directly — all such
work goes through ``mad_cli.core`` (see CONTRACTS.md, layering rule).
"""
