"""
Full End-to-End Test for Neuro-DnD AI Pipeline:
1. Generates text narrative via Ollama (Qwen Text)
2. Generates scene image via ComfyUI (Qwen Image 2.1 Turbo) over Tailscale
Run:
    python test_full_pipeline.py
"""
import sys
import os
import json
import time
import random
import socket
import urllib.parse
import httpx

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from server.core import config

# Automatic DNS resolution for Tailscale hostname
orig_getaddrinfo = socket.getaddrinfo
def custom_getaddrinfo(host, port, *args, **kwargs):
    if host == "mrskele.tail5c1221.ts.net":
        host = "100.126.92.69"
    return orig_getaddrinfo(host, port, *args, **kwargs)
socket.getaddrinfo = custom_getaddrinfo

def generate_text(prompt_text: str) -> str:
    print("\n" + "=" * 60)
    print("1. ГЕНЕРАЦИЯ ТЕКСТА (Ollama - Qwen Text)")
    print("=" * 60)
    print(f"Промпт: \"{prompt_text}\"")
    print("Отправка в Ollama...")

    payload = {
        "model": config.QWEN_TEXT_MODEL,
        "prompt": prompt_text,
        "stream": False
    }

    t0 = time.time()
    r = httpx.post(config.QWEN_API_URL, json=payload, timeout=config.QWEN_TIMEOUT)
    r.raise_for_status()
    elapsed = time.time() - t0

    answer = r.json().get("response", "").strip()
    print(f"[+] Ответ получен за {elapsed:.1f} сек:")
    print(f">>> {answer}")
    return answer

def generate_image(prompt_text: str, output_filename: str = "scene.png") -> str:
    print("\n" + "=" * 60)
    print("2. ГЕНЕРАЦИЯ КАРТИНКИ (ComfyUI - Qwen Image 2.1 Turbo)")
    print("=" * 60)
    print(f"Промпт для изображения: \"{prompt_text}\"")

    template_path = os.path.join(os.path.dirname(__file__), "comfy_workflow_template.json")
    with open(template_path, "r", encoding="utf-8") as f:
        wf = json.load(f)

    # Настраиваем параметры генерации под D&D сцену
    wf["4"]["inputs"]["text"] = prompt_text
    wf["5"]["inputs"]["text"] = "blurry, low quality, distorted, artifacts, bad anatomy, text, watermark"
    wf["6"]["inputs"]["seed"] = random.randint(1, 1000000000)
    wf["6"]["inputs"]["steps"] = 12  # Для Turbo модели 10-14 шагов оптимально
    wf["7"]["inputs"]["width"] = 768
    wf["7"]["inputs"]["height"] = 768
    wf["9"]["inputs"]["filename_prefix"] = "NeuroDnD_Scene"

    timeout = httpx.Timeout(connect=30.0, read=180.0, write=30.0, pool=30.0)

    print("Отправка задания в ComfyUI...")
    t0 = time.time()
    with httpx.Client(timeout=timeout, verify=False) as client:
        r = client.post(
            f"{config.COMFYUI_API_URL}/prompt",
            json={"prompt": wf, "client_id": "neuro_dnd_test"}
        )
        r.raise_for_status()
        prompt_id = r.json().get("prompt_id")
        print(f"[+] Задание принято, Prompt ID: {prompt_id}")
        print("Ожидание генерации на RTX 5070...")

        # Ожидание результата
        for _ in range(40):
            time.sleep(2.5)
            hist_r = client.get(f"{config.COMFYUI_API_URL}/history/{prompt_id}")
            hist = hist_r.json()
            if prompt_id in hist:
                outputs = hist[prompt_id].get("outputs", {})
                for node_id, out_data in outputs.items():
                    if "images" in out_data and out_data["images"]:
                        img_info = out_data["images"][0]
                        fn = img_info["filename"]
                        subfolder = img_info.get("subfolder", "")
                        img_type = img_info.get("type", "output")
                        
                        view_url = (
                            f"{config.COMFYUI_API_URL}/view"
                            f"?filename={urllib.parse.quote(fn)}"
                            f"&subfolder={urllib.parse.quote(subfolder)}"
                            f"&type={img_type}"
                        )
                        img_bytes = client.get(view_url).content
                        
                        out_path = config.IMAGES_DIR / output_filename
                        with open(out_path, "wb") as f_out:
                            f_out.write(img_bytes)

                        elapsed = time.time() - t0
                        print(f"[+] Картинка сгенерирована и сохранена за {elapsed:.1f} сек!")
                        print(f"[+] Путь к файлу: {out_path} ({len(img_bytes)} байт)")
                        return str(out_path)
            print("...", end="", flush=True)

    raise TimeoutError("Превышено время ожидания генерации изображения.")

if __name__ == "__main__":
    print("\n--- ЗАПУСК КОМПЛЕКСНОГО ТЕСТА (ТЕКСТ + КАРТИНКА) ---")
    
    # 1. Тест текста
    dnd_prompt = "Опиши кратко в 2 предложениях появление древнего красного дракона в пещере с сокровищами для игрока D&D."
    story = generate_text(dnd_prompt)

    # 2. Тест картинки
    image_prompt = "huge red dragon breathing smoke, sitting on gold treasure hoard in dark crystalline cavern, epic fantasy, dnd concept art, cinematic lighting, 8k"
    saved_img = generate_image(image_prompt, output_filename="dragon_treasure.png")

    print("\n" + "=" * 60)
    print("ИТОГ: ВСЕ СИСТЕМЫ ИНФЕРЕНСА (ТЕКСТ И КАРТИНКИ) РАБОТАЮТ ИДЕАЛЬНО!")
    print(f"Текст:\n{story}")
    print(f"\nФайл изображения:\n{saved_img}")
    print("=" * 60)
