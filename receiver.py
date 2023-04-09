"""
    Sample code for Receiver
    Python 3
    Usage: python3 receiver.py receiver_port sender_port FileReceived.txt flp rlp
    coding: utf-8

    Notes:
        Try to run the server first with the command:
            python3 receiver.py 9000 10000 FileReceived.txt 0 0
        Then run the sender:
            python3 sender.py 10000 9000 random1.txt 0 0

    Author: Rui Li (Tutor for COMP3331/9331)
"""
# here are the libs you may find it useful:
import datetime, time  # to calculate the time delta of packet transmission
import logging, sys  # to write the log
import socket  # Core lib, to send packet via UDP socket
from threading import Thread  # (Optional)threading will make the timer easily implemented
import random  # for flp and rlp function

from type_enums import HeaderType

BUFFERSIZE = 1024


class Receiver:
    def __init__(self, receiver_port: int, sender_port: int, filename: str, flp: float, rlp: float) -> None:
        '''
        The server will be able to receive the file from the sender via UDP
        :param receiver_port: the UDP port number to be used by the receiver to receive PTP segments from the sender.
        :param sender_port: the UDP port number to be used by the sender to send PTP segments to the receiver.
        :param filename: the name of the text file into which the text sent by the sender should be stored
        :param flp: forward loss probability, which is the probability that any segment in the forward direction (Data, FIN, SYN) is lost.
        :param rlp: reverse loss probability, which is the probability of a segment in the reverse direction (i.e., ACKs) being lost.

        '''
        self.address = "127.0.0.1"  # change it to 0.0.0.0 or public ipv4 address if want to test it between different computers
        self.receiver_port = int(receiver_port)
        self.sender_port = int(sender_port)
        self.server_address = (self.address, self.receiver_port)

        # init the UDP socket
        # define socket for the server side and bind address
        logging.debug(f"The sender is using the address {self.server_address} to receive message!")
        self.receiver_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.receiver_socket.bind(self.server_address)

        self.filename = filename
        self.seqno = -1
        pass

    def run(self) -> None:
        '''
        This function contain the main logic of the receiver
        '''
        # reset the file
        with open(self.filename, 'w') as file:
                # Write the string to the file
                file.write('')

        while True:

            # try to receive any incoming message from the sender
            try:
                incoming_message, sender_address = self.receiver_socket.recvfrom(BUFFERSIZE)
                # randomly drop the packet
                # if random.randint(1, 100) > 50: # 90% chance
                #     continue


                seqno = int.from_bytes(incoming_message[2:4], byteorder='big')
                header_type = int.from_bytes(incoming_message[0:2], byteorder='big')

                # check the type of header
                if header_type == HeaderType.SYN.value:
                    self.seqno = seqno + 1
                    ack_header_type = HeaderType.ACK.value
                    headers = ack_header_type.to_bytes(2, 'big') + self.seqno.to_bytes(2, 'big')
                    # reply_message = "ACK" # need to give an id
                    self.receiver_socket.sendto(headers, sender_address)
                    continue

                elif header_type == HeaderType.DATA.value:
                    self.seqno = self.seqno + len(incoming_message[4:])
                    bro = self.seqno.to_bytes(2, 'big')
                    print(int.from_bytes(bro, byteorder='big'))
                    ack_header_type = HeaderType.ACK.value
                    headers = ack_header_type.to_bytes(2, 'big') + self.seqno.to_bytes(2, 'big')
                    self.receiver_socket.sendto(headers, sender_address)

                    # Write the string to the file
                    with open(self.filename, 'a') as file:
                        file.write(incoming_message[4:].decode('utf-8'))

                    # logging.debug(incoming_message)

            except ConnectionResetError:
                continue

            # reply "ACK" once receive any message from sender
            # reply_message = "ACK" # need to give an id
            # self.receiver_socket.sendto(reply_message.encode("utf-8"),
            #                             sender_address)


if __name__ == '__main__':
    # logging is useful for the log part: https://docs.python.org/3/library/logging.html
    logging.basicConfig(
        # filename="Receiver_log.txt",
        stream=sys.stderr,
        level=logging.DEBUG,
        format='%(asctime)s,%(msecs)03d %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d:%H:%M:%S')

    if len(sys.argv) != 6:
        print(
            "\n===== Error usage, python3 receiver.py receiver_port sender_port FileReceived.txt flp rlp ======\n")
        exit(0)

    receiver = Receiver(*sys.argv[1:])
    receiver.run()
