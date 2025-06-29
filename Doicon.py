from PIL import Image, ImageDraw, ImageFont
import random
import string
import os

icon_img = "RNX"

def random_color():
    """生成随机颜色"""
    return tuple(random.randint(0, 255) for _ in range(3))

def random_text(length=3):
    """生成随机大写字母文本"""
    return icon_img

def generate_icon(text=None, size=256, bgcolor=None, fontcolor=None, font_size=None):
    """生成带随机元素的PNG图标，上方有GTS长方形标识"""
    if text is None:
        text = random_text()
    if bgcolor is None:
        bgcolor = random_color()
    if fontcolor is None:
        fontcolor = (255, 255, 255)
    if font_size is None:
        font_size = int(size * 0.45)
    img = Image.new("RGB", (size, size), bgcolor)
    draw = ImageDraw.Draw(img)

    # 1. 画顶部长方形（位置下移一点，颜色随机）
    rect_height = int(size * 0.22)
    rect_width = int(size * 0.7)
    rect_x = (size - rect_width) // 2
    rect_y = int(size * 0.14)
    rect_color = random_color()  # 颜色随机
    draw.rounded_rectangle([rect_x, rect_y, rect_x + rect_width, rect_y + rect_height], radius=int(rect_height*0.3), fill=rect_color)

    # 2. 写GTS（小号字体，随机颜色，完全居中在长方形内）
    gts_font_size = int(rect_height * 0.55)
    gts_font = None
    for font_name in ["arialbd.ttf", "DejaVuSans-Bold.ttf", "arial.ttf"]:
        try:
            gts_font = ImageFont.truetype(font_name, gts_font_size)
            break
        except:
            continue
    if gts_font is None:
        gts_font = ImageFont.load_default()
    gts_text = "GTS"
    gts_color = random_color()
    gts_bbox = draw.textbbox((0, 0), gts_text, font=gts_font)
    gts_w, gts_h = gts_bbox[2] - gts_bbox[0], gts_bbox[3] - gts_bbox[1]
    # 完全居中：横向和纵向都居中
    gts_x = rect_x + (rect_width - gts_w) // 2
    gts_y = rect_y + (rect_height - gts_h) // 2 -4
    draw.text((gts_x, gts_y), gts_text, font=gts_font, fill=gts_color)

    # 3. 主体大字母
    font = None
    for font_name in ["arialbd.ttf", "DejaVuSans-Bold.ttf", "arial.ttf"]:
        try:
            font = ImageFont.truetype(font_name, font_size)
            break
        except:
            continue
    if font is None:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    y_offset = int(size * 0.18)
    draw.text(((size-w)//2, (size-h)//2 + y_offset//2), text, font=font, fill=fontcolor)
    return img

def save_icon(img, out_path, sizes=[(256,256), (128,128), (64,64), (32,32), (16,16)]):
    """保存为多尺寸ICO"""
    img.save(out_path, format='ICO', sizes=sizes)
    print(f"已生成ICO图标: {out_path}")

if __name__ == "__main__":
    # 支持命令行输入字母，否则随机
    import sys
    if len(sys.argv) > 1:
        text = sys.argv[1][:3].upper()  # 只取前3位并大写
    else:
        text = random_text()
    bgcolor = random_color()
    icon_img = generate_icon(text=text, bgcolor=bgcolor)
    out_ico = f"icon_{text}.ico"
    save_icon(icon_img, out_ico)