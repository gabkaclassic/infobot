from PIL import Image
import os


def prepare_image(image_path):
    resized_image = resize_image(image_path)
    compressed_image = compress_image(resized_image)

    return compressed_image


def get_modified_filepath(image_path: str, prefix: str):
    filename = image_path[image_path.rindex('/') + 1:]
    image_path = image_path[:image_path.rindex('/') + 1]
    modified_path = f"{image_path}{prefix}_{filename}"

    return modified_path


def get_image_path(filename: str):
    return os.path.join('images', f'{filename}.jpg')


def compress_image(image_path, target_size_kb=550):
    compressed_path = image_path

    while os.path.getsize(compressed_path) > target_size_kb * 1024:
        with Image.open(compressed_path) as img:
            compressed_path = get_modified_filepath(image_path, 'compressed')
            img.save(compressed_path, format='JPEG', quality=10)
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

        resized_path = get_modified_filepath(image_path, 'resized')

        img.save(resized_path, quality=50)
        return resized_path
