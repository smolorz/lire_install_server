#!/usr/bin/env python

import SocketServer
import tempfile
import threading
import socket
import sys
import subprocess
import os.path

from os.path import join, isfile
from os import mkdir
from shutil import rmtree

import lire_base_socket_class

class LireInstallHandler(SocketServer.BaseRequestHandler, lire_base_socket_class.LireBaseSocketClass):

    def setup(self):
        """
        this is called before self.handle()
        """
        self.tmp_dir = tempfile.mkdtemp()
        self.lire_root_tar = join(self.tmp_dir, "lire_root.tar.bz2")
        self.lire_root_dir = join(self.tmp_dir, "lire_root_dir")
        self.lire_target_dir = join(self.tmp_dir, "lire_target_dir")
        mkdir(self.lire_target_dir)
        mkdir(self.lire_root_dir)
        

    def open_transport_connection(self):
        tmp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tmp_sock.bind(('',0))
        port = tmp_sock.getsockname()[1]
        tmp_sock.listen(1)
        data_sock = tmp_sock.accept()
        tmp_sock.close()
        return (data_sock[0], port)

    def md5sum_ok(self, f):
        md5sum = self.create_md5(self.lire_root_tar)
        self.send_word(self.request, "MD5:%s" % md5sum)
        if self.recv_word(self.request) == "OK":
            return True
        else:
            return False

    def handle(self):
        """
        This function is called whenever LireInstallServer gets a new connection. 
        The socket of this new connection is stored as self.request.
        """
        #get the lire_root_tar from the client
        connect_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connect_sock.bind(('',0))
        data_port = connect_sock.getsockname()[1]
        self.send_word(self.request, "SEND:lire_root_tar!%s" % data_port)
        connect_sock.listen(1)
        data_sock = connect_sock.accept()[0]
        connect_sock.close()
        self.recv_file(data_sock, self.lire_root_tar)
        data_sock.close()
        
        #check the md5sum of the lire_root_tar

        md5sum = self.create_md5(self.lire_root_tar)
        self.send_word(self.request, "MD5:lire_root_tar")
        answer = self.recv_word(self.request)
        if answer.split(":")[1] != md5sum:
            self.send_word(self.request, "ERROR: md5sum mismatch")
            self.clean_up()
            return

        self.make_install()

        result = os.path.join(self.lire_target_dir,'lire.tar.bz2')
        if not os.path.isfile(result):
            self.send_word(self.request, "ERROR: cannot find created image")
            self.clean_up()
            return

        connect_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connect_sock.bind(('',0))
        data_port = connect_sock.getsockname()[1]
        self.send_word(self.request, "RECV:lire.tar.bz2!%s" % data_port)
        connect_sock.listen(1)
        data_sock = connect_sock.accept()[0]
        connect_sock.close()
        self.send_file(data_sock, result)
        data_sock.close()

        md5sum = self.create_md5(result)
        self.send_word(self.request, "MD5:lire.tar.bz2")
        answer = self.recv_word(self.request)
        if answer.split(":")[1] != md5sum:
            self.send_word(self.request, "ERROR: md5sum mismatch")
            self.clean_up()
            return

        self.send_word(self.request, "END: The server says goodbye")
        self.request.close()
        self.clean_up()
        
        return


    def make_install(self):
        print "tmpdir: %s " % self.tmp_dir
        self.send_word(self.request, "ECHO:Extracting Lire root directory")
        ret = subprocess.call(['tar','-x','-f', self.lire_root_tar, '-C', self.lire_root_dir])
        if ret > 0:
            self.sen_word(self.request, "ECHO: Extracting [OK]")

        self.send_word(self.request, "ECHO: Running lire_core_install")
        (stdout, stderr) = subprocess.Popen(['/usr/local/bin/lire_core_install', self.lire_root_dir, self.lire_target_dir],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT).communicate()
        for line in stdout.split("\n"):
            self.send_word(self.request, "ECHO: %s" % line)

    def clean_up(self):
        rmtree(self.tmp_dir)
        

class LireInstallServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    pass


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print "USAGE: %s port" % sys.argv[0]
        sys.exit(1)
    port = int(sys.argv[1])
    server = LireInstallServer(('localhost', port), LireInstallHandler)
    server.serve_forever()
