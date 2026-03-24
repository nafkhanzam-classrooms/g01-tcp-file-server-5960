import os
import socket
import threading

HOST = "127.0.0.1"
PORT = 5000
SIZE = 4096
SERVER_FOLDER = "server_files"

os.makedirs(SERVER_FOLDER, exist_ok=True)

clients = []
clients_lock = threading.Lock()


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


def broadcast(message, sender=None):
    disconnected = []

    with clients_lock:
        current_clients = list(clients)

    for client in current_clients:
        if client != sender:
            try:
                send_line(client, "BROADCAST:" + message)
            except:
                disconnected.append(client)

    if disconnected:
        with clients_lock:
            for client in disconnected:
                if client in clients:
                    clients.remove(client)
                try:
                    client.close()
                except:
                    pass


def remove_client(conn):
    with clients_lock:
        if conn in clients:
            clients.remove(conn)


def handle_client(conn, addr):
    print(f"Client connected: {addr}")
    send_line(conn, "Connected to threaded server.")
    broadcast(f"Client {addr} joined the server.", conn)

    while True:
        try:
            command = recv_line(conn)
            if not command:
                break

            print(f"Command from {addr}: {command}")

            if command == "/list":
                files = os.listdir(SERVER_FOLDER)
                if not files:
                    send_line(conn, "EMPTY")
                else:
                    send_line(conn, "|".join(files))

            elif command.startswith("/upload "):
                filename = command[8:].strip()
                send_line(conn, "OK")

                filesize_line = recv_line(conn)
                if not filesize_line:
                    break

                filesize = int(filesize_line)
                filepath = os.path.join(SERVER_FOLDER, filename)

                with open(filepath, "wb") as f:
                    remaining = filesize
                    while remaining > 0:
                        data = conn.recv(min(SIZE, remaining))
                        if not data:
                            break
                        f.write(data)
                        remaining -= len(data)

                if remaining == 0:
                    send_line(conn, "Upload finished.")
                    broadcast(f"Client {addr} uploaded file: {filename}", conn)
                else:
                    send_line(conn, "Upload failed.")

            elif command.startswith("/download "):
                filename = command[10:].strip()
                filepath = os.path.join(SERVER_FOLDER, filename)

                if not os.path.exists(filepath):
                    send_line(conn, "NOT FOUND")
                else:
                    filesize = os.path.getsize(filepath)
                    send_line(conn, str(filesize))

                    reply = recv_line(conn)
                    if reply == "OK":
                        with open(filepath, "rb") as f:
                            while True:
                                data = f.read(SIZE)
                                if not data:
                                    break
                                conn.sendall(data)

            elif command.startswith("/msg "):
                message = command[5:].strip()
                if message:
                    broadcast(f"From {addr}: {message}", conn)
                    send_line(conn, "Message broadcasted.")
                else:
                    send_line(conn, "Message cannot be empty.")

            elif command == "quit":
                send_line(conn, "Goodbye.")
                break

            else:
                send_line(conn, "Invalid command.")

        except:
            break

    remove_client(conn)
    conn.close()
    broadcast(f"Client {addr} left the server.", conn)
    print(f"Client disconnected: {addr}")


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()

    print(f"Server running on {HOST}:{PORT}")
    print("Mode: threaded")

    while True:
        conn, addr = server.accept()
        with clients_lock:
            clients.append(conn)
        thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        thread.start()


if __name__ == "__main__":
    main()
