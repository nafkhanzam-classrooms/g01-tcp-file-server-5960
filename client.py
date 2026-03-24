# import os
# import socket

# HOST = "127.0.0.1"
# PORT = 5000
# SIZE = 1024
# DOWNLOAD_FOLDER = "client_downloads"

# os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


# def send_line(sock, text):
#     sock.sendall((text + "\n").encode())


# def recv_line(sock):
#     data = b""
#     while not data.endswith(b"\n"):
#         part = sock.recv(1)
#         if not part:
#             return None
#         data += part
#     return data.decode().strip()


# def do_list(sock):
#     send_line(sock, "/list")
#     reply = recv_line(sock)

#     if reply == "EMPTY":
#         print("Server folder is empty.")
#     else:
#         files = reply.split("|")
#         print("Files on server:")
#         for file in files:
#             print("-", file)


# def do_upload(sock, filename):
#     if not os.path.exists(filename):
#         print("File not found.")
#         return

#     send_line(sock, f"/upload {os.path.basename(filename)}")
#     reply = recv_line(sock)

#     if reply != "OK":
#         print("Server error.")
#         return

#     filesize = os.path.getsize(filename)
#     send_line(sock, str(filesize))

#     with open(filename, "rb") as f:
#         while True:
#             data = f.read(SIZE)
#             if not data:
#                 break
#             sock.sendall(data)

#     print(recv_line(sock))


# def do_download(sock, filename):
#     send_line(sock, f"/download {filename}")
#     reply = recv_line(sock)

#     if reply == "NOT FOUND":
#         print("File not found on server.")
#         return

#     filesize = int(reply)
#     send_line(sock, "OK")

#     filepath = os.path.join(DOWNLOAD_FOLDER, filename)

#     with open(filepath, "wb") as f:
#         remaining = filesize
#         while remaining > 0:
#             data = sock.recv(min(SIZE, remaining))
#             if not data:
#                 break
#             f.write(data)
#             remaining -= len(data)

#     print(f"Downloaded: {filepath}")


# def main():
#     client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     client.connect((HOST, PORT))

#     print(recv_line(client))

#     while True:
#         command = input("\nEnter command: ").strip()

#         if command == "/list":
#             do_list(client)

#         elif command.startswith("/upload "):
#             filename = command[8:].strip()
#             do_upload(client, filename)

#         elif command.startswith("/download "):
#             filename = command[10:].strip()
#             do_download(client, filename)

#         elif command == "quit":
#             send_line(client, "quit")
#             print(recv_line(client))
#             break

#         else:
#             print("Commands:")
#             print("/list")
#             print("/upload <filename>")
#             print("/download <filename>")
#             print("quit")

#     client.close()


# if __name__ == "__main__":
#     main()

import os
import socket
import threading
import queue

HOST = "127.0.0.1"
PORT = 5000
SIZE = 4096
DOWNLOAD_FOLDER = "client_downloads"

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

response_queue = queue.Queue()
running = True


def send_line(sock, text):
    sock.sendall((text + "\n").encode())


def recv_line(sock):
    data = b""
    while not data.endswith(b"\n"):
        part = sock.recv(1)
        if not part:
            return None
        data += part
    return data.decode().strip()


def receive_messages(sock):
    global running

    while running:
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

        except:
            print("\nConnection closed.")
            running = False
            break


def get_response():
    return response_queue.get()


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
    send_line(sock, f"/download {filename}")
    reply = get_response()

    if reply == "NOT FOUND":
        print("File not found on server.")
        return

    filesize = int(reply)
    send_line(sock, "OK")

    filepath = os.path.join(DOWNLOAD_FOLDER, filename)

    with open(filepath, "wb") as f:
        remaining = filesize
        while remaining > 0:
            data = sock.recv(min(SIZE, remaining))
            if not data:
                break
            f.write(data)
            remaining -= len(data)

    print(f"Downloaded: {filepath}")


def do_message(sock, text):
    send_line(sock, f"/msg {text}")
    print(get_response())


def main():
    global running

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((HOST, PORT))

    # thread untuk menerima pesan dari server
    receive_thread = threading.Thread(target=receive_messages, args=(client,), daemon=True)
    receive_thread.start()

    # pesan awal dari server
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