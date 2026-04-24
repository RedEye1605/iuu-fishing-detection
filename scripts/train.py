"""ST-GAT Training Script for IUU Fishing Detection.

Trains the Spatiotemporal Graph Attention Network on weekly graph snapshots.
Each snapshot is a full-graph forward pass (no batching needed — max ~3,400 nodes).

Usage:
    python scripts/train.py                        # 100 epochs, default config
    python scripts/train.py --epochs 50 --lr 0.001
    python scripts/train.py --baseline mlp         # MLP ablation (no graph)
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import classification_report, confusion_matrix, f1_score

# Ensure project root on path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.models.stgat import STGAT, STGATClassifier, LABEL_NAMES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

MODEL_DIR = Path(PROJECT_ROOT) / "data" / "processed" / "model"


# ============================================================
# Data Loading
# ============================================================

def load_data() -> dict:
    """Load all model-ready data from Phase 7 output."""
    d = MODEL_DIR
    logger.info("Loading model data...")

    node_features = np.load(d / "node_features.npy")
    flag_indices = np.load(d / "vessel_flag_indices.npy")
    class_indices = np.load(d / "vessel_class_indices.npy")
    class_weights = np.load(d / "class_weights.npy")

    snapshots = {}
    for split in ["train", "val", "test"]:
        pkl_path = d / "snapshots" / f"{split}_snapshots.pkl"
        if not pkl_path.exists():
            logger.warning(f"Missing {pkl_path}")
            continue
        import pickle
        with open(pkl_path, "rb") as f:
            data = pickle.load(f)
        snapshots[split] = data

    logger.info(
        f"  Nodes: {node_features.shape}, "
        f"Flags: {flag_indices.shape}, Classes: {class_indices.shape}"
    )
    for split, s in snapshots.items():
        logger.info(f"  {split}: {len(s['order'])} snapshots")

    return {
        "node_features": torch.from_numpy(node_features),
        "flag_indices": torch.from_numpy(flag_indices),
        "class_indices": torch.from_numpy(class_indices),
        "class_weights": torch.from_numpy(class_weights),
        "snapshots": snapshots,
        "num_flags": int(flag_indices.max()) + 1,
        "num_classes": int(class_indices.max()) + 1,
        "continuous_dim": node_features.shape[1],
    }


def prepare_snapshot(data: dict, split: str, week: str, device: torch.device) -> dict:
    """Prepare tensors for a single snapshot.

    Args:
        data: Global data dict from load_data().
        split: Which split (train/val/test).
        week: Snapshot week identifier.
        device: Target device.

    Returns:
        Dict with model-ready tensors.
    """
    snap = data["snapshots"][split]["data"][week]

    vi = snap["vessel_indices"]
    return {
        "x_cont": data["node_features"][vi].to(device),
        "edge_index": torch.from_numpy(snap["edge_index"]).long().to(device),
        "edge_type": torch.from_numpy(snap["edge_type"]).long().to(device),
        "edge_attr": torch.from_numpy(snap["edge_attr"]).float().to(device),
        "flag_idx": data["flag_indices"][vi].to(device),
        "class_idx": data["class_indices"][vi].to(device),
        "labels": torch.from_numpy(snap["labels"]).long().to(device),
    }


# ============================================================
# Training & Evaluation
# ============================================================

def compute_loss(
    logits: torch.Tensor,
    labels: torch.Tensor,
    weights: torch.Tensor,
    label_smoothing: float = 0.1,
) -> torch.Tensor:
    """Weighted cross-entropy with label smoothing."""
    return F.cross_entropy(logits, labels, weight=weights, label_smoothing=label_smoothing)


def train_epoch(
    model: torch.nn.Module,
    data: dict,
    device: torch.device,
    optimizer: torch.optim.Optimizer,
    label_smoothing: float,
    is_baseline: bool = False,
) -> tuple[float, float, int]:
    """Train for one epoch over all training snapshots."""
    model.train()
    total_loss = 0.0
    n_snapshots = 0
    correct = 0
    total = 0

    weeks = data["snapshots"]["train"]["order"]
    weights = data["class_weights"].to(device)

    for week in weeks:
        snap = prepare_snapshot(data, "train", week, device)

        optimizer.zero_grad()
        if is_baseline:
            logits = model(snap["x_cont"])
        else:
            logits = model(
                x_cont=snap["x_cont"],
                edge_index=snap["edge_index"],
                edge_type=snap["edge_type"],
                edge_attr=snap["edge_attr"],
                flag_idx=snap["flag_idx"],
                class_idx=snap["class_idx"],
            )
        loss = compute_loss(logits, snap["labels"], weights, label_smoothing)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()

        total_loss += loss.item() * snap["labels"].size(0)
        correct += (logits.argmax(dim=1) == snap["labels"]).sum().item()
        total += snap["labels"].size(0)
        n_snapshots += 1

    return total_loss / total, correct / total, n_snapshots


@torch.no_grad()
def evaluate(
    model: torch.nn.Module,
    data: dict,
    split: str,
    device: torch.device,
    label_smoothing: float,
    is_baseline: bool = False,
) -> dict:
    """Evaluate model on a split, return metrics dict."""
    model.eval()
    weights = data["class_weights"].to(device)

    all_preds = []
    all_labels = []
    total_loss = 0.0
    total = 0

    weeks = data["snapshots"][split]["order"]
    for week in weeks:
        snap = prepare_snapshot(data, split, week, device)

        if is_baseline:
            logits = model(snap["x_cont"])
        else:
            logits = model(
                x_cont=snap["x_cont"],
                edge_index=snap["edge_index"],
                edge_type=snap["edge_type"],
                edge_attr=snap["edge_attr"],
                flag_idx=snap["flag_idx"],
                class_idx=snap["class_idx"],
            )
        loss = compute_loss(logits, snap["labels"], weights, label_smoothing)

        preds = logits.argmax(dim=1)
        all_preds.append(preds.cpu())
        all_labels.append(snap["labels"].cpu())
        total_loss += loss.item() * snap["labels"].size(0)
        total += snap["labels"].size(0)

    y_true = torch.cat(all_labels).numpy()
    y_pred = torch.cat(all_preds).numpy()
    avg_loss = total_loss / total

    macro_f1 = f1_score(y_true, y_pred, average="macro")
    weighted_f1 = f1_score(y_true, y_pred, average="weighted")

    return {
        "loss": avg_loss,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "y_true": y_true,
        "y_pred": y_pred,
        "n_snapshots": len(weeks),
    }


def print_metrics(split: str, metrics: dict) -> None:
    """Print evaluation metrics for a split."""
    logger.info(
        f"  {split.upper():5s} | loss={metrics['loss']:.4f} | "
        f"macro_F1={metrics['macro_f1']:.4f} | "
        f"weighted_F1={metrics['weighted_f1']:.4f}"
    )


def print_final_report(metrics: dict) -> None:
    """Print detailed classification report and confusion matrix."""
    y_true, y_pred = metrics["y_true"], metrics["y_pred"]

    logger.info("\n" + "=" * 60)
    logger.info("FINAL TEST RESULTS")
    logger.info("=" * 60)

    report = classification_report(y_true, y_pred, target_names=LABEL_NAMES, digits=4)
    logger.info(f"\n{report}")

    cm = confusion_matrix(y_true, y_pred)
    n_classes = len(LABEL_NAMES)
    logger.info("Confusion Matrix:")
    header = "          " + "  ".join(f"{n:>10s}" for n in LABEL_NAMES)
    logger.info(header)
    for i in range(n_classes):
        row = f"{LABEL_NAMES[i]:>10s} " + "  ".join(f"{cm[i, j]:>10d}" for j in range(n_classes))
        logger.info(row)


# ============================================================
# Main
# ============================================================

def set_seed(seed: int = 42) -> None:
    """Set random seeds for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def main() -> None:
    parser = argparse.ArgumentParser(description="Train ST-GAT for IUU fishing detection")
    parser.add_argument("--epochs", type=int, default=100, help="Max training epochs")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--weight-decay", type=float, default=1e-5, help="Weight decay")
    parser.add_argument("--patience", type=int, default=15, help="Early stopping patience")
    parser.add_argument("--hidden-dim", type=int, default=64, help="GNN hidden dimension")
    parser.add_argument("--num-heads", type=int, default=4, help="Attention heads")
    parser.add_argument("--dropout", type=float, default=0.3, help="Dropout rate")
    parser.add_argument("--embed-dim", type=int, default=8, help="Embedding dimension")
    parser.add_argument("--label-smoothing", type=float, default=0.1, help="Label smoothing (epsilon)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--baseline", choices=[None, "mlp"], default=None,
                        help="Run MLP baseline (no graph structure)")
    parser.add_argument("--device", default="cpu",
                        help="Device: cpu/cuda (default: cpu)")
    args = parser.parse_args()

    set_seed(args.seed)

    device = torch.device(args.device)
    logger.info(f"Device: {device}, Seed: {args.seed}")

    data = load_data()

    # Build model
    if args.baseline == "mlp":
        logger.info("Building MLP baseline (no graph structure)...")
        model = STGATClassifier(
            input_dim=data["continuous_dim"],
            hidden_dim=args.hidden_dim * 2,
            output_dim=4,
            dropout=args.dropout,
        ).to(device)
    else:
        logger.info("Building ST-GAT...")
        model = STGAT(
            continuous_dim=data["continuous_dim"],
            num_flags=data["num_flags"],
            num_vessel_classes=data["num_classes"],
            embed_dim=args.embed_dim,
            hidden_dim=args.hidden_dim,
            num_heads=args.num_heads,
            dropout=args.dropout,
            label_smoothing=args.label_smoothing,
        ).to(device)

    total_params = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"Parameters: {total_params:,} total, {trainable:,} trainable")

    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.lr, weight_decay=args.weight_decay,
    )
    # T_max+1 so LR never fully decays to zero
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs + 1)

    best_macro_f1 = 0.0
    patience_counter = 0
    log = []
    is_bl = args.baseline is not None
    last_epoch = 0

    logger.info(f"\n{'='*60}")
    logger.info(f"Training: {args.epochs} epochs, patience={args.patience}")
    if args.baseline:
        logger.info(f"Mode: {args.baseline.upper()} baseline")
    logger.info(f"{'='*60}\n")

    t0 = time.time()
    for epoch in range(1, args.epochs + 1):
        last_epoch = epoch
        epoch_t0 = time.time()

        train_loss, train_acc, n_snaps = train_epoch(
            model, data, device, optimizer, args.label_smoothing, is_bl,
        )
        scheduler.step()

        val_metrics = evaluate(model, data, "val", device, args.label_smoothing, is_bl)

        lr = optimizer.param_groups[0]["lr"]
        entry = {
            "epoch": epoch,
            "train_loss": round(train_loss, 4),
            "train_acc": round(train_acc, 4),
            "val_loss": round(val_metrics["loss"], 4),
            "val_macro_f1": round(val_metrics["macro_f1"], 4),
            "val_weighted_f1": round(val_metrics["weighted_f1"], 4),
            "lr": lr,
        }
        log.append(entry)

        elapsed = time.time() - epoch_t0
        logger.info(
            f"Epoch {epoch:>3d}/{args.epochs} ({elapsed:.1f}s) | "
            f"train_loss={train_loss:.4f} acc={train_acc:.3f} | "
            f"val_loss={val_metrics['loss']:.4f} "
            f"macro_F1={val_metrics['macro_f1']:.4f} "
            f"weighted_F1={val_metrics['weighted_f1']:.4f} | "
            f"lr={lr:.2e}"
        )

        if val_metrics["macro_f1"] >= best_macro_f1:
            best_macro_f1 = val_metrics["macro_f1"]
            patience_counter = 0
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "macro_f1": best_macro_f1,
                "args": vars(args),
            }, MODEL_DIR / "best_model.pt")
            logger.info(f"  -> Saved best model (macro_F1={best_macro_f1:.4f})")
        else:
            patience_counter += 1
            if patience_counter >= args.patience:
                logger.info(f"  -> Early stopping at epoch {epoch} (patience={args.patience})")
                break

    total_time = time.time() - t0
    logger.info(f"\nTraining complete in {total_time/60:.1f} minutes ({last_epoch} epochs)")

    # Load best model for test evaluation
    logger.info("Loading best model for test evaluation...")
    ckpt = torch.load(MODEL_DIR / "best_model.pt", map_location=device, weights_only=False)
    model.load_state_dict(ckpt["model_state_dict"])
    logger.info(f"Best model from epoch {ckpt['epoch']} (macro_F1={ckpt['macro_f1']:.4f})")

    # Final evaluation on all splits
    logger.info("\n--- Final Evaluation ---")
    for split in ["train", "val", "test"]:
        metrics = evaluate(model, data, split, device, args.label_smoothing, is_bl)
        print_metrics(split, metrics)

    # Detailed test report
    test_metrics = evaluate(model, data, "test", device, args.label_smoothing, is_bl)
    print_final_report(test_metrics)

    # Save training log
    log_path = MODEL_DIR / "training_log.json"
    with open(log_path, "w") as f:
        json.dump(log, f, indent=2)
    logger.info(f"\nTraining log saved to {log_path}")

    summary = {
        "best_epoch": ckpt["epoch"],
        "best_val_macro_f1": round(ckpt["macro_f1"], 4),
        "test_macro_f1": round(test_metrics["macro_f1"], 4),
        "test_weighted_f1": round(test_metrics["weighted_f1"], 4),
        "test_loss": round(test_metrics["loss"], 4),
        "total_epochs": last_epoch,
        "total_time_minutes": round(total_time / 60, 1),
        "model_params": total_params,
        "seed": args.seed,
        "config": vars(args),
    }
    summary_path = MODEL_DIR / "test_results.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info(f"Test results saved to {summary_path}")


if __name__ == "__main__":
    main()
