import socket
from zlib import crc32
from hashlib import sha256

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
    #try:
        if my_crc == data[-CRC_LEN:].decode('utf-8') and int(
                data[:COUNTER_LEN]) == 0:  # a very lenghtily written name check
            my_data = str(my_data)
            fname = my_data.split(";")[0]
            num_of_packets = int(my_data.split(";")[1]) #the [:-1] gets rid of an unwanted <'>
        else: print ("a",end="")

    #except (ValueError, TypeError):
    #    print("Packet number not parsed")

print("Connected, address:", addr[0], "\nSaving to folder:", fname, "\nNumber of packets:", int(num_of_packets))
SENDER_IP = addr[0]  # IP from which we are receiving packets

sock.sendto(b"OK", (SENDER_IP, TARGET_PORT))


current = 1  # current packet

my_file = b"" #we first write into a bytes object
my_buffer = b"" #buffer data that is ahead

while True:
    data, addr = sock.recvfrom(1024)  # total packet size is 1024 bytes

    if b"HASH" in data[:COUNTER_LEN]:  # the final packet is the hash
        print("Hash received", end=" ")
        my_data = data[COUNTER_LEN: len(data) - CRC_LEN]
        my_crc = str(crc32(my_data))
        while len(my_crc) < 10:  # normalize crc to be 10 digits
            my_crc = '0' + my_crc
        if data[-CRC_LEN:].decode('utf-8') == my_crc:
            print("correctly!")

            their_hash = my_data.decode()
            break
        else:
            print("incorrectly")
            sock.sendto(b"NO", (SENDER_IP, TARGET_PORT))
    else:
            # -------------parse the packet-------------------------------------

        try:
            packet_num = int(data[:COUNTER_LEN])  # number of packet
        except (ValueError, TypeError):
            ("Packet number not parsed!")
        else:
            my_data = data[COUNTER_LEN: len(data) - CRC_LEN]  # the actual data

            # --------------create crc--------------------------------------
            my_crc = str(crc32(my_data))  # the crc the receiver makes
            while len(my_crc) < 10:  # normalize crc to be 10 digits
                my_crc = '0' + my_crc

                # -----------------evaluate correctness------------------------
            if data[-CRC_LEN:].decode('utf-8') == my_crc:  # compare CRCs
                sock.sendto(b"OK", (SENDER_IP, TARGET_PORT))
                if packet_num == current:  # verify that this packet is not a dupe
                    my_file += my_data
                    current += 1
            else:
                sock.sendto(b"NO", (SENDER_IP, TARGET_PORT))

# ok will be sent even if a duplicate is received, but it will not be written in the file
# this is so that the sender can catch up.


my_hash = str(sha256(my_file).hexdigest())
print("Hashes matching:", my_hash == their_hash)
if my_hash == their_hash:
    sock.sendto(b"OK", (SENDER_IP, TARGET_PORT))
    with open(fname, "wb+") as f:
        f.write(my_file)
else:
    sock.sendto(b"XX", (SENDER_IP, TARGET_PORT))
