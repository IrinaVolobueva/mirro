from OpenSSL.rand import status
from django.contrib.auth.hashers import PBKDF2PasswordHasher
from django.core.signing import TimestampSigner
from django.db.models import Q
from django.http import JsonResponse, QueryDict
from django.middleware.csrf import get_token
from django.template.context_processors import request
from django.utils.encoding import force_str, force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import csrf_exempt
from mirro_api.models import User, Board, AccessToEdit, Shape, Like


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

        board = Board.objects.create(
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
            queryset = queryset.order_by('-total_like')

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

def qwe(request):
    user = is_auth(request)
    if not user:
        return JsonResponse({
            'code': 401,
            'message': 'Пользователь не авторизован'
        }, safe=False, status=401)

    # boards = Board.objects.all().values()
    # print(boards)
    # shapes = Shape.objects.all().select_related('fk_type').values('pk_shape', 'fk_board', 'fk_type', 'fk_type__title')
    # shapes.filter('fk_type__title' == 'circle')
    # shapes = Shape.objects.all()
    # shapes_list = list(shapes)
    # print(shapes_list)
    # shapes = Shape.objects.select_related('fk_type').filter(fk_type__title = 'circle').values('pk_shape', 'fk_board', 'fk_type', 'fk_type__title')
    # print(shapes)

    access_id = AccessToEdit.objects.filter(fk_board=2, fk_user = user, author = 1).select_related('fk_user').values()
    is_author = bool(access_id)
    print(is_author)
    return JsonResponse("QWE", safe=False)

def boards_id(request, pk_board):
    try:
        board = Board.objects.get(pk_board=pk_board)
    except Board.DoesNotExist:
        return JsonResponse({'code': 404, 'message': 'Ресурс не найден'}, safe=False, status=404)
    if request.method == 'GET':
        return JsonResponse({'code': 200,
            'data': {
                'id_board': board.pk_board,
                'title': board.title,
                'is_published': bool(board.is_published),
                'likes': board.total_like,
            }
        }, safe=False, status=200)
    user = is_auth(request)
    if not user:
        return JsonResponse({'code': 401, 'message': 'Пользователь не авторизован'}, safe=False, status=401)
    is_owner = AccessToEdit.objects.filter(fk_board = board, fk_user = user, author = 1).exists()
    if not is_owner:
        return JsonResponse({'code': 403, 'message': 'Недостаточно прав'}, safe=False, status=403)

    if request.method in ['PATCH', 'PUT']:
        put_data = QueryDict(request.body)
        title = put_data.get('title')
        is_published = put_data.get('is_published')
        error422 = {
            # 'errors': {},
            'code': 422,
            'message': 'Некорректные данные'
        }
        errors = {
            'title': [],
            'is_published': [],
        }
        if not title or title == ' ':
            errors['title'].append('Поле не должно быть пустым')
        if not is_published or is_published not in ['1', '0']:
            errors['is_published'].append("Поле не должно быть пустым и значения только 0 или 1")

        for key in list(errors.keys()):
            if not errors[key]:
                del errors[key]

        if errors:
            error422['errors'] = errors
            return JsonResponse(error422, safe=False, status=422)

        board.title = title
        board.is_published = is_published
        board.save()
        return JsonResponse({'code': 201, 'message':'Доска обновлена'}, safe=False, status=201)

    elif request.method == 'DELETE':
        Shape.objects.filter(fk_board = board).delete()
        AccessToEdit.objects.filter(fk_board = board).delete()
        Like.objects.filter(fk_board = board).delete()
        board.delete()
        return JsonResponse({'code':202, 'message': 'Удаление норм'}, safe=False, status=202)


def boards_id_accesses(request, pk_board):
    user = is_auth(request)
    if not user:
        return JsonResponse({'code': 401, 'message': 'Пользователь не авторизован'}, safe=False, status=401)

    try:
        board = Board.objects.get(pk_board=pk_board)
    except Board.DoesNotExist:
        return JsonResponse({'code': 404, 'message': 'Ресурс не найден'}, safe=False, status=404)

    # Общая проверка прав: действия с доступами разрешены ТОЛЬКО владельцу (author=1), return 403
    is_owner = AccessToEdit.objects.filter(fk_board=board, fk_user=user, author=1).exists()
    if not is_owner:
        return JsonResponse({'code': 403, 'message': 'Недостаточно прав'}, safe=False, status=403)

    if request.method == 'GET':
        # Получаем всех, у кого author=0 (соавторы)
        coauthors = AccessToEdit.objects.select_related('fk_user').filter(fk_board=board, author=0)
        coauthors_list = []
        for coauthor in coauthors:
            coauthors_list.append({
                'id_user': coauthor.fk_user.pk_user,
                'username': coauthor.fk_user.username,
                'email': coauthor.fk_user.email,
            })
        return JsonResponse({
            'code': 200,
            'message': 'Список соавторов получен',
            'data': coauthors_list
        }, safe=False, status=200)

    # # --- ДОБАВЛЕНИЕ СОАВТОРА (POST) ---
    elif request.method == 'POST':
        # Извлекаем target_email
        target_email = request.POST.get('email')
        try:
            user_target = User.objects.get(email=target_email)
        except User.DoesNotExist:
            return JsonResponse({'code': 404, 'message': 'Пользователь с таким email не найден'}, safe=False, status=404)
        # Проверяем, нет ли уже доступа у пользователя с target_email
        is_owner = AccessToEdit.objects.filter(fk_board=board, fk_user=user_target).exists()
        if is_owner: # return 422
           return JsonResponse({'code': 422, 'message': 'Доступ уже есть'}, safe=False, status=422)
        else:
            # Создаем запись соавтора (author=0)
            # return 201
            accessToEdit = AccessToEdit.objects.create(
                fk_user = user_target,
                fk_board = board,
                author=0
            )
            return JsonResponse({'code': 201, 'message': 'Доступ пользователю предоставлен'}, safe=False, status=201)

    elif request.method == 'DELETE':
        put_data = QueryDict(request.body)
        target_email = put_data.get('email')
        print(target_email)
        error422 = {
            # 'errors': {},
            'code': 422,
            'message': 'Некорректные данные'
        }
        errors = {
            'target_email': [],
        }
        if not target_email or target_email == '':
            errors['target_email'].append("Поле не должно быть пустым")

        for key in list(errors.keys()):
            if not errors[key]:
                del errors[key]

        if errors:
            error422['errors'] = errors
            return JsonResponse(error422, safe=False, status=422)

        if user.email == target_email:
            return JsonResponse({'code': 403, 'message': 'Нет прав'}, safe=False, status=403)

        try:
            user_target = User.objects.get(email=target_email)
        except User.DoesNotExist:
            return JsonResponse({'code': 404, 'message': 'Пользователь с таким email не найден'}, safe=False,
                                status=404)

        # Проверяем, что пользователь является соавтором (author=0)
        access_entry = AccessToEdit.objects.filter(
            fk_board_id=pk_board,
            fk_user=user_target,
            author=0
        ).first()

        if not access_entry:
            return JsonResponse({'code': 404, 'message': 'Соавтор не найден'}, safe=False, status=404)

        access_entry.delete()
        return JsonResponse({'code': 200, 'message': 'Соавтор удален'}, safe=False, status=200)


@csrf_exempt
def boards_id_likes(request, pk_board):
    # получаем пользователя
    user = is_auth(request)
    # Общая проверка авторизован ли пользователь, return 401
    if not user:
        return JsonResponse({'code': 401, 'message': 'Пользователь не авторизован'}, safe=False, status=401)
    # Общая проверка существует ли доска с таким id, return 404
    try:
        board = Board.objects.get(pk_board = pk_board)
    except Board.DoesNotExist:
        return JsonResponse({'code': 404, 'message': 'Ресурс не найден'}, safe=False, status=404)
    # --- ПОЛУЧЕНИЕ СПИСКА ЛАЙКНУВШИХ (GET) ---
    if request.method == 'GET':
    # Проверка прав: только владелец (author=1) видит список тех, кто лайкнул
        author = AccessToEdit.objects.filter(fk_user=user, author=1, fk_board=board).exists()
        if not author:
            # return 403
            return JsonResponse({
                'code': 403,
                'message': 'Недостаточно прав'
            }, safe=False, status=403)
    # Получаем всех пользователей из таблицы Like для этой доски
        likes = Like.objects.select_related('fk_user').filter(fk_board=board)
    # fk_user, fk_board, pk_like
        likes_list = []
        for like in likes:
            likes_list.append({
                'username': like.fk_user.username,
                'email': like.fk_user.email,
            })

        return JsonResponse({
            'code': 200,
            'message': 'Список пользователей поставивших лайки',
            'data': likes_list
        }, safe=False, status=200)

    # --- ДОБАВЛЕНИЕ ЛАЙКА (POST) ---
    elif request.method == 'POST':
        # Проверяем, не стоит ли лайк уже
        like = Like.objects.filter(fk_user=user, fk_board=board).exists()
        if like:
            return JsonResponse({'code': 422, 'message': 'Пользователь уже поставил лайк'}, safe=False, status=422)
        # Создаем лайк
        Like.objects.create(
            fk_user=user,
            fk_board=board
        )
        # Обновляем счетчик в доске
        board.total_like += 1
        board.save()
        # return 201
        return JsonResponse({
            'code': 201,
            'message': 'Лайк поставлен',
            'data': {
                'total_like': board.total_like
            }
        }, safe=False, status=201)

    # --- УДАЛЕНИЕ ЛАЙКА (DELETE) ---
    elif request.method == 'DELETE':
        try:
            like = Like.objects.filter(fk_user=user, fk_board=board)
        except Like.DoesNotExist:
            return JsonResponse({'code': 404, 'message': 'Не найдено'}, safe=False, status=404)
    # Ищем лайк именно от текущего пользователя
    # return 404
        like.delete()
        board.total_like -= 1
        board.save()
        return JsonResponse({'code': 200, 'message': 'Лайк удален'}, safe=False, status=200)
    # удаляем лайк
    # Уменьшаем счетчик (не уходя в минус)
    # return 200
