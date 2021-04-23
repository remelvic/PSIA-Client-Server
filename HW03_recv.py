import socket
from zlib import crc32
from hashlib import sha256

import utils

PACKET_LEN = 1024
CRC_LEN = COUNTER_LEN = 10
COUNTER_WIN_SIZE_LEN = 5
COUNTER_OF_PACKETS_LEN = 3
MSG_LEN = PACKET_LEN - CRC_LEN - COUNTER_LEN  # length of data
FILE_NAME = COUNTER_WIN_SIZE_LEN + COUNTER_OF_PACKETS_LEN

UDP_IP = ""
LOCAL_PORT = 5999  # where i receive
TARGET_PORT = 4999  # where i send

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Internet, UDP

# receiving
sock.bind((UDP_IP, LOCAL_PORT))

print("Waiting, port: %i" % LOCAL_PORT)

# get name - "packet 0"

fname = ""
while not fname:
    data, addr = sock.recvfrom(1024)
    my_data = data[COUNTER_LEN: len(data) - CRC_LEN]
    my_crc = str(crc32(my_data))
    my_data = my_data.decode('utf-8')

    while len(my_crc) < 10:
        my_crc = "0" + my_crc
    try:
        if my_crc == data[-CRC_LEN:].decode('utf-8') and int(
                data[:COUNTER_LEN]) == 0:  # a very lenghtily written name check
            my_data = str(my_data)
            fname = my_data.split(";")[0]
            num_of_packets = int(my_data.split(";")[1])
        else: print ("a",end="")
    except UnicodeError: 
        print("Name couldn't be decoded")
    except (ValueError, TypeError):
        print("File name not parsed")

print("Connected, address:", addr[0], "\nSaving to folder:", fname, "\nNumber of packets:", int(num_of_packets))
SENDER_IP = addr[0]  # IP from which we are receiving packets

sock.sendto(b"ACK0", (SENDER_IP, TARGET_PORT))


current = 1  # current packet

my_file = b"" #we first write into a bytes object
data_buffer = [] #buffer data that is ahead
idx_buffer = []
their_hash = "" #define this first
sock.settimeout(15)


finished = False

while not finished:
    try:
        data, addr = sock.recvfrom(1024)  # total packet size is 1024 bytes
        my_data = data[COUNTER_LEN: len(data) - CRC_LEN]
        if b"HASH" in data[:COUNTER_LEN]:
            their_hash = my_data.decode('utf-8','ignore')
        else:
            packet_num = int(data[:COUNTER_LEN])
        
        crc = data[-CRC_LEN:].decode('utf-8') #crc in packet
       
        my_crc = str(crc32(data[:len(data)-CRC_LEN])) #crc of what i got
        while len(my_crc) < CRC_LEN:  # normalize crc to be 10 digits
            my_crc = '0' + my_crc

    except(ValueError, TypeError, UnicodeError):
        print("A packet was not parsed")
    except socket.timeout:
        print("Connection timed out")
        finished = True
    
    else:
        if their_hash:  # the final packet is the hash
            print("Hash received", end=" ")
            if crc == my_crc:
                print("correctly!")
                their_hash = my_data.decode('utf-8','ignore')
                finished = True
            else:
                print("incorrectly")
                sock.sendto(b"RES", (SENDER_IP, TARGET_PORT))
        else:
                # -----------------evaluate correctness------------------------
                if crc == my_crc:  # compare CRCs                
                    my_ack = utils.make_ack(True, packet_num, CRC_LEN) # this is a little messy
                    sock.sendto(my_ack, (SENDER_IP, TARGET_PORT))
                    if packet_num == current:
                        my_file += my_data
                        current += 1
                        while current in idx_buffer: #write buffered data if possible
                            my_file += data_buffer[idx_buffer.index(current)]
                            data_buffer.pop(idx_buffer.index(current))
                            idx_buffer.remove(current)
                            print("Popped %i from buffer" % current)
                            current +=1                         

                    elif packet_num > current and packet_num not in idx_buffer: #buffer ahead of time data
                        idx_buffer.append(packet_num)
                        data_buffer.append(my_data)
                        print("Buffered packet %i" % packet_num)


                else:
                    my_ack = utils.make_ack(False, packet_num, CRC_LEN)
                    sock.sendto(my_ack, (SENDER_IP, TARGET_PORT))

# ack will be sent even if an old packet is received, but it will not be written in the file

if their_hash:
    my_hash = str(sha256(my_file).hexdigest())
    print("Hashes matching:", my_hash == their_hash)
    if my_hash == their_hash:
        for i in range(5): # do this multiple times bc we can't resend
            sock.sendto(b"ACK", (SENDER_IP, TARGET_PORT))
        with open(fname, "wb+") as f:
            f.write(my_file)
    else:
        for i in range(5):
            sock.sendto(b"NACK", (SENDER_IP, TARGET_PORT))