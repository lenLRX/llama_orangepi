#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Copyright (C) 2022. Huawei Technologies Co., Ltd. All rights reserved.

database server
"""
import os
import sys
import time
import errno
import fcntl
import socket
import struct
import binascii
import signal
import random
import functools
import psutil

from tbe.common.repository_manager.utils.repository_manager_log import LOG_INSTANCE


SIOCGIFHWADDR = 0x8927
HEXADECIMAL = 16
TIME_SLEEP = 0.1
RANDOM = random.Random()


def config_main_info() -> tuple:
    """
    config __file__ and name of main to None

    @return: (orignal main module name, path)
    """
    main_module = sys.modules.get('__main__')
    print("config_main_info", sys.version)
    spec_attr = getattr(main_module, "__spec__", None)
    if spec_attr is None:
        print("setting spec attr")
        setattr(main_module, '__spec__', None)
    main_module_name = getattr(main_module.__spec__, "name", None)
    if main_module_name is not None:
        setattr(main_module.__spec__, "name", None)

    main_module_path = getattr(main_module, '__file__', None)
    if main_module_path is not None:
        setattr(main_module, '__file__', None)

    return (main_module_name, main_module_path)


def restore_main_info(name: str, path: str) -> None:
    """
    restore main module name and path
    """
    main_module = sys.modules.get('__main__')
    if name is not None:
        setattr(main_module.__spec__, "name", name)
    if path is not None:
        setattr(main_module, '__file__', path)


def generate_unique():
    """unique genertor

    Description:
    Generates globally unique values for possible keywords

    Return: str
    """
    return "_".join([str(os.getpid()), str(time.time()).replace(".", "_")[-9:], str(RANDOM.random())])


def pid_exists(pid: str) -> bool:
    """Check whether pid exists in the current process table.
    UNIX only.
    """
    pid = int(pid)
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError as err:
        if err.errno == errno.ESRCH:
            # ESRCH == No such process
            return False
        if err.errno == errno.EPERM:
            # EPERM clearly means there's a process to deny access to
            return True
        # According to "man 2 kill" possible error values are
        # EINVAL, EPERM, ESRCH
        raise
    finally:
        pass
    return True


def daemon_process(mgr_pid: int, ppid: str, running: object) -> None:
    """
    daemon_process
    """
    def sigint_handler(signum: int, frame: object) -> None:
        """sigint_handler"""
        LOG_INSTANCE.warn("Signal handler called with signal %d, frame %s.", signum, frame)

    running.set()
    LOG_INSTANCE.event("Daemon process start!ppid: %s" % ppid)
    signal.signal(signal.SIGINT, sigint_handler)
    while True:
        if not pid_exists(ppid):
            LOG_INSTANCE.warn(
                "The main process does not exist. We would kill multiprocess manager process: %d.", mgr_pid)
            os.kill(mgr_pid, signal.SIGKILL)
            break
        time.sleep(TIME_SLEEP)
    LOG_INSTANCE.event("Daemon process exit!")


def get_msg_file_dir() -> str:
    """Place the message handle file in the ~/Ascend directory."""
    home_path = os.environ.get("ASCEND_WORK_PATH", None)
    if not home_path:
        home_path = os.environ['HOME']
    else:
        home_path = os.path.join(home_path, "aoe_data")
    return os.path.join(home_path, "Ascend", "latest", ".lock", "cann_kb_manager")


def timer(func):
    """time statistical modifier function"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        begin = time.time()
        res = func(*args, **kwargs)
        LOG_INSTANCE.debug("[%s] cost time: %s s" % (func.__name__, time.time() - begin))
        return res
    return wrapper


def get_mac_addr():
    net_if_info = psutil.net_if_addrs()
    for k, v in net_if_info.items():
        for item in v:
            if not item[0] == 2 or item[1] == '127.0.0.1': # 2: AddressFamily.AF_INET; 127.0.0.1: choose not local
                continue
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            info = fcntl.ioctl(s.fileno(), SIOCGIFHWADDR, struct.pack('256s', k.encode()[:15])) # get ip config
            mac = binascii.b2a_hex(info[18:24]).decode('utf-8') # 18:24: get mac num
            if int(mac, HEXADECIMAL) == 0:
                continue
            return "_" + mac
    return ""
