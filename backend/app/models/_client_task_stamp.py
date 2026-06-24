"""Auto-stamp ``client_task_id`` (P0-2) on UserGeneration / PendingProviderTask.

The frontend mints a correlation id per generation and sends it as the
``X-Client-Task-Id`` header. The ``capture_client_task_id`` dependency (see
app/api/deps.py) stashes it on the request's DB session ``info`` dict. These
``before_insert`` listeners then copy it onto every UserGeneration and
PendingProviderTask inserted during that request — so we cover all ~29 model
construction sites across tools.py / generation.py without threading a param
through each endpoint.

Reading from ``session.info`` (a plain dict on the Session object) rather than
a ContextVar is deliberate: it survives the async→greenlet flush boundary and
the StreamingResponse generator, both of which make ContextVars unreliable.

No-op outside an HTTP request (worker/seed sessions have no info key) and when
the target already carries an explicit id (the reclaim worker sets it directly
from the PendingProviderTask it is materialising).
"""
from sqlalchemy import event
from sqlalchemy.orm import object_session

from app.models.user_generation import UserGeneration
from app.models.pending_provider_task import PendingProviderTask


def _stamp_client_task_id(mapper, connection, target):
    if getattr(target, "client_task_id", None):
        return
    sess = object_session(target)
    if sess is None:
        return
    ctid = sess.info.get("client_task_id")
    if ctid:
        target.client_task_id = ctid


for _model in (UserGeneration, PendingProviderTask):
    if not event.contains(_model, "before_insert", _stamp_client_task_id):
        event.listen(_model, "before_insert", _stamp_client_task_id)
