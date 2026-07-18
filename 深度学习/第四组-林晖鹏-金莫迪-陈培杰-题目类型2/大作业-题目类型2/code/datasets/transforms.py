"""Image and mask preprocessing for the rebuilt basic framework."""

import random

from PIL import Image, ImageEnhance, ImageOps
from torchvision import transforms
from torchvision.transforms import functional as TF


def _pad_to_square(image, mask):
    width, height = image.size
    size = max(width, height)
    pad_w = size - width
    pad_h = size - height
    padding = (
        pad_w // 2,
        pad_h // 2,
        pad_w - pad_w // 2,
        pad_h - pad_h // 2,
    )
    image = ImageOps.expand(image, border=padding, fill=0)
    mask = ImageOps.expand(mask, border=padding, fill=0)
    return image, mask


def _random_crop_flip_light(image, mask):
    width, height = image.size
    rand_h = random.randint(0, max(height // 12, 0))
    rand_w = random.randint(0, max(width // 12, 0))
    offset_h = 0 if rand_h == 0 else random.randint(0, rand_h)
    offset_w = 0 if rand_w == 0 else random.randint(0, rand_w)
    crop_box = (offset_w, offset_h, width + offset_w - rand_w, height + offset_h - rand_h)
    image = image.crop(crop_box)
    mask = mask.crop(crop_box)
    if random.random() < 0.5:
        image = TF.hflip(image)
        mask = TF.hflip(mask)
    return image, mask


def _random_rotate_light(image, mask):
    angle = random.randint(-10, 10)
    image = image.rotate(angle, resample=Image.BILINEAR)
    mask = mask.rotate(angle, resample=Image.NEAREST)
    return image, mask


def _random_light_light(image):
    contrast = 0.8 + 0.4 * random.random()
    image = ImageEnhance.Contrast(image).enhance(contrast)
    brightness = 0.9 + 0.2 * random.random()
    return ImageEnhance.Brightness(image).enhance(brightness)


def preprocess_sample(image, mask, image_size, train=False, augment_mode="basic"):
    if train:
        image, mask = _random_crop_flip_light(image, mask)
        if augment_mode == "full":
            image, mask = _random_rotate_light(image, mask)
            image = _random_light_light(image)
        elif augment_mode != "basic":
            raise ValueError(f"Unknown augment_mode: {augment_mode}")
    image, mask = _pad_to_square(image, mask)
    image = image.resize((image_size, image_size), Image.BILINEAR)
    mask = mask.resize((image_size, image_size), Image.NEAREST)
    return image, mask


def build_image_transform(_image_size):
    return transforms.Compose([transforms.ToTensor()])


def build_mask_transform(_image_size):
    return transforms.Compose([transforms.ToTensor()])
