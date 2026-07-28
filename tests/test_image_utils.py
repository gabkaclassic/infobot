import os

import pytest
from PIL import Image

from utils.image_utils import (
    compress_image,
    get_image_path,
    get_modified_filepath,
    prepare_image,
    resize_image,
)


def write_image(path, size, color=(120, 90, 200)):
    Image.new("RGB", size, color).save(path, format="JPEG", quality=95)
    return str(path)


def write_noise_image(path, size):
    """Однотонная картинка сжимается почти до нуля, поэтому для проверки
    ограничения размера нужен шум."""
    width, height = size
    image = Image.frombytes("RGB", size, os.urandom(width * height * 3))
    image.save(path, format="JPEG", quality=95)
    return str(path)


@pytest.fixture
def small_image(tmp_path):
    return write_image(tmp_path / "picture.jpg", (100, 80))


@pytest.fixture
def oversized_image(tmp_path):
    return write_noise_image(tmp_path / "big.jpg", (1500, 1500))


class TestPaths:
    def test_adds_prefix_to_filename(self):
        assert (
            get_modified_filepath("images/picture.jpg", "resized")
            == "images/resized_picture.jpg"
        )

    def test_handles_path_without_directory(self):
        assert get_modified_filepath("picture.jpg", "compressed") == "compressed_picture.jpg"

    def test_get_image_path_appends_extension(self):
        assert get_image_path("teacher").endswith(os.path.join("images", "teacher.jpg"))


class TestCompressImage:
    def test_small_file_returned_unchanged(self, small_image):
        assert compress_image(small_image) == small_image

    def test_large_file_is_compressed(self, oversized_image):
        assert os.path.getsize(oversized_image) > 550 * 1024

        result = compress_image(oversized_image)

        assert result != oversized_image
        assert os.path.basename(result) == "compressed_big.jpg"
        assert os.path.getsize(result) <= 550 * 1024

    def test_terminates_when_target_unreachable(self, small_image):
        """Регрессия: цикл без ограничения зависал на файле, который не ужимается
        до целевого размера, и блокировал весь процесс бота."""
        result = compress_image(small_image, target_size_kb=0, max_attempts=3)

        assert os.path.exists(result)
        assert os.path.getsize(result) > 0

    def test_source_file_is_not_destroyed(self, oversized_image):
        original_size = os.path.getsize(oversized_image)

        compress_image(oversized_image)

        assert os.path.getsize(oversized_image) == original_size

    def test_result_is_readable_image(self, oversized_image):
        result = compress_image(oversized_image)

        with Image.open(result) as img:
            assert img.size == (1500, 1500)


class TestResizeImage:
    def test_image_within_limits_returned_unchanged(self, small_image):
        assert resize_image(small_image) == small_image

    def test_oversized_image_is_resized(self, tmp_path):
        source = write_noise_image(tmp_path / "wide.jpg", (6000, 100))

        result = resize_image(source)

        assert os.path.basename(result) == "resized_wide.jpg"
        with Image.open(result) as img:
            assert img.width == 5000


class TestPrepareImage:
    def test_returns_existing_path_for_normal_image(self, small_image):
        assert prepare_image(small_image) == small_image

    def test_pipeline_resizes_then_compresses(self, tmp_path):
        source = write_noise_image(tmp_path / "wide.jpg", (6000, 100))

        result = prepare_image(source)

        assert os.path.getsize(result) <= 550 * 1024
        with Image.open(result) as img:
            assert img.width == 5000
