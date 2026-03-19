from channels.generic.websocket import AsyncWebsocketConsumer


class BoardConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        # Сохраняем нашего авторизованного user'а:
        self.user = self.scope["user"]
        # Получаем id_board из URLа (/ws/boards/<id_board>/)
        self.id_board = int(...)
        # Проверяем наличие доски с таким id_board (вынести в функцию, поскольку идет обращение к БД, декоратор @database_sync_to_async)

        # Если нет доски, то:
        await self.close()
        return

    # Если есть доска, то:
    # Сохраняем в self.scope, чтоб каждый раз не лезть в receive
    self.scope["exists"] = ...

    # Конструируем имя ГРУППЫ КАНАЛОВ этой ДОСКИ

    # Проверяем, есть ли у пользователя доступ к доске И какое право доступа "can_edit"/"can_view"//"нет доступа" (вынести в функцию, поскольку идет обращение к БД, декоратор @database_sync_to_async)

    # Если доступа нет, то:
    # Закрываем соединение

    # Если есть доступ, то:
    # Сохраняем право на редактирование в scope, чтобы не лезть в БД каждый раз в receive
    self.scope["can_edit"] = ...
    self.scope["can_view"] = ...

    # Добавляем текущее клиентское соединение(channel_name) в ГРУППУ КАНАЛОВ ДОСКИ, чтобы текущее соединение получало все сообщения, отправленные в группу

    # Принимаем WebSocket соединение:
    await self.accept()

    # Получаем все существующие фигуры на доске из БД (вынести в функцию, поскольку идет обращение к БД, декоратор @database_sync_to_async)

    # Отправляем ТОЛЬКО текущему клиентскому соединению (не всей группе каналов) состояние доски
    await self.send(text_data=json.dumps({
        "shapes": shapes,
        "id_board": self.id_board,
        "shapes": shapes,
        "exists": self.scope["exists"],
        "can_edit": self.scope["can_edit"],
        "can_view": self.scope["can_view"],
    }))


async def disconnect(self, close_code):
    # Проверяем, была ли инициализирована ГРУППА КАНАЛОВ ДОСКИ:
    if hasattr(self, 'board_group_name'):


# Удаляем текущее соединение (channel_name) из ГРУППЫ КАНАЛОВ ДОСКИ

async def receive(self, json_data):
    """
    Обработчик входящих сообщений от клиентских подключений.
    В каждом сообщении от клиентского соединения будет action

    """
    # Парсим полученный JSON
    data = json.loads(json_data)
    action = data.get('action')

    # Маршрутизация действий к соответствующим action'ам
    if action == 'grab_shape':  # захват фигуры
        await self.grab_shape(data)
    elif action == 'release_shape':  # освобождение фигуры
        await self.release_shape(data)


async def grab_shape(self, data):
    id_shape = data['id_shape']

    # Рассылаем в ГРУППУ КАНАЛОВ ДОСКИ: "Юзер X захватил фигуру Y"
    await self.channel_layer.group_send(
        self.room_group_name,
        {
            "type": "shape_focus",  # !!!!! Важно: это имя метода, который будет вызван
            "id_shape": id_shape,
            "name": self.user.username,
            "action": "shape_locked",
            "status": "locked"
        }
    )


async def release_shape(self, data):
    id_shape = data['id_shape']

    # Рассылаем в ГРУППУ КАНАЛОВ ДОСКИ: "Юзер X отпустил фигуру Y"
    await self.channel_layer.group_send(
        self.room_group_name,
        {
            "type": "shape_focus",  # !!!!! Важно: это имя метода, который будет вызван
            "id_shape": id_shape,
            "name": self.user.username,
            "action": "shape_unlocked",
            "status": "unlocked"
        }
    )


async def shape_focus(self, event):
    # РЕАКЦИЯ НА РАССЫЛКУ: все клиентские подключения, находящиеся в ГРУППЕ КАНАЛОВ ДОСКИ, получат сообщения
    # Этот метод вызывается автоматически, когда в ГРУППУ КАНАЛОВ ДОСКИ приходит сообщение с type="shape.focus"
    await self.send(text_data=json.dumps({
        "type": "focus_update",
        "id_shape": event.get("id_shape"),
        "name": event.get("username"),
        "action": event.get("action"),
        "status": event.get("status")
    }))