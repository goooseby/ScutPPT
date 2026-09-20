"""Build Windows and preview icon files from the 课页 word mark."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).parent


def build():
    size = 512
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((20, 20, 492, 492), radius=126, fill='#176e58')
    font_path = Path('C:/Windows/Fonts/msyhbd.ttc')
    if not font_path.exists():
        font_path = Path('C:/Windows/Fonts/msyh.ttc')
    font = ImageFont.truetype(str(font_path), 292)
    text = '页'
    box = draw.textbbox((0, 0), text, font=font)
    x = (size - (box[2] - box[0])) / 2 - box[0]
    y = (size - (box[3] - box[1])) / 2 - box[1] - 8
    draw.text((x, y), text, font=font, fill='white')
    draw.rounded_rectangle((330, 330, 424, 424), radius=12, outline='#d7eee4', width=19)
    image.save(ROOT / 'app-icon.png')
    image.save(ROOT / 'app-icon.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])


if __name__ == '__main__':
    build()
