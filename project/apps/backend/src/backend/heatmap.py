from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter

def build_heatmap_overlay(
    image_path: str,
    coords: list[tuple[float, float]],
    out_path: str = "heatmap_overlay.png",
    browser_size: tuple[int, int] = (1280, 720),
    cell_size: int = 4,
    blur_sigma: float = 2.5,
    alpha: float = 0.60
):
    # Загружаем скриншот сайта
    img = Image.open(image_path).convert("RGBA")
    w, h = img.size

    bw, bh = browser_size
    sx = w / bw
    sy = h / bh

    # Масштабируем координаты из окна браузера в размер изображения
    scaled = []
    for x, y in coords:
        xx = x * sx
        yy = y * sy
        if 0 <= xx < w and 0 <= yy < h:
            scaled.append((xx, yy))

    if not scaled:
        raise ValueError("После масштабирования не осталось валидных координат.")

    scaled = np.asarray(scaled, dtype=np.float32)

    # Грубая сетка для плотности точек
    grid_w = int(np.ceil(w / cell_size))
    grid_h = int(np.ceil(h / cell_size))
    heat = np.zeros((grid_h, grid_w), dtype=np.float32)

    gx = np.floor(scaled[:, 0] / cell_size).astype(int)
    gy = np.floor(scaled[:, 1] / cell_size).astype(int)

    valid = (gx >= 0) & (gx < grid_w) & (gy >= 0) & (gy < grid_h)
    np.add.at(heat, (gy[valid], gx[valid]), 1)

    # Размытие
    heat = gaussian_filter(heat, sigma=blur_sigma, mode="nearest")

    # Нормализация
    if heat.max() > 0:
        heat = heat / heat.max()

    # Масштабируем heatmap обратно до размера скриншота
    heat_img = Image.fromarray((heat * 255).astype(np.uint8), mode="L")
    heat_img = heat_img.resize((w, h), resample=Image.Resampling.BILINEAR)
    heat = np.asarray(heat_img, dtype=np.float32) / 255.0

    # Рисуем скриншот + heatmap поверх него
    fig, ax = plt.subplots(figsize=(w / 100, h / 100), dpi=100)
    ax.imshow(img, origin="upper")
    ax.imshow(
        heat,
        cmap="jet",
        origin="upper",
        interpolation="bilinear",
        alpha=alpha
    )
    ax.axis("off")
    fig.subplots_adjust(0, 0, 1, 1, 0)

    # Сохраняем именно наложенную картинку
    fig.savefig(out_path, dpi=100, pad_inches=0)
    plt.close(fig)

    return out_path