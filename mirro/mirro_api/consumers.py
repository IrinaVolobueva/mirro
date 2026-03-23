import json
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.http import JsonResponse
from mirro_api.models import Board, AccessToEdit, Shape, Type

class BoardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Сохраняем нашего авторизованного user'а:
        self.user = self.scope["user"]
        # Получаем id_board из URLа (/ws/boards/<id_board>/)
        self.id_board = int(self.scope['url_route']['kwargs']['id_board'])
        # Проверяем наличие доски с таким id_board (вынести в функцию, поскольку идет обращение к БД, декоратор @database_sync_to_async)
        exists = self.board_exists(self.id_board)
        # Если нет доски, то:
        if not self.board_exists():
            await self.close()
            return

        # Если есть доска, то:
        # Сохраняем в self.scope, чтоб каждый раз не лезть в receive
        self.scope["exists"] = exists

        # Конструируем имя ГРУППЫ КАНАЛОВ этой ДОСКИ
        self.board_group_name = f'board {self.id_bourd}'

        # Проверяем, есть ли у пользователя доступ к доске И какое право доступа "can_edit"/"can_view"//"нет доступа" (вынести в функцию, поскольку идет обращение к БД, декоратор @database_sync_to_async)
        access = self.get_board_access()\
        # Если доступа нет, то:
        # Закрываем соединение
        if not access.get('can_view'):
            await self.close()
            return

        # Если есть доступ, то:
        # Сохраняем право на редактирование в scope, чтобы не лезть в БД каждый раз в receive
        self.scope["can_edit"] = access.get('can_edit')
        self.scope["can_view"] = access.get('can_view')

        # Добавляем текущее клиентское соединение(channel_name) в ГРУППУ КАНАЛОВ ДОСКИ, чтобы текущее соединение получало все сообщения, отправленные в группу
        await self.channel_layer.group_add(self.board_group_name, self.channel_name)
        # Принимаем WebSocket соединение:
        await self.accept()

        # Получаем все существующие фигуры на доске из БД (вынести в функцию, поскольку идет обращение к БД, декоратор @database_sync_to_async)
        shapes = self.get_board_shapes()
        # Отправляем ТОЛЬКО текущему клиентскому соединению (не всей группе каналов) состояние доски
        await self.send(text_data=json.dumps({
            "shapes": shapes,
            "id_board": self.id_board,
            "exists": self.scope["exists"],
            "can_edit": self.scope["can_edit"],
            "can_view": self.scope["can_view"],
        }))

    async def disconnect(self, close_code):
        # Проверяем, была ли инициализирована ГРУППА КАНАЛОВ ДОСКИ:
        if hasattr(self, 'board_group_name'):
            # Удаляем текущее соединение (channel_name) из ГРУППЫ КАНАЛОВ ДОСКИ
            await self.channel_layer.group_discard(self.board_group_name, self.channel_name)

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
        # create_shape, delete_shape, update_shape
        elif action == 'create_shape':
            await self.create_shape(data)
        elif action == 'update_shape':
            await self.update_shape(data)
        elif action == 'delete_shape':
            await self.delete_shape(data)

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

    async def update_shape(self,data):
        shape_id = data['shape_id']
        properties=data['properties']
        success = await self.update_shape(shape_id,properties)
        if success:
            await self.channel_layer.group_send(
                self.board_group_name,{
                    'type': 'shape_message',
                    'action': 'shape_updated',
                    'shape_id': 'shape_message',
                    'type': 'shape_message',

                }
            )

    @database_sync_to_async
    def board_exists(self, id_board):
        return Board.objects.get(pk_board=id_board).exists()

    @database_sync_to_async
    def get_board_access(self, id_board):
        board = Board.objects.get(pk_board=id_board)
        is_editor = AccessToEdit.objects.filter(
            fk_board=board,
            fk_user=self.scope.user
        ).exists()
        is_viewer = board.is_published == 1 or is_editor
        return {
            'can_etit': is_editor,
            'can_view': is_viewer
        }

    @database_sync_to_async
    def get_board_shapes(self):
        shapes = Shape.objects.filter(fk_board_id = self.id_board).select_related('fk_type')
        return [
            {
                'id_shape':s.pk_shape,
                'type': s.fk_type.title,
                'properties': s.properties,
            }
            for s in shapes
        ]
    @database_sync_to_async
    def save_shape(self, shape_data):
        shape = Shape.objects.creat(
            properties = shape_data['properties'],
            fk_type_id =shape_data['type_id'],
            fk_board_id=shape_data['board_id']
        )
        return {
            'id': shape.pk_shape,
            'type':shape.fk_type.title,
            'type_id': shape.fk_type_id,
            'properties':shape.properties
        }
    @database_sync_to_async
    def update_shape(self, shape_id, properties):
        try:
            shape: Shape.objects.get(pk_shape =shape_id)
            shape.properties=properties
            shape.save()
        except:
            pass

    async def create_shape(self, data):
        # добавить в бд и разослать всем и всё
        shape_data = data['shape']
        shape = await  self.save_shape(shape_data)
        await  self.channel_layer.group_send(
            self.board_group_name,
            {
                'type':'shape_message',
                'action':'shape_created',
                'shape':shape
            }
        )
        shape = Shape.objects.creat()
        type = Type.objects.get()
