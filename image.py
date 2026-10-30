import os
import sys
import json
import ssl
import uuid
import socket
import random
import urllib.request
import urllib.parse
from pathlib import Path
import requests
import websocket
from dotenv import load_dotenv

# Настройка UTF-8 для консоли Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# 1. Загрузка переменных окружения из .env
load_dotenv()

# Адрес сервера берется из переменной окружения COMFYUI_SERVER_ADDRESS
SERVER_ADDRESS = os.getenv("COMFYUI_SERVER_ADDRESS", "mrskele.tail5c1221.ts.net")

# Автоматический DNS-резолвер для хоста Tailscale, если в Windows не включен MagicDNS
orig_getaddrinfo = socket.getaddrinfo
def custom_getaddrinfo(host, port, *args, **kwargs):
    if host == "mrskele.tail5c1221.ts.net":
        host = "100.126.92.69"
    return orig_getaddrinfo(host, port, *args, **kwargs)
socket.getaddrinfo = custom_getaddrinfo


def generate_image(
    prompt: str = "Питер Гриффин",
    negative_prompt: str = "размыто, низкое качество, плохое лицо, артефакты",
    width: int = 512,
    height: int = 512,
    steps: int = 8,
    cfg: float = 1.0,
    seed: int | None = None,
    workflow_path: str | Path = "qwen_api.json",
    output_dir: str | Path = "data/images",
    filename_prefix: str = "result",
    server_address: str | None = None,
) -> list[str]:
    """
    Генерирует изображение через ComfyUI API с использованием WebSocket.
    Все параметры изображения и текста регулируются при вызове.

    :param prompt: Текстовый запрос для генерации (узел 4)
    :param negative_prompt: Отрицательный запрос (узел 5)
    :param width: Ширина изображения (узел 7)
    :param height: Высота изображения (узел 7)
    :param steps: Число шагов сэмплера (узел 6)
    :param cfg: Параметр CFG scale (узел 6)
    :param seed: Сид генерации (если None, генерируется случайный)
    :param workflow_path: Путь к файлу шаблона qwen_api.json
    :param output_dir: Папка для сохранения готовых изображений
    :param filename_prefix: Префикс имени сохраняемого файла
    :param server_address: Адрес сервера (по умолчанию из env: COMFYUI_SERVER_ADDRESS)
    :return: Список путей к сохранённым файлам изображений
    """
    server = server_address or os.getenv("COMFYUI_SERVER_ADDRESS", SERVER_ADDRESS)
    client_id = str(uuid.uuid4())

    # 1. Загружаем схему workflow
    workflow_file = Path(workflow_path)
    if not workflow_file.is_absolute():
        # Проверяем в текущей папке или рядом с этим скриптом
        script_dir_file = Path(__file__).parent / workflow_path
        if script_dir_file.exists():
            workflow_file = script_dir_file

    with open(workflow_file, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    # 2. Настраиваем регулируемые параметры
    # Промпт (узел 4)
    if "4" in workflow and "inputs" in workflow["4"]:
        workflow["4"]["inputs"]["text"] = prompt

    # Негативный промпт (узел 5)
    if "5" in workflow and "inputs" in workflow["5"] and negative_prompt is not None:
        workflow["5"]["inputs"]["text"] = negative_prompt

    # Размеры (узел 7)
    if "7" in workflow and "inputs" in workflow["7"]:
        if width is not None:
            workflow["7"]["inputs"]["width"] = width
        if height is not None:
            workflow["7"]["inputs"]["height"] = height

    # Сэмплер: шаги, cfg, сид (узел 6)
    if "6" in workflow and "inputs" in workflow["6"]:
        if steps is not None:
            workflow["6"]["inputs"]["steps"] = steps
        if cfg is not None:
            workflow["6"]["inputs"]["cfg"] = cfg
        workflow["6"]["inputs"]["seed"] = seed if seed is not None else random.randint(1, 10**15)

    print(f"[*] Отправка задачи в ComfyUI ({server})...")
    print(f"    Промпт: \"{prompt}\"")
    print(f"    Размер: {width}x{height}, Шагов: {steps}")

    # SSL-контекст для запросов через Tailscale HTTPS
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    # 3. Отправляем задачу в очередь
    p = {"prompt": workflow, "client_id": client_id}
    data = json.dumps(p).encode("utf-8")
    req = urllib.request.Request(
        f"https://{server}/prompt",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    prompt_res = json.loads(urllib.request.urlopen(req, context=ssl_ctx).read())
    prompt_id = prompt_res["prompt_id"]
    print(f"[+] Задача отправлена. ID: {prompt_id}. Ждем генерации через WebSocket...")

    # 4. Ждем завершения через WebSocket
    ws = websocket.WebSocket(sslopt={"cert_reqs": ssl.CERT_NONE})
    ws.connect(f"wss://{server}/ws?clientId={client_id}", timeout=120.0)

    try:
        while True:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message.get("type") == "executing":
                    data = message.get("data", {})
                    if data.get("node") is None and data.get("prompt_id") == prompt_id:
                        print("✅ Генерация завершена!")
                        break
    finally:
        ws.close()

    # 5. Получаем историю и скачиваем картинку
    history_resp = requests.get(f"https://{server}/history/{prompt_id}", verify=False)
    history = history_resp.json()
    prompt_history = history.get(prompt_id, {})

    saved_files = []
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for node_id, node_output in prompt_history.get("outputs", {}).items():
        if "images" in node_output:
            for image in node_output["images"]:
                fn = image["filename"]
                sub = urllib.parse.quote(image.get("subfolder", ""))
                img_type = urllib.parse.quote(image.get("type", "output"))
                url = f"https://{server}/view?filename={urllib.parse.quote(fn)}&subfolder={sub}&type={img_type}"
                
                dest_filename = f"{filename_prefix}_{fn}"
                save_path = out_dir / dest_filename

                try:
                    view_req = urllib.request.Request(url)
                    img_data = urllib.request.urlopen(view_req, context=ssl_ctx).read()
                    with open(save_path, "wb") as f_out:
                        f_out.write(img_data)
                    print(f"✅ Картинка сохранена: {save_path} ({len(img_data)} байт)")
                    saved_files.append(str(save_path))
                except Exception as e:
                    print(f"❌ Ошибка скачивания {fn}: {e}")

    return saved_files
