"""Pipeline runner wrapper for model training.

Called by scripts/run_pipeline.py as Phase 8.
Delegates to scripts/train.py main().
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def run_train_all() -> None:
    """Run model training (Phase 8)."""
    import runpy
    train_script = Path(__file__).resolve().parent.parent.parent / "scripts" / "train.py"
    if not train_script.exists():
        logger.error(f"Training script not found: {train_script}")
        sys.exit(1)
    logger.info("Starting model training...")
    runpy.run_path(str(train_script), run_name="__main__")
    logger.info("Training complete")
