import os
from PIL import Image, ImageFilter, ImageDraw, ImageFont
from datetime import datetime
import traceback


def log(message):
    """ Log üzenetek fájlba """
    with open("log.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} - {message}\n")


def list_images(folder):
    return [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))]


def resize_image(img, width):
    w_percent = width / float(img.size[0])
    h_size = int((float(img.size[1]) * float(w_percent)))
    return img.resize((width, h_size), Image.Resampling.LANCZOS)


def process_images(
    input_folder,
    output_folder,
    resize_width=None,
    rotate_angle=0,
    crop_box=None,
    filter_mode=None,
    watermark_text=None
):

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    files = list_images(input_folder)

    if not files:
        print("❌ Nincsenek képek a mappában!")
        return

    print(f"📸 {len(files)} kép feldolgozása indul...")
    log("Process start")

    for filename in files:
        try:
            img_path = os.path.join(input_folder, filename)

            with Image.open(img_path) as img:

                # --- Crop ---
                if crop_box:
                    img = img.crop(crop_box)

                # --- Rotate ---
                if rotate_angle != 0:
                    img = img.rotate(rotate_angle, expand=True)

                # --- Resize ---
                if resize_width:
                    img = resize_image(img, resize_width)

                # --- Filterek ---
                if filter_mode == "blur":
                    img = img.filter(ImageFilter.BLUR)
                elif filter_mode == "sharpen":
                    img = img.filter(ImageFilter.SHARPEN)
                elif filter_mode == "bw":
                    img = img.convert("L")

                # --- Watermark ---
                if watermark_text:
                    draw = ImageDraw.Draw(img)
                    font = ImageFont.load_default()
                    draw.text((10, 10), watermark_text, fill="white", font=font)

                # --- Save ---
                output_path = os.path.join(output_folder, f"mod_{filename}")

                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                img.save(output_path, quality=95)
                print(f"✔ OK: {filename}")
                log(f"Success: {filename}")

        except Exception as e:
            print(f"❌ Hiba a(z) {filename}-nál!")
            log(traceback.format_exc())

    print("\n🎉 Kész! Minden kép feldolgozva.")
    log("Process complete")


# --------------- MENÜ ---------------

def menu():
    print("""
=========================================
   🖼️ Tömeges Képszerkesztő Pythonban
=========================================

1) Átméretezés
2) Forgatás
3) Vágás
4) Szűrők hozzáadása
5) Vízjel hozzáadása
6) MINDENT egyszerre
0) Kilépés

""")

    return input("Válassz opciót: ")


# --------------------------------------

if __name__ == "__main__":

    input_folder = r"E:\beadandok\Halado-prog\kepek"
    output_folder = "kesz_kepek"

    while True:
        choice = menu()

        if choice == "1":
            w = int(input("Új szélesség: "))
            process_images(input_folder, output_folder, resize_width=w)

        elif choice == "2":
            angle = int(input("Forgatás szöge: "))
            process_images(input_folder, output_folder, rotate_angle=angle)

        elif choice == "3":
            print("Add meg: bal, fent, jobb, lent")
            b = int(input("bal: "))
            f = int(input("fent: "))
            j = int(input("jobb: "))
            l = int(input("lent: "))
            process_images(input_folder, output_folder, crop_box=(b, f, j, l))

        elif choice == "4":
            print("1: Blur, 2: Sharpen, 3: Fekete-fehér")
            f = input("Választás: ")
            filters = {"1": "blur", "2": "sharpen", "3": "bw"}
            process_images(input_folder, output_folder, filter_mode=filters.get(f))

        elif choice == "5":
            txt = input("Vízjel szövege: ")
            process_images(input_folder, output_folder, watermark_text=txt)

        elif choice == "6":
            print("Minden effekt egyszerre alkalmazva!")
            process_images(
                input_folder,
                output_folder,
                resize_width=800,
                rotate_angle=90,
                crop_box=None,
                filter_mode="sharpen",
                watermark_text="© MyProject"
            )

        elif choice == "0":
            exit()

        print("\n--- Folytatáshoz ENTER ---")
        input()
