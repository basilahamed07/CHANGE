"""M15b — WorkspaceMiddleware: binds each authenticated request to that user's
workspace (their own Database + directories + AI state). Testing mode and
unauthenticated requests pass through untouched; the auth guard handles
rejection and per-user AI state is resolved lazily by ai_state_for().
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)


class WorkspaceMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, workspace_manager):
        super().__init__(app)
        self.manager = workspace_manager

    async def dispatch(self, request: Request, call_next):
        user = getattr(request.state, "user", None)
        if user is not None:
            ws = await self.manager.get_or_create(user)
            request.state.workspace = ws
            request.state.db = ws.db
            # M15c: bill this request's AI calls to THIS user's DB. Without it
            # every user's spend landed in the admin workspace's cost meter.
            try:
                from app import ai_usage
                ai_usage.set_request_sink(ws.db.record_ai_usage)
            except Exception:
                logger.exception("per-user cost-meter sink failed to bind")
            try:
                ai = await request.app.state.ai_state_for(request)
                # Attribute-style access object for routers that read
                # ai_state_for via request.state._ai (kept for future use);
                # tailoring/queue call ai_state_for() directly.
                request.state._evidence_store = ai.get("evidence_store")
                request.state._evidence_checker = ai.get("evidence_checker")
            except Exception:
                logger.exception("per-user AI state resolution failed — "
                                 "falling back to app defaults")
        return await call_next(request)
