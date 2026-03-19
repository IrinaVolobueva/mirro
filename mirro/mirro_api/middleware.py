from channels.db import database_sync_to_async
from django.core.signing import TimestampSigner
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode

from mirro_api.models import User


@database_sync_to_async
def get_user(token):
    signer = TimestampSigner(salt = 'django.core.signing')
    try:
        email = signer.unsign(force_str(urlsafe_base64_decode(token)), max_age=10000)
    except:
        return False
    else:
        user = User.objects.get(email=email)
        return user

class TokenAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b"").decode('utf-8')
        token = None
        for param in query_string.split('&'):
            if param.starswith('token='):
                token = param.split('=')[1]
                break
        if token:
            scope['user'] = await get_user(token)
        else:
            scope['user'] = False
        return await self.inner(scope, receive, send)