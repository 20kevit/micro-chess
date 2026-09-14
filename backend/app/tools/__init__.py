"""Offline/operations tooling (never imported by the application runtime).

Packages under ``app.tools`` are standalone ingestion/import helpers run
explicitly by an operator from ``backend/`` (e.g. ``python -m
app.tools.lichess_puzzles.cli --help``). They are NOT part of the
FastAPI request flow: ``app.main`` never imports them, no lifespan hook
runs them, and the normal API works without them.
"""
