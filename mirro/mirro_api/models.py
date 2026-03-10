from django.db import models

class AccessToEdit(models.Model):
    fk_user = models.ForeignKey('User', models.DO_NOTHING, db_column='fk_user')
    fk_board = models.ForeignKey('Board', models.DO_NOTHING, db_column='fk_board')
    author = models.IntegerField()
    pk_access_to_edit = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'access_to_edit'


class Board(models.Model):
    pk_board = models.AutoField(primary_key=True)
    title = models.CharField(max_length=45)
    is_published = models.IntegerField()
    total_like = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'board'


class Like(models.Model):
    fk_user = models.ForeignKey('User', models.DO_NOTHING, db_column='fk_user')
    fk_board = models.ForeignKey(Board, models.DO_NOTHING, db_column='fk_board')
    pk_like = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'like'

class Shape(models.Model):
    pk_shape = models.IntegerField(primary_key=True)
    properties = models.JSONField()
    fk_type = models.ForeignKey('Type', models.DO_NOTHING, db_column='fk_type')
    fk_board = models.ForeignKey(Board, models.DO_NOTHING, db_column='fk_board')

    class Meta:
        managed = False
        db_table = 'shape'


class Type(models.Model):
    pk_type = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = 'type'


class User(models.Model):
    pk_user = models.AutoField(primary_key=True)
    username = models.CharField(max_length=100)
    email = models.CharField(max_length=255)
    password = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = 'user'