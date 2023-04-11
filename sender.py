"""
    Sample code for Sender (multi-threading)
    Python 3
    Usage: python3 sender.py receiver_port sender_port FileToSend.txt max_recv_win rto
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
import random

from type_enums import HeaderType

BUFFERSIZE = 1024

# max_win is the maximum window size in byte for the sender window. Greater or equal to 1000 and a multiple of 1000.
class Sender:
    def __init__(self, sender_port: int, receiver_port: int, filename: str, max_win : int, rot: int) -> None:
        '''
        The Sender will be able to connect the Receiver via UDP
        :param sender_port: the UDP port number to be used by the sender to send PTP segments to the receiver
        :param receiver_port: the UDP port number on which receiver is expecting to receive PTP segments from the sender
        :param filename: the name of the text file that must be transferred from sender to receiver using your reliable transport protocol.
        :param max_win: the maximum window size in bytes for the sender window.
        :param rot: the value of the retransmission timer in milliseconds. This should be an unsigned integer.
        '''
        self.sender_port = int(sender_port)
        self.receiver_port = int(receiver_port)
        self.sender_address = ("127.0.0.1", self.sender_port)
        self.receiver_address = ("127.0.0.1", self.receiver_port)

        # init the UDP socket
        logging.debug(f"The sender is using the address {self.sender_address}")
        self.sender_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.sender_socket.bind(self.sender_address)

        # start the listening sub-thread first
        self._is_active = True  # for the multi-threading
        self.listen_thread = Thread(target=self.listen)
        # starts the listening thread
        self.listen_thread.start()

        self.packets = []

        self.filename = filename
        self.max_win = int(max_win)
        self.rot = int(rot)
        self.seqno = 0
        ################################################################
        # random.randint(0, 2**16-1)
        ################################################################
        self.synced = False
        # stop and wait
        self.timer_thread = Thread(target=self.timer_listen)

        self.i = 0

        self.state = 'CLOSED'

    def timer_listen(self):
        print('timer thread starting')
        while self._is_active:
            time.sleep(self.rot / 1000)
            if self.synced == False:
                if self.state == 'SYN_SENT':
                    header_type = HeaderType.SYN.value
                    headers = header_type.to_bytes(2, 'big') + self.seqno.to_bytes(2, 'big')
                    self.sender_socket.sendto(headers, self.receiver_address)
                else:
                    if self.i < len(self.packets):
                        self.sender_socket.sendto(self.packets[self.i], self.receiver_address)
                print('resending')

    # setup the connection between the sender and receiver
    def ptp_open(self):
        header_type = HeaderType.SYN.value
        headers = header_type.to_bytes(2, 'big') + self.seqno.to_bytes(2, 'big')
        self.state = 'SYN_SENT'
        self.sender_socket.sendto(headers, self.receiver_address)
        self.timer_thread.start()

    def ptp_send(self):
        # process text and split them into packets
        with open(self.filename, mode='r') as file:
            while True:
                content = file.read(1000).encode('utf-8')
                if content:
                    header_type = HeaderType.DATA.value
                    headers = header_type.to_bytes(2, 'big') + self.seqno.to_bytes(2, 'big')
                    packet = headers + content
                    self.packets.append(packet)
                    # self.sender_socket.sendto(packet, self.receiver_address)

                    # self.seqno += len(content)

                    # logging.debug(f"Packet {i}: {len(packet)} bytes")
                    self.i += 1
                else:
                    logging.debug(f'All {self.i} packets have been processed')
                    break

        # send the packets
        self.i = 0
        while self.i < len(self.packets):
            if self.synced:
                self.sender_socket.sendto(self.packets[self.i], self.receiver_address)
                self.synced = False

    def ptp_close(self):
        # todo add codes here
        time.sleep(3)
        self._is_active = False  # close the sub-thread

    def listen(self):
        '''(Multithread is used)listen the response from receiver'''
        logging.debug("Sub-thread for listening is running")
        while self._is_active:
            # decode packet
            incoming_message, _ = self.sender_socket.recvfrom(BUFFERSIZE)
            header_type = int.from_bytes(incoming_message[0:2], byteorder='big')
            seqno = int.from_bytes(incoming_message[2:4], byteorder='big')

            if header_type == HeaderType.ACK.value:
                if self.state == 'SYN_SENT':
                    logging.info("ACK expected is " + str(self.seqno + 1) + " | ACK received was " + str(seqno))
                    if (self.seqno + 1) == seqno:
                        self.seqno += 1
                        self.synced = True
                        self.state = 'ESTABLISHED'
                elif self.state == 'ESTABLISHED':
                    logging.info("ACK expected is " + str(self.seqno + len(self.packets[self.i][4:])) + " | ACK received was " + str(seqno))
                    if (self.seqno + len(self.packets[self.i][4:])):
                        self.seqno += len(self.packets[self.i][4:])
                        if self.i == len(self.packets) - 1:
                            self._is_active = False
                        self.i += 1

            # logging.info(f"received reply from receiver:, {incoming_message.decode('utf-8')}")

    def run(self):
        '''
        This function contain the main logic of the receiver
        '''
        # todo add/modify codes here
        self.ptp_open()
        self.ptp_send()
        self.ptp_close()

if __name__ == '__main__':
    # logging is useful for the log part: https://docs.python.org/3/library/logging.html
    logging.basicConfig(
        # filename="Sender_log.txt",
        stream=sys.stderr,
        level=logging.DEBUG,
        format='%(asctime)s,%(msecs)03d %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d:%H:%M:%S')

    if len(sys.argv) != 6:
        print(
            "\n===== Error usage, python3 sender.py sender_port receiver_port FileReceived.txt max_win rot ======\n")
        exit(0)

    sender = Sender(*sys.argv[1:])
    sender.run()
