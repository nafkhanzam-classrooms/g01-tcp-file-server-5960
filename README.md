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