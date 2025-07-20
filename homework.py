import os
import sys
import requests
import logging
import time
import exceptions
from http import HTTPStatus
from logging import StreamHandler
from telebot import TeleBot
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler(stream=sys.stdout)
formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверка доступности переменных окружения."""
    if (PRACTICUM_TOKEN is None
            or TELEGRAM_TOKEN is None or TELEGRAM_CHAT_ID is None):
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение через Бота Telegram."""
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logger.debug('Cообщение в Telegram было отправлено')


def get_api_answer(current_timestamp):
    """Запрос к ENDPOINT API-Яндекс.Практикум.Домашка."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception as error:
        message = f'Эндпоинт {ENDPOINT} недоступен: {error}'
        logger.error(message)
        raise exceptions.GetAPIAnswerException(message)
    if homework_statuses.status_code != HTTPStatus.OK:
        message = f'Код ответа API: {homework_statuses.status_code}'
        logger.error(message)
        raise exceptions.GetAPIAnswerException(message)
    try:
        return homework_statuses.json()
    except Exception as error:
        message = f'Ошибка преобразования к формату json: {error}'
        logger.error(message)
        raise exceptions.GetAPIAnswerException(message)


def check_response(response):
    """Проверяет корректность ответа API и возвращает список домашних работ."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не словарь')
    check_list_homeworks = response.get('homeworks')
    if check_list_homeworks is None:
        raise KeyError('Ключ "homeworks" не доступен')
    if not isinstance(check_list_homeworks, list):
        raise TypeError('Ответ API  оключу "homeworks" не список')
    if len(check_list_homeworks) > 0:
        return check_list_homeworks
    else:
        logger.debug('В текущей проверке новые статусы ДЗ отсутсвуют')


def parse_status(homework):
    """Извлекает из информации о конкретном ДЗ его статус."""
    if 'homework_name' not in homework:
        message = 'Ключ homework_name недоступен'
        logger.error(message)
        raise KeyError(message)
    if 'status' not in homework:
        message = 'Ключ status недоступен'
        logger.error(message)
        raise KeyError(message)
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        message = \
            f'Передан неизвестный статус домашней работы "{homework_status}"'
        logger.error(message)
        raise exceptions.ParseStatusException(message)


def main():
    """Основная логика работы бота."""
    logger.info('Вы запустили Бота')

    if check_tokens() is False:
        er_txt = (
            'Обязательные переменные окружения отсутствуют. '
            'Принудительная остановка Бота'
        )
        logger.critical(er_txt)
        return None

    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            # Делаем запрос
            response = get_api_answer(timestamp)
            # Если запрос ожидаемый словарь, бывший json:
            if isinstance(response, dict):
                check_response_hw = check_response(response)
                if isinstance(check_response_hw, list):
                    for hw in check_response_hw:
                        if isinstance(response, dict):
                            # Извлекаем статус домашки
                            message = parse_status(hw)
                            send_message(bot, message)
                        else:
                            logger.error('Домашняя работа не словарь')
            else:
                logger.error('Ответ API.Ya не корректен')
            # Берем дату из запроса для следующей провекри статусов ДЗ
            timestamp = response.get('current_date')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
