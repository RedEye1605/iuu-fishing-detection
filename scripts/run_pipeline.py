"""Master pipeline runner — executes all Phase 1-3 steps in order.

Usage:
    python scripts/run_pipeline.py                # Run all
    python scripts/run_pipeline.py --phase 1      # Run only Phase 1
    python scripts/run_pipeline.py --phase 2      # Run only Phase 2
    python scripts/run_pipeline.py --phase 3      # Run only Phase 3
    python scripts/run_pipeline.py --step 1.1     # Run specific step
"""

from __future__ import annotations

import argparse
import importlib
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# Step registry: (step_id, module_path, function_name)
STEPS = [
    ("1.1", "src.data.loaders", "run_step_1_1"),
    ("1.2", "src.data.loaders_sar_effort", "run_step_1_2"),
    ("1.3", "src.data.loaders_aux", "run_step_1_3"),
    ("1.4", "src.data.loaders_aux", "run_step_1_4"),
    ("1.5", "src.data.loaders_aux", "run_step_1_5"),
    ("2.1", "src.data.step_2_1_dedup", "run_step_2_1"),
    ("2.2", "src.data.step_2_2_clean", "run_step_2_2_to_2_6"),
    ("2.7", "src.data.step_2_7_clean_rest", None),  # runs on __main__
    ("3.1", "src.data.step_3_1_vessel_features", "run_step_3_1"),
    ("3.4", "src.data.step_3_4_behavioral", "run_step_3_4"),
    ("3.5", "src.data.step_3_5_enrichment", "run_step_3_5"),
]

PHASE_MAP = {"1": ["1.1","1.2","1.3","1.4","1.5"],
             "2": ["2.1","2.2","2.7"],
             "3": ["3.1","3.4","3.5"]}


def run_step(step_id: str):
    """Run a single pipeline step."""
    match = [(s, m, f) for s, m, f in STEPS if s == step_id]
    if not match:
        logger.error(f"Unknown step: {step_id}")
        sys.exit(1)

    _, module_path, func_name = match[0]
    logger.info(f"▶ Running step {step_id} ({module_path}.{func_name or '__main__'})")

    t0 = time.time()
    mod = importlib.import_module(module_path)

    if func_name:
        getattr(mod, func_name)()
    else:
        # Run the module's main block logic directly
        from src.data.step_2_7_clean_rest import clean_sar_effort, clean_zenodo
        clean_sar_effort()
        clean_zenodo()

    elapsed = time.time() - t0
    logger.info(f"✅ Step {step_id} complete ({elapsed:.1f}s)")


def main():
    parser = argparse.ArgumentParser(description="IUU Fishing Detection Pipeline Runner")
    parser.add_argument("--phase", choices=["1","2","3"], help="Run only this phase")
    parser.add_argument("--step", help="Run a specific step (e.g. 2.1)")
    args = parser.parse_args()

    if args.step:
        run_step(args.step)
    elif args.phase:
        for step_id in PHASE_MAP[args.phase]:
            run_step(step_id)
    else:
        logger.info("🚀 Running full pipeline (Phase 1 → 2 → 3)")
        for phase in ["1","2","3"]:
            logger.info(f"\n{'='*60}\n  PHASE {phase}\n{'='*60}")
            for step_id in PHASE_MAP[phase]:
                run_step(step_id)
        logger.info("\n🎉 Full pipeline complete!")


if __name__ == "__main__":
    main()
