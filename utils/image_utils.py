from PIL import Image
import os
from dotenv import load_dotenv
from config import env_str
from logger_config import logger

load_dotenv()

IMAGES_PATH = env_str("IMAGES_PATH", "./images")


def prepare_image(image_path):
    resized_image = resize_image(image_path)
    compressed_image = compress_image(resized_image)

    return compressed_image


def get_modified_filepath(image_path: str, prefix: str):
    directory, filename = os.path.split(image_path)

    return os.path.join(directory, f"{prefix}_{filename}")


def get_image_path(filename: str):
    return os.path.join(IMAGES_PATH, f"{filename}.jpg")


def compress_image(image_path, target_size_kb=550, quality=10, max_attempts=5):
    target_size = target_size_kb * 1024
    compressed_path = image_path
    attempts = 0

    # Число попыток ограничено: файл, который не ужимается до целевого размера,
    # иначе крутил бы цикл бесконечно и вешал процесс бота.
    while os.path.getsize(compressed_path) > target_size and attempts < max_attempts:
        with Image.open(compressed_path) as img:
            img.load()
            frame = img.convert("RGB")

        compressed_path = get_modified_filepath(image_path, "compressed")
        frame.save(compressed_path, format="JPEG", quality=quality)
        attempts += 1

    if os.path.getsize(compressed_path) > target_size:
        logger.warning(
            f"Image {image_path} is still {os.path.getsize(compressed_path)} bytes "
            f"after {max_attempts} compression attempts"
        )

    return compressed_path


def resize_image(image_path):
    min_size = 10
    max_size = 5000

    with Image.open(image_path) as img:
        img_width = img.width
        img_height = img.height

        if min_size <= img_width <= max_size and min_size <= img_height <= max_size:
            return image_path

        img_width = min(max(min_size, img_width), max_size)
        img_height = min(max(min_size, img_height), max_size)
        img = img.resize((img_width, img_height), Image.LANCZOS)

        resized_path = get_modified_filepath(image_path, "resized")

        img.save(resized_path, quality=50)
        return resized_path
