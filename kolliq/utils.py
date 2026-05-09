from rest_framework.views import exception_handler
from rest_framework.response import Response


def custom_exception_handler(exc, context):
    """
    Wraps all DRF errors in our standard envelope:
    { success, data, error, code }
    """
    response = exception_handler(exc, context)

    if response is not None:
        response.data = {
            'success': False,
            'data': None,
            'error': response.data,
            'code': response.status_code,
        }

    return response


def success_response(data=None, status=200):
    from rest_framework.response import Response
    return Response({
        'success': True,
        'data': data,
        'error': None,
        'code': status,
    }, status=status)


def error_response(error, status=400):
    from rest_framework.response import Response
    return Response({
        'success': False,
        'data': None,
        'error': error,
        'code': status,
    }, status=status)