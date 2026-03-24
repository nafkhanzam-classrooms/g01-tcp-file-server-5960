import os
import socket
import threading
import queue
import time

HOST = "127.0.0.1"
PORT = 5000
SIZE = 4096
DOWNLOAD_FOLDER = "client_downloads"

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

response_queue = queue.Queue()
running = True
pause_receiver = threading.Event()
receiver_paused_ack = threading.Event()


def send_line(sock, text):
    sock.sendall((text + "\n").encode())


def recv_line(sock):
    data = b""
    while not data.endswith(b"\n"):
        try:
            part = sock.recv(1)
        except socket.timeout:
            if not data:
                raise
            continue
        if not part:
            return None
        data += part
    return data.decode().strip()


def receive_messages(sock):
    global running

    while running:
        if pause_receiver.is_set():
            receiver_paused_ack.set()
            time.sleep(0.05)
            continue

        receiver_paused_ack.clear()

        try:
            message = recv_line(sock)

            if not message:
                print("\nServer disconnected.")
                running = False
                break

            if message.startswith("BROADCAST:"):
                print(f"\n{message[10:]}")
            else:
                response_queue.put(message)

        except socket.timeout:
            continue
        except:
            print("\nConnection closed.")
            running = False
            break


def get_response():
    return response_queue.get()

def recv_line_direct(sock):
    while running:
        try:
            return recv_line(sock)
        except socket.timeout:
            continue


def do_list(sock):
    send_line(sock, "/list")
    reply = get_response()

    if reply == "EMPTY":
        print("Server folder is empty.")
    else:
        files = reply.split("|")
        print("Files on server:")
        for file in files:
            print("-", file)


def do_upload(sock, filename):
    if not os.path.exists(filename):
        print("File not found.")
        return

    send_line(sock, f"/upload {os.path.basename(filename)}")
    reply = get_response()

    if reply != "OK":
        print("Server error:", reply)
        return

    filesize = os.path.getsize(filename)
    send_line(sock, str(filesize))

    with open(filename, "rb") as f:
        while True:
            data = f.read(SIZE)
            if not data:
                break
            sock.sendall(data)

    print(get_response())


def do_download(sock, filename):
    pause_receiver.set()
    receiver_paused_ack.wait()

    try:
        send_line(sock, f"/download {filename}")
        reply = recv_line_direct(sock)

        if reply == "NOT FOUND":
            print("File not found on server.")
            return

        filesize = int(reply)
        send_line(sock, "OK")

        filepath = os.path.join(DOWNLOAD_FOLDER, filename)

        with open(filepath, "wb") as f:
            remaining = filesize
            while remaining > 0:
                try:
                    data = sock.recv(min(SIZE, remaining))
                except socket.timeout:
                    continue
                if not data:
                    break
                f.write(data)
                remaining -= len(data)

        if remaining == 0:
            print(f"Downloaded: {filepath}")
        else:
            print("Download interrupted.")

    finally:
        pause_receiver.clear()
        receiver_paused_ack.clear()


def do_message(sock, text):
    send_line(sock, f"/msg {text}")
    print(get_response())


def main():
    global running

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((HOST, PORT))
    client.settimeout(0.2)

    receive_thread = threading.Thread(target=receive_messages, args=(client,), daemon=True)
    receive_thread.start()

    print(get_response())

    while running:
        try:
            command = input("\nEnter command: ").strip()

            if command == "/list":
                do_list(client)

            elif command.startswith("/upload "):
                filename = command[8:].strip()
                do_upload(client, filename)

            elif command.startswith("/download "):
                filename = command[10:].strip()
                do_download(client, filename)

            elif command.startswith("/msg "):
                text = command[5:].strip()
                if text:
                    do_message(client, text)
                else:
                    print("Usage: /msg <message>")

            elif command == "quit":
                send_line(client, "quit")
                print(get_response())
                running = False
                break

            else:
                print("Commands:")
                print("/list")
                print("/upload <filename>")
                print("/download <filename>")
                print("/msg <message>")
                print("quit")

        except KeyboardInterrupt:
            print("\nClient closed.")
            running = False
            break

    client.close()


if __name__ == "__main__":
    main()