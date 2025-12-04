from drf_spectacular.utils import OpenApiResponse


BAD_REQUEST_RESPONSE = OpenApiResponse(
   response={
       'type': 'object',
       'properties': {
           'field_name': {'type': 'array', 'items': {'type': 'string', 'example': 'description'}}
       }
   },
   description='Bad Request'
)

UNAUTHORIZED_RESPONSE = OpenApiResponse(
   response={
       'type': 'object',
       'properties': {
           'detail': {'type': 'string', 'example': 'Учетные данные не были предоставлены.'}
       }
   },
   description='Unauthorized'
)

FORBIDDEN_RESPONSE = OpenApiResponse(
   response={
       'type': 'object',
       'properties': {
           'detail': {'type': 'string', 'example': 'У вас недостаточно прав для выполнения данного действия.'}
       }
   },
   description='Forbidden'
)

NOT_FOUND_RESPONSE = OpenApiResponse(
   response={
       'type': 'object',
       'properties': {
           'detail': {'type': 'string', 'example': 'No User matches the given query.'}
       }
   },
   description='Not Found'
)

INTERNAL_SERVER_ERROR = OpenApiResponse(
   response={
       'type': 'string'
   },
   description='Internal Server Error'
)
