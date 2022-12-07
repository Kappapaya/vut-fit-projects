#!/usr/bin/env python3

import sys
import argparse
import re
import os
import socket

# kontrola poctu argumentu
if (len(sys.argv) != 5):
    sys.stderr.write("Invalid number of arguments.")
    sys.exit(2)

# parsovani argumentu, -n je ip adresa a -f je surl
parser = argparse.ArgumentParser()
parser.add_argument('-n', required=True) #
parser.add_argument('-f', required=True) 

# rozdeleni ip adresy a cisla portu
string_split = sys.argv[2].split(":")
ip_address = string_split[0] 
port = int(string_split[1]) 

# osetreni ip adresy
ip_match = re.search(r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$", string_split[0])
if (not ip_match):
    sys.stderr.write("Invalid ip address.")
    sys.exit(2)
    
# osetreni portu
if port < 1 and port > 65535:
    sys.stderr.write("Invalid port number")
    sys.exit(2)
    
# kontrola surl (cesty)
surl = sys.argv[4]
path_match = re.search(r"fsp:\/\/[a-zA-Z0-9\-\_\.]+(\/\w+)*(\*?|\w+)($|\.\w+)", surl)
if (not path_match):
    sys.stderr.write("Invalid path.")
    sys.exit(2)

# rozdeleni serveru od fsp a cesty k souboru (tri lomitka?)
separate_f_p = surl.split("/",3)

# najdu adresar, ve kterem se nachazim
current_dir = os.getcwd()  

# vytvorim sockety pro name a file server
try:
    ns_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #name server
    fs_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #file server
except socket.error:
    sys.stderr.write("Error while creating sockets.")
    sys.exit(2)

# pripojeni, UDP komunikace
try:
    ns_socket.connect((ip_address, port))
    ns_socket.send(f"WHEREIS {separate_f_p[2]}".encode('utf-8')) # first.server
    ns_data = ns_socket.recv(1024).split(b' ', 1) # prijme zpravu OK 127.0.0.1:nove_cislo_portu

    if (ns_data[0] == b'ERR'):
        sys.stderr.write("File server " + ns_data[1].decode("utf-8").lower())
        sys.exit(2)
    ns_socket.close()
    
except (socket.timeout, socket.error):
    sys.stderr.write("Server is not responding.")
    sys.exit(2)

# rozdeleni ip adresy a portu pro file server
split_ns_data = ns_data[1].split(b':')
f_ip = split_ns_data[0].decode("utf-8") # osetrit ip a port??
f_port = int(split_ns_data[1].decode("utf-8"))

# pripojeni k file serveru
try:
    fs_socket.connect((f_ip, f_port))
except (socket.gaierror, socket.error):
    sys.stderr.write("Failed to connect to the server.")
    sys.exit(2)

file_name = separate_f_p[3].split("/")  #jmeno souboru

# request_func posle dotaz GET
def request_func(filename, fileserver, s_socket):
    try:
        s_socket.send(("GET " + filename + " FSP/1.0\r\nHostname: " + fileserver + "\r\nAgent: xauero00\r\n\r\n").encode("utf-8"))

        # odejmuti hlavicky, zapis dat
        header = True
        url = filename.split("/")
        with open(os.path.join(current_dir, url[len(url) - 1]), "wb") as file:
            while True:
                fs_data = s_socket.recv(1024) # odpoved FSP/1.0 Success\r\nLength: 34\r\n\r\nobsah_souboru

                if (header):
                    if (not fs_data):
                        break

                    if (fs_data.find(b'Not Found') == -1):
                        header = False
                    else:
                        file.close()
                        os.remove(os.path.join(current_dir, url[len(url) - 1]))
                        sys.stderr.write("File not found.")
                        sys.exit(2)

                    if (fs_data.find(b'Bad Request') == -1):
                        header = False
                    else:
                        file.close()
                        os.remove(os.path.join(current_dir, url[len(url) - 1]))
                        sys.stderr.write("Bad request.")
                        sys.exit(2)

                    if (fs_data.find(b'Server Error') == -1):
                        header = False
                    else:
                        file.close()
                        os.remove(os.path.join(current_dir, url[len(url) - 1]))
                        sys.stderr.write("Server error.")
                        sys.exit(2)
                else:
                    if (not fs_data):
                        break
                    file.write(fs_data)
            file.close()
        s_socket.close()
    except (socket.timeout, socket.error):
        sys.stderr.write("Server is not responding.")
        sys.exit(2)


# GET ALL
if (file_name[len(file_name) - 1] == '*'):
    try:
        fs_socket.send(("GET index FSP/1.0\r\nHostname: " + separate_f_p[2] + "\r\nAgent: xauero00\r\n\r\n").encode("utf-8"))

        header = True
        while True:
            data = fs_socket.recv(1024)
            if (header):
                if (not data):
                    break
                header = False
            else:
                if (not data):
                    break
                all_files = data.decode('utf-8').split("\r\n")
        fs_socket.close()
    except (socket.timeout, socket.error):
        sys.stderr.write("Server is not responding.")
        sys.exit(2)

    # dokud stahuju, musim vytvaret nove sockety, aby prosly data
    for i in range(len(all_files) - 1):
        try:
            fs_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            fs_socket.connect((f_ip, f_port))
            request_func(all_files[i], separate_f_p[2], fs_socket)

        except (socket.gaierror, socket.error):
            sys.stderr.write("Server is not responding.")
            sys.exit(2)
else:
    request_func(separate_f_p[len(separate_f_p) - 1], separate_f_p[2], fs_socket)

