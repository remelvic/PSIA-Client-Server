import socket
import sys
import os
from zlib import crc32
from hashlib import sha256
from math import ceil

PACKET_LEN = 1024
CRC_LEN = COUNTER_LEN = 10
COUNTER_WIN_SIZE = 5
MSG_LEN = PACKET_LEN - CRC_LEN - COUNTER_LEN  # length of data
WIN_SIZE = 150

UDP_IP = "192.168.30.11"

TARGET_PORT = 5999  # where this as the sender sends stuff
LOCAL_PORT = 4999  # where this as the sender receives stuff

# parse name of file
try:
    fname = sys.argv[1]
except:
    sys.exit("Call as %s <name of file>" % sys.argv[0])

if not os.path.exists(fname):
    sys.exit("%s: No such file in directory!" % fname)

if len(fname) > MSG_LEN:
    sys.exit("Your filename is very long and very impressive. I'm proud of you,"
             " but please change it.")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("", LOCAL_PORT))  # bind for receiving confirmations
sock.settimeout(1)

print("Sending file %s to address %s, port %i, window size %s" % (fname, UDP_IP,
                                                                  TARGET_PORT, WIN_SIZE))

with open(fname, "rb") as f:
    fcontent = f.read()
    my_hash = str(sha256(fcontent).hexdigest()).encode()

    pck_count = ceil(len(fcontent) / MSG_LEN)  # how many packets to send file
    if pck_count >= 10 ** COUNTER_LEN:
        sys.exit("Sorry, the file is larger than is currently supported")
    # the packet can only fit COUNTER_LEN digits
    print("%i packets will be sent" % pck_count)

    i = 0  # the iterator has to be moved manually because of the retries :/
    current = 1
    # ^ i could surely use the iterator for this with some changes but i just
    # couldn't be arsed right now

    retry_counter = 0

    # ------------------------- BEGIN TRANSMISSION ----------------------------

    # ----------------- send file name - "packet 0" ---------------------------

    name_ok = False
    while not name_ok:
        # counter of packet
        my_counter = "0"
        while len(my_counter) < COUNTER_LEN:  # normalize counter
            my_counter = "0" + my_counter
        my_counter = bytes(my_counter, 'utf-8')  # convert to bytes

        # counter of window size

        while len(str(WIN_SIZE)) < COUNTER_WIN_SIZE:  # normalize counter winsize
            WIN_SIZE = "0" + str(WIN_SIZE)

        fname += WIN_SIZE + str(pck_count)
        # crc of packet
        name_crc = str(crc32(bytes(fname, 'utf-8')))
        while len(name_crc) < 10:  # normalize crc to be 10 digits
            name_crc = '0' + name_crc
        name_crc = bytes(name_crc, 'utf-8')

        my_name = my_counter + bytes(fname, 'utf-8') + name_crc

        sock.sendto(my_name, (UDP_IP, TARGET_PORT))
        try:
            data, addr = sock.recvfrom(1024)
            if data.decode('utf-8') == "OK":
                print("Receiver confirmed name")
                name_ok = True
                retry_counter = 0
        except socket.timeout:
            print("timeout while sending file name")
            retry_counter += 1
            if retry_counter == 10:
                sys.exit("Failed to send name repeatedly. Shutting down")

    # -------------------- send contents of the file --------------------------

    while i < len(fcontent):
        # number of packet comes first
        my_counter = str(current)
        while len(my_counter) < COUNTER_LEN:
            my_counter = "0" + my_counter
        my_counter = bytes(my_counter, 'utf-8')

        mess = fcontent[i:i + MSG_LEN]  # the message

        my_crc = str(crc32(mess))
        while len(my_crc) < 10:
            my_crc = '0' + my_crc
        my_crc = bytes(my_crc, 'utf-8')

        # assemble and send packet
        mypacket = my_counter + mess + my_crc
        sock.sendto(mypacket, (UDP_IP, TARGET_PORT))
        print("Packet %s/%s: " % (current, pck_count), end="")


        # get response
        try:
            data, addr = sock.recvfrom(1024)
            # parse response
            if data.decode('utf-8')[0:2] == "OK":  # crc matched
                print("ok")
                i += MSG_LEN  # only time we advance the iterator is when the
                # message has been received ok
                current += 1  # add to counter
                retry_counter = 0  # reset our retries
            elif data.decode('utf-8')[0:2] == "NO":
                print("CRC check failed! Re-sending last packet...")
                retry_counter += 1
            else:
                print("Unknown response received! Re-sending?")  # this should never happen!
                retry_counter += 1
        except socket.timeout:  # in case of a timeout
            print("Timeout. retrying")
            retry_counter += 1

        if retry_counter == 10:
            print("Failed to get proper response 10 times in a row. Aborting transmission.")
            break

# -----------------------------send hash----------------------------------------

hashheader = "HASH"  # this goes instead of packet number
while len(hashheader) < COUNTER_LEN:
    hashheader += "0"
hashheader = bytes(hashheader, 'utf-8')

my_crc = str(crc32(my_hash))
while len(my_crc) < 10:  # normalize crc to be 10 digits
    my_crc = '0' + my_crc
my_crc = bytes(my_crc, 'utf-8')

mypacket = hashheader + my_hash + my_crc

while True:
    sock.sendto(mypacket, (UDP_IP, TARGET_PORT))
    print("Hash sent!")
    try:
        data, addr = sock.recvfrom(1024)
        if data.decode('utf-8')[0:2] == "OK":
            print("Hashes confirmed matching")
            break

        if data.decode('utf-8')[0:2] == "XX":
            print("Hashes don't match!")
            break

        if data.decode('utf-8')[0:2] == "NO":
            print("Hash re-send requested by receiver")
            retry_counter += 1
    except sock.timeout:
        retry_counter += 1
        print("hash timeout. resending.")
    finally:
        if retry_counter == 10:
            print("Hash confirmation not received. Can't verify match.")
            break

print("Shutting down.")
