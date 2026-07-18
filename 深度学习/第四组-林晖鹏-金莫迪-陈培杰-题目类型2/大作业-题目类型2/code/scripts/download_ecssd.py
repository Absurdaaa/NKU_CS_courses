"""Download and prepare the ECSSD dataset."""

import argparse
import random
import shutil
from pathlib import Path
from urllib.request import urlretrieve
import zipfile


DEFAULT_IMAGE_URL = "https://www.cse.cuhk.edu.hk/leojia/projects/hsaliency/data/ECSSD/images.zip"
DEFAULT_MASK_URL = "https://www.cse.cuhk.edu.hk/leojia/projects/hsaliency/data/ECSSD/ground_truth_mask.zip"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}
MASK_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp"}


def ensure_layout(root: Path) -> None:
    for kind in ("images", "masks"):
        for split in ("train", "test"):
            (root / kind / split).mkdir(parents=True, exist_ok=True)


def clear_split_contents(root: Path) -> None:
    # 每次重新划分前先清空旧的 train/test 内容，避免历史文件残留到错误的 split 中。
    for kind in ("images", "masks"):
        for split in ("train", "test"):
            split_dir = root / kind / split
            if not split_dir.exists():
                continue
            for item in split_dir.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()


def download_file(url: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        return output_path
    urlretrieve(url, output_path)
    return output_path


def extract_zip(zip_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(output_dir)
    return output_dir


def collect_files(root: Path, suffixes):
    return [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes]


def copy_pairs(image_paths, mask_paths, output_root: Path, train_count: int, seed: int) -> None:
    images_by_stem = {path.stem: path for path in image_paths}
    masks_by_stem = {path.stem: path for path in mask_paths}
    names = sorted(set(images_by_stem) & set(masks_by_stem))

    if not names:
        raise RuntimeError("No matched image/mask pairs found in the extracted dataset.")

    # 按固定随机种子划分 700/300，保证组内复现实验时划分一致。
    random.Random(seed).shuffle(names)
    train_names = set(names[: min(train_count, len(names))])

    ensure_layout(output_root)
    clear_split_contents(output_root)
    for name in names:
        split = "train" if name in train_names else "test"
        image_dst = output_root / "images" / split / f"{name}{images_by_stem[name].suffix.lower()}"
        mask_dst = output_root / "masks" / split / f"{name}.png"
        shutil.copy2(images_by_stem[name], image_dst)
        shutil.copy2(masks_by_stem[name], mask_dst)


def prepare_dataset(raw_root: Path, output_root: Path, train_count: int, seed: int) -> None:
    image_paths = collect_files(raw_root / "images", IMAGE_SUFFIXES)
    mask_paths = collect_files(raw_root / "masks", MASK_SUFFIXES)
    copy_pairs(image_paths, mask_paths, output_root, train_count=train_count, seed=seed)


def parse_args():
    parser = argparse.ArgumentParser(description="Download and prepare the ECSSD dataset.")
    parser.add_argument("--output-root", type=Path, default=Path("data/ECSSD"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/raw/ECSSD"))
    parser.add_argument("--image-url", default=DEFAULT_IMAGE_URL)
    parser.add_argument("--mask-url", default=DEFAULT_MASK_URL)
    parser.add_argument("--train-count", type=int, default=700)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Use already downloaded zip files under cache-dir.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    image_zip = args.cache_dir / "images.zip"
    mask_zip = args.cache_dir / "ground_truth_mask.zip"
    raw_images_dir = args.cache_dir / "images"
    raw_masks_dir = args.cache_dir / "masks"

    if not args.skip_download:
        download_file(args.image_url, image_zip)
        download_file(args.mask_url, mask_zip)

    # 先解压到缓存目录，再统一整理成训练代码使用的固定结构。
    extract_zip(image_zip, raw_images_dir)
    extract_zip(mask_zip, raw_masks_dir)
    prepare_dataset(args.cache_dir, args.output_root, train_count=args.train_count, seed=args.seed)
    print(f"Prepared ECSSD dataset at: {args.output_root}")


if __name__ == "__main__":
    main()
