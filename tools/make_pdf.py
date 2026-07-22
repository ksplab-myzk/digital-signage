from pdf2image import convert_from_path
import os
import sys

def load_pdf_as_images(pdf_path, output_dir, dpi=150):

    print("[START] Loading PDF:", pdf_path)

    # 出力フォルダがなければ作成
    os.makedirs(output_dir, exist_ok=True)
    
    pages = convert_from_path(pdf_path, dpi=dpi)
    total = len(pages)
    print(f"[INFO] {total} pages detected.")

    image_paths = []

    for i, page in enumerate(pages):
        out_path = os.path.join(output_dir, f"page_{i:03d}.png")
        print(f"[PAGE] {i+1} / {total} converting → {out_path}")
        page.save(out_path, "PNG")
        image_paths.append(out_path)

    print(f"[DONE] Generated {len(image_paths)} pages.")
    return image_paths

def main():
    if len(sys.argv) < 2:
        print("Usage: python pdf_convert.py input.pdf [output_folder]")
        return

    pdf_path = sys.argv[1]

    if not os.path.exists(pdf_path):
        print("Error: file not found:", pdf_path)
        return

    # 出力フォルダ指定があれば使う
    if len(sys.argv) >= 3:
        output_dir = sys.argv[2]
    else:
        # input.pdf → input_pages/
        base = os.path.splitext(os.path.basename(pdf_path))[0]
        output_dir = base + "_pages"

    print("[INFO] Converting:", pdf_path)
    print("[INFO] Output folder:", output_dir)

    try:
        images = load_pdf_as_images(pdf_path, output_dir)
    except Exception as e:
        print("[ERROR] Conversion failed:", e)
        return

    print("Done. Generated", len(images), "pages.")
    for img in images:
        print(" -", img)

if __name__ == "__main__":
    main()
