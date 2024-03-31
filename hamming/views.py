from django.shortcuts import render
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes
from django.http import HttpResponse, JsonResponse
from hamming.coding import code_segment, decode_segment
from hamming.error_managing import lose_frame, insert_error, get_error_vector
import logging
import base64

# Create your views here.
logger = logging.getLogger(__name__)

SEGMENT_LEN = 120

request_data = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "user": openapi.Schema(type=openapi.TYPE_STRING),
        "datetime": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME),
        "number": openapi.Schema(type=openapi.TYPE_INTEGER),
        "segment": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_BASE64),
    }
)

@permission_classes([AllowAny])
@swagger_auto_schema(method='post', 
                     request_body=request_data,
                     responses={200: request_data, 400: ""},
)
@api_view(['Post'])
def code(request, segment_len=SEGMENT_LEN):
    """
    Кодирование и декодирование полученного от транспортного уровня сегмента
    """
    bin_len = 8 * segment_len
    bytes_segment = base64.b64decode(request.data["segment"])

    logger.warning(f'От транспортного уровня получили сегмент длиной {len(bytes_segment)} байт')

    bin_segment = bin(int.from_bytes(bytes_segment))[2::].rjust(960, "0")

    try:
        # получаем код сегмента из параметров запроса
        logger.warning(f'или {len(bin_segment)} бит:\n'
                       f' {bin_segment}')
        
        if len(bin_segment) != bin_len:
            raise Exception(f"segment length is not {segment_len * 8} bits")
        
        # кодирование для получения кадра
        frame = code_segment(bin_segment)
        logger.warning(f'Закодировали, получили кадр длиной {len(frame)}:\n'
                       f' {frame}')

        # получение возможной ошибки
        error_vector = get_error_vector(length=len(frame))
        if int(error_vector):
            logger.warning(f'Получили вектор ошибки: \n'
                           f'{error_vector}')
        else:
            logger.warning(f'Ошибки в кадре не будет')

        # внесение ошибки в кадр
        processed_frame = insert_error(frame, error_vector, length=len(frame))
        logger.warning(f'Наложили вектор ошибки, получили: '
                       f'{processed_frame}')

        # декодирование
        decoded_segment = decode_segment(processed_frame)
        logger.warning(f'Декодировали кадр, получили: '
                       f'{decoded_segment}')
        if bin_segment == decoded_segment:
            logger.warning(f'Сегмент сохранен в исходном виде')
        else:
            logger.warning(f'Сегмент изменился при обработке')
            logger.warning(f"Отличаются бит с индексом: {", ".join(bit_dif)}")



        bytes_decoded_segment = bytes(int(decoded_segment[i:(i + 8)], 2) 
                                      for i in range(0, len(decoded_segment), 8))
        logger.warning(f"Полученный сегмент в байтах: {bytes_decoded_segment}")
        bit_dif = [str(i) for i in range(0, len(bin_segment)) if bin_segment[i] != decoded_segment[i]]

        # возможная потеря кадра
        if lose_frame():
            raise Exception("frame loss")
        return JsonResponse(data={
            'user': request.data["user"],
            'datetime': request.data["datetime"],
            'number': request.data["number"],
            'segment': base64.b64encode(bytes_decoded_segment).decode('utf-8')
        }, status=200)
    
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return HttpResponse(content=None, status=400, reason=e)
