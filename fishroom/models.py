#!/usr/bin/env python3
from marshmallow import Schema, fields


class ChannelType(object):
    """\
    Channel Types
    """
    XMPP = "xmpp"
    IRC = "irc"
    Telegram = "telegram"


class MessageType(object):
    """\
    Message Types
    """
    Text = "text"
    Photo = "photo"
    Sticker = "sticker"
    Event = "event"
    Command = "command"


class Message(object):
    """\
    Message instance

    Attributes:
        channel: one in ChannelType.{XMPP, Telegram, IRC}
        sender: sender name
        receiver: receiver name
        content: message content
        mtype: text or photo or sticker

    """

    _schema = None

    def __init__(self, channel, sender, receiver, content,
                 mtype=MessageType.Text, date=None, time=None, media_url=None):
        self.channel = channel
        self.sender = sender
        self.receiver = receiver
        self.content = content
        self.mtype = mtype
        self.date = date
        self.time = time
        self.media_url = media_url

    def __repr__(self):
        return (
            "[{channel}] {mtype} from: {sender}, to: {receiver}, {content}"
            .format(
                channel=self.channel, mtype=self.mtype, sender=self.sender,
                receiver=self.receiver, content=self.content,
            ))

    def dumps(self):
        return self._schema.dumps(self).data

    @classmethod
    def loads(cls, jstr):
        return cls._schema.loads(jstr).data


class MessageSchema(Schema):
    """\
    Json Schema for Message
    """
    channel = fields.Enum(
        (ChannelType.IRC, ChannelType.XMPP, ChannelType.Telegram, ),
    )
    sender = fields.String()
    receiver = fields.String()
    mtype = fields.Enum(
        (MessageType.Photo, MessageType.Text, MessageType.Sticker,
         MessageType.Command, MessageType.Event),
    )
    media_url = fields.String()
    content = fields.String()
    date = fields.String()
    time = fields.String()

    def make_object(self, kwargs):
        return Message(**kwargs)

Message._schema = MessageSchema()

# vim: ts=4 sw=4 sts=4 expandtab
