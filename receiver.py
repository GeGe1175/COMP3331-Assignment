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
        self.flp = float(flp)
        self.rlp = float(rlp)

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

        self.db = {}
        self.stats = {
            'numDataReceivedBytes': 0,
            'numDataSegs': 0,
            'numDupSegs': 0,
            'numDataSegsDrp': 0,
            'numACKSegsDrp' : 0
        }

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

                # probability that the packet gets lost to the receiver
                if random.randint(1, 100) <= int(self.flp * 100):
                    if header_type == HeaderType.DATA.value:
                        logging.info(f'drp\x20\x20\x20\x20{((time.time()-self.start_time)*1000):.2f}\x20\x20\x20\x20DATA\x20\x20\x20\x20{self.seqno}\x20\x20\x20\x20{len(incoming_message[4:])}')
                        self.stats['numDataSegsDrp'] += 1
                    elif header_type == HeaderType.SYN.value:
                        logging.info(f'drp\x20\x20\x20\x20uninitalised\x20\x20\x20\x20SYN\x20\x20\x20\x20{self.seqno}\x20\x20\x20\x20{0}')
                    elif header_type == HeaderType.FIN.value:
                        logging.info(f'drp\x20\x20\x20\x20{((time.time()-self.start_time)*1000):.2f}\x20\x20\x20\x20FIN\x20\x20\x20\x20{self.seqno}\x20\x20\x20\x20{0}')
                    continue

                # check the type of header
                if header_type == HeaderType.SYN.value:
                    self.state = State.ESTABLISHED
                    logging.info(f'rcv\x20\x20\x20\x20{0:.2f}\x20\x20\x20\x20SYN\x20\x20\x20\x20{seqno}\x20\x20\x20\x20{0}')
                    self.start_time = time.time()
                    self.seqno = seqno + 1
                    ack_header_type = HeaderType.ACK.value
                    headers = ack_header_type.to_bytes(2, 'big') + self.seqno.to_bytes(2, 'big')
                    self.receiver_socket.sendto(headers, sender_address)
                    logging.info(f'snd\x20\x20\x20\x20{((time.time()-self.start_time)*1000):.2f}\x20\x20\x20\x20ACK\x20\x20\x20\x20{self.seqno}\x20\x20\x20\x20{0}')

                elif header_type == HeaderType.DATA.value:
                    logging.info(f'rcv\x20\x20\x20\x20{((time.time()-self.start_time)*1000):.2f}\x20\x20\x20\x20DATA\x20\x20\x20\x20{seqno}\x20\x20\x20\x20{len(incoming_message[4:])}')
                    if seqno not in self.db:
                        # Write the string to the file
                        with open(self.filename, 'a') as file:
                            file.write(incoming_message[4:].decode('utf-8'))
                            self.seqno = self.seqno + len(incoming_message[4:])
                            self.stats['numDataReceivedBytes'] += len(incoming_message[4:])
                            self.stats['numDataSegs'] += 1

                    # check if that packet sequence number is already in the data to find if it is a duplicate
                    if seqno in self.db:
                        self.stats['numDupSegs'] += 1

                    ack_header_type = HeaderType.ACK.value
                    headers = ack_header_type.to_bytes(2, 'big') + self.seqno.to_bytes(2, 'big')
                    logging.info(f'snd\x20\x20\x20\x20{((time.time()-self.start_time)*1000):.2f}\x20\x20\x20\x20ACK\x20\x20\x20\x20{self.seqno}\x20\x20\x20\x20{0}')
                    self.db[seqno] = self.db.get(seqno, 0) + 1
                    # probability that the packet gets lost on the way back
                    if random.randint(1, 100) >= int(self.rlp * 100):
                        self.receiver_socket.sendto(headers, sender_address)
                    else:
                        self.stats['numACKSegsDrp'] += 1

                elif header_type == HeaderType.FIN.value:
                    logging.info(f'rcv\x20\x20\x20\x20{((time.time()-self.start_time)*1000):.2f}\x20\x20\x20\x20FIN\x20\x20\x20\x20{self.seqno}\x20\x20\x20\x20{0}')
                    self.seqno = seqno + 1
                    ack_header_type = HeaderType.ACK.value
                    headers = ack_header_type.to_bytes(2, 'big') + self.seqno.to_bytes(2, 'big')
                    self.receiver_socket.sendto(headers, sender_address)
                    logging.info(f'snd\x20\x20\x20\x20{((time.time()-self.start_time)*1000):.2f}\x20\x20\x20\x20ACK\x20\x20\x20\x20{self.seqno}\x20\x20\x20\x20{0}')

                    self.state = State.TIME_WAIT
                    self.listen_thread.start()
                    time.sleep(5)

            except ConnectionResetError:
                continue
        logging.info(f"Amount of original data received in bytes: {self.stats['numDataReceivedBytes']}")
        logging.info(f"Number of original data segments received: {self.stats['numDataSegs']}")
        logging.info(f"Number of duplicate data segments received: {self.stats['numDupSegs']}")
        logging.info(f"Number of data segments dropped: {self.stats['numDataSegsDrp']}")
        logging.info(f"Number of ACK segments dropped: {self.stats['numACKSegsDrp']}")

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
