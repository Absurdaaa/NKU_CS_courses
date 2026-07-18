import argparse
import os

import torch

from TrainAndTest import (
    N_LETTERS,
    gen_load_category_lines,
    gen_collect_hidden_states,
    gen_split_category_lines,
    sample_char_rnn_group,
    train_char_rnn_generator,
)
from Plot import compute_perplexity, plot_loss_curve, plot_tsne_clusters
from RNN import CharRNNGenerator

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_DIR = os.path.join(BASE_DIR, 'data', 'names')


def run_char_rnn_generation(args):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f'Using {device}')

    category_lines, all_categories = gen_load_category_lines(args.data_dir)
    train_category_lines, val_category_lines = gen_split_category_lines(
        category_lines,
        val_ratio=args.val_ratio,
    )
    n_categories = len(all_categories)

    rnn = CharRNNGenerator(
        input_size=N_LETTERS,
        hidden_size=args.hidden_size,
        output_size=N_LETTERS,
        category_size=n_categories,
    ).to(device)

    train_losses, val_losses = train_char_rnn_generator(
        rnn=rnn,
        category_lines=train_category_lines,
        all_categories=all_categories,
        device=device,
        n_iters=args.iters,
        print_every=args.print_every,
        plot_every=args.plot_every,
        learning_rate=args.learning_rate,
        val_category_lines=val_category_lines,
        val_samples=args.val_samples,
    )

    results_dir = os.path.join(BASE_DIR, 'results')
    if val_losses:
        compute_perplexity(val_losses[-1], results_dir=results_dir, filename='metrics.txt')
    plot_loss_curve(train_losses, val_losses, save_path=os.path.join(results_dir, 'loss_curve.png'))

    hidden_states, tsne_labels = gen_collect_hidden_states(
        rnn,
        val_category_lines,
        all_categories,
        device,
        max_per_category=args.tsne_max_per_category,
        seed=args.tsne_seed,
    )
    if tsne_labels:
        plot_tsne_clusters(
            hidden_states,
            tsne_labels,
            save_path=os.path.join(results_dir, 'tsne_clusters.png'),
            perplexity=args.tsne_perplexity,
        )

    if args.sample_category:
        sample_categories = [args.sample_category]
    else:
        sample_categories = [c for c in ('Russian', 'German', 'Spanish', 'Chinese') if c in all_categories]
        if not sample_categories:
            sample_categories = all_categories[:4]

    for category in sample_categories:
        outputs = sample_char_rnn_group(
            rnn,
            category,
            all_categories,
            start_letters=args.start_letters,
            max_length=args.max_length,
            device=device,
        )
        print(f'[{category}]')
        for name in outputs:
            print(name)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Character-level RNN name generation')
    parser.add_argument('--data-dir', default=DEFAULT_DATA_DIR)
    parser.add_argument('--iters', type=int, default=100000)
    parser.add_argument('--hidden-size', type=int, default=128)
    parser.add_argument('--learning-rate', type=float, default=0.0005)
    parser.add_argument('--print-every', type=int, default=5000)
    parser.add_argument('--plot-every', type=int, default=500)
    parser.add_argument('--val-ratio', type=float, default=0.1)
    parser.add_argument('--val-samples', type=int, default=200)
    parser.add_argument('--tsne-max-per-category', type=int, default=100)
    parser.add_argument('--tsne-perplexity', type=int, default=30)
    parser.add_argument('--tsne-seed', type=int, default=42)
    parser.add_argument('--start-letters', default='ABC')
    parser.add_argument('--max-length', type=int, default=20)
    parser.add_argument('--sample-category', default='')

    args = parser.parse_args()
    args.sample_category = args.sample_category.strip() or None
    run_char_rnn_generation(args)
