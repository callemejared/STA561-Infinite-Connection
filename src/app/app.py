"""Compatibility entrypoint for Streamlit deployment.

The full evaluation dashboard now lives in `Evaluation.py`, but Streamlit Cloud
can continue targeting `src/app/app.py` without any configuration changes.
"""

from Evaluation import *  # noqa: F401,F403
