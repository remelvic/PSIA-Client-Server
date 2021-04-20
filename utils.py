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
    while len(my_crc) < 10:
        my_crc = '0' + my_crc
    my_crc = bytes(my_crc, 'utf-8')

    # assemble and return packet
    mypacket = my_counter + mess + my_crc
    return mypacket
