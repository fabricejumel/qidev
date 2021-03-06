"""
connection.py

A Connection object manages all remote communication via SSH and qi Session.
"""


import qi
import os
import paramiko
from scp import SCPClient, SCPException
import xml.etree.ElementTree as ET
import zipfile
import clio as io
import config
from clint.textui import colored as col
import package_utils as pu
import socket
qi.logging.setLevel(0)


class Connection():
    """Establish a connection to ip/hostname and a qi session."""

    def __init__(self,
                 verb,  # verbose print function
                 hostname=None,  # ip/hostname
                 port='9559',
                 username='nao',
                 password='nao',
                 ssh=True,  # create SSH tunnel?
                 qi_session=True):  # create qi session?
        self.verb = verb
        if not hostname:
            try:
                self.hostname = str(config.read_field('hostname'))
            except IOError:
                raise RuntimeError('%s: Connect to a hostname first with "qidev connect"' %
                                   col.red('ERROR'))
        else:
            self.hostname = hostname
        verb('Connect to {}'.format(self.hostname))
        self.user = username
        self.pw = password
        self.virtual = False
        self.ssh = None
        self.scp = None
        if qi_session:
            verb('Create qi session')
            try:
                self.session = qi.Session()
                self.session.connect(self.hostname)
            except RuntimeError:
                raise RuntimeError('%s: could not establish connection to %s' %
                                   (col.red('ERROR'), col.blue(self.hostname)))
        else:
            self.session = None
        if ssh:
            verb('Establish connection via SSH')
            try:
                self.ssh = paramiko.SSHClient()
                self.ssh.load_system_host_keys()
                # accept unknown keys
                self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self.ssh.connect(self.hostname,
                                 # port=self.port,
                                 username=self.user,
                                 password=self.pw,
                                 allow_agent=False,
                                 look_for_keys=False)  # have pw, don't look for private keys
                self.scp = SCPClient(self.ssh.get_transport())
            except socket.gaierror as e:
                raise RuntimeError('{}: {} ... for hostname: {}'.format(col.red('ERROR'), e,
                                                                        col.blue(self.hostname)))
            except socket.error as e:
                verb('Virtual robot detected')
                self.virtual = True  # assuming this is a virtual bot... kind of a hack?
        if self.virtual:
            self.install_path = os.path.expanduser('~')
        else:
            self.install_path = '/home/nao/'  # always linux
        self.install_path = os.path.join(self.install_path,
                                         '.local', 'share', 'PackageManager', 'apps')

    def transfer(self, pkg_absolute_path):
        """Transfer the package to the remote filesystem.
        :param pkg_absolute_path: absolute path of the .pkg file.
        """
        pkg = pkg_absolute_path.split(os.sep)[-1]
        if not self.virtual:
            remote_path = os.path.join(self.install_path, pkg)
            self.scp.put(pkg_absolute_path, remote_path)
        return pkg

    def remote_get(self, file_absolute_path, local_path=None):
        """Grab a file from the remote host."""
        try:
            self.scp.get(file_absolute_path, local_path=local_path)
        except SCPException:
            raise RuntimeError

    def delete_pkg_file(self, abs_path):
        """Remove pkg from apps/ on robot or abs_path on local machine.
        :param pkg: the name of the package, e.g. my-package.pkg
        :param abs_path: the absolute path of the package on the local machine.
        """
        pkg = abs_path.split(os.sep)[-1]
        if self.virtual:  # delete the file from the local machine
            os.remove(abs_path)
        else:  # delete the file on the remote machine
            remote_path_to_pkg = os.path.join(self.install_path, pkg)
            sftp = self.ssh.open_sftp()
            sftp.remove(remote_path_to_pkg)
            sftp.close()

    def get_package_uid(self, path):
        """Get the UUID of the package locatated at path by parsing the manifest.
        :params path: absolute path to the package directory.
        :return: the UUID of package.
        """
        with open(os.path.join(path, 'manifest.xml'), 'r') as manifest:
            xml = ET.fromstring(manifest.read())
            try:
                uid = xml.attrib['uuid']
                return uid
            except KeyError:
                print 'no UUID found'
                return None

    def create_package(self, pkg_path=None):
        """Create a package out of the contents of the current directory.
        :return: the absolute path to the package on the local machine.
        """
        if not pkg_path:
            pkg_path = os.getcwd()
        pkg = self.get_package_uid(pkg_path) + '.pkg'
        path = os.path.join(pkg_path, '..', pkg)
        zipf = zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED)
        zip_dir(pkg_path, zipf)
        zipf.close()
        return path

    def install_package(self, abs_path):
        """Install package on system.
        abs_path (str): absolute path to the package.
        """
        pacman = self.session.service('PackageManager')
        pkg = abs_path.split(os.sep)[-1]
        uuid = pkg.replace('.pkg', '')
        if self.remove_package(uuid):
            self.verb('Removed previous package: {}'.format(uuid))
        if self.virtual:
            pacman.install(os.path.join(abs_path))
        else:
            pacman.install(os.path.join(self.install_path, pkg))

    def remove_package(self, uuid):
        """Remove a package from the robot via PackageManager.
        uuid (str): uuid of the package to remove
        """
        pacman = self.session.service('PackageManager')
        try:
            pacman.removePkg(uuid)
            return True
        except RuntimeError:
            return False

    def get_installed_package_data(self, verb):
        return pu.get_packages('en_US', verb, session=self.session)

    def get_running_behaviors(self):
        behman = self.session.service('ALBehaviorManager')
        return behman.getRunningBehaviors()

    def get_installed_behaviors(self):
        behman = self.session.service('ALBehaviorManager')
        return behman.getInstalledBehaviors()

    def get_behavior_nature(self, b):
        behman = self.session.service('ALBehaviorManager')
        return behman.getBehaviorNature(b)

    def get_running_services(self):
        servman = self.session.service('ALServiceManager')
        # 'execStart': path to launcher
        # 'name': name
        # 'running': true or false
        services = [s['name'] for s in servman.services()]
        return [s for s in services if servman.isServiceRunning(s)]

    def get_declared_services(self):
        servman = self.session.service('ALServiceManager')
        return [s['name'] for s in servman.services()]

    def start_behavior(self, behavior):
        behman = self.session.service('ALBehaviorManager')
        try:
            behman.startBehavior(behavior)
            return True
        except RuntimeError:
            return False

    def stop_behavior(self, behavior):
        behman = self.session.service('ALBehaviorManager')
        try:
            behman.stopBehavior(behavior)
            return True
        except RuntimeError:
            return False

    def life_switch_focus(self, activity):
        life = self.session.service('ALAutonomousLife')
        try:
            life.switchFocus(activity)
            return True
        except RuntimeError:
            return False

    def life_stop_focus(self):
        life = self.session.service('ALAutonomousLife')
        try:
            life.stopFocus()
            return True
        except RuntimeError:
            return False
        life.stopFocus()

    def get_focused_activity(self):
        life = self.session.service('ALAutonomousLife')
        return life.focusedActivity()

    def start_service(self, service):
        servman = self.session.service('ALServiceManager')
        return servman.startService(service)

    def stop_service(self, service):
        servman = self.session.service('ALServiceManager')
        return servman.stopService(service)

    def life_off(self):
        life = self.session.service('ALAutonomousLife')
        life.setState('disabled')

    def life_on(self):
        life = self.session.service('ALAutonomousLife')
        life.setState('solitary')

    def robot_reboot(self):
        system = self.session.service('ALSystem')
        system.reboot()

    def robot_shutdown(self):
        system = self.session.service('ALSystem')
        system.shutdown()

    def set_volume(self, level):
        audio = self.session.service('ALAudioDevice')
        curr_level = int(audio.getOutputVolume())
        if level == 'up':
            target = min(curr_level + 10, 100)
        elif level == 'down':
            target = max(curr_level - 10, 0)
        elif '+' in level:
            target = min(curr_level + int(level.replace('+', '')), 100)
        elif '-' in level:
            target = max(curr_level - int(level.replace('-', '')), 0)
        else:
            target = min(max(int(level), 0), 100)
        audio.setOutputVolume(target)
        return target

    def wake_up(self):
        motion = self.session.service('ALMotion')
        motion.wakeUp()

    def rest(self):
        motion = self.session.service('ALMotion')
        motion.rest()

    def init_dialog_window(self):
        memory = self.session.service('ALMemory')
        dialog = self.session.service('ALDialog')
        wr = memory.subscriber('WordRecognizedAndGrammar')
        wr_id = wr.signal.connect(io.show_dialog_input)
        li = memory.subscriber('Dialog/Answered')
        li_id = li.signal.connect(io.show_dialog_output)
        while(True):
            try:
                inp = raw_input()
                dialog.forceInput(inp)
            except KeyboardInterrupt:
                wr.signal.disconnect(wr_id)
                li.signal.disconnect(li_id)
                print('')
                break

    def get_robot_name(self):
        system = self.session.service('ALSystem')
        return system.robotName()


def zip_dir(path, zipfile):
    """Create a zip of contents of path by traversing it."""
    for root, dirs, files in os.walk(path):
        for f in files:
            zipfile.write(os.path.join(root, f),
                          arcname=os.path.relpath(os.path.join(root, f), path))
