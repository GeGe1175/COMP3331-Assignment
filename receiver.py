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
from state_enums import State

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
        self.receiver_port = int(receiver_port)
        self.sender_port = int(sender_port)
        self.filename = filename
        self.flp = flp
        self.rlp = rlp

        self.address = "127.0.0.1"
        self.server_address = (self.address, self.receiver_port)

        self.state = State.CLOSED

        # init the UDP socket
        # define socket for the server side and bind address
        print(f"The sender is using the address {self.server_address} to receive message!")
        self.receiver_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.receiver_socket.bind(self.server_address)

        self.state = State.LISTEN

        self.seqno = -1

        self.end = False

        self.start_time = None

        # listener when receiver is in TIME_WAIT state
        self._is_active = True  # for the multi-threading
        self.listen_thread = Thread(target=self.listen)

# remove this shit soon
        random.seed(8)

    def listen(self):
        while self._is_active:
            start_time = time.time()
            while time.time() - start_time < 2:
                continue
            self._is_active = False

        print('closed')
        self.state = State.CLOSED
        self.end = True

    def run(self) -> None:
        '''
        This function contain the main logic of the receiver
        '''
        # reset the file
        with open(self.filename, 'w') as file:
                # Write the string to the file
                file.write('')

        while self.end == False:
            # try to receive any incoming message from the sender
            try:
                incoming_message, sender_address = self.receiver_socket.recvfrom(BUFFERSIZE)

                seqno = int.from_bytes(incoming_message[2:4], byteorder='big')
                header_type = int.from_bytes(incoming_message[0:2], byteorder='big')

                if header_type == HeaderType.RESET.value:
                    logging.info('The connection has been reset')
                    self.end = True
                    break

                # randomly drop the packet, meaning that the packet did not reach the receiver
                if random.randint(1, 100) > 10:
                    if header_type == HeaderType.DATA.value:
                        logging.info(f'drp\t{((time.time()-self.start_time)*1000):.2f}\tDATA\t{self.seqno}\t{len(incoming_message[4:])}')
                    elif header_type == HeaderType.SYN.value:
                        logging.info(f'drp\tuninitalised\tSYN\t{self.seqno}\t{0}')
                    elif header_type == HeaderType.FIN.value:
                        logging.info(f'drp\t{((time.time()-self.start_time)*1000):.2f}\tFIN\t{self.seqno}\t{0}')
                    continue

                # check the type of header
                if header_type == HeaderType.SYN.value:
                    self.state = State.ESTABLISHED
                    logging.info(f'rcv\t{0}\tSYN\t{seqno}\t{0}')
                    self.start_time = time.time()
                    self.seqno = seqno + 1
                    ack_header_type = HeaderType.ACK.value
                    headers = ack_header_type.to_bytes(2, 'big') + self.seqno.to_bytes(2, 'big')
                    self.receiver_socket.sendto(headers, sender_address)
                    logging.info(f'snd\t{((time.time()-self.start_time)*1000):.2f}\tACK\t{self.seqno}\t{0}')

                elif header_type == HeaderType.DATA.value:
                    logging.info(f'rcv\t{((time.time()-self.start_time)*1000):.2f}\tDATA\t{seqno}\t{len(incoming_message[4:])}')
                    self.seqno = self.seqno + len(incoming_message[4:])

                    # TODO randomly drop the packet, meaning the packet did not reach the sender
                    if random.randint(1, 100) > 10:
                        continue

                    ack_header_type = HeaderType.ACK.value
                    headers = ack_header_type.to_bytes(2, 'big') + self.seqno.to_bytes(2, 'big')
                    self.receiver_socket.sendto(headers, sender_address)
                    logging.info(f'snd\t{((time.time()-self.start_time)*1000):.2f}\tACK\t{self.seqno}\t{0}')


                    # Write the string to the file
                    with open(self.filename, 'a') as file:
                        file.write(incoming_message[4:].decode('utf-8'))

                elif header_type == HeaderType.FIN.value:
                    logging.info(f'rcv\t{((time.time()-self.start_time)*1000):.2f}\tFIN\t{self.seqno}\t{0}')
                    self.seqno = seqno + 1
                    ack_header_type = HeaderType.ACK.value
                    headers = ack_header_type.to_bytes(2, 'big') + self.seqno.to_bytes(2, 'big')
                    self.receiver_socket.sendto(headers, sender_address)
                    logging.info(f'snd\t{((time.time()-self.start_time)*1000):.2f}\tACK\t{self.seqno}\t{0}')

                    self.state = State.TIME_WAIT
                    self.listen_thread.start()
                    time.sleep(5)

            except ConnectionResetError:
                continue

if __name__ == '__main__':
    logging.basicConfig(
        filename="Receiver_log.txt",
        level=logging.DEBUG,
        format='',
        filemode='w')

    if len(sys.argv) != 6:
        print(
            "\n===== Error usage, python3 receiver.py receiver_port sender_port FileReceived.txt flp rlp ======\n")
        exit(0)

    receiver = Receiver(*sys.argv[1:])
    receiver.run()
