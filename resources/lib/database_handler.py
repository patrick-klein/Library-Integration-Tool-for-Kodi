#!/usr/bin/python
# -*- coding: utf-8 -*-
''' This modules provides a class that interfaces with the SQLite database '''

import os
import sqlite3

import xbmcaddon

import contentitem
from utils import utf8_decorator, log_decorator

addon = xbmcaddon.Addon()
MANAGED_FOLDER = addon.getSetting('managed_folder')
DB_FILE = os.path.join(MANAGED_FOLDER, 'managed.db')

class DB_Handler(object):
    '''
    This class initializes a connection with the SQLite file
    and provides methods for interfacing with database.
    SQLite connection is closed when object is deleted.
    '''
    #TODO: reimplement blocked keywords
    #TODO: use **kwargs to dynamically add constraints

    def __init__(self):
        # connect to database
        self.db = sqlite3.connect(DB_FILE)
        self.db.text_factory = str
        self.c = self.db.cursor()
        # create tables if they doesn't exist
        self.c.execute(
            "CREATE TABLE IF NOT EXISTS Content \
            (Directory TEXT PRIMARY KEY, Title TEXT, Mediatype TEXT, Status TEXT, Show_Title TEXT)")
        self.c.execute(
            "CREATE TABLE IF NOT EXISTS Synced \
            (Directory TEXT PRIMARY KEY, Label TEXT, Type TEXT)")
        self.c.execute(
            "CREATE TABLE IF NOT EXISTS Blocked \
            (Value TEXT NOT NULL, Type TEXT NOT NULL)")
        self.db.commit()

    def __del__(self):
        ''' close connection when deleted '''
        self.db.close()

    @log_decorator
    def get_content_items(self, status, mediatype=None):
        ''' Queries Content table for sorted items with status and mediatype (optional)
        and casts results as ContentItem subclass '''
        # query database, add Mediatype constraint if parameter is provided
        if mediatype:
            self.c.execute(
                "SELECT * FROM Content WHERE Status=? AND Mediatype=? \
                ORDER BY (CASE WHEN Title LIKE 'the %' THEN substr(Title,5) ELSE Title END)",
                (status, mediatype))
        else:
            self.c.execute(
                "SELECT * FROM Content WHERE Status=? \
                ORDER BY (CASE WHEN Title LIKE 'the %' THEN substr(Title,5) ELSE Title END)",
                (status,))
        # get results and return items as objects
        rows = self.c.fetchall()
        return [self.content_item_from_db(x) for x in rows]

    @log_decorator
    def get_all_shows(self, status):
        ''' Queries Content table for all (not null) distinct show_titles
        and casts results as list of strings '''
        # query database
        self.c.execute(
            "SELECT DISTINCT Show_Title FROM Content WHERE Status=? \
            ORDER BY (CASE WHEN Show_Title LIKE 'the %' THEN substr(Show_Title,5) ELSE Show_Title END)",
            (status,))
        # get results and return items as list
        rows = self.c.fetchall()
        return [x[0] for x in rows if x[0] is not None]

    @log_decorator
    def get_show_episodes(self, status, show_title):
        ''' Queries Content table for tvshow items with show_title
        and casts results as EpisodeItem '''
        # query database
        self.c.execute(
            "SELECT * FROM Content WHERE Status=? AND Show_Title=?\
            ORDER BY (CASE WHEN Title LIKE 'the %' THEN substr(Title,5) ELSE Title END)",
            (status, show_title))
        # get results and return items as objects
        rows = self.c.fetchall()
        return [self.content_item_from_db(x) for x in rows]

    @utf8_decorator
    @log_decorator
    def load_item(self, path):
        ''' Queries a single item with path and casts result as ContentItem subclass '''
        # query database
        self.c.execute(
            'SELECT * FROM Content WHERE Directory=?',
            (path,))
        # get results and return items as object
        item = self.c.fetchone()
        return self.content_item_from_db(item)

    @utf8_decorator
    @log_decorator
    def path_exists(self, path, status=None):
        ''' Returns True if path is already in database (with given status) '''
        #TODO: consider adding mediatype as optional parameter
        #       might speed-up by adding additional constraint
        #TODO: test speed against a set from "get_content_paths"
        # query database, add Status constraint if parameter is provided
        if status:
            self.c.execute(
                'SELECT (Directory) FROM Content WHERE Directory=? AND Status=?',
                (path, status))
        else:
            self.c.execute(
                'SELECT (Directory) FROM Content WHERE Directory=?',
                (path,))
        # get result and return True if result is found
        res = self.c.fetchone()
        return bool(res)

    @utf8_decorator
    @log_decorator
    def add_content_item(self, path, title, mediatype, show_title=None):
        ''' Adds item to Content with given parameters '''
        # log and insert row according to mediatype
        if mediatype == 'movie':
            self.c.execute(
                "INSERT OR IGNORE INTO Content \
                    (Directory, Title, Mediatype, Status, Show_Title) \
                    VALUES (?, ?, ?, 'staged', NULL)",
                (path, title, mediatype))
        elif mediatype == 'tvshow':
            self.c.execute(
                "INSERT OR IGNORE INTO Content \
                (Directory, Title, Mediatype, Status, Show_Title) \
                VALUES (?, ?, ?, 'staged', ?)",
                (path, title, mediatype, show_title))
        self.db.commit()

    @utf8_decorator
    @log_decorator
    def update_content_status(self, path, status):
        ''' Updates Status for item in Content with specified path '''
        # update item
        self.c.execute(
            "UPDATE Content SET Status=(?) WHERE Directory=?",
            (status, path))
        self.db.commit()

    @utf8_decorator
    @log_decorator
    def update_content_title(self, path, title):
        ''' Updates title for item in Content with specified path '''
        # update item
        self.c.execute(
            "UPDATE Content SET Title=(?) WHERE Directory=?",
            (title, path))
        self.db.commit()

    @utf8_decorator
    @log_decorator
    def remove_content_item(self, path):
        ''' Removes the item in Content with specified path '''
        # delete from table
        self.c.execute(
            "DELETE FROM Content WHERE Directory=?",
            (path,))
        self.db.commit()

    @log_decorator
    def remove_all_content_items(self, status, mediatype):
        ''' Removes all items from Content with status and mediatype '''
        # delete from table
        self.c.execute(
            "DELETE FROM Content WHERE Status=? AND Mediatype=?",
            (status, mediatype))
        self.db.commit()

    @utf8_decorator
    @log_decorator
    def remove_all_show_episodes(self, status, show_title):
        ''' Removes all tvshow items from Content with status and show_title '''
        # delete from table
        self.c.execute(
            "DELETE FROM Content WHERE Status=? AND Show_Title=?",
            (status, show_title))
        self.db.commit()

    @utf8_decorator
    @log_decorator
    def get_synced_dirs(self):
        ''' Gets all items in Synced cast as a list of dicts '''
        # query database
        self.c.execute(
            "SELECT * FROM Synced \
            ORDER BY (CASE WHEN Label LIKE 'the %' THEN substr(Label,5) ELSE Label END)")
        # get results and return as list of dicts
        rows = self.c.fetchall()
        return [self.synced_item_dict(x) for x in rows]

    @utf8_decorator
    @log_decorator
    def add_synced_dir(self, label, path, mediatype):
        ''' Create an entry in Synced with specified values '''
        self.c.execute(
            "INSERT OR REPLACE INTO Synced (Directory, Label, Type) VALUES (?, ?, ?)",
            (path, label, mediatype))
        self.db.commit()

    @utf8_decorator
    @log_decorator
    def remove_synced_dir(self, path):
        ''' Removes the entry in Synced with the specified Directory '''
        # remove entry
        self.c.execute(
            "DELETE FROM Synced WHERE Directory=?",
            (path,))
        self.db.commit()

    @log_decorator
    def remove_all_synced_dirs(self):
        ''' Deletes all entries in Synced '''
        # remove all rows
        self.c.execute(
            "DELETE FROM Synced")
        self.db.commit()

    @log_decorator
    def get_blocked_items(self):
        ''' Returns all items in Blocked as a list of dicts '''
        self.c.execute(
            "SELECT * FROM Blocked ORDER BY Value, Type")
        rows = self.c.fetchall()
        return [self.blocked_item_dict(x) for x in rows]

    @utf8_decorator
    @log_decorator
    def add_blocked_item(self, value, mediatype):
        ''' Adds an item to Blocked with the specified valeus '''
        # ignore if already in table
        if not self.check_blocked(value, mediatype):
            # insert into table
            self.c.execute(
                "INSERT INTO Blocked (Value, Type) VALUES (?, ?)",
                (value, mediatype))
            self.db.commit()

    @utf8_decorator
    @log_decorator
    def check_blocked(self, value, mediatype):
        ''' Returns True if the given entry is in Blocked '''
        self.c.execute(
            'SELECT (Value) FROM Blocked WHERE Value=? AND Type=?',
            (value, mediatype))
        res = self.c.fetchone()
        return bool(res)

    @utf8_decorator
    @log_decorator
    def remove_blocked(self, value, mediatype):
        ''' Removes the item in Blocked with the specified parameters '''
        self.c.execute(
            'DELETE FROM Blocked WHERE Value=? AND Type=?',
            (value, mediatype))
        self.db.commit()

    @staticmethod
    def content_item_from_db(item):
        ''' Static method that converts Content query output to ContentItem subclass '''
        if item[2] == 'movie':
            return contentitem.MovieItem(item[0], item[1], 'movie')
        elif item[2] == 'tvshow':
            return contentitem.EpisodeItem(item[0], item[1], 'tvshow', item[4])
        raise ValueError('Unrecognized Mediatype in Content query')

    @staticmethod
    def synced_item_dict(item):
        ''' Static method that converts Synced query output to dict '''
        return {'dir': item[0], 'label': item[1], 'type': item[2]}

    @staticmethod
    def blocked_item_dict(item):
        ''' Static method that converts Blocked query output to dict '''
        return {'value': item[0], 'type': item[1]}
