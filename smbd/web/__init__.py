"""Local web app for SMBD (`smbd serve`).

A thin FastAPI wrapper over the engine. Runs on your machine; any API keys are
**bring-your-own**, passed per request from the browser and **never stored or
logged**. Requires the ``web`` extra: ``pip install -e ".[web]"``.
"""
