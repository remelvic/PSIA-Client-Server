import socket
import sys
import os
from zlib import crc32
from hashlib import sha256

PACKETLEN = 1024
CRCLEN = 10
COUNTERLEN = 10
COUNTERWINSIZE = 5
MSGLEN = PACKETLEN - CRCLEN - COUNTERLEN  # length of data

UDP_IP = ""
LOCAL_PORT = 5999  # where i receive
TARGET_PORT = 4999  # where i send

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Internet, UDP
# socktwo = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# receiving
# socktwo.bind(("",TARGET_PORT))
sock.bind((UDP_IP, LOCAL_PORT))  # zde připojujeme IP a port

print("Waiting, port: %i" % LOCAL_PORT)

# get name - "packet 0"

fname = ""
while not fname:
    data, addr = sock.recvfrom(1024)
    my_data = data[COUNTERLEN: len(data) - CRCLEN]
    my_crc = str(crc32(my_data))
    while len(my_crc) < 10:
        my_crc = "0" + my_crc
    try:
        if my_crc == data[-CRCLEN:].decode('utf-8') and int(
                data[:COUNTERLEN]) == 0:  # a very lenghtily written name check
            fname = my_data[:-COUNTERWINSIZE].decode('utf-8')
            winsize = my_data[-COUNTERWINSIZE:].decode("utf-8")
    except (ValueError, TypeError):
        print("Packet number not parsed")

print("Connected, address:", addr[0], "\nSaving to folder:", fname, "\nSize window:", int(winsize))
SENDER_IP = addr[0]  # IP from which we are receiving packets

sock.sendto(b"OK", (SENDER_IP, TARGET_PORT))

current = 1  # current packet

with open(fname, "wb+") as f:
    while int(current) <= int(winsize):
        while True:
            data, addr = sock.recvfrom(1024)  # buffer size is 1024 bytes

            if b"HASH" in data[:COUNTERLEN]:  # the final packet is the hash
                print("Hash received", end=" ")
                my_data = data[COUNTERLEN: len(data) - CRCLEN]
                my_crc = str(crc32(my_data))
                while len(my_crc) < 10:  # normalize crc to be 10 digits
                    my_crc = '0' + my_crc
                if data[-CRCLEN:].decode('utf-8') == my_crc:
                    print("correctly!")

                    their_hash = my_data.decode()
                    break
                else:
                    print("incorrectly")
                    sock.sendto(b"NO", (SENDER_IP, TARGET_PORT))
            else:
                # -------------parse the packet-------------------------------------

                try:
                    packet_num = int(data[:COUNTERLEN])  # number of packet
                except (ValueError, TypeError):
                    ("Packet number not parsed!")
                else:
                    my_data = data[COUNTERLEN: len(data) - CRCLEN]  # the actual data

                    # --------------create crc--------------------------------------
                    my_crc = str(crc32(my_data))  # the crc the receiver makes
                    while len(my_crc) < 10:  # normalize crc to be 10 digits
                        my_crc = '0' + my_crc

                    # -----------------evaluate correctness------------------------
                    if data[-CRCLEN:].decode('utf-8') == my_crc:  # compare CRCs
                        sock.sendto(b"OK", (SENDER_IP, TARGET_PORT))
                        if packet_num == current:  # verify that this packet is not a dupe
                            f.write(my_data)
                            current += 1
                    else:
                        sock.sendto(b"NO", (SENDER_IP, TARGET_PORT))

# ok will be sent even if a duplicate is received, but it will not be written in the file
# this is so that the sender can catch up.

with open(fname, "rb") as f:
    my_hash = str(sha256(f.read()).hexdigest())
    print("Hashes matching:", my_hash == their_hash)
    if my_hash == their_hash:
        sock.sendto(b"OK", (SENDER_IP, TARGET_PORT))
    else:
        sock.sendto(b"XX", (SENDER_IP, TARGET_PORT))
