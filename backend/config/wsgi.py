"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

application = get_wsgi_application()

# The MCP endpoint is a Starlette app, and Django routes to views rather than to other
# ASGI applications, so `/mcp` has no Django route at all. `config/mcp_mount.py`
# dispatches it — and the RFC 9728 document beside it, which config/urls.py leaves to
# the MCP app — before the request reaches Django's handler. That is also what keeps
# session and CSRF middleware off a path that authenticates with its own bearer-token
# verifier and answers JSON.
#
# This wrapping has to happen here: the dispatch is outside Django's request handling,
# so it goes around the WSGI callable, and this module is what constructs it.
# `runserver` resolves WSGI_APPLICATION to this module too, so development and
# production serve MCP by the same path.
if os.environ.get("MCP_ENABLED", "1") != "0":
    from config.mcp_mount import mount

    application = mount(application)
