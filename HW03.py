import socket
import sys
import os
from zlib import crc32
from hashlib import sha256
from math import ceil

import utils

PACKET_LEN = 1024
CRC_LEN = COUNTER_LEN = 10
COUNTER_WIN_SIZE = 5
MSG_LEN = PACKET_LEN - CRC_LEN - COUNTER_LEN  # length of data
WIN_SIZE = 5

UDP_IP = "192.168.30.21"

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
    sys.exit("Given filename exceeds maximum data length. Please change it.")

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

    fname += ";" + str(pck_count)
    # crc of packet
    name_crc = str(crc32(bytes(fname, 'utf-8')))
    while len(name_crc) < 10:  # normalize crc to be 10 digits
        name_crc = '0' + name_crc
    name_crc = bytes(name_crc, 'utf-8')

    my_name = my_counter + bytes(fname, 'utf-8') + name_crc

    sock.sendto(my_name, (UDP_IP, TARGET_PORT))
    try:
        data, addr = sock.recvfrom(1024)
        if data.decode('utf-8') == "ACK0":
            print("Receiver confirmed name")
            name_ok = True
            retry_counter = 0
    except socket.timeout:
        print("timeout while sending file name")
        retry_counter += 1
        if retry_counter == 10:
            sys.exit("Failed to send name repeatedly. Shutting down")

    # -------------------- send contents of the file --------------------------

awaiting_ack = [] #counters of packets awaiting ACK

finished = False
while not finished:
        
    for j in range(WIN_SIZE):
        # make packet
        my_packet = utils.make_packet(i,fcontent, COUNTER_LEN, MSG_LEN, CRC_LEN)
        
        sock.sendto(my_packet, (UDP_IP, TARGET_PORT))
        print("Packet %s/%s sent " % ((i//MSG_LEN)+1, pck_count))
    
        awaiting_ack.append((i//MSG_LEN)+1)
        i += MSG_LEN

    # get response
    print(awaiting_ack)
    while awaiting_ack:
        try:
            data, addr = sock.recvfrom(1024)
            my_ack = data.decode('utf-8')
            # parse response
            if my_ack[0:3] == "ACK":  # crc matched
                #try:
                ack_num = int(my_ack[3:])
                print("ACK", ack_num)
                awaiting_ack.remove(ack_num)

                #except (ValueError, TypeError):
                    #print("ack number not parsed:" + my_ack[2:])
                
                retry_counter = 0  # reset our retries
                if i >= len(fcontent) and not awaiting_ack:
                    finished = True

            elif data.decode('utf-8')[0:3] == "RES":
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
            finished = True

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
    except socket.timeout:
        retry_counter += 1
        print("hash timeout. resending.")
    finally:
            if retry_counter == 10:
                print("Hash confirmation not received. Can't verify match.")
                break

print("Shutting down.")
