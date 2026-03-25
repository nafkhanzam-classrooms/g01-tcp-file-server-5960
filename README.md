[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/mRmkZGKe)
# Network Programming - Assignment G01

## Anggota Kelompok
| Nama                     | NRP        | Kelas     |
| ---                      | ---        | ----------|
| Puspita Wijayanti Kusuma | 5025241059 | C         |
| Christina Tan            | 5025241060 | C         |

## Link Youtube (Unlisted)
Link ditaruh di bawah ini
```
https://www.youtube.com/watch?v=tsOZWD01BrE
```

## Penjelasan Program
### `client.py`
```python
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
```

`client.py` adalah program sebagai client untuk berkomunikasi dengan server. Mempunyai beberapa command seperti `/list`, `/upload`, `/download`, dan `/msg`. Client membuat koneksi ke server dan berkomunikasi menggunakan fungsi `send_line()` dan `recv_line()`. Saat client mengirim command, fungsi seperti `do_list()`, `do_upload()`, dan `do_download()` akan dijalankan untuk mengirim request ke server dan menerima respon dari server. File hasil download disimpan ke folder `client_downloads` dan file yang diupload akan tersimpan di server di folder `server_files`. Untuk implementasi menerima broadcast, dibuat thread khusus `receive_messages` untuk menerima messages dari server dan client lain. Pesan broadcast ditandai dengan prefix "BROADCAST:" dan langsung ditampilkan, sedangkan respon biasa dimasukkan ke `response_queue` agar bisa diambil oleh fungsi `get_response()`. Dengan cara ini, client bisa tetap menerima pesan kapan saja tanpa mengganggu alur command, sehingga fitur broadcast bisa berjalan bersamaan dengan transfer file.

### `server-sync.py`
```python
import os
import socket

HOST = "127.0.0.1"
PORT = 5000
SIZE = 4096
SERVER_FOLDER = "server_files"

os.makedirs(SERVER_FOLDER, exist_ok=True)

clients = []


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
    for client in clients:
        if client != sender:
            try:
                send_line(client, "BROADCAST:" + message)
            except:
                pass


def handle_client(conn, addr):
    print(f"Client connected: {addr}")
    send_line(conn, "Connected to sync server.")

    while True:
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

            send_line(conn, "Upload finished.")
            broadcast(f"Client {addr} uploaded file: {filename}", conn)

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

    conn.close()
    if conn in clients:
        clients.remove(conn)
    print(f"Client disconnected: {addr}")


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen(1)

    print(f"Server running on {HOST}:{PORT}")
    print("Mode: synchronous")

    while True:
        conn, addr = server.accept()
        clients.append(conn)
        handle_client(conn, addr)


if __name__ == "__main__":
    main()
```

`server-sync.py` adalah program server untuk berkomunikasi dengan client dan berjalan secara synchronous (hanya dapat menerima 1 client per waktu). Server akan menunggu koneksi dari client menggunakan `accept()`, kemudian setiap client yang terconnect akan ditambahkan ke dalam list `clients`. Komunikasi antara server dan client dilakukan menggunakan fungsi `send_line()` untuk mengirim data dan `recv_line()` untuk menerima data. Server ini mengsupport beberapa command dari client seperti `/list`, `/upload`, `/download`, dan `/msg`. Saat server menerima command, fungsi `handle_client()` akan memproses request tersebut. `/list` digunakan untuk menampilkan daftar file yang ada di folder `server_files`, `/upload` digunakan untuk menerima file dari client dan menyimpannya ke server, dan `/download` digunakan untuk mengirim file dari server ke client. Untuk fitur broadcast, server menggunakan fungsi `broadcast()` untuk mengirim message ke semua client yang terhubung kecuali sender. Message broadcast ditandai dengan prefix "BROADCAST:" sehingga dapat dikenali oleh client. Dengan mekanisme ini, server bisa menangani transfer file dan juga mengsupport komunikasi antar client melalui fitur broadcast.

### `server-select.py`
```python
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
```

`server-select.py` adalah program server yang digunakan untuk berkomunikasi dengan client dan berjalan menggunakan mekanisme non-blocking dengan modul select, sehingga server dapat menangani banyak client secara bersamaan. Server akan menunggu aktivitas pada beberapa socket menggunakan `select.select()`, baik itu koneksi baru maupun data dari client yang sudah terhubung. Ketika ada client baru, server akan menerima koneksi menggunakan `accept()`, lalu menambahkan socket client tersebut ke dalam `sockets_list` dan menyimpan addressnya di `client_addresses`. Komunikasi antara server dan client tetap menggunakan fungsi `send_line()` untuk dan `recv_line()`.

<br>

### `server-poll.py`
```python
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
```

File `server-poll.py` ini adalah implementasi TCP file server yang bisa menangani banyak client sekaligus tanpa menggunakan thread. Jadi semua koneksi ditangani dalam satu proses utama dengan bantuan `select.poll()`, yang berfungsi untuk memantau banyak socket dan memberi tahu kapan socket tersebut siap dibaca atau ditulis. Karena socket di-set non-blocking, server tidak akan berhenti menunggu satu client saja, tapi bisa langsung lanjut menangani client lain yang siap.

Di awal program, server dibuat dengan socket TCP biasa, lalu di-bind ke alamat dan port tertentu. Folder `server_files` juga terdapat folder sebagai tempat penyimpanan file di sisi server. Setelah itu, server didaftarkan ke poller supaya setiap ada koneksi baru atau data masuk, server bisa langsung mendeteksinya lewat event yang diberikan oleh `poll()`.

Karena tidak menggunakan thread, server harus menyimpan kondisi setiap client secara manual. Di sini digunakan beberapa struktur data seperti `clients` untuk menyimpan alamat client, `buffers` untuk menampung data yang masuk (karena data TCP bisa datang tidak langsung full), serta `upload_states` dan `download_states` untuk menyimpan status transfer file. Misalnya saat client sedang upload, server harus tahu sudah berapa byte yang diterima dan apakah masih menunggu ukuran file atau sudah masuk ke isi file.

Untuk komunikasi, server membedakan dua jenis data, yaitu perintah teks dan data file. Perintah seperti `/list`, `/upload`, `/download`, dan `/msg` dikirim dalam bentuk teks yang diakhiri newline, lalu diproses oleh fungsi `handle_command`. Sedangkan untuk file, data dikirim dalam bentuk biner per chunk. Supaya tidak tertukar, server menggunakan mekanisme buffer dan parsing per baris melalui `recv_line_from_buffer`. 

Alur dari command `/list` yaitu akan mengirim daftar file di server. `/upload` dimulai dengan client mengirim nama file, lalu ukuran file, baru isi file dikirim bertahap sampai selesai. `/download` kebalikannya, server kirim ukuran file dulu, lalu menunggu konfirmasi "OK" dari client sebelum mengirim isi file. Untuk `/msg`, server akan broadcast pesan ke semua client lain dengan format tertentu supaya bisa dikenali sebagai broadcast di sisi client.

Loop utama server berjalan dengan `poller.poll()`. Setiap event yang muncul akan dicek, kalau dari socket server berarti ada client baru yang connect, kalau dari socket client berarti ada data masuk. Data ini kemudian diproses berdasarkan kondisi client, apakah sedang upload, download, atau hanya mengirim command biasa. Terakhir, ada fungsi `cleanup_client` menjaga server tetap stabil. Kalau ada client yang disconnect atau error, semua data terkait client tersebut dibersihkan, termasuk buffer dan file yang mungkin masih terbuka. Ini mencegah memory leak dan memastikan server tetap bisa melayani client lain tanpa masalah.

<br>

### `server-thread.py`
```python
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
```

File `server-thread.py` ini mengimplementasikan TCP file server dengan multithreading, di mana setiap client yang terhubung akan dilayani oleh satu thread tersendiri. Jadi saat ada beberapa client yang melakukan aktivitas seperti upload, download, atau kirim pesan, semuanya bisa berjalan secara bersamaan tanpa harus saling menunggu. 

Untuk mengelola client yang sedang aktif, server menyimpan semua koneksi di dalam list `clients`. Karena list ini diakses oleh banyak thread sekaligus, digunakan `clients_lock` untuk mencegah konflik saat ada thread yang menambah atau menghapus client. Tanpa lock ini, bisa terjadi race condition, misalnya dua thread mencoba mengubah list di waktu yang sama dan menyebabkan error. Jadi setiap operasi yang berhubungan dengan list client selalu  di-lock agar aman.

Dari sisi komunikasi, server membedakan antara perintah teks dan data file. Perintah seperti `/list`, `/upload`, `/download`, `/msg`, dan `quit` dikirim dalam bentuk teks satu baris (diakhiri newline), dan diproses menggunakan fungsi `recv_line`. Sedangkan untuk data file, digunakan metode chunk-based, di mana file dikirim sedikit demi sedikit dalam bentuk biner. Karena setiap client punya thread sendiri jadi lebih sederhana, di mana server tidak perlu menyimpan banyak state seperti pada model poll atau select.

Untuk fitur-fiturnya, `/list` akan mengirim daftar file yang ada di folder server. Untuk `/upload` dimulai dengan server mengirim `OK`, lalu client mengirim ukuran file dan isi file sampai selesai. Kalau berhasil, server mengirim `Upload finished.` dan memberi tahu client lain bahwa ada file baru. `/download` bekerja sebaliknya, server kirim ukuran file dulu, lalu menunggu konfirmasi `OK` sebelum mengirim isi file. Untuk `/msg`, server akan mengirim pesan ke semua client lain menggunakan fungsi `broadcast`, sekaligus menangani jika ada client yang sudah tidak aktif.

Alur utama server ada di fungsi `main()`, di mana server menunggu koneksi masuk menggunakan `accept()`. Setiap kali ada client baru, server langsung membuat thread baru yang menjalankan fungsi `handle_client`. Di dalam fungsi ini, server terus membaca command dari client sampai client disconnect atau mengirim `quit`. Setelah itu, koneksi ditutup dan client dihapus dari list.

<br>

## Screenshot Hasil
### Modul synchronous
`server`:
![](/media/sync_server.png)
<br>

`client`:
![](/media/sync_client.png)

<br>

### Modul select
`server`:
![](/media/select_server.png)
<br>

`client`:
![](/media/select_client1.png)

![](/media/select_client2.png)


### Modul poll

`server and clients`  
![img](/media/server-poll.jpeg)


### Modul thread
`server and clients`  
![img](/media/server-thread-img.jpeg)