#!/usr/bin/env python

# external import
import os
import getpass
import argparse
import paramiko
import socket
import time
import datetime
import StringIO
import select
import traceback
import random
import string
import tempfile

# 1A import
import log

# default timeout to execute a command (in seconds)
# can be overridden for each command
DEFAULT_RUN_CMD_TIMEOUT = 90

class SSHSession:
    def __init__(self, host, username, proxy_transport=None, retry=False, private_key_file=None):
        self.host = host
        self.username = username
        self.ssh_client = paramiko.client.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_remote_session = None

        connected_to_host = False
        while not connected_to_host:
            try:
                # this is a remote ssh session
                if proxy_transport:
                    # open a `direct-tcpip` channel passing
                    # the destination hostname:port and the local hostname:port
                    dest_addr = (self.host, 22)
                    local_addr = ('127.0.0.1', 22)
                    ssh_channel = proxy_transport.open_channel("direct-tcpip", dest_addr, local_addr)

                    # pass this channel to ssh_client as the `sock`
                    self.ssh_client.connect('localhost', port=22, username=self.username, sock=ssh_channel, key_filename=private_key_file)
                # this is a normal ssh session
                else:
                    # connect to the host
                    self.ssh_client.connect(self.host, port=22, username=self.username, key_filename=private_key_file)

                connected_to_host = True
            except (paramiko.ssh_exception.AuthenticationException, paramiko.ssh_exception.ChannelException, paramiko.ssh_exception.SSHException):
                if retry:
                    log.warning("ssh to '%s' still not possible. Keep retrying..." % host)
                    time.sleep(10)
                else:
                    raise

        # Get the client's transport
        self.ssh_transport = self.ssh_client.get_transport()

        log.info("Successfully connected to '%s'" % self.host)

    def __del__(self):
        self.close()

    def close(self):
        if self.ssh_remote_session:
            self.ssh_remote_session.close()
            self.ssh_remote_session = None
        if self.ssh_client and self.ssh_client.get_transport() and self.ssh_client.get_transport().is_active():
            log.info("Closing connection to '%s'..." % self.host)
            self.ssh_client.close()

    def run_cmd(self, cmd, username=None, exit_if_error=True, debug=False, timeout=DEFAULT_RUN_CMD_TIMEOUT, input_data={}):
        try:
            user = self.username
            my_cmd = cmd
            if username:
                user = username
                my_cmd = 'sudo su - ' + username + ' -c "' + cmd.replace('"', '\\"') + '"'
            if debug is not None:
                log.debug("Running command '%s' on '%s' as %s..." % (cmd, self.host, user))

            # check session is still active before running a command
            if not self.ssh_transport.is_active():
                log.error("Unable to run command '%s', SSH session to '%s' is closed" % (cmd, self.host))

            channel = self.ssh_transport.open_session()

            # raise error rather than blocking the call
            channel.setblocking(0)

            # Forward local agent
            paramiko.agent.AgentRequestHandler(channel)
            # Commands executed after this point will see the forwarded agent on the remote end.

            channel.set_combine_stderr(True)
            channel.get_pty()
            channel.exec_command(my_cmd)

            # prepare timer for timeout
            start = datetime.datetime.now()
            start_secs = time.mktime(start.timetuple())

            output = StringIO.StringIO()
            while True:
                got_chunk = False
                readq, _, _ = select.select([channel], [], [], timeout)
                for c in readq:
                    if c.recv_ready():
                        data = channel.recv(len(c.in_buffer))
                        output.write(data)
                        got_chunk = True

                        if debug and len(data.strip()) > 0:
                            print data

                        if channel.send_ready():
                            # We received a potential prompt.
                            for pattern in input_data.keys():
                                # pattern text matching => send input data
                                if pattern in data:
                                    channel.send(input_data[pattern] + '\n')

                # remote process has exited and returned an exit status
                if not got_chunk and channel.exit_status_ready() and not channel.recv_ready():
                    time.sleep(0.1)  # add small timer to let enough time to get all data from the buffer
                    channel.shutdown_read()  # indicate that we're not going to read from this channel anymore
                    channel.close()
                    break  # exit as remote side is finished and our buffers are empty

                # Timeout check
                now = datetime.datetime.now()
                now_secs = time.mktime(now.timetuple())
                et_secs = now_secs - start_secs
                if et_secs > timeout:
                    raise socket.timeout

            if debug:
                log.debug(output.getvalue())

            return_code = channel.recv_exit_status()

            if exit_if_error and return_code != 0:
                log.error("Error launching command '%s' => return code %d, output :\n%s" % (cmd, return_code, output.getvalue()))
            return (return_code, output.getvalue())
        except socket.timeout:
            channel.close()
            log.error("Timeout of %ds reached when calling command '%s'. Increase timeout if you think the command was still running successfully." % (timeout, cmd))
        except socket.error:
            log.error("Socket error when launching command '%s' =>\n%s" % (cmd, traceback.format_exc()))


    def get_cmd_output(self, cmd, username=None, exit_if_error=True, timeout=DEFAULT_RUN_CMD_TIMEOUT):
        (status, output) = self.run_cmd(cmd, username, exit_if_error, timeout=timeout)
        return output

    def get_exit_code(self, cmd, username=None, debug=False, timeout=DEFAULT_RUN_CMD_TIMEOUT):
        (status, output) = self.run_cmd(cmd, username, False, debug, timeout=timeout)
        return status

    def run_cmds(self, cmds, username=None, exit_if_error=True, debug=False, timeout=DEFAULT_RUN_CMD_TIMEOUT, input_data={}):
        return self.run_cmd(" && ".join(cmds), username, exit_if_error, debug, timeout, input_data)

    def get_remote_session(self, remote_host, username=None, retry=False):
        # get user to be used for remote ssh session
        user = self.username
        if username:
            user = username

        if self.ssh_remote_session:
            # if requested session already active, return it
            if self.ssh_transport.is_active() and self.ssh_remote_session.host == remote_host and self.ssh_remote_session.username == user:
                return self.ssh_remote_session
            # close previous existing sessions as only 1 tunnel possible on port 22
            else:
                self.ssh_remote_session.close()
                self.ssh_remote_session = None

        log.info("Connecting to '%s' through '%s' with user '%s'..." % (remote_host, self.host, user))
        self.ssh_remote_session = SSHSession(remote_host, user, self.ssh_transport, retry=retry)
        return self.ssh_remote_session

    def get_sftp_client(self):
        '''
        See documentation for available methods on paramiko.sftp_client at :
            http://docs.paramiko.org/en/1.16/api/sftp.html
        '''
        return paramiko.sftp_client.SFTPClient.from_transport(self.ssh_transport)


    def exists(self, path, use_root_access=False):
        '''
        Check if path exists on the remote host
        '''
        # cannot use sftp as root access is not possible
        if use_root_access:
            return self.get_exit_code("sudo ls %s" % path) == 0
        else:
            try:
                self.get_sftp_client().stat(path)
            except IOError, e:
                if e[0] == 2:
                    return False
                raise
            else:
                return True


    def scp(self, local_path, remote_path, username=None, permissions=None):
        '''
            Method to copy local file on a remote host
            Overriding user allows to copy file in location with restricted permissions
        '''
        user = self.username
        if username:
            user = username
        log.debug("Copy local file '%s' on remote host '%s' in '%s' as '%s'" % (local_path, self.host, remote_path, user))

        if not os.path.isfile(local_path):
            log.error("Local file '%s' does not exist")

        sftp_client = self.get_sftp_client()

        # copy local file on remote host in a temp file
        tmp_remote_path = "/tmp/%s" % ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(15))
        with open(local_path) as local_file, sftp_client.file(tmp_remote_path, mode='w+') as remote_file:
            remote_file.write(local_file.read())

        # mv this file in the final destination, with the requested user
        self.run_cmd("mv %s %s" % (tmp_remote_path, remote_path),
                     username=user,
                     debug=None)

        # file will be owned by the specified user
        if username:
            self.run_cmd("sudo chown %s:%s %s" % (username, username, remote_path), debug=None)

        if permissions:
            self.run_cmd("sudo chmod %s %s" % (permissions, remote_path), debug=None)

    def file(self, remote_path, content, username=None, permissions=None):
        '''
            Method to create a remote file
            Overriding user allows to create file in a location with restricted permissions
        '''
        with tempfile.NamedTemporaryFile() as tmp_local_file:
            tmp_local_file.write(content)
            tmp_local_file.seek(0)
            self.scp(tmp_local_file.name, remote_path, username, permissions)


class SFTPClient(paramiko.SFTPClient):

    def put_dir(self, source, target):
        ''' Uploads the contents of the source directory to the target path. The
            target directory needs to exists. All subdirectories in source are
            created under target.
        '''
        for item in os.listdir(source):
            if os.path.isfile(os.path.join(source, item)):
                self.put(os.path.join(source, item), '%s/%s' % (target, item))
            else:
                self.mkdir('%s/%s' % (target, item), ignore_existing=True)
                self.put_dir(os.path.join(source, item), '%s/%s' % (target, item))

    def mkdir(self, path, mode=511, ignore_existing=False):
        ''' Augments mkdir by adding an option to not fail if the folder exists  '''
        try:
            super(SFTPClient, self).mkdir(path, mode)
        except IOError:
            if not ignore_existing:
                raise

if __name__ == "__main__":
        parser = argparse.ArgumentParser(description='Run ssh command on a remote host through a proxy')

        parser.add_argument('-p', '--proxy', required=True, help='Hostname or IP of the proxy')
        parser.add_argument('-r', '--remote', required=True, help='Hostname or IP of the remote host on which to execute command')
        parser.add_argument('-c', '--command', action='append', required=True, help='Command to execute on the remote host')
        parser.add_argument('-u', '--user', default=getpass.getuser(), help='Username used to login on both proxy and remote host')
        parser.add_argument('-s', '--command-user', help='Username used to run the command on the remote host')

        options = parser.parse_args()

        options.command_user = options.command_user if options.command_user else options.user

        proxy_session = SSHSession(options.proxy, options.user)

        ssh_remote_session = proxy_session.get_remote_session(options.remote)
        try:
            for cmd in options.command:
                (status, output) = ssh_remote_session.run_cmd(cmd, options.command_user)
                print "exit status: %s" % status
                print output
        finally:
            proxy_session.close()

