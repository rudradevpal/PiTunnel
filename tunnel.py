import socket
import select
import sys
import threading
import paramiko
import logging
import time

logging.basicConfig(format='%(asctime)s\t[%(levelname)s]\t%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def check_connection():
    try:
        host = socket.gethostbyname("www.google.com")
        s = socket.create_connection((host, 80), 2)
        s.close()
        return True
    except Exception as e:
        return False


def handler(chan, local_server_ip, local_server_port, remote_target_port):
    sock = socket.socket()
    try:
        sock.connect((local_server_ip, local_server_port))
    except Exception as e:
        logger.error("Tunneling request " + str(chan.origin_addr[0]) + ":" + str(chan.origin_addr[1]) + " --> "
                     + str(chan.getpeername()[0]) + ":" + str(remote_target_port) + " --> " + str(local_server_ip) + ":"
                     + str(local_server_port) + " refused!")
        logger.error(str(e))
        return

    logger.info("Tunneling request " + str(chan.origin_addr[0]) + ":" + str(chan.origin_addr[1]) + " --> "
                + str(chan.getpeername()[0]) + ":" + str(remote_target_port) + " --> " + str(local_server_ip) + ":"
                + str(local_server_port) + " successful!")
    while True:
        r, w, x = select.select([sock, chan], [], [])
        if sock in r:
            data = sock.recv(1024)
            if len(data) == 0:
                break
            chan.send(data)
        if chan in r:
            data = chan.recv(1024)
            if len(data) == 0:
                break
            sock.send(data)
    chan.close()
    sock.close()
    logger.info("Tunnel closed from " + str(chan.origin_addr[0]) + ":" + str(chan.origin_addr[1]))


def reverse_forward_tunnel(remote_target_port, local_server_ip, local_server_port, transport):
    try:
        transport.request_port_forward("", remote_target_port)
        logger.info("Reverse Tunnel Started!")
        while True:
            chan = transport.accept(1000)
            if chan is None:
                continue
            logger.info("Tunneling request from " + str(chan.origin_addr[0]) + ":" + str(chan.origin_addr[1]))
            thr = threading.Thread(
                target=handler, args=(chan, local_server_ip, local_server_port, remote_target_port)
            )
            thr.setDaemon(True)
            thr.start()
        return True
    except Exception as e:
        logger.error(str(e))
        return False


def ssh_connection(remote_public_ip, remote_ssh_port, remote_os_username, remote_os_key):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.WarningPolicy())
    try:
        client.connect(
            remote_public_ip,
            remote_ssh_port,
            username=remote_os_username,
            # password=remote_os_password,
            key_filename=remote_os_key,
        )
        return client
    except paramiko.SSHException:
        logger.error("SSH Error")
        return None
    except Exception as e:
        logger.error(str(e))
        return None


def main():
    try:
        logger.info("Starting PiTunnel...")

        local_server_ip = "127.0.0.1"
        local_server_port = int(sys.argv[1])
        remote_ssh_port = 22
        remote_public_ip_port = str(sys.argv[2]).split(":")
        remote_public_ip = str(remote_public_ip_port[0])
        remote_target_port = int(remote_public_ip_port[1])
        remote_os_username = str(sys.argv[3])
        # remote_os_password = str(sys.argv[4])
        remote_os_key = str(sys.argv[4])

        logger.info("Waiting for internet...")
        timer = 0
        while timer <= 300:
            if check_connection():
                logger.info("Internet is now connected!")
                break
            else:
                if timer == 300:
                    logger.info("Failed to connect to internet!")
                    exit(1)
                else:
                    timer += 10
                    time.sleep(10)

        logger.info("Starting Secure Shell Connection")
        timer = 0
        client = None
        while timer <= 180:
            client = ssh_connection(remote_public_ip, remote_ssh_port, remote_os_username, remote_os_key)
            if client is not None:
                logger.info("Secure Shell Connected!")
                break
            else:
                if timer == 180:
                    logger.error("Secure Shell Connection Failed!")
                    exit(1)
                else:
                    timer += 10
                    time.sleep(10)
                    if timer <= 180:
                        logger.info("Retrying Secure Shell Connection")

        time.sleep(6)
        logger.info("Starting Reverse Tunnel")
        counter = 0
        while True:
            res = reverse_forward_tunnel(remote_target_port, local_server_ip, local_server_port, client.get_transport())
            if not res:
                time.sleep(10)
                counter += 1
                logger.info(str(counter) + ": Retrying Reverse Tunnel")

        # timer = 0
        # while timer <= 180:
        #     res = reverse_forward_tunnel(remote_target_port, local_server_ip, local_server_port, client.get_transport())
        #     if not res:
        #         if timer == 180:
        #             logger.error("Reverse Tunnel Start Failed!")
        #             exit(1)
        #         else:
        #             timer += 10
        #             time.sleep(10)
        #             if timer <= 180:
        #                 logger.info("Retrying Reverse Tunnel")

    except KeyboardInterrupt:
        logger.info("PiTunnel Stopped!\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
