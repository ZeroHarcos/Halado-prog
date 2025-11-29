#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Képszerkesztő (javított, tisztított verzió)
- Írós crop eltávolítva
- Egérrel húzható crop (fixálva)
- Autosave szerkesztett_kepek mappába
- Autoload kepek mappából
- Új: Quick Save → kesz_kepek mappába
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from turtle import right
from PIL import Image, ImageFilter, ImageEnhance, ImageTk, ImageOps, ImageDraw, ImageFont


# ------------------- Segédfüggvények -------------------
def safe_open_image(path):
    try:
        return Image.open(path).convert("RGB")
    except Exception as e:
        print("Hiba kép megnyitásakor:", e)
        return None


def pil_to_tk(img, maxsize=(900, 600)):
    w, h = img.size
    max_w, max_h = maxsize
    ratio = min(max_w / w, max_h / h, 1.0)
    disp_w, disp_h = int(w * ratio), int(h * ratio)
    disp_img = img.resize((disp_w, disp_h), Image.Resampling.LANCZOS)
    return ImageTk.PhotoImage(disp_img), ratio, (disp_w, disp_h)


def clamp_box(box, img_size):
    L, U, R, D = box
    w, h = img_size
    L = max(0, min(L, w - 1))
    R = max(1, min(R, w))
    U = max(0, min(U, h - 1))
    D = max(1, min(D, h))
    if R <= L: R = min(L + 1, w)
    if D <= U: D = min(U + 1, h)
    return (L, U, R, D)


# ---------------------- APP CLASS -----------------------
class ImageEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Képszerkesztő – Final Version")
        self.root.geometry("1250x800")

             # ----- DARK GREEN UI THEME -----
        style = ttk.Style()
        style.theme_use("clam")

        # Globális háttér fekete
        self.root.configure(bg="#000000")
        style.configure(".", background="#000000", foreground="#00ff66")

        # Frame-ek & Label-ek
        style.configure("TFrame", background="#000000")
        style.configure("TLabel", background="#000000", foreground="#00ff66")

        # Zöld gombok
        style.configure(
            "TButton",
            background="#00cc44",
            foreground="black",
            padding=6,
            font=("Segoe UI", 10, "bold")
        )
        style.map("TButton", background=[("active", "#00ff66")])

        # Input mezők (Entry, Spinbox)
        style.configure(
            "TEntry",
            fieldbackground="#ffffff",
            foreground="black"
        )
        style.configure(
            "TSpinbox",
            fieldbackground="#ffffff",
            foreground="black"
        )


        # Autosave mappa
        self.autosave_dir = "szerkesztett_kepek"
        os.makedirs(self.autosave_dir, exist_ok=True)

        # Quick save mappa
        self.export_dir = "kesz_kepek"
        os.makedirs(self.export_dir, exist_ok=True)

        # Autoload könyvtár
        self.autoload_dir = "kepek"
        os.makedirs(self.autoload_dir, exist_ok=True)

        # Állapotok
        self.original_image = None
        self.current_image = None
        self.undo_stack = []
        self.max_undo = 10

        # Crop state
        self.select_start = None
        self.select_rect = None

        # Preview adatok
        self.preview_ratio = 1.0
        self.preview_offset = (0, 0)
        self.display_size = (0, 0)

        self._build_ui()

    # ------------------- UI ----------------------
    def _build_ui(self):
        left = ttk.Frame(self.root, padding=8)
        left.pack(side="left", fill="y")

        ttk.Button(left, text="Open Image...", command=self.open_image).pack(fill="x", pady=4)
        ttk.Button(left, text="Save Image As...", command=self.save_image_as).pack(fill="x", pady=4)
        ttk.Button(left, text="Quick Save (→ kesz_kepek)", command=self.quick_save).pack(fill="x", pady=4)
        ttk.Button(left, text="Reset to Original", command=self.reset_image).pack(fill="x", pady=4)
        ttk.Button(left, text="Undo", command=self.undo).pack(fill="x", pady=4)

        ttk.Separator(left).pack(fill="x", pady=6)

        # Autoload list
        ttk.Label(left, text="Load from /kepek:").pack(anchor="w")
        self.autoload_list = tk.Listbox(left, height=6)
        self.autoload_list.pack(fill="x", pady=4)
        ttk.Button(left, text="Open Selected", command=self.autoload_open).pack(fill="x")
        self.refresh_autoload()

        ttk.Separator(left).pack(fill="x", pady=8)

        # Resize
        ttk.Label(left, text="Resize (width px):").pack(anchor="w")
        self.resize_var = tk.StringVar()
        ttk.Entry(left, textvariable=self.resize_var).pack(fill="x")
        ttk.Button(left, text="Apply Resize", command=self.apply_resize).pack(fill="x", pady=3)

        # Rotate
        ttk.Label(left, text="Rotate (degrees):").pack(anchor="w", pady=4)
        self.rotate_var = tk.StringVar(value="0")
        ttk.Entry(left, textvariable=self.rotate_var).pack(fill="x")
        ttk.Button(left, text="Apply Rotate", command=self.apply_rotate).pack(fill="x", pady=3)

        ttk.Separator(left).pack(fill="x", pady=8)

        # Filters
        ttk.Label(left, text="Filters:").pack(anchor="w", pady=2)
        for name, mode in [("Blur", "blur"), ("Sharpen", "sharpen"),
                           ("Black/White", "bw"), ("Edge", "edge")]:
            ttk.Button(left, text=name, command=lambda m=mode: self.apply_filter(m)).pack(fill="x", pady=2)

        ttk.Separator(left).pack(fill="x", pady=8)

        # Brightness/Contrast
        ttk.Label(left, text="Brightness / Contrast").pack(anchor="w")
        self.brightness_scale = ttk.Scale(left, from_=0.2, to=2.0, value=1.0, orient="horizontal")
        self.brightness_scale.pack(fill="x", pady=2)
        self.contrast_scale = ttk.Scale(left, from_=0.2, to=2.0, value=1.0, orient="horizontal")
        self.contrast_scale.pack(fill="x", pady=2)
        ttk.Button(left, text="Apply B/C", command=self.apply_bc).pack(fill="x", pady=3)

        ttk.Separator(left).pack(fill="x", pady=8)

        # Watermark
        ttk.Label(left, text="Watermark Text:").pack(anchor="w")
        self.wm_var = tk.StringVar()
        ttk.Entry(left, textvariable=self.wm_var).pack(fill="x")
        self.wm_size = tk.IntVar(value=22)
        ttk.Spinbox(left, from_=8, to=200, textvariable=self.wm_size).pack(fill="x", pady=2)
        ttk.Button(left, text="Apply Watermark", command=self.apply_watermark).pack(fill="x", pady=3)

        ttk.Button(left, text="Auto Enhance", command=self.auto_enhance).pack(fill="x", pady=4)
        ttk.Button(left, text="Histogram Equalize", command=self.hist_equalize).pack(fill="x", pady=4)

        # Canvas (crop csak egerrel!)
        right = ttk.Frame(self.root, padding=8)
        right.pack(side="right", fill="both", expand=True)
        self.canvas = tk.Canvas(right, bg="#000000", cursor="crosshair", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<Button-1>", self.crop_start)
        self.canvas.bind("<B1-Motion>", self.crop_drag)
        self.canvas.bind("<ButtonRelease-1>", self.crop_end)

        self.status = tk.StringVar(value="Welcome!")
        statusbar = tk.Label(
        self.root,
        textvariable=self.status,
        bg="#000000",
        fg="#00ff66",
        pady=4
        )
        statusbar.pack(side="bottom", fill="x")



    # ---------------- Autoload -------------------
    def refresh_autoload(self):
        self.autoload_list.delete(0, tk.END)
        for f in os.listdir(self.autoload_dir):
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp")):
                self.autoload_list.insert(tk.END, f)

    def autoload_open(self):
        sel = self.autoload_list.curselection()
        if not sel:
            return
        fname = self.autoload_list.get(sel[0])
        self.load_image(os.path.join(self.autoload_dir, fname))

    # ---------------- File műveletek -------------------
    def open_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff;*.webp")]
        )
        if path:
            self.load_image(path)

    def load_image(self, path):
        img = safe_open_image(path)
        if img is None:
            messagebox.showerror("Error", "Failed to open image.")
            return

        self.original_image = img.copy()
        self.current_image = img.copy()
        self.undo_stack.clear()
        self.update_preview()
        self.status.set(f"Loaded: {os.path.basename(path)}")

    def save_image_as(self):
        if self.current_image is None:
            return
        path = filedialog.asksaveasfilename(defaultextension=".jpg")
        if path:
            self.current_image.save(path)
            messagebox.showinfo("Saved", f"Saved: {path}")

    def quick_save(self):
        """Új funkció: gyors mentés a kesz_kepek mappába"""
        if self.current_image is None:
            return

        files = [f for f in os.listdir(self.export_dir) if f.lower().endswith(".jpg")]
        idx = len(files)
        fname = f"export_{idx:03d}.jpg"
        path = os.path.join(self.export_dir, fname)

        self.current_image.save(path, quality=95)
        self.status.set(f"Quick Saved → {fname}")

    # ---------------- Undo/Reset -------------------
    def push_undo(self):
        if self.current_image:
            self.undo_stack.append(self.current_image.copy())
            if len(self.undo_stack) > self.max_undo:
                self.undo_stack.pop(0)

    def undo(self):
        if not self.undo_stack:
            messagebox.showinfo("Undo", "Nothing to undo.")
            return
        self.current_image = self.undo_stack.pop()
        self.update_preview()

    def reset_image(self):
        if self.original_image:
            self.push_undo()
            self.current_image = self.original_image.copy()
            self.update_preview()

    # ---------------- Műveletek -------------------
    def apply_resize(self):
        if not self.current_image:
            return
        try:
            w = int(self.resize_var.get())
            if w <= 0:
                raise ValueError()
        except:
            messagebox.showerror("Error", "Invalid width.")
            return

        self.push_undo()
        w0, h0 = self.current_image.size
        h = int(h0 * w / w0)
        self.current_image = self.current_image.resize((w, h), Image.Resampling.LANCZOS)
        self.update_preview()

    def apply_rotate(self):
        if not self.current_image:
            return
        try:
            angle = float(self.rotate_var.get())
        except:
            messagebox.showerror("Error", "Invalid angle.")
            return

        self.push_undo()
        self.current_image = self.current_image.rotate(-angle, expand=True)
        self.update_preview()

    def apply_filter(self, mode):
        if not self.current_image:
            return

        self.push_undo()
        if mode == "blur":
            img = self.current_image.filter(ImageFilter.BLUR)
        elif mode == "sharpen":
            img = self.current_image.filter(ImageFilter.SHARPEN)
        elif mode == "bw":
            img = self.current_image.convert("L").convert("RGB")
        elif mode == "edge":
            img = self.current_image.filter(ImageFilter.FIND_EDGES)
        else:
            return

        self.current_image = img
        self.update_preview()

    def apply_bc(self):
        if not self.current_image:
            return

        b = self.brightness_scale.get()
        c = self.contrast_scale.get()

        self.push_undo()
        img = ImageEnhance.Brightness(self.current_image).enhance(b)
        img = ImageEnhance.Contrast(img).enhance(c)
        self.current_image = img
        self.update_preview()

    def apply_watermark(self):
        if not self.current_image:
            return

        text = self.wm_var.get().strip()
        if not text:
            messagebox.showinfo("Watermark", "Enter text.")
            return

        self.push_undo()

        img = self.current_image.convert("RGBA")
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        try:
            font = ImageFont.truetype("arial.ttf", self.wm_size.get())
        except:
            font = ImageFont.load_default()

        W, H = img.size
        bbox = draw.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = W - w - 10
        y = H - h - 10

        draw.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0, 180))
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 220))

        self.current_image = Image.alpha_composite(img, layer).convert("RGB")
        self.update_preview()

    def auto_enhance(self):
        if not self.current_image:
            return
        self.push_undo()
        img = ImageOps.autocontrast(self.current_image)
        img = ImageEnhance.Sharpness(img).enhance(1.3)
        self.current_image = img
        self.update_preview()

    def hist_equalize(self):
        if not self.current_image:
            return
        self.push_undo()
        ycbcr = self.current_image.convert("YCbCr")
        y, cb, cr = ycbcr.split()
        y2 = ImageOps.equalize(y)
        out = Image.merge("YCbCr", (y2, cb, cr)).convert("RGB")
        self.current_image = out
        self.update_preview()

    # ---------------- Crop egérrel -------------------
    def canvas_to_img(self, cx, cy):
        ox, oy = self.preview_offset
        r = self.preview_ratio
        ix = int((cx - ox) / r)
        iy = int((cy - oy) / r)
        return ix, iy

    def crop_start(self, event):
        if not self.current_image:
            return
        self.select_start = (event.x, event.y)
        if self.select_rect:
            self.canvas.delete(self.select_rect)
            self.select_rect = None

    def crop_drag(self, event):
        if not self.current_image or not self.select_start:
            return

        x0, y0 = self.select_start
        x1, y1 = event.x, event.y

        if self.select_rect:
            self.canvas.delete(self.select_rect)

        self.select_rect = self.canvas.create_rectangle(
            x0, y0, x1, y1, outline="red", dash=(3, 3), width=2
        )

    def crop_end(self, event):
        if not self.current_image or not self.select_start:
            return

        x0, y0 = self.select_start
        x1, y1 = event.x, event.y

        if self.select_rect:
            self.canvas.delete(self.select_rect)
            self.select_rect = None

        if abs(x1 - x0) < 5 or abs(y1 - y0) < 5:
            self.status.set("Crop cancelled (area too small)")
            return

        ix0, iy0 = self.canvas_to_img(x0, y0)
        ix1, iy1 = self.canvas_to_img(x1, y1)

        L, R = sorted((ix0, ix1))
        U, D = sorted((iy0, iy1))

        box = clamp_box((L, U, R, D), self.current_image.size)
        w = box[2] - box[0]
        h = box[3] - box[1]

        if w < 5 or h < 5:
            self.status.set("Crop cancelled (after mapping)")
            return

        self.push_undo()
        self.current_image = self.current_image.crop(box)
        self.update_preview()
        self.status.set("Crop done")

        self.select_start = None

    # ---------------- Preview -------------------
    def update_preview(self):
        if not self.current_image:
            return

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()

        if cw < 50 or ch < 50:
            cw, ch = 800, 600

        tkimg, r, (dw, dh) = pil_to_tk(self.current_image, (cw, ch))
        self.preview_ratio = r

        ox = (cw - dw) // 2
        oy = (ch - dh) // 2
        self.preview_offset = (ox, oy)

        self.canvas.delete("all")
        self.canvas_img = tkimg
        self.canvas.create_image(ox, oy, image=tkimg, anchor="nw")


# -------------------- MAIN --------------------
def main():
    root = tk.Tk()
    app = ImageEditorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
