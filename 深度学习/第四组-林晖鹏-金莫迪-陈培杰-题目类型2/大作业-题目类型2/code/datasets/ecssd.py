"""ECSSD dataset loader with optional split-file selection."""

import json
from pathlib import Path

from PIL import Image
from torch.utils.data import Dataset

from datasets.transforms import build_image_transform, build_mask_transform, preprocess_sample


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}
MASK_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp"}
REQUIRED_SPLITS = ("train", "val", "test")


def load_split_file(path) -> dict[str, list[str]]:
    split_path = Path(path)
    data = json.loads(split_path.read_text())
    for split_name in REQUIRED_SPLITS:
        if split_name not in data:
            raise ValueError(f"Missing split '{split_name}' in {split_path}.")
    return data


class ECSSDDataset(Dataset):
    def __init__(self, root, split="train", image_size=256, augment=None, split_file=None, augment_mode="basic"):
        self.root = Path(root)
        self.split = split
        self.image_size = image_size
        self.augment = split == "train" if augment is None else augment
        self.split_file = Path(split_file) if split_file is not None else None
        self.augment_mode = augment_mode
        self.image_transform = build_image_transform(image_size)
        self.mask_transform = build_mask_transform(image_size)

        if split not in REQUIRED_SPLITS:
            raise ValueError(f"Unsupported split '{split}'. Expected one of {REQUIRED_SPLITS}.")

        self.samples = self._scan_samples()
        if not self.samples:
            raise RuntimeError(f"No matched image/mask pairs found in {self.root} for split '{split}'.")

    def _collect_paths(self):
        if self.split_file is None:
            image_dir = self.root / "images" / self.split
            mask_dir = self.root / "masks" / self.split
            if not image_dir.exists() or not mask_dir.exists():
                raise FileNotFoundError(
                    "Expected dataset layout 'root/images/{split}' and 'root/masks/{split}'. "
                    f"Missing: {image_dir} or {mask_dir}"
                )
            image_paths = [path for path in sorted(image_dir.iterdir()) if path.suffix.lower() in IMAGE_SUFFIXES]
            mask_paths = [path for path in sorted(mask_dir.iterdir()) if path.suffix.lower() in MASK_SUFFIXES]
            return image_paths, mask_paths

        image_root = self.root / "images"
        mask_root = self.root / "masks"
        if not image_root.exists() or not mask_root.exists():
            raise FileNotFoundError(
                "Expected dataset layout with 'root/images' and 'root/masks'. "
                f"Missing: {image_root} or {mask_root}"
            )
        image_paths = [path for path in sorted(image_root.rglob("*")) if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES]
        mask_paths = [path for path in sorted(mask_root.rglob("*")) if path.is_file() and path.suffix.lower() in MASK_SUFFIXES]
        return image_paths, mask_paths

    def _scan_samples(self):
        image_paths, mask_paths = self._collect_paths()
        images = {path.stem: path for path in image_paths}
        masks = {path.stem: path for path in mask_paths}

        if self.split_file is None:
            names = sorted(set(images) & set(masks))
        else:
            split_data = load_split_file(self.split_file)
            requested_names = split_data[self.split]
            missing_image_names = [name for name in requested_names if name not in images]
            missing_mask_names = [name for name in requested_names if name not in masks]
            if missing_image_names or missing_mask_names:
                details = []
                if missing_image_names:
                    details.append(f"missing images for: {missing_image_names[:5]}")
                if missing_mask_names:
                    details.append(f"missing masks for: {missing_mask_names[:5]}")
                raise RuntimeError("Split file references missing samples: " + "; ".join(details))
            names = requested_names

        if self.split_file is None and (len(names) != len(images) or len(names) != len(masks)):
            missing_masks = sorted(set(images) - set(masks))
            missing_images = sorted(set(masks) - set(images))
            details = []
            if missing_masks:
                details.append(f"missing masks for: {missing_masks[:5]}")
            if missing_images:
                details.append(f"missing images for: {missing_images[:5]}")
            if details:
                raise RuntimeError("Image/mask mismatch detected: " + "; ".join(details))

        return [(name, images[name], masks[name]) for name in names]

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):
        name, image_path, mask_path = self.samples[index]
        image = Image.open(image_path).convert("RGB")
        mask = Image.open(mask_path).convert("L")
        image, mask = preprocess_sample(
            image,
            mask,
            self.image_size,
            train=self.augment,
            augment_mode=self.augment_mode,
        )
        image = self.image_transform(image)
        mask = self.mask_transform(mask)
        mask = (mask > 0.5).float()
        return image, mask, name
