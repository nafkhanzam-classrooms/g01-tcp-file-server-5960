import os
import socket
import select

HOST = "127.0.0.1"
PORT = 5000
SIZE = 4096
SERVER_FOLDER = "server_files"

os.makedirs(SERVER_FOLDER, exist_ok=True)


def send_line(conn, text):
    conn.sendall((text + "\n").encode())


def recv_line(conn):
    data = b""
    while not data.endswith(b"\n"):
        part = conn.recv(1)
        if not part:
            return None
        data += part
    return data.decode().strip()


def broadcast(message, clients, sender=None):
    for client in clients:
        if client != sender:
            try:
                send_line(client, "BROADCAST:" + message)
            except:
                pass


server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen()
server.setblocking(False)

sockets_list = [server]
client_addresses = {}

print(f"Server running on {HOST}:{PORT}")
print("Mode: select")

while True:
    readable, _, _ = select.select(sockets_list, [], [])

    for sock in readable:
        if sock == server:
            conn, addr = server.accept()
            print("Connected by", addr)
            sockets_list.append(conn)
            client_addresses[conn] = addr
            send_line(conn, "Connected to select server.")
            broadcast(f"Client {addr} joined the server.", sockets_list[1:], conn)

        else:
            try:
                command = recv_line(sock)

                if not command:
                    addr = client_addresses.get(sock)
                    print("Client disconnected:", addr)
                    broadcast(f"Client {addr} left the server.", sockets_list[1:], sock)

                    sockets_list.remove(sock)
                    if sock in client_addresses:
                        del client_addresses[sock]
                    sock.close()
                    continue

                addr = client_addresses[sock]
                print(f"Command from {addr}: {command}")

                if command == "/list":
                    files = os.listdir(SERVER_FOLDER)
                    if not files:
                        send_line(sock, "EMPTY")
                    else:
                        send_line(sock, "|".join(files))

                elif command.startswith("/upload "):
                    filename = command[8:].strip()
                    send_line(sock, "OK")

                    filesize_line = recv_line(sock)
                    if not filesize_line:
                        sockets_list.remove(sock)
                        del client_addresses[sock]
                        sock.close()
                        continue

                    filesize = int(filesize_line)
                    filepath = os.path.join(SERVER_FOLDER, filename)

                    with open(filepath, "wb") as f:
                        remaining = filesize
                        while remaining > 0:
                            data = sock.recv(min(SIZE, remaining))
                            if not data:
                                break
                            f.write(data)
                            remaining -= len(data)

                    send_line(sock, "Upload finished.")
                    broadcast(f"Client {addr} uploaded file: {filename}", sockets_list[1:], sock)

                elif command.startswith("/download "):
                    filename = command[10:].strip()
                    filepath = os.path.join(SERVER_FOLDER, filename)

                    if not os.path.exists(filepath):
                        send_line(sock, "NOT FOUND")
                    else:
                        filesize = os.path.getsize(filepath)
                        send_line(sock, str(filesize))

                        reply = recv_line(sock)
                        if reply == "OK":
                            with open(filepath, "rb") as f:
                                while True:
                                    data = f.read(SIZE)
                                    if not data:
                                        break
                                    sock.sendall(data)

                elif command.startswith("/msg "):
                    message = command[5:].strip()
                    if message:
                        broadcast(f"From {addr}: {message}", sockets_list[1:], sock)
                        send_line(sock, "Message broadcasted.")
                    else:
                        send_line(sock, "Message cannot be empty.")

                elif command == "quit":
                    send_line(sock, "Goodbye.")
                    broadcast(f"Client {addr} left the server.", sockets_list[1:], sock)

                    sockets_list.remove(sock)
                    del client_addresses[sock]
                    sock.close()
                    print("Client disconnected:", addr)

                else:
                    send_line(sock, "Invalid command.")

            except:
                if sock in sockets_list:
                    sockets_list.remove(sock)
                if sock in client_addresses:
                    print("Client error/disconnected:", client_addresses[sock])
                    del client_addresses[sock]
                sock.close()