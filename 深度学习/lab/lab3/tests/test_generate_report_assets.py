import unittest
from pathlib import Path
import tempfile

from scripts import generate_report_assets


class GenerateReportAssetsTest(unittest.TestCase):
    def test_curve_figure_contains_train_and_val_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            epoch_metrics = Path(tmp_dir) / "epoch_metrics.csv"
            epoch_metrics.write_text(
                "\n".join(
                    [
                        "epoch,train_loss,train_acc,train_exact_match,val_loss,val_acc,val_exact_match",
                        "1,4.0,0.2,0.0,4.5,0.1,0.0",
                        "2,3.0,0.4,0.1,3.8,0.3,0.05",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            rows = [
                {"model": "seq2seq_rnn", "epoch_metrics_path": str(epoch_metrics)},
                {"model": "seq2seq_attn", "epoch_metrics_path": str(epoch_metrics)},
                {"model": "seq2seq_luong", "epoch_metrics_path": str(epoch_metrics)},
            ]

            figure = generate_report_assets.build_best_run_curve_figure(rows)
            axes = figure.axes
            titles = [axis.get_title() for axis in axes]

            self.assertEqual(len(axes), 6)
            self.assertEqual(
                titles,
                [
                    "Train Loss",
                    "Train Token Accuracy",
                    "Train Exact Match",
                    "Validation Loss",
                    "Validation Token Accuracy",
                    "Validation Exact Match",
                ],
            )


if __name__ == "__main__":
    unittest.main()
