from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from tasks import parse_tenders_task
from celery.result import AsyncResult
import csv
import os
from logging_conf import logger
from typing import List, Dict, Any

app = FastAPI()
app.mount("/static", StaticFiles(directory="frontend"), name="static")

CSV_FILE_PATH: str = "tenders.csv"

def read_csv_to_json(csv_path: str) -> List[Dict[str, Any]]:
    """
    Считывает содержимое CSV файла и возвращает как список словарей.

    :param csv_path: путь к CSV файлу
    :return: список записей в виде словарей
    :raises FileNotFoundError: если файл не найден по указанному пути
    """
    if not os.path.exists(csv_path):
        logger.error(f"Файл для чтения не найден: {csv_path}")
        raise FileNotFoundError(f"Файл {csv_path} не найден.")

    with open(csv_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        data = list(reader)
    logger.info(f"Успешно считаны данные из файла {csv_path}")
    return data

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/tenders/")
async def get_tenders() -> JSONResponse:
    """
    Эндпоинт для получения списка тендеров из CSV файла.

    :return: JSON с данными тендеров
    :raises HTTPException 404: если файл не найден
    :raises HTTPException 500: при ошибках сервера или чтения данных
    """
    try:
        tenders_data = read_csv_to_json(CSV_FILE_PATH)
        logger.info(f"Отправляю данные тендеров, всего записей: {len(tenders_data)}")
        return JSONResponse(content=tenders_data)
    except FileNotFoundError as fnf_err:
        logger.warning(f"Ошибка при запросе тендеров: {fnf_err}")
        raise HTTPException(status_code=404, detail=str(fnf_err))
    except Exception as exc:
        logger.error(f"Ошибка сервера при запросе тендеров: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {exc}")

@app.post("/parse/")
async def start_parse(max: int = 10) -> Dict[str, Any]:
    """
    Запускает задачу асинхронного парсинга тендеров через Celery.

    :param max: максимальное количество тендеров для парсинга
    :return: словарь с ID задачи и статусом запуска
    """
    logger.info(f"Запущена задача парсинга тендеров, max: {max}")
    task = parse_tenders_task.delay(max)
    logger.info(f"Задача парсинга отправлена в очередь, task_id: {task.id}")
    return {"task_id": task.id, "status": "started"}

@app.get("/status/{task_id}")
async def get_status(task_id: str) -> Dict[str, Any]:
    """
    Получает статус и результат выполнения задачи парсинга по task_id.

    :param task_id: идентификатор задачи Celery
    :return: словарь с информацией о статусе и результате выполнения
    """
    task_result = AsyncResult(task_id)
    logger.info(f"Запрошен статус задачи {task_id}: {task_result.status}")
    return {"task_id": task_id, "status": task_result.status, "result": task_result.result}
