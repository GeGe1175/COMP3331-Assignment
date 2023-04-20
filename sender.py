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
from state_enums import State

BUFFERSIZE = 1024

# max_win is the maximum window size in byte for the sender window. Greater or equal to 1000 and a multiple of 1000.
class Sender:
    def __init__(self, sender_port: int, receiver_port: int, filename: str, max_win : int, rto: int) -> None:
        '''
        The Sender will be able to connect the Receiver via UDP
        :param sender_port: the UDP port number to be used by the sender to send PTP segments to the receiver
        :param receiver_port: the UDP port number on which receiver is expecting to receive PTP segments from the sender
        :param filename: the name of the text file that must be transferred from sender to receiver using your reliable transport protocol.
        :param max_win: the maximum window size in bytes for the sender window.
        :param rto: the value of the retransmission timer in milliseconds. This should be an unsigned integer.
        '''
        self.sender_port = int(sender_port)
        self.receiver_port = int(receiver_port)
        self.filename = filename
        self.max_win = int(max_win)
        self.rto = int(rto)

        # setup ip
        self.sender_address = ("127.0.0.1", self.sender_port)
        self.receiver_address = ("127.0.0.1", self.receiver_port)

        # init the UDP socket
        print(f"The sender is using the address {self.sender_address}")
        self.sender_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.sender_socket.bind(self.sender_address)

        # start the listening sub-thread first
        self._is_active = True  # for the multi-threading
        self.listen_thread = Thread(target=self.listen)
        # starts the listening thread
        self.listen_thread.start()

        self.packets = []

        self.seqno = random.randint(0, 2**16-1)
        self.synced = False
        # stop and wait
        self.timer_thread = Thread(target=self.timer_listen)

        self.i = 0

        self.state = State.CLOSED

        # when the timer starts counting
        self.start_time = None
        # the current time that the oldest packet got sent
        self.curr_packet_time = None

        # for tracking number of retransmissions
        self.db = {}
        # for tracking duplicate acks
        self.acks = {}
        self.stats = {
            'numDataTransferBytes': 0,
            'numDataSegs': 0,
            'numDataRetransSegs': 0,
            'numDupACKS': 0
        }

    # for retransmitting packets
    def timer_listen(self):
        print('timer thread starting')
        while self._is_active:
            while((time.time() - self.curr_packet_time) < (self.rto / 1000)):
                continue
            if self.synced == False:
                if self.state == State.SYN_SENT:
                    # send RESET segment after 3 failed retransmissions
                    if self.db['syn'] == 4:
                        header_type = HeaderType.RESET.value
                        self.seqno = 0
                        headers = header_type.to_bytes(2, 'big') + self.seqno.to_bytes(2, 'big')
                        self.sender_socket.sendto(headers, self.receiver_address)
                        self.state = State.CLOSED
                        self._is_active = False
                        logging.info(f'snd\x20\x20\x20\x20{((time.time()-self.start_time)*1000):.2f}\x20\x20\x20\x20RESET\x20\x20\x20\x20{0}\x20\x20\x20\x20{0}')
                    else:
                        header_type = HeaderType.SYN.value
                        headers = header_type.to_bytes(2, 'big') + (self.seqno-1).to_bytes(2, 'big')
                        self.sender_socket.sendto(headers, self.receiver_address)
                        self.db['syn'] += 1
                        logging.info(f'snd\x20\x20\x20\x20{((time.time()-self.start_time)*1000):.2f}\x20\x20\x20\x20SYN\x20\x20\x20\x20{self.seqno-1}\x20\x20\x20\x20{0}')

                elif self.state == State.ESTABLISHED or self.state == State.CLOSING:
                    if self.i < len(self.packets):
                        self.sender_socket.sendto(self.packets[self.i], self.receiver_address)
                        content_size = int.from_bytes(self.packets[self.i][2:4], byteorder='big')
                        logging.info(f'snd\x20\x20\x20\x20{((time.time()-self.start_time)*1000):.2f}\x20\x20\x20\x20DATA\x20\x20\x20\x20{content_size}\x20\x20\x20\x20{len(self.packets[self.i][4:])}')
                        self.stats['numDataRetransSegs'] += 1

                elif self.state == State.FIN_WAIT:
                    # send RESET segment after 3 failed retransmissions
                    if self.db['fin'] == 4:
                        header_type = HeaderType.RESET.value
                        self.seqno = 0
                        headers = header_type.to_bytes(2, 'big') + self.seqno.to_bytes(2, 'big')
                        self.sender_socket.sendto(headers, self.receiver_address)
                        self.state = State.CLOSED
                        self._is_active = False
                        logging.info(f'snd\x20\x20\x20\x20{((time.time()-self.start_time)*1000):.2f}\x20\x20\x20\x20RESET\x20\x20\x20\x20{0}\x20\x20\x20\x20{0}')
                    else:
                        header_type = HeaderType.FIN.value
                        headers = header_type.to_bytes(2, 'big') + (self.seqno-1).to_bytes(2, 'big')
                        self.sender_socket.sendto(headers, self.receiver_address)
                        self.db['fin'] += 1
                        logging.info(f'snd\x20\x20\x20\x20{((time.time()-self.start_time)*1000):.2f}\x20\x20\x20\x20FIN\x20\x20\x20\x20{(self.seqno-1)}\x20\x20\x20\x20{0}')
                self.curr_packet_time = time.time()

    # setup the connection between the sender and receiver
    def ptp_open(self):
        # setup the syn packet
        header_type = HeaderType.SYN.value
        headers = header_type.to_bytes(2, 'big') + self.seqno.to_bytes(2, 'big')
        self.state = State.SYN_SENT

        self.sender_socket.sendto(headers, self.receiver_address)
        # add the syn to the db so it knows how many syns have been sent so far
        self.db['syn'] = 1
        # this time is to find all the packet times from the intial start time
        self.start_time = time.time()
        # timer starts from when the syn is send
        self.curr_packet_time = self.start_time
        logging.info(f'snd\x20\x20\x20\x20{0:.2f}\x20\x20\x20\x20SYN\x20\x20\x20\x20{self.seqno}\x20\x20\x20\x20{0}')
        self.seqno += 1

        # start timing the syn packet and other packets
        self.timer_thread.start()

    def ptp_send(self):
        while self.state != State.ESTABLISHED:
            if self.state == State.CLOSED:
                return
            continue
        # process text and split them into packets
        seqno = self.seqno
        with open(self.filename, mode='r') as file:
            while True:
                content = file.read(1000).encode('utf-8')
                if content:
                    header_type = HeaderType.DATA.value
                    headers = header_type.to_bytes(2, 'big') + seqno.to_bytes(2, 'big')
                    packet = headers + content
                    self.packets.append(packet)
                    seqno += len(content)
                else:
                    break

        # send the packets
        while self.i < len(self.packets):
            if self.synced:
                if self.i < len(self.packets):
                    self.sender_socket.sendto(self.packets[self.i], self.receiver_address)
                    content_size = int.from_bytes(self.packets[self.i][2:4], byteorder='big')
                    logging.info(f'snd\x20\x20\x20\x20{((time.time()-self.start_time)*1000):.2f}\x20\x20\x20\x20DATA\x20\x20\x20\x20{content_size}\x20\x20\x20\x20{len(self.packets[self.i][4:])}')
                    self.synced = False
                    # track the time of the oldest sent out packet
                    self.curr_packet_time = time.time()
                    self.stats['numDataTransferBytes'] += len(self.packets[self.i][4:])
                    self.stats['numDataSegs'] += 1
        self.state = State.CLOSING

    def ptp_close(self):
        # dont send the fin if the RESET segment has been sent
        if self.state != State.CLOSED:
            self.state = State.FIN_WAIT
            logging.info(f'snd\x20\x20\x20\x20{((time.time()-self.start_time)*1000):.2f}\x20\x20\x20\x20FIN\x20\x20\x20\x20{self.seqno}\x20\x20\x20\x20{0}')
            header_type = HeaderType.FIN.value
            headers = header_type.to_bytes(2, 'big') + (self.seqno).to_bytes(2, 'big')
            self.seqno += 1
            self.db['fin'] = 1
            self.sender_socket.sendto(headers, self.receiver_address)
            self.curr_packet_time = time.time()
            self.synced = False

        time.sleep(5)
        self._is_active = False
        self.sender_socket.close()
        logging.info(f"Amount of original data transferred in bytes excluding retransmissions: {self.stats['numDataTransferBytes']}")
        logging.info(f"Number of data segments sent excluding retransmissions: {self.stats['numDataSegs']}")
        logging.info(f"Number of retransmitted data segments: {self.stats['numDataRetransSegs']}")
        logging.info(f"Number of duplicate acknowledgements received: {self.stats['numDupACKS']}")

    def listen(self):
        '''(Multithread is used)listen the response from receiver'''
        print("Sub-thread for listening is running")
        while self._is_active:
            incoming_message = bytes()
            # decode packet
            try:
                incoming_message, _ = self.sender_socket.recvfrom(BUFFERSIZE)
            # when the socket closes but the socket tries to retrieve a packet we can stop the exception
            except:
                break

            header_type = int.from_bytes(incoming_message[0:2], byteorder='big')
            seqno = int.from_bytes(incoming_message[2:4], byteorder='big')

            if self.acks.get(seqno, 0) != 0:
                self.stats['numDupACKS'] += 1
            self.acks[seqno] = self.acks.get(seqno, 0) + 1

            # when the sender is sending a syn, it will wait for the ack to come back
            if self.state == State.SYN_SENT:
                if self.seqno == seqno:
                    self.synced = True
                    self.state = State.ESTABLISHED
                    logging.info(f'rcv\x20\x20\x20\x20{((time.time()-self.start_time)*1000):.2f}\x20\x20\x20\x20ACK\x20\x20\x20\x20{self.seqno}\x20\x20\x20\x20{0}')

            elif (self.state == State.ESTABLISHED or self.state == State.CLOSING) and self.i < len(self.packets):
                print("ACK expected is " + str(self.seqno + len(self.packets[self.i][4:])) + " | ACK received was " + str(seqno))
                if (self.seqno + len(self.packets[self.i][4:])) == seqno:
                    self.seqno += len(self.packets[self.i][4:])
                    logging.info(f'rcv\x20\x20\x20\x20{((time.time()-self.start_time)*1000):.2f}\x20\x20\x20\x20ACK\x20\x20\x20\x20{self.seqno}\x20\x20\x20\x20{len(self.packets[self.i][4:])}')
                    if self.i < len(self.packets):
                        self.i += 1
                    self.synced = True

            elif self.state == State.FIN_WAIT:
                if self.seqno == seqno:
                    logging.info(f'rcv\x20\x20\x20\x20{((time.time()-self.start_time)*1000):.2f}\x20\x20\x20\x20ACK\x20\x20\x20\x20{self.seqno}\x20\x20\x20\x20{0}')
                    self.synced = True
                    self.state = State.CLOSED
                    # set to false once the ack is received from the fin
                    self._is_active = False

    # controller
    def run(self):
        self.ptp_open()
        self.ptp_send()
        self.ptp_close()

if __name__ == '__main__':
    logging.basicConfig(
        filename="Sender_log.txt",
        format='',
        level=logging.DEBUG,
        filemode='w')

    if len(sys.argv) != 6:
        print(
            "\n===== Error usage, python3 sender.py sender_port receiver_port FileReceived.txt max_win rto ======\n")
        exit(0)

    sender = Sender(*sys.argv[1:])
    sender.run()
