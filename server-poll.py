import os
import socket
import select

HOST = "127.0.0.1"
PORT = 5000
SIZE = 4096
SERVER_FOLDER = "server_files"

os.makedirs(SERVER_FOLDER, exist_ok=True)

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen()
server.setblocking(False)

poller = select.poll()
poller.register(server, select.POLLIN)

fd_to_socket = {server.fileno(): server}
clients = {}
buffers = {}
upload_states = {}
download_states = {}


def send_line(sock, text):
    sock.sendall((text + "\n").encode())


def recv_line_from_buffer(sock):
    buf = buffers.get(sock, b"")
    if b"\n" not in buf:
        return None

    line, rest = buf.split(b"\n", 1)
    buffers[sock] = rest
    return line.decode().strip()


def cleanup_client(sock):
    addr = clients.get(sock)

    if addr is not None:
        print(f"[DISCONNECT] Client disconnected: {addr}")

    try:
        poller.unregister(sock)
    except:
        pass

    fd = sock.fileno()

    if sock in clients:
        del clients[sock]
    if sock in buffers:
        del buffers[sock]
    if sock in upload_states:
        state = upload_states[sock]
        if state.get("file"):
            try:
                state["file"].close()
            except:
                pass
        del upload_states[sock]
    if sock in download_states:
        del download_states[sock]
    if fd in fd_to_socket:
        del fd_to_socket[fd]

    try:
        sock.close()
    except:
        pass


def broadcast(sender_sock, text):
    dead_clients = []

    for client_sock in list(clients.keys()):
        if client_sock != sender_sock:
            try:
                send_line(client_sock, f"BROADCAST:{text}")
            except:
                dead_clients.append(client_sock)

    for dead_sock in dead_clients:
        cleanup_client(dead_sock)


def handle_command(sock, command):
    addr = clients.get(sock)
    print(f"[COMMAND] From {addr}: {command}")

    if command == "/list":
        print(f"[LIST] {addr} requested file list")
        files = os.listdir(SERVER_FOLDER)

        if not files:
            send_line(sock, "EMPTY")
            print(f"[LIST-RESULT] Sent EMPTY to {addr}")
        else:
            send_line(sock, "|".join(files))
            print(f"[LIST-RESULT] Sent file list to {addr}: {files}")

    elif command.startswith("/upload "):
        filename = command[8:].strip()

        if not filename:
            send_line(sock, "Invalid filename.")
            print(f"[UPLOAD-ERROR] {addr} sent invalid filename")
            return

        print(f"[UPLOAD-REQ] {addr} wants to upload {filename}")

        upload_states[sock] = {
            "filename": os.path.basename(filename),
            "waiting_size": True,
            "filesize": 0,
            "received": 0,
            "file": None,
        }
        send_line(sock, "OK")
        print(f"[UPLOAD-ACK] Ready to receive {filename} from {addr}")

    elif command.startswith("/download "):
        filename = command[10:].strip()
        filepath = os.path.join(SERVER_FOLDER, os.path.basename(filename))

        print(f"[DOWNLOAD-REQ] {addr} requested {filename}")

        if not os.path.exists(filepath):
            send_line(sock, "NOT FOUND")
            print(f"[DOWNLOAD-FAIL] File not found: {filename}")
            return

        filesize = os.path.getsize(filepath)
        download_states[sock] = {
            "filepath": filepath,
            "waiting_ack": True,
        }

        send_line(sock, str(filesize))
        print(f"[DOWNLOAD-READY] {filename} ({filesize} bytes) prepared for {addr}")

    elif command.startswith("/msg "):
        text = command[5:].strip()

        if not text:
            send_line(sock, "Message cannot be empty.")
            print(f"[MSG-ERROR] Empty message from {addr}")
            return

        print(f"[MSG] {addr}: {text}")
        broadcast_text = f"From {addr}: {text}"
        broadcast(sock, broadcast_text)
        send_line(sock, "Message broadcasted.")
        print(f"[MSG-DONE] Broadcasted message from {addr}")

    elif command == "quit":
        print(f"[QUIT] {addr} disconnected by request")
        send_line(sock, "Goodbye.")
        cleanup_client(sock)

    else:
        send_line(sock, "Unknown command.")
        print(f"[UNKNOWN] {addr}: {command}")


print(f"Server running on {HOST}:{PORT}")
print("Mode: poll")

while True:
    events = poller.poll()

    for fd, event in events:
        sock = fd_to_socket[fd]

        if sock is server:
            client_sock, client_addr = server.accept()
            client_sock.setblocking(False)

            poller.register(client_sock, select.POLLIN)
            fd_to_socket[client_sock.fileno()] = client_sock
            clients[client_sock] = client_addr
            buffers[client_sock] = b""

            print(f"[CONNECT] Client connected: {client_addr}")
            send_line(client_sock, "Connected to poll server.")

        else:
            if event & (select.POLLHUP | select.POLLERR):
                print(f"[SOCKET-EVENT] HUP/ERR from {clients.get(sock)}")
                cleanup_client(sock)
                continue

            try:
                data = sock.recv(SIZE)

                if not data:
                    cleanup_client(sock)
                    continue

                if sock in upload_states:
                    state = upload_states[sock]
                    addr = clients.get(sock)

                    if state["waiting_size"]:
                        buffers[sock] += data
                        size_line = recv_line_from_buffer(sock)

                        if size_line is None:
                            continue

                        try:
                            filesize = int(size_line)
                        except ValueError:
                            send_line(sock, "Invalid filesize.")
                            print(f"[UPLOAD-ERROR] Invalid filesize from {addr}: {size_line}")
                            if state["file"]:
                                state["file"].close()
                            del upload_states[sock]
                            continue

                        filepath = os.path.join(SERVER_FOLDER, state["filename"])
                        state["filesize"] = filesize
                        state["waiting_size"] = False
                        state["received"] = 0
                        state["file"] = open(filepath, "wb")

                        print(
                            f"[UPLOAD-START] {addr} uploading {state['filename']} "
                            f"({filesize} bytes)"
                        )

                        leftover = buffers[sock]
                        buffers[sock] = b""

                        if leftover:
                            write_size = min(
                                len(leftover),
                                state["filesize"] - state["received"]
                            )
                            state["file"].write(leftover[:write_size])
                            state["received"] += write_size

                        if state["received"] >= state["filesize"]:
                            state["file"].close()
                            filename = state["filename"]
                            print(f"[UPLOAD-DONE] {addr} uploaded {filename}")
                            del upload_states[sock]
                            send_line(sock, "Upload finished.")
                            broadcast(sock, f"Client {addr} uploaded file: {filename}")
                            print(f"[UPLOAD-BROADCAST] Notified others about upload {filename}")

                    else:
                        remaining = state["filesize"] - state["received"]
                        chunk = data[:remaining]

                        state["file"].write(chunk)
                        state["received"] += len(chunk)

                        if state["received"] >= state["filesize"]:
                            state["file"].close()
                            extra = data[remaining:]
                            filename = state["filename"]

                            print(f"[UPLOAD-DONE] {addr} uploaded {filename}")

                            del upload_states[sock]
                            send_line(sock, "Upload finished.")
                            broadcast(sock, f"Client {addr} uploaded file: {filename}")
                            print(f"[UPLOAD-BROADCAST] Notified others about upload {filename}")

                            if extra:
                                buffers[sock] += extra

                elif sock in download_states:
                    state = download_states[sock]
                    addr = clients.get(sock)

                    if state["waiting_ack"]:
                        buffers[sock] += data
                        ack = recv_line_from_buffer(sock)

                        if ack is None:
                            continue

                        if ack == "OK":
                            filename = os.path.basename(state["filepath"])
                            print(f"[DOWNLOAD-START] Sending {filename} to {addr}")

                            with open(state["filepath"], "rb") as f:
                                while True:
                                    chunk = f.read(SIZE)
                                    if not chunk:
                                        break
                                    sock.sendall(chunk)

                            print(f"[DOWNLOAD-DONE] Sent {filename} to {addr}")
                        else:
                            print(f"[DOWNLOAD-CANCEL] Invalid ACK from {addr}: {ack}")

                        del download_states[sock]

                else:
                    buffers[sock] += data

                    while True:
                        command = recv_line_from_buffer(sock)
                        if command is None:
                            break
                        handle_command(sock, command)

            except ConnectionResetError:
                print(f"[ERROR] Connection reset by {clients.get(sock)}")
                cleanup_client(sock)
            except Exception as e:
                print(f"[ERROR] {e}")
                cleanup_client(sock)