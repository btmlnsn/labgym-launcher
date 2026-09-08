import struct
import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from labgym_launcher.app_icon import (
    APP_NAME,
    WINDOWS_APP_USER_MODEL_ID,
    get_frame_icon_path,
    packaged_icon_paths,
    set_windows_app_user_model_id,
    setup_application_icons,
)

ALPHA_MIN = 8
MIN_SIDE_PAD = 0.08
MAX_SIDE_PAD = 0.12
MIN_FILL = 0.78
MAX_FILL = 0.84


def _png_size(path: Path):
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError("%s is not a PNG" % path)
    return struct.unpack(">II", data[16:24])


def _ico_sizes(path: Path):
    data = path.read_bytes()
    count = struct.unpack_from("<H", data, 4)[0]
    sizes = []
    for index in range(count):
        width = data[6 + index * 16]
        height = data[7 + index * 16]
        sizes.append((256 if width == 0 else width, 256 if height == 0 else height))
    return sizes


def _visible_geometry(image, alpha_min: int = ALPHA_MIN):
    rgba = image.convert("RGBA")
    width, height = rgba.size
    mask = rgba.getchannel("A").point(
        lambda value, threshold=alpha_min: 255 if value >= threshold else 0
    )
    bbox = mask.getbbox()
    if bbox is None:
        raise AssertionError("icon artwork is fully transparent")
    left, top, right, bottom = bbox
    pad_left = left
    pad_top = top
    pad_right = width - right
    pad_bottom = height - bottom
    visible_w = right - left
    visible_h = bottom - top
    return {
        "canvas": (width, height),
        "bbox": bbox,
        "padding": (pad_left, pad_top, pad_right, pad_bottom),
        "min_side_pad": min(pad_left, pad_top, pad_right, pad_bottom) / width,
        "fill_w": visible_w / width,
        "fill_h": visible_h / height,
        "fill_max": max(visible_w / width, visible_h / height),
        "corners": (
            rgba.getpixel((0, 0)),
            rgba.getpixel((width - 1, 0)),
            rgba.getpixel((0, height - 1)),
            rgba.getpixel((width - 1, height - 1)),
        ),
    }


def _assert_macos_geometry(test_case: unittest.TestCase, image, label: str) -> None:
    geo = _visible_geometry(image)
    test_case.assertGreaterEqual(
        geo["min_side_pad"],
        MIN_SIDE_PAD,
        "%s min side pad %s" % (label, geo),
    )
    test_case.assertLessEqual(
        geo["min_side_pad"],
        MAX_SIDE_PAD,
        "%s min side pad %s" % (label, geo),
    )
    test_case.assertGreaterEqual(
        geo["fill_max"],
        MIN_FILL,
        "%s fill %s" % (label, geo),
    )
    test_case.assertLessEqual(
        geo["fill_max"],
        MAX_FILL,
        "%s fill %s" % (label, geo),
    )
    for corner in geo["corners"]:
        test_case.assertEqual(corner[3], 0, "%s corner %s" % (label, corner))


def _icns_png_payload(path: Path, ostype: bytes):
    data = path.read_bytes()
    offset = 8
    while offset + 8 <= len(data):
        chunk_type, length = struct.unpack_from(">4sI", data, offset)
        payload = data[offset + 8 : offset + length]
        if chunk_type == ostype and payload[:8] == b"\x89PNG\r\n\x1a\n":
            from PIL import Image as PILImage

            return PILImage.open(BytesIO(payload)).convert("RGBA")
        if length < 8:
            break
        offset += length
    raise AssertionError("ICNS is missing PNG payload %s" % ostype.decode("latin1"))


class AppIconTests(unittest.TestCase):
    def test_packaged_png_ico_and_icns_exist(self) -> None:
        paths = packaged_icon_paths()
        for kind in ("png", "ico", "icns"):
            path = paths[kind]
            self.assertTrue(path.is_file(), kind)
            self.assertEqual(path.stem, "labgym-launcher")
            self.assertEqual(path.suffix, "." + kind)

    def test_packaged_png_is_square(self) -> None:
        width, height = _png_size(packaged_icon_paths()["png"])
        self.assertEqual(width, height)
        self.assertEqual((width, height), (512, 512))

    def test_packaged_ico_has_square_windows_sizes(self) -> None:
        sizes = _ico_sizes(packaged_icon_paths()["ico"])
        self.assertTrue(sizes)
        for width, height in sizes:
            self.assertEqual(width, height)
            self.assertLessEqual(width, 256)
        self.assertIn((16, 16), sizes)
        self.assertIn((32, 32), sizes)
        self.assertIn((256, 256), sizes)

    def test_packaged_icns_has_icns_magic(self) -> None:
        data = packaged_icon_paths()["icns"].read_bytes()[:4]
        self.assertEqual(data, b"icns")

    def test_packaged_png_has_macos_padding(self) -> None:
        from PIL import Image as PILImage

        image = PILImage.open(packaged_icon_paths()["png"])
        _assert_macos_geometry(self, image, "packaged PNG")

    def test_packaged_ico_256_has_macos_padding(self) -> None:
        from PIL import Image as PILImage

        with PILImage.open(packaged_icon_paths()["ico"]) as ico:
            frame = ico.ico.getimage((256, 256))
            _assert_macos_geometry(self, frame, "packaged ICO 256")

    def test_packaged_icns_has_macos_padding(self) -> None:
        icns = packaged_icon_paths()["icns"]
        _assert_macos_geometry(self, _icns_png_payload(icns, b"ic09"), "ICNS 512")
        _assert_macos_geometry(self, _icns_png_payload(icns, b"ic10"), "ICNS 1024")

    def test_windows_identity_is_launcher_specific(self) -> None:
        self.assertEqual(APP_NAME, "LabGym Launcher")
        self.assertEqual(WINDOWS_APP_USER_MODEL_ID, "umyelab.LabGymLauncher")
        self.assertNotEqual(WINDOWS_APP_USER_MODEL_ID, "umyelab.LabGym")

    def test_macos_frame_icon_is_launcher_png(self) -> None:
        with patch("labgym_launcher.app_icon.sys.platform", "darwin"):
            path = get_frame_icon_path()
        self.assertTrue(path.endswith("labgym-launcher.png"))
        self.assertNotIn("/labgym.png", path.replace("\\", "/"))

    def test_linux_frame_icon_is_launcher_png(self) -> None:
        with patch("labgym_launcher.app_icon.sys.platform", "linux"):
            path = get_frame_icon_path()
        self.assertTrue(path.endswith("labgym-launcher.png"))
        self.assertTrue(Path(path).is_file())

    def test_windows_frame_icon_prefers_launcher_ico(self) -> None:
        with patch("labgym_launcher.app_icon.sys.platform", "win32"):
            path = get_frame_icon_path()
        self.assertTrue(path.endswith("labgym-launcher.ico"))
        self.assertTrue(Path(path).is_file())

    def test_setup_application_icons_is_safe_on_linux(self) -> None:
        with patch("labgym_launcher.app_icon.sys.platform", "linux"):
            setup_application_icons()

    def test_windows_app_user_model_id_call_uses_launcher_id(self) -> None:
        recorded = {}

        class _Shell32:
            @staticmethod
            def SetCurrentProcessExplicitAppUserModelID(app_id):
                recorded["id"] = app_id

        class _Ctypes:
            class windll:
                shell32 = _Shell32()

        with patch("labgym_launcher.app_icon.sys.platform", "win32"):
            with patch.dict(sys.modules, {"ctypes": _Ctypes}):
                set_windows_app_user_model_id()
        self.assertEqual(recorded["id"], "umyelab.LabGymLauncher")


if __name__ == "__main__":
    unittest.main()
