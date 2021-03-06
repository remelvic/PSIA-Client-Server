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
WIN_SIZE = 15

UDP_IP = "127.0.0.1"

TARGET_PORT = 5998  # where this as the sender sends stuff
LOCAL_PORT = 4998  # where this as the sender receives stuff

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

i = 1  # the iterator has to be moved manually because of the retries :/

retry_counter = 0
timeouts = 0

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
        if data[:4].decode('utf-8', 'ignore') == "ACK0":
            print("Receiver confirmed name")
            name_ok = True
            timeouts = 0
        elif data[:4].decode('utf-8', 'ignore') == "RES0":
            print("Name resend requested")
    except socket.timeout:
        print("timeout while sending file name")
        timeouts += 1
        if timeouts == 10:
            sys.exit("Failed to connect to receiver")

    # -------------------- send contents of the file --------------------------

awaiting_ack = [] #counters of packets awaiting ACK
send_hash = False #whether hash will be sent. will be true if file sent succesfully

finished = False
while not finished:
        
    for j in range(WIN_SIZE):
        # make packet
        if i > pck_count:
            break
        my_packet = utils.make_packet(i,fcontent, COUNTER_LEN, MSG_LEN, CRC_LEN)
        
        sock.sendto(my_packet, (UDP_IP, TARGET_PORT))
        print("Packet %s/%s sent " % (i, pck_count))
    
        awaiting_ack.append(i)
        i += 1

    # get response
    
    while awaiting_ack:
        try:
            data, addr = sock.recvfrom(1024)
            my_ack = data.decode('utf-8') #parsing the ack here
            ack_type = my_ack[0:3]
            ack_num = int(my_ack[3:-CRC_LEN])
            ack_crc = my_ack[-CRC_LEN:]

        except UnicodeError:
            print("A response was not successfully decoded")
        except (ValueError, TypeError):
            print("ack number not parsed:" + my_ack[3:-CRC_LEN])
        except socket.timeout:  # in case of a timeout
            if timeouts >= 10:
                print("Connection to receiver has timed out.")
                finished = True
                break
            print("Timeout. retrying")
            for j in awaiting_ack:
                my_packet = utils.make_packet(j,fcontent, COUNTER_LEN, MSG_LEN, CRC_LEN)
                sock.sendto(my_packet, (UDP_IP, TARGET_PORT))
                print("Packet %s/%s sent " % (j, pck_count))
            timeouts += 1

        else:
            my_crc = str(crc32(data[:-CRC_LEN]))
            while len(my_crc) < CRC_LEN:  # normalize crc
                my_crc = '0' + my_crc

            # CHECK CRC
            if my_crc == ack_crc:
                if ack_type == "ACK":
                    print("ACK", ack_num)
                    if ack_num in awaiting_ack:
                        awaiting_ack.remove(ack_num)
                    timeouts = 0
                    if i > pck_count and not awaiting_ack:
                        finished = send_hash = True

                elif ack_type == "RES":
                    print("RES", ack_num)
                    my_packet = utils.make_packet(ack_num,fcontent, COUNTER_LEN, MSG_LEN, CRC_LEN)
                    sock.sendto(my_packet, (UDP_IP, TARGET_PORT))
                    print("Packet %s/%s sent " % (ack_num, pck_count))      

            else:
                print("ACK doesn't match CRC")          

# -----------------------------send hash----------------------------------------

hashheader = "HASH"  # this goes instead of packet number
while len(hashheader) < COUNTER_LEN:
    hashheader = "0" + hashheader
hashheader = bytes(hashheader, 'utf-8')

my_hash = hashheader + my_hash

my_crc = str(crc32(my_hash))
while len(my_crc) < 10:  # normalize crc to be 10 digits
    my_crc = '0' + my_crc
my_crc = bytes(my_crc, 'utf-8')

mypacket = my_hash + my_crc

while send_hash:
    sock.sendto(mypacket, (UDP_IP, TARGET_PORT))
    print("Hash sent!")
    try:
        data, addr = sock.recvfrom(1024)
        if data.decode('utf-8')[0:3] == "ACK":
            print("Hashes confirmed matching")
            send_hash = False

        if data.decode('utf-8')[0:4] == "NACK":
            print("Hashes don't match!")
            send_hash = False

        if data.decode('utf-8')[0:3] == "RES":
            print("Hash re-send requested by receiver")

    except UnicodeError:
        print("Unicode error")
    except socket.timeout:
        timeouts += 1
        print("hash timeout. resending.")
    finally:
            if timeouts == 10:
                print("Hash confirmation not received. Can't verify match.")
                break

print("Shutting down.")
