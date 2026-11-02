"""
Check connectivity and health of AI inference services (Ollama and ComfyUI) over Tailscale.
Run:
    python check_services.py
"""
import sys
import httpx
from server.core import config

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

def check_ollama():
    print("=" * 60)
    print(f"1. ПРОВЕРКА OLLAMA (Генерация текста):")
    print(f"   URL: {config.QWEN_API_URL}")
    print(f"   Модель: {config.QWEN_TEXT_MODEL}")
    print("-" * 60)

    base_url = config.QWEN_API_URL.rsplit("/", 2)[0] # http://100.126.92.69:11434
    
    # 1. Проверка доступности сервиса и моделей
    try:
        r = httpx.get(f"{base_url}/api/tags", timeout=5.0)
        if r.status_code == 200:
            models = [m.get("name") for m in r.json().get("models", [])]
            print(f"   [+] Ollama доступна! HTTP 200")
            print(f"   [+] Доступные модели: {models}")
            if any(config.QWEN_TEXT_MODEL in m for m in models):
                print(f"   [+] Модель '{config.QWEN_TEXT_MODEL}' найдена!")
            else:
                print(f"   [!] Внимание: Модель '{config.QWEN_TEXT_MODEL}' не найдена в списке {models}")
        else:
            print(f"   [-] Ollama ответила с кодом: {r.status_code}")
            return
    except Exception as e:
        print(f"   [-] Ошибка подключения к Ollama ({base_url}): {e}")
        return

    # 2. Тестовая генерация
    print("   [*] Отправка тестового промпта...")
    payload = {
        "model": config.QWEN_TEXT_MODEL,
        "prompt": "Привет! Ответь одним коротким предложением: ты готов вести D&D?",
        "stream": False
    }
    try:
        r = httpx.post(config.QWEN_API_URL, json=payload, timeout=config.QWEN_TIMEOUT)
        r.raise_for_status()
        answer = r.json().get("response", "").strip()
        print(f"   [+] Генерация текста УСПЕШНА!")
        print(f"   Ответ модели:\n   >>> \"{answer}\"")
    except Exception as e:
        print(f"   [-] Ошибка при генерации текста: {e}")

def check_comfyui():
    print("\n" + "=" * 60)
    print(f"2. ПРОВЕРКА COMFYUI (Генерация картинок):")
    print(f"   URL: {config.COMFYUI_API_URL}")
    print(f"   Модель: {config.QWEN_IMAGE_MODEL}")
    print("-" * 60)

    # Вспомогательный сокет-резолвер для Tailscale MagicDNS, если системный DNS не настроен
    import socket
    orig_getaddrinfo = socket.getaddrinfo
    def custom_getaddrinfo(host, port, *args, **kwargs):
        if host == "mrskele.tail5c1221.ts.net":
            host = "100.126.92.69"
        return orig_getaddrinfo(host, port, *args, **kwargs)
    socket.getaddrinfo = custom_getaddrinfo

    try:
        r = httpx.get(f"{config.COMFYUI_API_URL}/system_stats", timeout=10.0, verify=False)
        if r.status_code == 200:
            stats = r.json()
            devices = stats.get("devices", [])
            comfy_ver = stats.get("system", {}).get("comfyui_version", "unknown")
            print(f"   [+] ComfyUI доступен! HTTP 200 (Версия: {comfy_ver})")
            for dev in devices:
                print(f"   [+] Устройство: {dev.get('name')} (VRAM: {dev.get('vram_total', 0) // (1024*1024)} MB)")
        else:
            print(f"   [-] ComfyUI ответил с кодом: {r.status_code}")
    except httpx.ConnectTimeout:
        print(f"   [-] Таймаут соединения: ComfyUI не отвечает по адресу {config.COMFYUI_API_URL}.")
    except httpx.ConnectError as e:
        print(f"   [-] Ошибка соединения: {e}")
    except Exception as e:
        print(f"   [-] Ошибка подключения: {e}")
    finally:
        socket.getaddrinfo = orig_getaddrinfo

def check_backend_api():
    print("\n" + "=" * 60)
    print("3. ПРОВЕРКА ЛОКАЛЬНОГО FASTAPI СЕРВЕРА:")
    print("   URL: http://127.0.0.1:8000/api/health")
    print("-" * 60)
    try:
        r = httpx.get("http://127.0.0.1:8000/api/health", timeout=3.0)
        if r.status_code == 200:
            print("   [+] Локальный сервер Neuro-DnD запущен и работает (HTTP 200).")
        else:
            print(f"   [!] Сервер ответил с кодом: {r.status_code}")
    except Exception:
        print("   [i] Локальный сервер пока не запущен (запустите run_dev.bat при необходимости).")

if __name__ == "__main__":
    check_ollama()
    check_comfyui()
    check_backend_api()
    print("\n" + "=" * 60)
