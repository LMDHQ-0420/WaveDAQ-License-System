from pathlib import Path

from PIL import Image


root = Path(__file__).resolve().parents[2]
assets = root / "launcher" / "assets"
assets.mkdir(parents=True, exist_ok=True)
image = Image.open(root / "logo.png").convert("RGBA").resize((1024, 1024), Image.Resampling.LANCZOS)
image.save(assets / "app.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
image.save(assets / "app.icns", sizes=[(16, 16), (32, 32), (128, 128), (256, 256), (512, 512)])
