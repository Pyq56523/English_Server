"""注册验证码：Pillow 生成图片，验证码存 redis（TLL 5 分钟）。

GET  /captcha             -> { captcha_id, image(base64) }
POST /auth/register       -> 携带 captcha_id + captcha_code，创建前校验
"""
import base64
import io
import random
import string
import uuid

import redis
from fastapi import HTTPException, status
from PIL import Image, ImageDraw, ImageFont
from database.config import load_db_config

_REDIS = load_db_config().get("redis", {})
TTL = _REDIS.get("ttl", 60)
_PREFIX = "captcha:"

_client = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis(
            host=_REDIS.get("host", "127.0.0.1"),
            port=_REDIS.get("port", 6379),
            db=_REDIS.get("db", 0),
            password=_REDIS.get("password", None),
            decode_responses=True,
        )
    return _client


_CHARS = string.digits + string.ascii_uppercase
_SIZE = 4
_WIDTH, _HEIGHT = 120, 42


def _font():
    for path in ("C:/Windows/Fonts/Arial.ttf", "C:/Windows/Fonts/segoeuib.ttf"):
        try:
            return ImageFont.truetype(path, 28)
        except Exception:
            continue
    return ImageFont.load_default()


def _generate_image(code: str) -> Image.Image:
    img = Image.new("RGB", (_WIDTH, _HEIGHT), (247, 248, 252))
    draw = ImageDraw.Draw(img)
    font = _font()
    for _ in range(80):  # 噪点
        draw.point((random.randint(0, _WIDTH - 1), random.randint(0, _HEIGHT - 1)),
                   fill=(random.randint(140, 220),) * 3)
    for _ in range(3):  # 干扰线
        draw.line((random.randint(0, _WIDTH // 3), random.randint(0, _HEIGHT),
                   random.randint(_WIDTH * 2 // 3, _WIDTH), random.randint(0, _HEIGHT)),
                  fill=(random.randint(100, 200),) * 3, width=2)
    step = _WIDTH // (_SIZE + 1)
    for i, ch in enumerate(code):  # 字符（随机偏移/颜色）
        draw.text((step * (i + 1) - 8 + random.randint(-3, 3), random.randint(4, 14)),
                  ch, font=font, fill=(random.randint(20, 120),) * 3)
    return img


def generate():
    code = "".join(random.choice(_CHARS) for _ in range(_SIZE))
    buf = io.BytesIO()
    _generate_image(code).save(buf, format="PNG")
    image = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    captcha_id = uuid.uuid4().hex
    try:
        get_redis().setex(f"{_PREFIX}{captcha_id}", TTL, code)
    except Exception as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Captcha unavailable: {e}")
    return {"captcha_id": captcha_id, "image": image}


def verify(captcha_id: str, captcha_code: str):
    key = f"{_PREFIX}{captcha_id}"
    stored = get_redis().get(key)
    if stored is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码已过期或不存在，请刷新")
    if stored.upper() != captcha_code.strip().upper():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码错误")
    get_redis().delete(key)
    return True