"""Application services shared by every front end (desktop app, command line, agent tools).

They sit between the processing library (organize, wbpp, pipeline, comet, ...) and a user interface, return plain
JSON-friendly data and never import a GUI toolkit:
    jobs     serial job queue with progress events and cancellation (one PixInsight at a time)
    targets  what is on disk: targets, their status, previews and finished images
    recipes  editable recipe parameters and the user's per-target overrides
"""
