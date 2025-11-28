#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Egyszerű Tkinter alapú képszerkesztő
Támogatott funkciók:
- Open / Save
- Resize (szélesség megadása, arány megtartása)
- Rotate (fokban)
- Crop (kézi koordináták vagy "képkiválasztás" egyszerű módon)
- Filters: blur, sharpen, bw, edge
- Brightness / Contrast csúszkák
- Watermark text
- Undo stack (néhány lépés visszavonása)
- Reset original image
"""
import os
import sys
import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageFilter, ImageEnhance, ImageTk, ImageOps, ImageDraw, ImageFont
import traceback

# ---------- Segédfüggvények ----------
def safe_open_image(path):
    try:
        return Image.open(path).convert("RGB")
    except Exception as e:
        print("Hiba kép megnyitásakor:", e)
        return None

def pil_to_tk(img, maxsize=(900, 600)):
    """Convert PIL image to Tk PhotoImage, resize to fit maxsize while keeping ratio"""
    w, h = img.size
    max_w, max_h = maxsize
    ratio = min(max_w / w, max_h / h, 1.0)
    disp_w, disp_h = int(w * ratio), int(h * ratio)
    disp_img = img.resize((disp_w, disp_h), Image.Resampling.LANCZOS)
    return ImageTk.PhotoImage(disp_img), ratio

def clamp_box(box, img_size):
    L, U, R, D = box
    w, h = img_size
    L = max(0, min(L, w-1))
    R = max(1, min(R, w))
    U = max(0, min(U, h-1))
    D = max(1, min(D, h))
    if R <= L: R = min(L+1, w)
    if D <= U: D = min(U+1, h)
    return (L, U, R, D)

# ---------- Fő GUI osztály ----------
class ImageEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Képszerkesztő - Haladó Prog Beadandó")
        self.root.geometry("1200x750")

        # állapotok
        self.image_path = None
        self.original_image = None  # eredeti (PIL.Image)
        self.current_image = None   # dolgozó egy példány
        self.preview_ratio = 1.0    # arány a megjelenítéshez
        self.undo_stack = []        # visszavonási stack (PIL képek)
        self.max_undo = 10

        self._build_ui()

    def _build_ui(self):
        # bal oldali panel: gombok, beállítások
        left_frame = ttk.Frame(self.root, padding=8)
        left_frame.pack(side="left", fill="y")

        # Open / Save
        btn_open = ttk.Button(left_frame, text="Open image...", command=self.open_image)
        btn_open.pack(fill="x", pady=4)
        btn_save = ttk.Button(left_frame, text="Save image as...", command=self.save_image_as)
        btn_save.pack(fill="x", pady=4)
        btn_reset = ttk.Button(left_frame, text="Reset to original", command=self.reset_image)
        btn_reset.pack(fill="x", pady=4)
        btn_undo = ttk.Button(left_frame, text="Undo", command=self.undo)
        btn_undo.pack(fill="x", pady=4)

        ttk.Separator(left_frame, orient="horizontal").pack(fill="x", pady=6)

        # Resize
        ttk.Label(left_frame, text="Resize (width px):").pack(anchor="w")
        self.resize_var = tk.StringVar()
        resize_entry = ttk.Entry(left_frame, textvariable=self.resize_var)
        resize_entry.pack(fill="x", pady=2)
        resize_btn = ttk.Button(left_frame, text="Apply Resize", command=self.apply_resize)
        resize_btn.pack(fill="x", pady=2)

        # Rotate
        ttk.Label(left_frame, text="Rotate (degrees):").pack(anchor="w", pady=(8,0))
        self.rotate_var = tk.StringVar(value="0")
        rotate_entry = ttk.Entry(left_frame, textvariable=self.rotate_var)
        rotate_entry.pack(fill="x", pady=2)
        rotate_btn = ttk.Button(left_frame, text="Apply Rotate", command=self.apply_rotate)
        rotate_btn.pack(fill="x", pady=2)

        # Crop
        ttk.Label(left_frame, text="Crop (L U R D):").pack(anchor="w", pady=(8,0))
        self.crop_vars = [tk.StringVar(value="0"), tk.StringVar(value="0"), tk.StringVar(value="0"), tk.StringVar(value="0")]
        crop_frame = ttk.Frame(left_frame)
        crop_frame.pack(fill="x", pady=2)
        for v in self.crop_vars:
            ttk.Entry(crop_frame, textvariable=v, width=6).pack(side="left", padx=2)
        crop_btn = ttk.Button(left_frame, text="Apply Crop", command=self.apply_crop)
        crop_btn.pack(fill="x", pady=2)

        ttk.Separator(left_frame, orient="horizontal").pack(fill="x", pady=6)

        # Filters
        ttk.Label(left_frame, text="Filters:").pack(anchor="w")
        filters = [("Blur", "blur"), ("Sharpen", "sharpen"), ("B/W", "bw"), ("Edge", "edge")]
        for label, mode in filters:
            ttk.Button(left_frame, text=label, command=lambda m=mode: self.apply_filter(m)).pack(fill="x", pady=2)

        ttk.Separator(left_frame, orient="horizontal").pack(fill="x", pady=6)

        # Brightness / Contrast
        ttk.Label(left_frame, text="Brightness / Contrast:").pack(anchor="w")
        self.brightness_scale = ttk.Scale(left_frame, from_=0.2, to=2.0, value=1.0, orient="horizontal", command=self.on_brightness_change)
        self.brightness_scale.pack(fill="x", pady=2)
        self.contrast_scale = ttk.Scale(left_frame, from_=0.2, to=2.0, value=1.0, orient="horizontal", command=self.on_contrast_change)
        self.contrast_scale.pack(fill="x", pady=2)
        apply_bc = ttk.Button(left_frame, text="Apply B/C", command=self.apply_brightness_contrast)
        apply_bc.pack(fill="x", pady=2)

        ttk.Separator(left_frame, orient="horizontal").pack(fill="x", pady=6)

        # Watermark
        ttk.Label(left_frame, text="Watermark text:").pack(anchor="w")
        self.wm_text_var = tk.StringVar()
        ttk.Entry(left_frame, textvariable=self.wm_text_var).pack(fill="x", pady=2)
        self.wm_size_var = tk.IntVar(value=24)
        ttk.Label(left_frame, text="Font size:").pack(anchor="w")
        ttk.Spinbox(left_frame, from_=8, to=200, textvariable=self.wm_size_var).pack(fill="x", pady=2)
        ttk.Button(left_frame, text="Apply Watermark", command=self.apply_watermark).pack(fill="x", pady=2)

        ttk.Separator(left_frame, orient="horizontal").pack(fill="x", pady=6)

        # Misc
        ttk.Button(left_frame, text="Auto-Enhance (autocontrast+sharp)", command=self.auto_enhance).pack(fill="x", pady=2)
        ttk.Button(left_frame, text="Histogram Equalize", command=self.hist_equalize).pack(fill="x", pady=2)

        # jobb oldal: kép preview és státusz
        right_frame = ttk.Frame(self.root, padding=8)
        right_frame.pack(side="right", fill="both", expand=True)

        # canavas / label a képpel
        self.canvas = tk.Canvas(right_frame, bg="gray90")
        self.canvas.pack(fill="both", expand=True)
        self.canvas_img_id = None

        # státusz alul
        self.status_var = tk.StringVar(value="No image loaded")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.pack(side="bottom", fill="x")

        # bind dupla katt crop quick demo (később bővíthető)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

    # ---------- File műveletek ----------
    def open_image(self):
        path = filedialog.askopenfilename(title="Open image", filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff;*.webp"), ("All files", "*.*")])
        if not path:
            return
        img = safe_open_image(path)
        if img is None:
            messagebox.showerror("Error", "Nem sikerült megnyitni a képet.")
            return
        self.image_path = path
        self.original_image = img.copy()
        self.current_image = img.copy()
        self.undo_stack = []
        self._update_preview()
        self.status_var.set(f"Opened: {os.path.basename(path)} ({img.size[0]}x{img.size[1]})")

    def save_image_as(self):
        if self.current_image is None:
            messagebox.showinfo("Info", "Nincs kép mentésre.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".jpg", filetypes=[("JPEG", "*.jpg;*.jpeg"), ("PNG", "*.png"), ("WEBP", "*.webp"), ("TIFF","*.tiff")])
        if not path:
            return
        try:
            # formátum beállítás a kiterjesztés alapján
            ext = os.path.splitext(path)[1].lower()
            fmt = "JPEG"
            if ext in (".png",):
                fmt = "PNG"
            elif ext in (".webp",):
                fmt = "WEBP"
            elif ext in (".tif", ".tiff"):
                fmt = "TIFF"
            save_kw = {}
            if fmt == "JPEG":
                save_kw["quality"] = 95
            self.current_image.save(path, fmt, **save_kw)
            self.status_var.set(f"Saved: {path}")
            messagebox.showinfo("Saved", f"Kép elmentve: {path}")
        except Exception as e:
            messagebox.showerror("Save error", str(e))

    # ---------- Undo / Reset ----------
    def push_undo(self):
        if self.current_image is None:
            return
        # limitáljuk a stack méretet
        try:
            self.undo_stack.append(self.current_image.copy())
            if len(self.undo_stack) > self.max_undo:
                self.undo_stack.pop(0)
        except Exception:
            pass

    def undo(self):
        if not self.undo_stack:
            messagebox.showinfo("Undo", "Nincs több visszavonható művelet.")
            return
        self.current_image = self.undo_stack.pop()
        self._update_preview()
        self.status_var.set("Undo")

    def reset_image(self):
        if self.original_image is None:
            return
        self.push_undo()
        self.current_image = self.original_image.copy()
        self._update_preview()
        self.status_var.set("Reset to original")

    # ---------- Alap műveletek ----------
    def apply_resize(self):
        if self.current_image is None:
            return
        s = self.resize_var.get().strip()
        if not s:
            messagebox.showinfo("Info", "Adj meg egy szélességet (px).")
            return
        try:
            w = int(s)
            if w <= 0:
                raise ValueError()
        except Exception:
            messagebox.showerror("Hiba", "Helytelen szélesség.")
            return
        self.push_undo()
        w0, h0 = self.current_image.size
        ratio = w / float(w0)
        h = max(1, int(h0 * ratio))
        self.current_image = self.current_image.resize((w, h), Image.Resampling.LANCZOS)
        self._update_preview()
        self.status_var.set(f"Resized to {w}x{h}")

    def apply_rotate(self):
        if self.current_image is None:
            return
        s = self.rotate_var.get().strip()
        try:
            angle = float(s)
        except Exception:
            messagebox.showerror("Hiba", "Helytelen szög.")
            return
        self.push_undo()
        self.current_image = self.current_image.rotate(-angle, expand=True)
        self._update_preview()
        self.status_var.set(f"Rotated {angle}°")

    def apply_crop(self):
        if self.current_image is None:
            return
        try:
            vals = [int(v.get()) for v in self.crop_vars]
        except Exception:
            messagebox.showerror("Hiba", "Helytelen crop érték.")
            return
        box = clamp_box(tuple(vals), self.current_image.size)
        self.push_undo()
        self.current_image = self.current_image.crop(box)
        self._update_preview()
        self.status_var.set(f"Cropped to box {box}")

    def apply_filter(self, mode):
        if self.current_image is None:
            return
        self.push_undo()
        mode = mode.lower()
        if mode == "blur":
            img = self.current_image.filter(ImageFilter.BLUR)
        elif mode == "sharpen":
            img = self.current_image.filter(ImageFilter.SHARPEN)
        elif mode in ("bw", "grayscale", "gray"):
            img = self.current_image.convert("L").convert("RGB")
        elif mode == "edge":
            img = self.current_image.filter(ImageFilter.FIND_EDGES)
        else:
            return
        self.current_image = img
        self._update_preview()
        self.status_var.set(f"Applied filter: {mode}")

    def on_brightness_change(self, _=None):
        # valós időben ne alkalmazzunk, csak tároljuk
        val = self.brightness_scale.get()
        self.status_var.set(f"Brightness preview: {val:.2f}")

    def on_contrast_change(self, _=None):
        val = self.contrast_scale.get()
        self.status_var.set(f"Contrast preview: {val:.2f}")

    def apply_brightness_contrast(self):
        if self.current_image is None:
            return
        self.push_undo()
        b = float(self.brightness_scale.get())
        c = float(self.contrast_scale.get())
        img = ImageEnhance.Brightness(self.current_image).enhance(b)
        img = ImageEnhance.Contrast(img).enhance(c)
        self.current_image = img
        self._update_preview()
        self.status_var.set(f"Applied B/C: {b:.2f}/{c:.2f}")

    def apply_watermark(self):
        if self.current_image is None:
            return
        text = self.wm_text_var.get().strip()
        if not text:
            messagebox.showinfo("Watermark", "Adj meg vízjelszöveget.")
            return
        self.push_undo()
        img = self.current_image.convert("RGBA")
        txt_layer = Image.new("RGBA", img.size, (255,255,255,0))
        draw = ImageDraw.Draw(txt_layer)
        # próbálunk betűtípust betölteni, ha van
        font = None
        try:
            font = ImageFont.truetype("arial.ttf", self.wm_size_var.get())
        except Exception:
            try:
                font = ImageFont.load_default()
            except Exception:
                font = None
        W, H = img.size
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        # jobb alsó sarok
        margin = 10
        x = W - text_w - margin
        y = H - text_h - margin
        # árnyék és fehér text
        draw.text((x+1, y+1), text, font=font, fill=(0,0,0,140))
        draw.text((x, y), text, font=font, fill=(255,255,255,200))
        out = Image.alpha_composite(img, txt_layer).convert("RGB")
        self.current_image = out
        self._update_preview()
        self.status_var.set("Watermark applied")

    def auto_enhance(self):
        if self.current_image is None:
            return
        self.push_undo()
        img = ImageOps.autocontrast(self.current_image)
        img = ImageEnhance.Sharpness(img).enhance(1.2)
        self.current_image = img
        self._update_preview()
        self.status_var.set("Auto-enhance applied")

    def hist_equalize(self):
        if self.current_image is None:
            return
        if self.current_image.mode != "RGB":
            img = self.current_image.convert("RGB")
        else:
            img = self.current_image
        self.push_undo()
        try:
            ycbcr = img.convert("YCbCr")
            y, cb, cr = ycbcr.split()
            y_eq = ImageOps.equalize(y)
            merged = Image.merge("YCbCr", (y_eq, cb, cr)).convert("RGB")
            self.current_image = merged
            self._update_preview()
            self.status_var.set("Histogram equalize applied")
        except Exception as e:
            messagebox.showerror("Error", f"Hist equalize error: {e}")

    # ---------- Canvas click (egyszerű demó) ----------
    def on_canvas_click(self, event):
        # egyszerű információs demo: megmutatja a pozíciót és képpont színét
        if not self.current_image:
            return
        # átszámoljuk a canvas pozíciót a teljes kép pozíciójára a preview_ratio segítségével
        x = int(event.x / self.preview_ratio)
        y = int(event.y / self.preview_ratio)
        x = max(0, min(x, self.current_image.size[0]-1))
        y = max(0, min(y, self.current_image.size[1]-1))
        pix = self.current_image.getpixel((x,y))
        self.status_var.set(f"Pos: ({x},{y}) Color: {pix}")

    # ---------- Preview frissítés ----------
    def _update_preview(self):
        if self.current_image is None:
            self.canvas.delete("all")
            self.canvas_img_id = None
            return
        try:
            # méretezés a canvas méretéhez (nem a root ablakhoz)
            canvas_w = max(200, self.canvas.winfo_width())
            canvas_h = max(200, self.canvas.winfo_height())
            tkimg, ratio = pil_to_tk(self.current_image, maxsize=(canvas_w, canvas_h))
            self.preview_ratio = ratio
            self.canvas.delete("all")
            self.canvas_img = tkimg  # referenciát meg kell tartani
            self.canvas_img_id = self.canvas.create_image(canvas_w//2, canvas_h//2, image=tkimg, anchor="center")
        except Exception as e:
            print("Preview error:", e)
            traceback.print_exc()

# ---------- Futás ----------
def main():
    root = tk.Tk()
    app = ImageEditorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
