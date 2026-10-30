"""
Dedicated test for image generation module (image.py).
Run:
    python tests/test_image.py
"""
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from image import generate_image

def test_image_generation():
    print("Testing image generation via ComfyUI...")
    paths = generate_image(
        prompt="D&D fantasy hero warrior, portrait, concept art",
        negative_prompt="blurry, low quality, bad anatomy, artifacts",
        width=512,
        height=512,
        steps=8,
        output_dir="data/images",
        filename_prefix="test_hero"
    )
    assert len(paths) > 0, "No image was generated"
    assert os.path.exists(paths[0]), f"Generated file {paths[0]} does not exist"
    print(f"OK! Generated file: {paths[0]}")

if __name__ == "__main__":
    test_image_generation()
