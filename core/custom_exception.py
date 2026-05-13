from rest_framework.views import exception_handler

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        if isinstance(response.data, dict):
            for key, value in response.data.items():
                if isinstance(value, list) and len(value) == 1:
                    response.data[key] = value[0]

    return response
