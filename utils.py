from zlib import crc32


"""
returns a ready to send packet
"""
def make_packet(i, fcontent, COUNTER_LEN, MSG_LEN, CRC_LEN):
    my_counter = str(i)
    while len(my_counter) < COUNTER_LEN:
        my_counter = "0" + my_counter
    my_counter = bytes(my_counter, 'utf-8')
    
    mess = fcontent[(i-1)*MSG_LEN :((i-1)*MSG_LEN) + MSG_LEN]  # the message

    my_crc = str(crc32(mess))
    while len(my_crc) < CRC_LEN:
        my_crc = '0' + my_crc
    my_crc = bytes(my_crc, 'utf-8')

    # assemble and return packet
    mypacket = my_counter + mess + my_crc
    return mypacket

def make_ack(ack, packet_num, CRC_LEN):
    if ack == True:
        my_ack = b"ACK"+bytes(str(packet_num), 'utf-8')
    else: 
        my_ack = b"RES"+bytes(str(packet_num), 'utf-8')

    my_crc = str(crc32(my_ack))
    while len(my_crc) < CRC_LEN:
        my_crc = '0' + my_crc
    my_crc = bytes(my_crc, 'utf-8')

    my_ack += my_crc
    return my_ack