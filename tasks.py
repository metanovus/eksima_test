from app_celery import celery_app
from app_parser import parse_and_save_tenders
from logging_conf import logger

@celery_app.task
def parse_tenders_task(max_tenders: int = 10, output_file: str = "tenders.csv") -> str:
    """
    Задача Celery для запуска парсинга тендеров.

    :param max_tenders: максимальное количество тендеров для парсинга
    :param output_file: имя файла для сохранения результатов
    :return: строка с описанием завершения задачи и пути результата
    """
    logger.info(f"Начинается парсинг тендеров: max_tenders={max_tenders}, output_file={output_file}")
    try:
        result_file = parse_and_save_tenders(max_tenders=max_tenders, output_file=output_file)
        logger.info(f"Парсинг успешно завершён, результаты в файле: {result_file}")
    except Exception as e:
        logger.error(f"Парсер завершился с ошибкой: {e}")
        raise Exception(f"Парсер завершился с ошибкой: {e}")
    return f"Парсер завершён, результаты в {result_file}"
