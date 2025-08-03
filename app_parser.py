import requests
from bs4 import BeautifulSoup
import re
import csv
import argparse
from logging_conf import logger
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from typing import List, Dict, Optional

url: str = "https://rostender.info/extsearch"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception_type(requests.RequestException))
def get_page_content(url_: str, params: Optional[Dict[str, str]] = None) -> str:
    """
    Выполняет HTTP GET запрос с повтором при ошибках.

    :param url_: URL страницы для запроса
    :param params: опциональные параметры запроса
    :return: текст ответа страницы
    :raises requests.RequestException: при неудачных попытках запроса
    """
    response = requests.get(url_, headers=headers, params=params)
    response.raise_for_status()
    response.encoding = 'utf-8'
    return response.text


def get_tender_urls(pages: int = 5) -> List[str]:
    """
    Собирает ссылки на тендеры со страниц сайта.

    :param pages: количество страниц для сканирования
    :return: список ссылок на тендеры
    """
    all_urls: List[str] = []
    for page in range(1, pages + 1):
        logger.info(f"[{page}/{pages}] Запрашиваю страницу {page} с тендерами")
        params = {"page": page}
        try:
            html = get_page_content(url, params=params)
            soup = BeautifulSoup(html, "html.parser")
            table_body = soup.find("div", class_="table-body")
            page_links_count = 0
            if table_body:
                for link in table_body.find_all("a", class_="description tender-info__description tender-info__link"):
                    href = link.get("href")
                    if href:
                        full_url = "https://rostender.info" + href
                        all_urls.append(full_url)
                        page_links_count += 1
                logger.info(
                    f"[{page}/{pages}] На странице найдено ссылок: {page_links_count}, всего накоплено ссылок: {len(all_urls)}")
            else:
                logger.warning(f"[{page}/{pages}] Не найден блок с таблицей тендеров на странице {page}")
        except Exception as e:
            logger.error(f"[{page}/{pages}] Ошибка при получении ссылок с страницы {page}: {e}")
    logger.info(f"Всего найдено ссылок: {len(all_urls)}")
    return all_urls


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception_type(requests.RequestException))
def get_tender_page(tender_url: str) -> str:
    """
    Получает HTML содержимое страницы с тендером.

    :param tender_url: URL страницы тендера
    :return: HTML текст страницы тендера
    :raises requests.RequestException: при ошибках запроса
    """
    resp = requests.get(tender_url, headers=headers)
    resp.raise_for_status()
    resp.encoding = 'utf-8'
    return resp.text


def parse_tender(tender_url: str, idx: int, total: int) -> Dict[str, Optional[str]]:
    """
    Парсит информацию о тендере со страницы.

    :param tender_url: URL страницы тендера
    :param idx: текущий индекс парсинга (для логов)
    :param total: общее количество тендеров
    :return: словарь с данными тендера
    """
    logger.info(f"[{idx}/{total}] Парсинг тендера {tender_url}")
    try:
        html = get_tender_page(tender_url)
        s = BeautifulSoup(html, "html.parser")
        tender_data: Dict[str, Optional[str]] = {}
        title_tag = s.find("h1")
        title_text = title_tag.text.strip() if title_tag else tender_url.split("/")[-1]
        if title_text.startswith("Тендер: "):
            title_text = title_text[len("Тендер: "):]
        tender_data["Тендер"] = title_text
        tender_data["Ссылка"] = tender_url
        tender_body = s.find("div", class_="tender-body")
        if tender_body:
            def get_text_after_label(label: str) -> Optional[str]:
                label_span = tender_body.find("span", string=label)
                if label_span:
                    next_span = label_span.find_next_sibling("span")
                    return next_span.get_text(separator=" ", strip=True) if next_span else None
                return None
            price_text = get_text_after_label("Начальная цена")
            if price_text:
                price_num = re.sub(r"[^\d]", "", price_text)
                tender_data["Начальная цена, руб."] = int(price_num) if price_num.isdigit() else None
            place_val = None
            place_span = tender_body.find("span", string="Место поставки")
            if place_span:
                place_field = place_span.find_next_sibling("span")
                if place_field:
                    parts = [pt.text.strip() for pt in place_field.find_all("span", class_="tender-info__text")]
                    a_text = ""
                    a = place_field.find("a", class_="tender-body__text")
                    if a:
                        a_text = " , " + a.text.strip()
                    place_val = ", ".join(parts) + a_text
            if place_val:
                tender_data["Место поставки"] = place_val
            organizer_text = get_text_after_label("Организатор закупки")
            if organizer_text:
                tender_data["Организатор закупки"] = (
                    "Доступно после регистрации" if "доступно после" in organizer_text.lower() else organizer_text
                )
            end_span = tender_body.find("span", string="Окончание (МСК)")
            if end_span:
                end_field = end_span.find_next_sibling("span")
                if end_field:
                    date_span = end_field.find("span", class_="black")
                    time_span = end_field.find("span", class_="tender__countdown-container")
                    if date_span and time_span:
                        tender_data["Окончание"] = f"{date_span.text.strip()} {time_span.text.strip()}"
                    elif date_span:
                        tender_data["Окончание"] = date_span.text.strip()
            placement_span = tender_body.find("span", string=re.compile("Способ размещения", re.I))
            if placement_span:
                placement_field = placement_span.find_next_sibling("span")
                if placement_field:
                    texts = [c.text.strip() for c in placement_field.children if hasattr(c, "text") and c.text.strip()]
                    tender_data["Способ размещения"] = ", ".join(texts)
            restrictions_span = tender_body.find("span", string="Ограничения и запреты")
            if restrictions_span:
                restrictions_field = restrictions_span.find_next_sibling("span")
                if restrictions_field:
                    lis = restrictions_field.find_all("li")
                    if lis:
                        restrictions = " ".join(f"{i}. {li.text.strip()}" for i, li in enumerate(lis, 1))
                    else:
                        restrictions = restrictions_field.get_text(separator=" ", strip=True)
                    if restrictions:
                        tender_data["Требования и преимущества"] = "Ограничения и запреты: " + restrictions
            sector_span = tender_body.find("span", string=lambda t: t and "Отрасль" in t)
            if sector_span:
                parent = sector_span.find_parent(class_="tender-body__block")
                if parent:
                    next_blk = parent.find_next_sibling(class_="tender-body__block")
                    if next_blk:
                        sector_field = next_blk.find("span", class_="tender-body__field")
                        if sector_field:
                            lis = sector_field.find_all("li")
                            sectors = []
                            for i, li in enumerate(lis, 1):
                                a = li.find("a")
                                if a:
                                    txt = re.sub(r"\s+", " ", a.text.strip())
                                    sectors.append(f"{i}. {txt}")
                            if sectors:
                                tender_data["Отрасль"] = ", ".join(sectors)
            source_label = tender_body.find("span", string=lambda t: t and "Ссылки на источники" in t)
            if source_label:
                blk = source_label.find_parent("div", class_="tender-body__block")
                if blk:
                    source_field = blk.find("span", class_="tender-body__field")
                    if source_field:
                        text = source_field.get_text(separator=" ", strip=True)
                        tender_data["Ссылки на источники"] = text
        logger.info(f"[{idx}/{total}] Успешно распарсил тендер: {tender_data.get('Тендер')}")
        return tender_data
    except Exception as e:
        logger.error(f"[{idx}/{total}] Ошибка при парсинге тендера {tender_url}: {e}")
        return {}


def save_to_csv(tenders: List[Dict[str, Optional[str]]], filename: str = "tenders.csv") -> None:
    """
    Сохраняет список тендеров в CSV файл.

    :param tenders: список словарей с данными тендеров
    :param filename: имя выходного CSV файла
    """
    if not tenders:
        logger.warning("Нет данных для записи в CSV")
        return
    keys = sorted({key for tender in tenders for key in tender.keys()})
    try:
        with open(filename, mode='w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for tender in tenders:
                writer.writerow(tender)
        logger.info(f"Данные успешно сохранены в файл {filename}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении файла {filename}: {e}")


def parse_and_save_tenders(max_tenders: int = 10, output_file: str = "tenders.csv") -> str:
    """
    Основная функция для парсинга тендеров с сайта и сохранения в файл.

    :param max_tenders: максимальное количество тендеров для парсинга
    :param output_file: имя файла для сохранения результатов
    :return: имя файла с сохранёнными результатами
    """
    tenders_per_page = 20
    pages_needed = (max_tenders + tenders_per_page - 1) // tenders_per_page
    logger.info(f"Начинаю сбор ссылок (будем парсить максимум {max_tenders} тендеров, значит, нужно страниц: {pages_needed})")
    urls = get_tender_urls(pages=pages_needed)
    if max_tenders > 0:
        urls = urls[:max_tenders]
    total = len(urls)
    logger.info(f"Начинаю парсинг {total} тендеров")
    all_tenders: List[Dict[str, Optional[str]]] = []
    for i, url_ in enumerate(urls, start=1):
        tender_data = parse_tender(url_, i, total)
        all_tenders.append(tender_data)
    save_to_csv(all_tenders, filename=output_file)
    logger.info("Парсинг завершён")
    return output_file


def main() -> None:
    """
    Точка входа для запуска скрипта из командной строки.
    Парсит аргументы и запускает процесс парсинга.
    """
    parser = argparse.ArgumentParser(description="Парсер тендеров с rostender.info")
    parser.add_argument('--max', type=int, default=10, help="Сколько последних тендеров парсить (по умолчанию 10)")
    parser.add_argument('--output', type=str, default="tenders.csv",
                        help="Имя файла для сохранения (по умолчанию tenders.csv)")
    args = parser.parse_args()
    parse_and_save_tenders(max_tenders=args.max, output_file=args.output)

if __name__ == "__main__":
    main()
