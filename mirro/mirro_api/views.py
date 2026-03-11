from django.contrib.auth.hashers import PBKDF2PasswordHasher
from django.core.signing import TimestampSigner
from django.db.models import Q
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.template.context_processors import request
from django.utils.encoding import force_str, force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from mirro.mirro_api.models import User, Board, AccessToEdit


def get_xcsrf(request):
    data = {
        'X-CSRFToken': get_token(request)
    }
    return JsonResponse(data, safe=False, status=200)

def is_auth(request):
    if not request.headers.get('Authorization'):
        return False
    token = request.headers.get('Authorization').split(' ')[-1]
    signer = TimestampSigner(salt='django.core.signing')
    try:
        email = signer.unsign(force_str(urlsafe_base64_decode(token)), max_age=1000)
    except:
        return False
    else:
        user = User.objects.get(email=email)
        return user

def users(request):
    if request.method == 'POST':
        if is_auth(request):
            return JsonResponse({'code': 403, 'message': 'Доступ запрещён'}, safe=False, status=403)
        data = {
            # 'user': {},
        }
        error422 = {
            # 'errors': {},
            'code': 422,
            'message': 'Некорректные данные'
        }
        errors = {
            'username': [],
            'email': [],
            'password': [],
        }

        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')

        # ОШИБКИ
        if not username or username == ' ':
            errors['username'].append('Поле не должно быть пустым')
        elif not username.isalpha() or not username.isascii():
            errors['username'].append('Поле должно содержать только латиницу')

        if not password or password == ' ':
            errors['password'].append('Поле не должно быть пустым')
        elif len(password) < 8 or not any(not char.isalnum() for char in password) or not any(char.isdigit() for char in password):
            errors['password'].append('Пароль должен быть больше 8 символов, должен содержать спецсимволы и цифры')

        if not email or email == ' ':
            errors['email'].append('Поле не должно быть пустым')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            user = None
        if user:
            errors['email'].append('Пользователь с таким email уже существует')

        for key in list(errors.keys()):
            if not errors[key]:
                del errors[key]

        if errors:
            error422['errors'] = errors
            return JsonResponse(error422, safe=False, status=422)

        hasher = PBKDF2PasswordHasher()
        hash_password = hasher.encode(password, salt='extra')
        user = User(username=username, email=email, password=hash_password)
        user.save()

        data['user'] = {
            'username': user.username,
            'email': user.email,
        }
        return JsonResponse({'code': 201, 'message': 'Пользователь добавлен', 'data': data}, safe=False, status=201)



def auth(request):
    if request.method == 'POST':
        if is_auth(request):
            return JsonResponse({'code': 403, 'message': 'Доступ запрещён'}, safe=False, status=403)

    data = {
        # 'user': {},
        # 'token': {},
    }
    error422 = {
        # 'errors':{},
        'code': 422,
        'message': 'Некорректные данные',
    }
    errors = {
        'email': [],
        'password': [],
    }

    email = request.POST.get('email')
    password = request.POST.get('password')

    if not email or ' ' in email:
        errors['email'].append('Поле не должно быть пустым')
    if not password or ' ' in password:
        errors['password'].append('Поле не должно быть пустым')

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        user = None

    if not user:
        errors['email'].append('Пользователь с таким email не существует')

    for key in list(errors.keys()):
        if not errors[key]:
            del errors[key]

    if errors:
        error422['errors'] = errors
        return JsonResponse(error422, safe=False, status=422)

    hasher = PBKDF2PasswordHasher()
    if not hasher.verify(password, user.password):
        return JsonResponse({'code': 401, 'message': 'Пользователь не авторизован'}, safe=False, status=401)

    data['user'] = {
        'id_user': user.pk_user,
        'username': user.username,
        'email': user.email,
    }
    signer = TimestampSigner(salt='django.core.signing')
    token = urlsafe_base64_encode(force_bytes(signer.sign(user.email)))
    data['token'] = token

    return JsonResponse({'code': 200, 'data': data}, safe=False, status=200)


def boards(request):
    user = is_auth(request)
    if request.method == "POST":
        if not user:
            return JsonResponse({'code': 401,'message': 'Пользователь не авторизирован'}, safe=False, status=401)

        title = request.POST.get('title')
        if not title or title.strip() == '':
            return JsonResponse({'code': 422, 'message':'Поле не должен быть пустым'}, safe=False, status=422)

        board = Board.object.create(
            title = title,
            is_published = 0,
            total_like = 1,
        )
        AccessToEdit.objects.create(
            author = 1,
            fk_user = user,
            fk_board = board
        )
        return JsonResponse({
            'code': 201,
            'message': 'Доска создана',
            'data': {
                'id_board': board.pk_board
            }
        }, safe=False, status=201)

    elif request.method == 'GET':
        if not user:
            return JsonResponse({'code': 401,'message': 'Пользователь не авторизирован'}, safe=False, status=401)

        filter_param = request.POST.get('filter', 'published')
        accessed_ids = AccessToEdit.objects.filter(fk_user = user).values_list('fk_board', flat=True)

        if filter_param == 'all':
            # доски, которые публичные или к которым есть доступ у пользователя, при чем авторство или соавторство
            queryset = Board.objects.filter(Q(is_published = 1) | Q(pk_board__in = accessed_ids))
        elif filter_param == 'accessed': # доски, к которым есть доступ (автор/соавтор)
            queryset = Board.objects.filter(pk_board__in = accessed_ids)
        else: # только публичные
            queryset = Board.objects.filter(is_published = 1)

        if request.GET.get('sort') == 'likes':
            queryset = queryset.order_by('-total_likes')

        boards_list = []

        for board in queryset:
            ower_entry = AccessToEdit.objects.filter(fk_board = board, author = 1).select_related('fk_user').first()
            boards_list.append({
                'id_board': board.pk_board,
                'title': board.title,
                'likes': board.total_like,
                'is_published': bool(board.is_published),
                'username': ower_entry.fk_user.username,
            })

        return JsonResponse({'data':boards_list}, safe=False, status=200)