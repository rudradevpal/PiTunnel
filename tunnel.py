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


def main():
    try:
        logger.info("Starting PiTunnel...")

        logger.info("Waiting for internet...")
        for t in range(0, 13):
            if check_connection():
                logger.info("Internet is now connected!")
                break
            else:
                if t < 12:
                    time.sleep(10)
                else:
                    logger.info("Failed to connect to internet!")
                    exit(1)

        local_server_ip = "127.0.0.1"
        local_server_port = int(sys.argv[1])
        remote_ssh_port = 22
        remote_public_ip_port = str(sys.argv[2]).split(":")
        remote_public_ip = str(remote_public_ip_port[0])
        remote_target_port = int(remote_public_ip_port[1])
        remote_os_username = str(sys.argv[3])
        # remote_os_password = str(sys.argv[4])
        remote_os_key = str(sys.argv[4])

        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.WarningPolicy())
        try:
            logger.info("Starting Secure Shell Connection")
            client.connect(
                remote_public_ip,
                remote_ssh_port,
                username=remote_os_username,
                # password=remote_os_password,
                key_filename=remote_os_key,
            )
            logger.info("Secure Shell Connected!")
        except Exception as e:
            logger.error("Secure Shell Connection Failed!")
            logger.error(str(e))
            sys.exit(1)
        try:
            logger.info("Starting Reverse Tunnel")
            reverse_forward_tunnel(
                remote_target_port, local_server_ip, local_server_port, client.get_transport()
            )
        except Exception as e:
            logger.error("Reverse Tunnel Start Failed!")
            logger.error(str(e))
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("PiTunnel Stopped!\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
