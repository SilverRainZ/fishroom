#!/usr/bin/env python3
import re
import redis
import threading

from .bus import MessageBus
from .models import MessageType, Message
from .chatlogger import ChatLogger
from .photostore import Imgur, VimCN
from .textstore import Pastebin, Vinergy, RedisStore, ChatLoggerStore
from .telegram import (RedisNickStore, RedisStickerURLStore,
                       Telegram, TelegramThread)
from .irchandle import IRCHandle, IRCThread
from .xmpp import XMPPHandle, XMPPThread
from .command import get_command_handler, parse_command

from .config import config


redis_client = redis.StrictRedis(
    host=config['redis']['host'], port=config['redis']['port'])
message_bus = MessageBus(redis_client)
chat_logger = ChatLogger(redis_client)


def load_plugins():
    from importlib import import_module
    for plugin in config['plugins']:
        module = ".plugins." + plugin
        import_module(module, package="fishroom")


def init_text_store():
    provider = config['text_store']['provider']
    if provider == "pastebin":
        options = config['text_store']['options']
        return Pastebin(**options)
    elif provider == "vinergy":
        return Vinergy()
    elif provider == "redis":
        return RedisStore(redis_client)
    elif provider == "chat_logger":
        return ChatLoggerStore()


def init_telegram():

    def photo_store_init():
        provider = config['photo_store']['provider']
        if provider == "imgur":
            options = config['photo_store']['options']
            return Imgur(**options)
        elif provider == "vim-cn":
            return VimCN()

    nick_store = RedisNickStore(redis_client)
    sticker_url_store = RedisStickerURLStore(redis_client)
    photo_store = photo_store_init()

    return Telegram(
        config["telegram"]["token"],
        sticker_url_store=sticker_url_store,
        nick_store=nick_store,
        photo_store=photo_store,
    )


def init_irc():
    irc_channels = [b["irc"] for _, b in config['bindings'].items()]
    server = config['irc']['server']
    port = config['irc']['port']
    nickname = config['irc']['nick']
    usessl = config['irc']['ssl']
    blacklist = config['irc']['blacklist']
    return IRCHandle(server, port, usessl, nickname, irc_channels, blacklist)


def init_xmpp():
    rooms = [b["xmpp"] for _, b in config['bindings'].items()]
    server = config['xmpp']['server']
    port = config['xmpp']['port']
    nickname = config['xmpp']['nick']
    jid = config['xmpp']['jid']
    password = config['xmpp']['password']
    return XMPPHandle(server, port, jid, password, rooms, nickname)


def ForwardingThread(channels, text_store):
    bindings = config['bindings']

    def get_binding(msg):
        for c, b in bindings.items():
            if msg.receiver == b[msg.channel.lower()]:
                return c, b
        return (None, None)

    msg_tmpl = "[{sender}] {content}"
    ev_tmpl = "{content}"

    for msg in message_bus.message_stream():
        c, b = get_binding(msg)
        print(msg, c, len(msg.content.encode('utf-8')))
        if b is None:
            continue

        # Handle commands
        bot_reply = ""
        if msg.mtype == MessageType.Command:
            try:
                cmd, args = parse_command(msg.content)
                handler = get_command_handler(cmd)
                if handler is not None:
                    bot_reply = handler(cmd, *args, msg=msg)
            except:
                msg.mtype = MessageType.Text
                pass

        msg_id = chat_logger.log(c, msg)
        if bot_reply:
            chat_logger.log(
                c,
                Message(
                    msg.channel, config.get("name", "bot"), msg.receiver,
                    content=bot_reply, date=msg.date, time=msg.time,
                )
            )

        # Event Message
        if msg.mtype == MessageType.Event:
            for c in channels:
                target = b[c.ChanTag.lower()]
                c.send_msg(target, ev_tmpl.format(content=msg.content))
            continue

        # Other Message
        if (msg.content.count('\n') > 5
                or len(msg.content.encode('utf-8')) >= 400):
            text_url = text_store.new_paste(
                msg.content, msg.sender,
                channel=c, date=msg.date, time=msg.time, msg_id=msg_id
            )

            if text_url is None:
                # Fail
                print("Failed to publish text")
                continue
            # messages = msg
            contents = [text_url + " (long text)", ]
            send_back = True
        else:
            contents = [
                line for line in msg.content.split("\n")
                if not re.match(r'^\s*$', line)
            ]
            send_back = False

        for c in channels:
            target = b[c.ChanTag.lower()]
            if c.ChanTag != msg.channel or send_back is True:
                for line in contents:
                    c.send_msg(
                        target,
                        msg_tmpl.format(sender=msg.sender, content=line)
                    )
            if bot_reply:
                c.send_msg(target, bot_reply)


def main():

    load_plugins()

    irchandle = init_irc()
    tghandle = init_telegram()
    xmpphandle = init_xmpp()
    text_store = init_text_store()
    tasks = []

    for target, args in (
            (TelegramThread, (tghandle, message_bus), ),
            (IRCThread, (irchandle, message_bus), ),
            (XMPPThread, (xmpphandle, message_bus), ),
            (
                ForwardingThread,
                ((tghandle, irchandle, xmpphandle, ), text_store, ),
            ),
    ):
        t = threading.Thread(target=target, args=args)
        t.setDaemon(True)
        t.start()
        tasks.append(t)

    for t in tasks:
        t.join()

if __name__ == "__main__":
    main()


# vim: ts=4 sw=4 sts=4 expandtab
