"""Master pipeline runner — executes all pipeline steps in order.

Usage:
    python scripts/run_pipeline.py                # Run all
    python scripts/run_pipeline.py --phase 1      # Run only Phase 1
    python scripts/run_pipeline.py --step extract  # Run specific step
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# Step registry: (step_id, module_path, function_name)
STEPS = [
    ("extract",  "src.data.pipeline.extract", "run_extract_all"),
    ("clean",   "src.data.pipeline.clean",   "run_clean_all"),
    ("features", "src.data.pipeline.features", "run_features_all"),
    ("labels",  "src.data.pipeline.labels",   "run_label_all"),
    ("graph",   "src.data.pipeline.graph",    "run_graph_all"),
    ("split",   "src.data.pipeline.split",    "run_split_all"),
    ("prepare", "src.data.pipeline.prepare",  "run_prepare_all"),
]

PHASE_MAP = {
    "1": ["extract"],
    "2": ["clean"],
    "3": ["features"],
    "4": ["labels"],
    "5": ["graph"],
    "6": ["split"],
    "7": ["prepare"],
}


def run_step(step_id: str) -> None:
    """Run a single pipeline step."""
    match = [(s, m, f) for s, m, f in STEPS if s == step_id]
    if not match:
        logger.error(f"Unknown step: {step_id}")
        sys.exit(1)

    _, module_path, func_name = match[0]
    logger.info(f"▶ Running step {step_id} ({module_path}.{func_name})")

    import importlib
    t0 = time.time()
    mod = importlib.import_module(module_path)
    getattr(mod, func_name)()
    elapsed = time.time() - t0
    logger.info(f"✅ Step {step_id} complete ({elapsed:.1f}s)")


def main() -> None:
    import sys
    from pathlib import Path
    # Ensure project root is on sys.path for `src` imports
    project_root = str(Path(__file__).resolve().parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    parser = argparse.ArgumentParser(description="IUU Fishing Detection Pipeline Runner")
    parser.add_argument("--phase", choices=["1","2","3","4","5","6","7"], help="Run only this phase")
    parser.add_argument("--step", help="Run a specific step (extract|clean|features|labels|graph|split|prepare)")
    args = parser.parse_args()

    if args.step:
        run_step(args.step)
    elif args.phase:
        for step_id in PHASE_MAP[args.phase]:
            run_step(step_id)
    else:
        logger.info("🚀 Running full pipeline (Phase 1 → 7)")
        for phase in ["1","2","3","4","5","6","7"]:
            logger.info(f"\n{'='*60}\n  PHASE {phase}\n{'='*60}")
            for step_id in PHASE_MAP[phase]:
                run_step(step_id)
        logger.info("\n🎉 Full pipeline complete!")


if __name__ == "__main__":
    main()
